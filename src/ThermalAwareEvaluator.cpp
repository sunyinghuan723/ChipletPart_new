#include "ThermalAwareEvaluator.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace chiplet {
namespace {

constexpr double kEpsilon = 1e-9;

std::string JsonEscape(const std::string& value) {
  std::ostringstream os;
  for (char c : value) {
    switch (c) {
      case '\\': os << "\\\\"; break;
      case '"': os << "\\\""; break;
      case '\n': os << "\\n"; break;
      case '\r': os << "\\r"; break;
      case '\t': os << "\\t"; break;
      default: os << c; break;
    }
  }
  return os.str();
}

void WriteArray(std::ostream& os, const std::vector<double>& values) {
  os << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i > 0) {
      os << ",";
    }
    os << std::setprecision(10) << values[i];
  }
  os << "]";
}

void WriteIntArray(std::ostream& os, const std::vector<int>& values) {
  os << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i > 0) {
      os << ",";
    }
    os << values[i];
  }
  os << "]";
}

void WriteStringArray(std::ostream& os, const std::vector<std::string>& values) {
  os << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i > 0) {
      os << ",";
    }
    os << "\"" << JsonEscape(values[i]) << "\"";
  }
  os << "]";
}

int NumPartitions(const std::vector<int>& partition) {
  int num_partitions = 0;
  for (int part_id : partition) {
    if (part_id < 0) {
      throw std::runtime_error("[THERMAL] Negative partition id in candidate");
    }
    num_partitions = std::max(num_partitions, part_id + 1);
  }
  return num_partitions;
}

std::string PathStemOrUnknown(const std::string& path) {
  if (path.empty()) {
    return "unknown";
  }
  std::filesystem::path fs_path(path);
  if (fs_path.has_parent_path()) {
    const std::string parent = fs_path.parent_path().filename().string();
    if (!parent.empty()) {
      return parent;
    }
  }
  return fs_path.stem().empty() ? "unknown" : fs_path.stem().string();
}

std::string ShortHash(const std::string& text) {
  std::ostringstream os;
  os << std::hex << std::hash<std::string>{}(text);
  return os.str();
}

bool IsAreaScalingTechSupported(const std::string& tech) {
  static const std::set<std::string> supported = {
      "90nm", "65nm", "45nm", "32nm", "20nm", "16nm", "14nm", "10nm", "7nm"};
  return supported.find(tech) != supported.end();
}

bool IsPowerScalingTechSupported(const std::string& tech) {
  static const std::set<std::string> supported = {
      "180nm", "130nm", "90nm", "65nm", "45nm", "32nm", "20nm", "16nm",
      "14nm", "10nm", "7nm"};
  return supported.find(tech) != supported.end();
}

double SafeAreaScaling(const std::string& initial_tech,
                       const std::string& actual_tech,
                       bool is_memory) {
  if (!IsAreaScalingTechSupported(initial_tech) ||
      !IsAreaScalingTechSupported(actual_tech)) {
    throw std::runtime_error("[THERMAL] Unsupported technology in area scaling: " +
                             initial_tech + " -> " + actual_tech);
  }
  return area_scaling_factor(initial_tech, actual_tech, is_memory);
}

double SafePowerScaling(const std::string& initial_tech,
                        const std::string& actual_tech) {
  if (!IsPowerScalingTechSupported(initial_tech) ||
      !IsPowerScalingTechSupported(actual_tech)) {
    throw std::runtime_error("[THERMAL] Unsupported technology in power scaling: " +
                             initial_tech + " -> " + actual_tech);
  }
  const double scale = power_scaling_factor(initial_tech, actual_tech);
  if (scale < 0.0) {
    throw std::runtime_error("[THERMAL] Failed technology power scaling: " +
                             initial_tech + " -> " + actual_tech);
  }
  return scale;
}

double ClampPositive(double value, double fallback) {
  return value > kEpsilon ? value : fallback;
}

} // namespace

ThermalInstanceEncoder::ThermalInstanceEncoder(ThermalConfig config)
    : config_(std::move(config)) {}

std::vector<std::string> ThermalInstanceEncoder::NormalizeTechArray(
    const std::vector<std::string>& tech_assignment, int num_partitions) const {
  if (num_partitions <= 0) {
    throw std::runtime_error("[THERMAL] Candidate has no partitions");
  }
  if (tech_assignment.empty()) {
    throw std::runtime_error("[THERMAL] Missing technology assignment");
  }
  std::vector<std::string> techs(num_partitions);
  for (int i = 0; i < num_partitions; ++i) {
    if (i < static_cast<int>(tech_assignment.size()) && !tech_assignment[i].empty()) {
      techs[i] = tech_assignment[i];
    } else {
      techs[i] = tech_assignment.front();
    }
  }
  return techs;
}

std::vector<double> ThermalInstanceEncoder::ComputeIoPowerByPartition(
    const std::vector<int>& partition,
    const LibraryDicts* library_dicts,
    int num_partitions) const {
  std::vector<double> io_power(num_partitions, 0.0);
  if (library_dicts == nullptr) {
    throw std::runtime_error("[THERMAL] Missing cost-model libraries for IO power");
  }

  for (const auto& matrix_entry : library_dicts->global_adjacency_matrix) {
    const std::string& io_type = matrix_entry.first;
    const auto& connection_matrix = matrix_entry.second;
    const auto bw_it = library_dicts->average_bandwidth_utilization.find(io_type);
    if (bw_it == library_dicts->average_bandwidth_utilization.end()) {
      continue;
    }

    const design::IO* matching_io = nullptr;
    for (const auto& io : library_dicts->ios) {
      if (io.GetType() == io_type) {
        matching_io = &io;
        break;
      }
    }
    if (matching_io == nullptr) {
      continue;
    }

    const double bidirectional_factor = matching_io->GetBidirectional() ? 0.5 : 1.0;
    const double io_scale = matching_io->GetBandwidth() *
                            matching_io->GetEnergyPerBit() *
                            bidirectional_factor;
    const auto& bandwidth = bw_it->second;

    for (size_t i = 0; i < partition.size(); ++i) {
      const int src_part = partition[i];
      for (size_t j = 0; j < partition.size(); ++j) {
        const int dst_part = partition[j];
        if (src_part == dst_part || src_part < 0 || src_part >= num_partitions) {
          continue;
        }
        double connection = 0.0;
        if (i < connection_matrix.size() && j < connection_matrix[i].size()) {
          connection = static_cast<double>(connection_matrix[i][j]);
        }
        double bw = 0.0;
        if (i < bandwidth.size() && j < bandwidth[i].size()) {
          bw = bandwidth[i][j];
        }
        io_power[src_part] += connection * bw * io_scale;
      }
    }
  }

  return io_power;
}

ThermalInstance ThermalInstanceEncoder::Encode(
    const std::vector<int>& partition,
    const std::vector<std::string>& tech_assignment,
    const std::vector<float>& aspect_ratios,
    const std::vector<float>& x_locations,
    const std::vector<float>& y_locations,
    const std::vector<block>& blocks,
    const LibraryDicts* library_dicts) const {
  if (partition.empty()) {
    throw std::runtime_error("[THERMAL] Missing partition for thermal encoding");
  }
  if (partition.size() != blocks.size()) {
    throw std::runtime_error("[THERMAL] Partition/block count mismatch: " +
                             std::to_string(partition.size()) + " vs " +
                             std::to_string(blocks.size()));
  }
  if (config_.grid_x <= 0 || config_.grid_y <= 0) {
    throw std::runtime_error("[THERMAL] Thermal grid dimensions must be positive");
  }

  const int num_partitions = NumPartitions(partition);
  std::vector<std::string> techs = NormalizeTechArray(tech_assignment, num_partitions);
  std::vector<double> compute_power(num_partitions, 0.0);
  std::vector<double> area(num_partitions, 0.0);

  for (size_t block_id = 0; block_id < blocks.size(); ++block_id) {
    const int part_id = partition[block_id];
    const block& b = blocks[block_id];
    area[part_id] += b.area * SafeAreaScaling(b.tech, techs[part_id], b.is_memory);
    compute_power[part_id] += b.power * SafePowerScaling(b.tech, techs[part_id]);
  }

  std::vector<double> io_power =
      ComputeIoPowerByPartition(partition, library_dicts, num_partitions);

  ThermalInstance instance;
  instance.grid_x = config_.grid_x;
  instance.grid_y = config_.grid_y;
  instance.ambient_temperature = config_.ambient_temperature;
  instance.heat_transfer_coefficient = config_.heat_transfer_coefficient;
  instance.source_testcase = config_.thermal_source_testcase;
  instance.partition = partition;
  instance.technology_assignment = techs;
  instance.channel_names = {
      "package_domain",
      "chiplet_footprint",
      "chiplet_boundary",
      "power_density_w_per_mm2",
      "silicon_material",
      "interposer_material",
      "tim_material",
      "package_material",
      "ambient_temperature",
      "heat_transfer_coefficient"};

  instance.chiplets.reserve(num_partitions);
  double min_x = std::numeric_limits<double>::max();
  double min_y = std::numeric_limits<double>::max();
  double max_x = 0.0;
  double max_y = 0.0;

  for (int part_id = 0; part_id < num_partitions; ++part_id) {
    const double chip_area = ClampPositive(area[part_id], 1.0);
    const double aspect_ratio =
        part_id < static_cast<int>(aspect_ratios.size())
            ? ClampPositive(aspect_ratios[part_id], 1.0)
            : 1.0;
    const double width = std::sqrt(chip_area * aspect_ratio);
    const double height = std::sqrt(chip_area / aspect_ratio);
    const double x = part_id < static_cast<int>(x_locations.size())
                         ? std::max(0.0f, x_locations[part_id])
                         : 0.0;
    const double y = part_id < static_cast<int>(y_locations.size())
                         ? std::max(0.0f, y_locations[part_id])
                         : 0.0;

    ThermalChipletInfo chiplet;
    chiplet.id = part_id;
    chiplet.technology = techs[part_id];
    chiplet.x_mm = x;
    chiplet.y_mm = y;
    chiplet.width_mm = width;
    chiplet.height_mm = height;
    chiplet.area_mm2 = chip_area;
    chiplet.compute_power = compute_power[part_id];
    chiplet.io_power = io_power[part_id];
    chiplet.total_power = compute_power[part_id] + io_power[part_id];
    instance.total_power_before_raster += chiplet.total_power;
    instance.chiplets.push_back(chiplet);

    min_x = std::min(min_x, x);
    min_y = std::min(min_y, y);
    max_x = std::max(max_x, x + width);
    max_y = std::max(max_y, y + height);
  }

  if (instance.chiplets.empty()) {
    throw std::runtime_error("[THERMAL] Thermal instance has no chiplets");
  }

  if (min_x == std::numeric_limits<double>::max()) {
    min_x = 0.0;
    min_y = 0.0;
  }
  for (auto& chiplet : instance.chiplets) {
    chiplet.x_mm -= min_x;
    chiplet.y_mm -= min_y;
  }
  instance.package_width_mm = ClampPositive(max_x - min_x, 1.0);
  instance.package_height_mm = ClampPositive(max_y - min_y, 1.0);

  Rasterize(instance);
  return instance;
}

void ThermalInstanceEncoder::Rasterize(ThermalInstance& instance) const {
  const int grid_size = instance.grid_x * instance.grid_y;
  instance.package_domain.assign(grid_size, 1.0);
  instance.chiplet_footprint.assign(grid_size, 0.0);
  instance.chiplet_boundary.assign(grid_size, 0.0);
  instance.power_density.assign(grid_size, 0.0);
  instance.silicon_material.assign(grid_size, 0.0);
  instance.interposer_material.assign(grid_size, config_.interposer_conductivity);
  instance.tim_material.assign(grid_size, config_.tim_conductivity);
  instance.package_material.assign(grid_size, config_.package_conductivity);
  instance.ambient_channel.assign(grid_size, config_.ambient_temperature);
  instance.htc_channel.assign(grid_size, config_.heat_transfer_coefficient);

  const double cell_w = instance.package_width_mm / instance.grid_x;
  const double cell_h = instance.package_height_mm / instance.grid_y;
  const double cell_area = ClampPositive(cell_w * cell_h, 1.0);

  for (const auto& chiplet : instance.chiplets) {
    const double density = chiplet.total_power / ClampPositive(chiplet.area_mm2, 1.0);
    for (int gy = 0; gy < instance.grid_y; ++gy) {
      const double cell_y0 = gy * cell_h;
      const double cell_y1 = cell_y0 + cell_h;
      for (int gx = 0; gx < instance.grid_x; ++gx) {
        const double cell_x0 = gx * cell_w;
        const double cell_x1 = cell_x0 + cell_w;
        const double ix0 = std::max(cell_x0, chiplet.x_mm);
        const double iy0 = std::max(cell_y0, chiplet.y_mm);
        const double ix1 = std::min(cell_x1, chiplet.x_mm + chiplet.width_mm);
        const double iy1 = std::min(cell_y1, chiplet.y_mm + chiplet.height_mm);
        if (ix1 <= ix0 || iy1 <= iy0) {
          continue;
        }
        const double overlap_area = (ix1 - ix0) * (iy1 - iy0);
        const double coverage = overlap_area / cell_area;
        const int idx = gy * instance.grid_x + gx;
        instance.chiplet_footprint[idx] =
            std::min(1.0, instance.chiplet_footprint[idx] + coverage);
        instance.power_density[idx] += density * coverage;
        instance.silicon_material[idx] = config_.silicon_conductivity;
        if (coverage > 0.0 && coverage < 0.999) {
          instance.chiplet_boundary[idx] = 1.0;
        }
      }
    }
  }

  instance.total_power_after_raster = 0.0;
  for (double density : instance.power_density) {
    instance.total_power_after_raster += density * cell_area;
  }

  instance.raster_power_error =
      instance.total_power_after_raster - instance.total_power_before_raster;
  if (std::abs(instance.raster_power_error) >
      std::max(1e-3, 0.01 * std::abs(instance.total_power_before_raster))) {
    std::cerr << "[THERMAL] Warning: raster power mismatch before="
              << instance.total_power_before_raster
              << " after=" << instance.total_power_after_raster
              << " error=" << instance.raster_power_error << std::endl;
  }
}

std::string ThermalInstanceEncoder::DumpJson(const ThermalInstance& instance,
                                             const std::string& dump_dir,
                                             const std::string& key) const {
  if (dump_dir.empty()) {
    return "";
  }
  std::filesystem::create_directories(dump_dir);
  const std::string instance_id =
      instance.instance_id.empty() ? config_.thermal_dump_prefix + "_" + ShortHash(key)
                                   : instance.instance_id;
  const std::string file_name = instance_id + ".json";
  const std::filesystem::path path = std::filesystem::path(dump_dir) / file_name;
  std::ofstream os(path);
  if (!os.is_open()) {
    throw std::runtime_error("[THERMAL] Cannot write thermal instance: " +
                             path.string());
  }

  os << "{\n";
  os << "  \"schema\": \"chipletpart.thermal_instance.v1\",\n";
  os << "  \"schema_version\": \"" << JsonEscape(instance.schema_version) << "\",\n";
  os << "  \"instance_id\": \"" << JsonEscape(instance_id) << "\",\n";
  os << "  \"source_testcase\": \"" << JsonEscape(instance.source_testcase) << "\",\n";
  os << "  \"units\": {\n";
  os << "    \"length\": \"mm\", \"area\": \"mm^2\", \"power\": \"cost_model_power\",";
  os << " \"power_density\": \"cost_model_power/mm^2\", \"temperature\": \"K\"\n";
  os << "  },\n";
  os << "  \"grid\": {\"x\": " << instance.grid_x << ", \"y\": " << instance.grid_y
     << ", \"z\": " << config_.grid_z << "},\n";
  os << "  \"grid_x\": " << instance.grid_x << ",\n";
  os << "  \"grid_y\": " << instance.grid_y << ",\n";
  os << "  \"package\": {\"width_mm\": " << instance.package_width_mm
     << ", \"height_mm\": " << instance.package_height_mm << "},\n";
  os << "  \"package_width_mm\": " << instance.package_width_mm << ",\n";
  os << "  \"package_height_mm\": " << instance.package_height_mm << ",\n";
  os << "  \"channel_names\": ";
  WriteStringArray(os, instance.channel_names);
  os << ",\n";
  os << "  \"boundary_conditions\": {\"ambient_temperature\": "
     << instance.ambient_temperature << ", \"heat_transfer_coefficient\": "
     << instance.heat_transfer_coefficient << "},\n";
  os << "  \"cost_objective\": ";
  if (instance.has_cost_objective) {
    os << instance.cost_objective;
  } else {
    os << "null";
  }
  os << ",\n";
  os << "  \"partition\": ";
  WriteIntArray(os, instance.partition);
  os << ",\n";
  os << "  \"technology_assignment\": ";
  WriteStringArray(os, instance.technology_assignment);
  os << ",\n";
  os << "  \"rasterization\": {\"total_power_before_raster\": "
     << instance.total_power_before_raster << ", \"total_power_after_raster\": "
     << instance.total_power_after_raster << ", \"power_error\": "
     << instance.raster_power_error << "},\n";
  os << "  \"total_power_before_raster\": " << instance.total_power_before_raster << ",\n";
  os << "  \"total_power_after_raster\": " << instance.total_power_after_raster << ",\n";
  os << "  \"raster_power_error\": " << instance.raster_power_error << ",\n";
  os << "  \"chiplets\": [\n";
  for (size_t i = 0; i < instance.chiplets.size(); ++i) {
    const auto& chiplet = instance.chiplets[i];
    os << "    {\"id\": " << chiplet.id << ", \"technology\": \""
       << JsonEscape(chiplet.technology) << "\", \"x_mm\": " << chiplet.x_mm
       << ", \"y_mm\": " << chiplet.y_mm << ", \"width_mm\": "
       << chiplet.width_mm << ", \"height_mm\": " << chiplet.height_mm
       << ", \"area_mm2\": " << chiplet.area_mm2 << ", \"compute_power\": "
       << chiplet.compute_power << ", \"io_power\": " << chiplet.io_power
       << ", \"total_power\": " << chiplet.total_power << "}";
    os << (i + 1 == instance.chiplets.size() ? "\n" : ",\n");
  }
  os << "  ],\n";
  os << "  \"channels\": {\n";
  os << "    \"package_domain\": ";
  WriteArray(os, instance.package_domain);
  os << ",\n    \"chiplet_footprint\": ";
  WriteArray(os, instance.chiplet_footprint);
  os << ",\n    \"chiplet_boundary\": ";
  WriteArray(os, instance.chiplet_boundary);
  os << ",\n    \"power_density_w_per_mm2\": ";
  WriteArray(os, instance.power_density);
  os << ",\n    \"silicon_material\": ";
  WriteArray(os, instance.silicon_material);
  os << ",\n    \"interposer_material\": ";
  WriteArray(os, instance.interposer_material);
  os << ",\n    \"tim_material\": ";
  WriteArray(os, instance.tim_material);
  os << ",\n    \"package_material\": ";
  WriteArray(os, instance.package_material);
  os << ",\n    \"ambient_temperature\": ";
  WriteArray(os, instance.ambient_channel);
  os << ",\n    \"heat_transfer_coefficient\": ";
  WriteArray(os, instance.htc_channel);
  os << "\n  }\n";
  os << "}\n";

  if (!config_.thermal_dump_manifest.empty()) {
    const bool new_file = !std::filesystem::exists(config_.thermal_dump_manifest);
    const auto manifest_parent =
        std::filesystem::path(config_.thermal_dump_manifest).parent_path();
    if (!manifest_parent.empty()) {
      std::filesystem::create_directories(manifest_parent);
    }
    std::ofstream manifest(config_.thermal_dump_manifest, std::ios::app);
    if (!manifest.is_open()) {
      throw std::runtime_error("[THERMAL] Cannot write thermal manifest: " +
                               config_.thermal_dump_manifest);
    }
    double total_power = instance.total_power_before_raster;
    manifest << "{"
             << "\"instance_id\":\"" << JsonEscape(instance_id) << "\","
             << "\"json_path\":\"" << JsonEscape(path.string()) << "\","
             << "\"testcase\":\"" << JsonEscape(instance.source_testcase) << "\","
             << "\"num_chiplets\":" << instance.chiplets.size() << ","
             << "\"technology_assignment\":";
    WriteStringArray(manifest, instance.technology_assignment);
    manifest << ",\"cost\":";
    if (instance.has_cost_objective) {
      manifest << instance.cost_objective;
    } else {
      manifest << "null";
    }
    manifest << ",\"total_power\":" << total_power
             << ",\"label_path\":\"\","
             << "\"split\":\"" << JsonEscape(config_.thermal_dump_split) << "\""
             << "}\n";
    if (new_file) {
      std::cout << "[THERMAL-DATA] Created manifest "
                << config_.thermal_dump_manifest << std::endl;
    }
  }
  return path.string();
}

MockThermalSurrogate::MockThermalSurrogate(ThermalConfig config)
    : config_(std::move(config)) {}

ThermalResult MockThermalSurrogate::Predict(const ThermalInstance& instance,
                                            const std::string&) {
  double max_density = 0.0;
  double avg_density = 0.0;
  for (double value : instance.power_density) {
    max_density = std::max(max_density, value);
    avg_density += value;
  }
  if (!instance.power_density.empty()) {
    avg_density /= static_cast<double>(instance.power_density.size());
  }
  const double package_scale =
      std::sqrt(ClampPositive(instance.package_width_mm * instance.package_height_mm, 1.0));

  ThermalResult result;
  result.t_avg = config_.ambient_temperature +
                 0.02 * instance.total_power_before_raster / package_scale +
                 0.10 * avg_density;
  result.t_max = result.t_avg + 0.25 * max_density;
  return result;
}

PythonDeepOHeatAdapter::PythonDeepOHeatAdapter(ThermalConfig config)
    : config_(std::move(config)) {}

std::string PythonDeepOHeatAdapter::ShellQuote(const std::string& value) const {
  std::string quoted = "'";
  for (char c : value) {
    if (c == '\'') {
      quoted += "'\\''";
    } else {
      quoted += c;
    }
  }
  quoted += "'";
  return quoted;
}

std::string PythonDeepOHeatAdapter::ResolveInferenceScript() const {
  std::vector<std::string> candidates;
  if (!config_.thermal_inference_script.empty()) {
    candidates.push_back(config_.thermal_inference_script);
  }
  if (config_.thermal_backend == "package_thermal") {
    candidates.push_back("DeepOHeat/package_thermal/infer_package.py");
    candidates.push_back("../DeepOHeat/package_thermal/infer_package.py");
    candidates.push_back("../../DeepOHeat/package_thermal/infer_package.py");
    candidates.push_back("../../../DeepOHeat/package_thermal/infer_package.py");
  } else {
    candidates.push_back("DeepOHeat/scripts/infer_package.py");
    candidates.push_back("../DeepOHeat/scripts/infer_package.py");
    candidates.push_back("../../DeepOHeat/scripts/infer_package.py");
    candidates.push_back("../../../DeepOHeat/scripts/infer_package.py");
  }

  for (const auto& candidate : candidates) {
    if (std::filesystem::exists(candidate)) {
      return candidate;
    }
  }
  throw std::runtime_error("[THERMAL] Cannot find DeepOHeat inference script. "
                           "Set --thermal_inference_script explicitly.");
}

double PythonDeepOHeatAdapter::ExtractJsonNumber(const std::string& json,
                                                const std::string& key) const {
  const std::string pattern = "\"" + key + "\"";
  size_t pos = json.find(pattern);
  if (pos == std::string::npos) {
    throw std::runtime_error("[THERMAL] Inference JSON missing key: " + key);
  }
  pos = json.find(':', pos);
  if (pos == std::string::npos) {
    throw std::runtime_error("[THERMAL] Malformed inference JSON for key: " + key);
  }
  ++pos;
  while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) {
    ++pos;
  }
  size_t end = pos;
  while (end < json.size() &&
         (std::isdigit(static_cast<unsigned char>(json[end])) || json[end] == '-' ||
          json[end] == '+' || json[end] == '.' || json[end] == 'e' ||
          json[end] == 'E')) {
    ++end;
  }
  return std::stod(json.substr(pos, end - pos));
}

std::string PythonDeepOHeatAdapter::ExtractJsonString(const std::string& json,
                                                     const std::string& key) const {
  const std::string pattern = "\"" + key + "\"";
  size_t pos = json.find(pattern);
  if (pos == std::string::npos) {
    return "";
  }
  pos = json.find(':', pos);
  if (pos == std::string::npos) {
    return "";
  }
  pos = json.find('"', pos + 1);
  if (pos == std::string::npos) {
    return "";
  }
  const size_t end = json.find('"', pos + 1);
  if (end == std::string::npos) {
    return "";
  }
  return json.substr(pos + 1, end - pos - 1);
}

ThermalResult PythonDeepOHeatAdapter::Predict(const ThermalInstance&,
                                              const std::string& instance_path) {
  if (config_.thermal_model_path.empty()) {
    throw std::runtime_error("[THERMAL] --thermal_model_path is required when "
                             "--thermal_use_mock is not set");
  }
  if (instance_path.empty()) {
    throw std::runtime_error("[THERMAL] DeepOHeat adapter requires dumped instance JSON");
  }
  const std::string script = ResolveInferenceScript();
  const std::filesystem::path output_path =
      std::filesystem::path(instance_path).replace_extension(".thermal_result.json");

  std::ostringstream cmd;
  cmd << ShellQuote(config_.python_executable)
      << " " << ShellQuote(script)
      << " --instance " << ShellQuote(instance_path)
      << " --model " << ShellQuote(config_.thermal_model_path)
      << " --output " << ShellQuote(output_path.string());
  if (!config_.thermal_model_config.empty()) {
    cmd << " --config " << ShellQuote(config_.thermal_model_config);
  }

  const int status = std::system(cmd.str().c_str());
  if (status != 0) {
    throw std::runtime_error("[THERMAL] DeepOHeat inference failed with status " +
                             std::to_string(status) + ". Command: " + cmd.str());
  }

  std::ifstream is(output_path);
  if (!is.is_open()) {
    throw std::runtime_error("[THERMAL] DeepOHeat inference did not produce " +
                             output_path.string());
  }
  std::stringstream buffer;
  buffer << is.rdbuf();
  const std::string json = buffer.str();

  ThermalResult result;
  result.t_max = ExtractJsonNumber(json, "t_max");
  result.t_avg = ExtractJsonNumber(json, "t_avg");
  result.field_path = ExtractJsonString(json, "field_path");
  return result;
}

ThermalAwareEvaluator::ThermalAwareEvaluator(ThermalConfig config,
                                             const std::string& io_file,
                                             const std::string& netlist_file,
                                             const std::string& blocks_file)
    : config_(std::move(config)),
      io_file_(io_file),
      netlist_file_(netlist_file),
      blocks_file_(blocks_file),
      encoder_(config_) {
  if (config_.enable_thermal) {
    if (config_.use_mock_thermal_model || config_.thermal_backend == "mock") {
      surrogate_ = std::make_unique<MockThermalSurrogate>(config_);
    } else if (config_.thermal_backend == "legacy_2d_power_map" ||
               config_.thermal_backend == "package_thermal") {
      surrogate_ = std::make_unique<PythonDeepOHeatAdapter>(config_);
    } else {
      throw std::runtime_error("[THERMAL] Unknown thermal backend: " +
                               config_.thermal_backend);
    }
  }
}

ThermalAwareEvaluator::~ThermalAwareEvaluator() {
  if (library_dicts_ != nullptr) {
    destroyDatabase(library_dicts_);
    library_dicts_ = nullptr;
  }
}

void ThermalAwareEvaluator::EnsureInitialized() {
  if (initialized_) {
    return;
  }
  blocks_ = readBlocks(blocks_file_);
  if (blocks_.empty()) {
    throw std::runtime_error("[THERMAL] No blocks read from " + blocks_file_);
  }
  library_dicts_ = new LibraryDicts();
  try {
    library_dicts_->ios = read_design::IODefinitionListFromFile(io_file_);
    auto netlist_result =
        read_design::GlobalAdjacencyMatrixFromFile(netlist_file_, library_dicts_->ios);
    library_dicts_->global_adjacency_matrix = std::get<0>(netlist_result);
    library_dicts_->average_bandwidth_utilization = std::get<1>(netlist_result);
    library_dicts_->block_names = std::get<2>(netlist_result);
  } catch (const std::exception& e) {
    delete library_dicts_;
    library_dicts_ = nullptr;
    throw std::runtime_error("[THERMAL] Failed to read IO/netlist libraries for "
                             "thermal power: " + std::string(e.what()));
  }
  initialized_ = true;
}

std::string ThermalAwareEvaluator::BuildCacheKey(
    const std::vector<int>& partition,
    const std::vector<std::string>& tech_assignment,
    const std::vector<float>& aspect_ratios,
    const std::vector<float>& x_locations,
    const std::vector<float>& y_locations) const {
  std::ostringstream os;
  os << "grid=" << config_.grid_x << "x" << config_.grid_y << ";";
  os << "amb=" << config_.ambient_temperature << ";htc="
     << config_.heat_transfer_coefficient << ";";
  os << "p=";
  for (int part : partition) {
    os << part << ",";
  }
  os << ";t=";
  for (const auto& tech : tech_assignment) {
    os << tech << ",";
  }
  os << ";ar=";
  for (float value : aspect_ratios) {
    os << std::setprecision(6) << value << ",";
  }
  os << ";x=";
  for (float value : x_locations) {
    os << std::setprecision(6) << value << ",";
  }
  os << ";y=";
  for (float value : y_locations) {
    os << std::setprecision(6) << value << ",";
  }
  return os.str();
}

double ThermalAwareEvaluator::Objective(double base_cost,
                                        const ThermalResult& thermal) const {
  const double peak_over =
      std::max(0.0, thermal.t_max - config_.thermal_budget);
  return base_cost + config_.lambda_peak * peak_over * peak_over +
         config_.lambda_avg * thermal.t_avg;
}

void ThermalAwareEvaluator::LogEvaluation(const ThermalEvaluation& evaluation) const {
  std::cout << "[THERMAL] cost=" << evaluation.base_cost
            << " t_max=" << evaluation.thermal.t_max
            << " t_avg=" << evaluation.thermal.t_avg
            << " peak_penalty=" << evaluation.peak_penalty
            << " avg_penalty=" << evaluation.avg_penalty
            << " objective=" << evaluation.objective
            << " cache=" << (evaluation.cache_hit ? "hit" : "miss")
            << std::endl;
}

ThermalEvaluation ThermalAwareEvaluator::Evaluate(
    double base_cost,
    const std::vector<int>& partition,
    const std::vector<std::string>& tech_assignment,
    const std::vector<float>& aspect_ratios,
    const std::vector<float>& x_locations,
    const std::vector<float>& y_locations,
    bool floorplan_success) {
  ThermalEvaluation evaluation;
  evaluation.base_cost = base_cost;
  evaluation.objective = base_cost;

  if (!config_.enable_thermal) {
    return evaluation;
  }
  if (!floorplan_success) {
    throw std::runtime_error("[THERMAL] Cannot evaluate thermal objective: "
                             "floorplanner reported infeasible candidate");
  }

  try {
    std::lock_guard<std::mutex> lock(mutex_);
    EnsureInitialized();
    const std::string key =
        BuildCacheKey(partition, tech_assignment, aspect_ratios, x_locations, y_locations);

    if (config_.thermal_cache_enable) {
      const auto it = result_cache_.find(key);
      if (it != result_cache_.end()) {
        evaluation.thermal = it->second;
        evaluation.cache_hit = true;
      }
    }

    if (!evaluation.cache_hit) {
      ThermalInstance instance = encoder_.Encode(partition, tech_assignment, aspect_ratios,
                                                 x_locations, y_locations, blocks_,
                                                 library_dicts_);
      if (instance.source_testcase.empty()) {
        instance.source_testcase = PathStemOrUnknown(blocks_file_);
      }
      instance.cost_objective = base_cost;
      instance.has_cost_objective = true;
      const std::string instance_path =
          encoder_.DumpJson(instance, config_.thermal_dump_instances, key);
      const bool using_mock =
          config_.use_mock_thermal_model || config_.thermal_backend == "mock";
      if (!using_mock && instance_path.empty()) {
        throw std::runtime_error("[THERMAL] Non-mock DeepOHeat inference requires "
                                 "--thermal_dump_instances so the adapter has JSON input");
      }
      evaluation.thermal = surrogate_->Predict(instance, instance_path);
      if (config_.thermal_cache_enable) {
        result_cache_[key] = evaluation.thermal;
      }
    }

    const double peak_over =
        std::max(0.0, evaluation.thermal.t_max - config_.thermal_budget);
    evaluation.peak_penalty = config_.lambda_peak * peak_over * peak_over;
    evaluation.avg_penalty = config_.lambda_avg * evaluation.thermal.t_avg;
    evaluation.objective = base_cost + evaluation.peak_penalty + evaluation.avg_penalty;
    LogEvaluation(evaluation);
  } catch (const std::exception& e) {
    if (config_.allow_thermal_fallback) {
      std::cerr << "[THERMAL] Warning: " << e.what()
                << "; falling back to cost-only objective" << std::endl;
      evaluation.objective = base_cost;
      return evaluation;
    }
    throw;
  }

  return evaluation;
}

} // namespace chiplet

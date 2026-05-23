#include "ThermalAwareEvaluator.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cerrno>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <utility>

#include <sys/wait.h>
#include <unistd.h>

namespace chiplet {
namespace {

constexpr double kEpsilon = 1e-9;

bool VerboseThermalLogging() {
  return std::getenv("CHIPLET_PART_VERBOSE_THERMAL") != nullptr;
}

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

void WriteStringCountsObject(std::ostream& os,
                             const std::vector<std::string>& values) {
  std::map<std::string, int> counts;
  for (const auto& value : values) {
    counts[value] += 1;
  }
  os << "{";
  size_t index = 0;
  for (const auto& [value, count] : counts) {
    if (index++ > 0) {
      os << ",";
    }
    os << "\"" << JsonEscape(value) << "\":" << count;
  }
  os << "}";
}

long long UnixTimeSeconds() {
  return std::chrono::duration_cast<std::chrono::seconds>(
             std::chrono::system_clock::now().time_since_epoch())
      .count();
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
  uint64_t hash = 1469598103934665603ULL;
  for (unsigned char c : text) {
    hash ^= static_cast<uint64_t>(c);
    hash *= 1099511628211ULL;
  }
  std::ostringstream os;
  os << std::hex << hash;
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

bool StartsWith(const std::string& text, const std::string& prefix) {
  return text.rfind(prefix, 0) == 0;
}

int TrailingIndexOrMax(const std::string& text, const std::string& prefix) {
  if (!StartsWith(text, prefix)) {
    return std::numeric_limits<int>::max();
  }
  const std::string suffix = text.substr(prefix.size());
  if (suffix.empty()) {
    return std::numeric_limits<int>::max();
  }
  for (char c : suffix) {
    if (!std::isdigit(static_cast<unsigned char>(c))) {
      return std::numeric_limits<int>::max();
    }
  }
  return std::stoi(suffix);
}

std::vector<int> FindIndexedTargets(const std::vector<std::string>& names,
                                    const std::string& prefix) {
  std::vector<int> targets;
  for (size_t i = 0; i < names.size(); ++i) {
    if (StartsWith(names[i], prefix)) {
      targets.push_back(static_cast<int>(i));
    }
  }
  std::stable_sort(targets.begin(), targets.end(), [&](int lhs, int rhs) {
    return TrailingIndexOrMax(names[lhs], prefix) <
           TrailingIndexOrMax(names[rhs], prefix);
  });
  return targets;
}

void SortBlockIndicesBySuffix(const std::vector<block>& blocks,
                              const std::string& prefix,
                              std::vector<int>& indices) {
  std::stable_sort(indices.begin(), indices.end(), [&](int lhs, int rhs) {
    return TrailingIndexOrMax(blocks[lhs].name, prefix) <
           TrailingIndexOrMax(blocks[rhs].name, prefix);
  });
}

void AssignProportionally(const std::vector<int>& block_indices,
                          const std::vector<int>& target_vertices,
                          std::vector<int>& block_to_graph_vertex) {
  if (block_indices.empty() || target_vertices.empty()) {
    return;
  }
  for (size_t i = 0; i < block_indices.size(); ++i) {
    const size_t target_pos = std::min(
        target_vertices.size() - 1,
        (i * target_vertices.size()) / block_indices.size());
    block_to_graph_vertex[block_indices[i]] = target_vertices[target_pos];
  }
}

std::vector<int> BuildBlockToGraphVertexMappingImpl(
    const std::vector<block>& blocks,
    const std::vector<std::string>& graph_block_names) {
  if (graph_block_names.empty()) {
    throw std::runtime_error("[THERMAL] Netlist did not expose block names for "
                             "thermal power mapping");
  }

  std::unordered_map<std::string, int> graph_index_by_name;
  for (size_t i = 0; i < graph_block_names.size(); ++i) {
    graph_index_by_name[graph_block_names[i]] = static_cast<int>(i);
  }

  std::vector<int> mapping(blocks.size(), -1);
  std::vector<int> sm_blocks;
  std::vector<int> hbm_phy_blocks;
  std::vector<int> fallback_blocks;

  for (size_t i = 0; i < blocks.size(); ++i) {
    const auto exact = graph_index_by_name.find(blocks[i].name);
    if (exact != graph_index_by_name.end()) {
      mapping[i] = exact->second;
    } else if (StartsWith(blocks[i].name, "sm_")) {
      sm_blocks.push_back(static_cast<int>(i));
    } else if (StartsWith(blocks[i].name, "hbm_1024_phy_")) {
      hbm_phy_blocks.push_back(static_cast<int>(i));
    } else {
      fallback_blocks.push_back(static_cast<int>(i));
    }
  }

  SortBlockIndicesBySuffix(blocks, "sm_", sm_blocks);
  SortBlockIndicesBySuffix(blocks, "hbm_1024_phy_", hbm_phy_blocks);
  AssignProportionally(sm_blocks, FindIndexedTargets(graph_block_names, "l2_"),
                       mapping);
  AssignProportionally(hbm_phy_blocks,
                       FindIndexedTargets(graph_block_names, "hbm_1536_ctrl_"),
                       mapping);

  if (!fallback_blocks.empty()) {
    std::vector<int> all_targets(graph_block_names.size());
    std::iota(all_targets.begin(), all_targets.end(), 0);
    AssignProportionally(fallback_blocks, all_targets, mapping);
    std::cerr << "[THERMAL] Warning: distributed " << fallback_blocks.size()
              << " block-power records without exact/hierarchy mapping across "
              << graph_block_names.size() << " netlist vertices" << std::endl;
  }

  for (size_t i = 0; i < mapping.size(); ++i) {
    if (mapping[i] < 0) {
      throw std::runtime_error("[THERMAL] Could not map block power record '" +
                               blocks[i].name + "' onto a netlist vertex");
    }
  }
  return mapping;
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

double RectArea(double width, double height) {
  return ClampPositive(width * height, 1.0);
}

double SumBlockAreas(const std::vector<ThermalBlockInfo>& blocks,
                     const std::vector<int>& block_indices,
                     size_t begin,
                     size_t end) {
  double total = 0.0;
  for (size_t i = begin; i < end; ++i) {
    total += ClampPositive(blocks[block_indices[i]].area_mm2, 1.0);
  }
  return total;
}

void PackBlocksRecursive(std::vector<ThermalBlockInfo>& blocks,
                         const std::vector<int>& block_indices,
                         size_t begin,
                         size_t end,
                         double x,
                         double y,
                         double width,
                         double height) {
  if (begin >= end) {
    return;
  }
  if (end - begin == 1) {
    auto& block_info = blocks[block_indices[begin]];
    block_info.x_mm = x;
    block_info.y_mm = y;
    block_info.width_mm = width;
    block_info.height_mm = height;
    return;
  }

  const double total_area = SumBlockAreas(blocks, block_indices, begin, end);
  if (total_area <= kEpsilon) {
    const size_t mid = begin + (end - begin) / 2;
    const double ratio =
        static_cast<double>(mid - begin) / static_cast<double>(end - begin);
    if (width >= height) {
      const double left_width = width * ratio;
      PackBlocksRecursive(blocks, block_indices, begin, mid, x, y, left_width,
                          height);
      PackBlocksRecursive(blocks, block_indices, mid, end, x + left_width, y,
                          width - left_width, height);
    } else {
      const double lower_height = height * ratio;
      PackBlocksRecursive(blocks, block_indices, begin, mid, x, y, width,
                          lower_height);
      PackBlocksRecursive(blocks, block_indices, mid, end, x, y + lower_height,
                          width, height - lower_height);
    }
    return;
  }

  double prefix_area = 0.0;
  double best_diff = std::numeric_limits<double>::max();
  size_t split = begin + 1;
  for (size_t i = begin + 1; i < end; ++i) {
    prefix_area += ClampPositive(blocks[block_indices[i - 1]].area_mm2, 1.0);
    const double diff = std::abs(prefix_area - total_area * 0.5);
    if (diff < best_diff) {
      best_diff = diff;
      split = i;
    }
  }

  const double left_area = SumBlockAreas(blocks, block_indices, begin, split);
  const double ratio = std::min(1.0, std::max(0.0, left_area / total_area));
  if (width >= height) {
    const double left_width = width * ratio;
    PackBlocksRecursive(blocks, block_indices, begin, split, x, y, left_width,
                        height);
    PackBlocksRecursive(blocks, block_indices, split, end, x + left_width, y,
                        width - left_width, height);
  } else {
    const double lower_height = height * ratio;
    PackBlocksRecursive(blocks, block_indices, begin, split, x, y, width,
                        lower_height);
    PackBlocksRecursive(blocks, block_indices, split, end, x, y + lower_height,
                        width, height - lower_height);
  }
}

void AddRectToRaster(const double rect_x,
                     const double rect_y,
                     const double rect_w,
                     const double rect_h,
                     const double density,
                     const double cell_w,
                     const double cell_h,
                     const double cell_area,
                     ThermalInstance& instance) {
  for (int gy = 0; gy < instance.grid_y; ++gy) {
    const double cell_y0 = gy * cell_h;
    const double cell_y1 = cell_y0 + cell_h;
    for (int gx = 0; gx < instance.grid_x; ++gx) {
      const double cell_x0 = gx * cell_w;
      const double cell_x1 = cell_x0 + cell_w;
      const double ix0 = std::max(cell_x0, rect_x);
      const double iy0 = std::max(cell_y0, rect_y);
      const double ix1 = std::min(cell_x1, rect_x + rect_w);
      const double iy1 = std::min(cell_y1, rect_y + rect_h);
      if (ix1 <= ix0 || iy1 <= iy0) {
        continue;
      }
      const double overlap_area = (ix1 - ix0) * (iy1 - iy0);
      const double coverage = overlap_area / cell_area;
      const int idx = gy * instance.grid_x + gx;
      instance.power_density[idx] += density * coverage;
    }
  }
}

} // namespace

std::vector<int> BuildThermalBlockToGraphVertexMapping(
    const std::vector<block>& blocks,
    const std::vector<std::string>& graph_block_names) {
  return BuildBlockToGraphVertexMappingImpl(blocks, graph_block_names);
}

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
    const LibraryDicts* library_dicts,
    const std::vector<int>* io_partition) const {
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
  std::vector<double> block_area(blocks.size(), 0.0);
  std::vector<double> block_compute_power(blocks.size(), 0.0);

  for (size_t block_id = 0; block_id < blocks.size(); ++block_id) {
    const int part_id = partition[block_id];
    const block& b = blocks[block_id];
    block_area[block_id] =
        b.area * SafeAreaScaling(b.tech, techs[part_id], b.is_memory);
    block_compute_power[block_id] =
        b.power * SafePowerScaling(b.tech, techs[part_id]);
    area[part_id] += block_area[block_id];
    compute_power[part_id] += block_compute_power[block_id];
  }

  const std::vector<int>& io_partition_ref =
      io_partition == nullptr ? partition : *io_partition;
  std::vector<double> io_power =
      ComputeIoPowerByPartition(io_partition_ref, library_dicts, num_partitions);

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
                         ? x_locations[part_id]
                         : 0.0;
    const double y = part_id < static_cast<int>(y_locations.size())
                         ? y_locations[part_id]
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

  for (size_t left = 0; left < instance.chiplets.size(); ++left) {
    const auto& a = instance.chiplets[left];
    for (size_t right = left + 1; right < instance.chiplets.size(); ++right) {
      const auto& b = instance.chiplets[right];
      const double overlap_x =
          std::min(a.x_mm + a.width_mm, b.x_mm + b.width_mm) -
          std::max(a.x_mm, b.x_mm);
      const double overlap_y =
          std::min(a.y_mm + a.height_mm, b.y_mm + b.height_mm) -
          std::max(a.y_mm, b.y_mm);
      if (overlap_x > kEpsilon && overlap_y > kEpsilon) {
        throw std::runtime_error(
            "[THERMAL] Overlapping chiplets in encoded floorplan: " +
            std::to_string(a.id) + " and " + std::to_string(b.id));
      }
    }
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

  instance.blocks.resize(blocks.size());
  std::vector<std::vector<int>> blocks_by_partition(num_partitions);
  for (size_t block_id = 0; block_id < blocks.size(); ++block_id) {
    const int part_id = partition[block_id];
    const block& b = blocks[block_id];
    ThermalBlockInfo block_info;
    block_info.id = static_cast<int>(block_id);
    block_info.name = b.name;
    block_info.chiplet_id = part_id;
    block_info.source_technology = b.tech;
    block_info.technology = techs[part_id];
    block_info.is_memory = b.is_memory;
    block_info.area_mm2 = ClampPositive(block_area[block_id], 1.0);
    block_info.compute_power = block_compute_power[block_id];
    instance.blocks[block_id] = block_info;
    blocks_by_partition[part_id].push_back(static_cast<int>(block_id));
  }
  for (const auto& chiplet : instance.chiplets) {
    PackBlocksRecursive(instance.blocks, blocks_by_partition[chiplet.id], 0,
                        blocks_by_partition[chiplet.id].size(), chiplet.x_mm,
                        chiplet.y_mm, chiplet.width_mm, chiplet.height_mm);
  }

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
    const double io_density = chiplet.io_power / ClampPositive(chiplet.area_mm2, 1.0);
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
        instance.power_density[idx] += io_density * coverage;
        instance.silicon_material[idx] = config_.silicon_conductivity;
        if (coverage > 0.0 && coverage < 0.999) {
          instance.chiplet_boundary[idx] = 1.0;
        }
      }
    }
  }

  for (const auto& block_info : instance.blocks) {
    const double block_density =
        block_info.compute_power / RectArea(block_info.width_mm, block_info.height_mm);
    AddRectToRaster(block_info.x_mm, block_info.y_mm, block_info.width_mm,
                    block_info.height_mm, block_density, cell_w, cell_h,
                    cell_area, instance);
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
  const std::string instance_hash =
      instance.instance_hash.empty() ? ShortHash(key) : instance.instance_hash;
  const std::string candidate_source =
      instance.candidate_source.empty() ? "unknown" : instance.candidate_source;
  const std::string search_stage =
      instance.search_stage.empty() ? "unknown" : instance.search_stage;
  const long long generation_time_unix_sec = UnixTimeSeconds();
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
  os << "  \"run_id\": \"" << JsonEscape(instance.run_id) << "\",\n";
  os << "  \"benchmark\": \"" << JsonEscape(instance.source_testcase) << "\",\n";
  os << "  \"seed\": \"" << JsonEscape(instance.seed) << "\",\n";
  os << "  \"candidate_index\": ";
  if (instance.candidate_index >= 0) {
    os << instance.candidate_index;
  } else {
    os << "null";
  }
  os << ",\n";
  os << "  \"candidate_source\": \"" << JsonEscape(candidate_source) << "\",\n";
  os << "  \"search_stage\": \"" << JsonEscape(search_stage) << "\",\n";
  os << "  \"thermal_enabled\": " << (instance.thermal_enabled ? "true" : "false") << ",\n";
  os << "  \"floorplan_feasible\": "
     << (instance.floorplan_feasible ? "true" : "false") << ",\n";
  os << "  \"io_feasible\": " << (instance.io_feasible ? "true" : "false") << ",\n";
  os << "  \"instance_hash\": \"" << JsonEscape(instance_hash) << "\",\n";
  os << "  \"generation_time_unix_sec\": " << generation_time_unix_sec << ",\n";
  os << "  \"units\": {\n";
  os << "    \"length\": \"mm\", \"area\": \"mm^2\", \"power\": \"cost_model_power\",";
  os << " \"power_density\": \"cost_model_power/mm^2\", \"temperature\": \"K\"\n";
  os << "  },\n";
  os << "  \"provenance\": {\n";
  os << "    \"run_id\": \"" << JsonEscape(instance.run_id) << "\",\n";
  os << "    \"benchmark\": \"" << JsonEscape(instance.source_testcase) << "\",\n";
  os << "    \"testcase\": \"" << JsonEscape(instance.source_testcase) << "\",\n";
  os << "    \"seed\": \"" << JsonEscape(instance.seed) << "\",\n";
  os << "    \"candidate_index\": ";
  if (instance.candidate_index >= 0) {
    os << instance.candidate_index;
  } else {
    os << "null";
  }
  os << ",\n";
  os << "    \"candidate_source\": \"" << JsonEscape(candidate_source) << "\",\n";
  os << "    \"search_stage\": \"" << JsonEscape(search_stage) << "\",\n";
  os << "    \"num_chiplets\": " << instance.chiplets.size() << ",\n";
  os << "    \"technology_assignment_summary\": ";
  WriteStringCountsObject(os, instance.technology_assignment);
  os << ",\n";
  os << "    \"cost\": ";
  if (instance.has_cost_objective) {
    os << instance.cost_objective;
  } else {
    os << "null";
  }
  os << ",\n";
  os << "    \"thermal_enabled\": " << (instance.thermal_enabled ? "true" : "false")
     << ",\n";
  os << "    \"floorplan_feasible\": "
     << (instance.floorplan_feasible ? "true" : "false") << ",\n";
  os << "    \"io_feasible\": " << (instance.io_feasible ? "true" : "false") << ",\n";
  os << "    \"instance_hash\": \"" << JsonEscape(instance_hash) << "\",\n";
  os << "    \"generation_time_unix_sec\": " << generation_time_unix_sec << "\n";
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
  os << "  \"technology_assignment_summary\": ";
  WriteStringCountsObject(os, instance.technology_assignment);
  os << ",\n";
  os << "  \"rasterization\": {\"mode\": \"synthetic_block_treemap\", "
     << "\"io_power_mode\": \"chiplet_uniform\", "
     << "\"total_power_before_raster\": "
     << instance.total_power_before_raster << ", \"total_power_after_raster\": "
     << instance.total_power_after_raster << ", \"power_error\": "
     << instance.raster_power_error << "},\n";
  os << "  \"block_rasterization_mode\": \"synthetic_block_treemap\",\n";
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
  os << "  \"blocks\": [\n";
  for (size_t i = 0; i < instance.blocks.size(); ++i) {
    const auto& block_info = instance.blocks[i];
    os << "    {\"id\": " << block_info.id << ", \"name\": \""
       << JsonEscape(block_info.name) << "\", \"chiplet_id\": "
       << block_info.chiplet_id << ", \"source_technology\": \""
       << JsonEscape(block_info.source_technology)
       << "\", \"technology\": \"" << JsonEscape(block_info.technology)
       << "\", \"is_memory\": " << (block_info.is_memory ? "true" : "false")
       << ", \"x_mm\": " << block_info.x_mm << ", \"y_mm\": "
       << block_info.y_mm << ", \"width_mm\": " << block_info.width_mm
       << ", \"height_mm\": " << block_info.height_mm
       << ", \"area_mm2\": " << block_info.area_mm2
       << ", \"compute_power\": " << block_info.compute_power << "}";
    os << (i + 1 == instance.blocks.size() ? "\n" : ",\n");
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
             << "\"instance_hash\":\"" << JsonEscape(instance_hash) << "\","
             << "\"json_path\":\"" << JsonEscape(path.string()) << "\","
             << "\"testcase\":\"" << JsonEscape(instance.source_testcase) << "\","
             << "\"benchmark\":\"" << JsonEscape(instance.source_testcase) << "\","
             << "\"grid_x\":" << instance.grid_x << ","
             << "\"grid_y\":" << instance.grid_y << ","
             << "\"run_id\":\"" << JsonEscape(instance.run_id) << "\","
             << "\"seed\":\"" << JsonEscape(instance.seed) << "\","
             << "\"candidate_index\":";
    if (instance.candidate_index >= 0) {
      manifest << instance.candidate_index;
    } else {
      manifest << "null";
    }
    manifest << ",\"candidate_source\":\"" << JsonEscape(candidate_source) << "\","
             << "\"search_stage\":\"" << JsonEscape(search_stage) << "\","
             << "\"num_chiplets\":" << instance.chiplets.size() << ","
             << "\"technology_assignment\":";
    WriteStringArray(manifest, instance.technology_assignment);
    manifest << ",\"technology_assignment_summary\":";
    WriteStringCountsObject(manifest, instance.technology_assignment);
    manifest << ",\"cost\":";
    if (instance.has_cost_objective) {
      manifest << instance.cost_objective;
    } else {
      manifest << "null";
    }
    manifest << ",\"total_power\":" << total_power
             << ",\"thermal_enabled\":"
             << (instance.thermal_enabled ? "true" : "false")
             << ",\"floorplan_feasible\":"
             << (instance.floorplan_feasible ? "true" : "false")
             << ",\"io_feasible\":"
             << (instance.io_feasible ? "true" : "false")
             << ",\"generation_time_unix_sec\":" << generation_time_unix_sec
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
    : config_(std::move(config)) {
  std::signal(SIGPIPE, SIG_IGN);
}

PythonDeepOHeatAdapter::~PythonDeepOHeatAdapter() {
  StopService();
}

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

std::string PythonDeepOHeatAdapter::JsonEscape(const std::string& value) const {
  std::ostringstream os;
  for (char c : value) {
    switch (c) {
      case '\\':
        os << "\\\\";
        break;
      case '"':
        os << "\\\"";
        break;
      case '\n':
        os << "\\n";
        break;
      case '\r':
        os << "\\r";
        break;
      case '\t':
        os << "\\t";
        break;
      default:
        os << c;
        break;
    }
  }
  return os.str();
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

ThermalResult PythonDeepOHeatAdapter::PredictWithSubprocess(
    const std::string& instance_path,
    const std::filesystem::path& output_path,
    const std::string& script) const {
  std::ostringstream cmd;
  cmd << ShellQuote(config_.python_executable)
      << " " << ShellQuote(script)
      << " --instance " << ShellQuote(instance_path)
      << " --model " << ShellQuote(config_.thermal_model_path)
      << " --output " << ShellQuote(output_path.string());
  if (!config_.thermal_model_config.empty()) {
    cmd << " --config " << ShellQuote(config_.thermal_model_config);
  }
  if (!config_.thermal_device.empty()) {
    cmd << " --device " << ShellQuote(config_.thermal_device);
  }
  if (config_.thermal_backend == "package_thermal") {
    cmd << " --dump_field";
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

void PythonDeepOHeatAdapter::StartService(const std::string& script) {
  if (service_pid_ > 0 && service_script_ == script) {
    return;
  }
  StopService();

  int stdin_pipe[2] = {-1, -1};
  int stdout_pipe[2] = {-1, -1};
  if (pipe(stdin_pipe) != 0 || pipe(stdout_pipe) != 0) {
    if (stdin_pipe[0] >= 0) {
      close(stdin_pipe[0]);
    }
    if (stdin_pipe[1] >= 0) {
      close(stdin_pipe[1]);
    }
    if (stdout_pipe[0] >= 0) {
      close(stdout_pipe[0]);
    }
    if (stdout_pipe[1] >= 0) {
      close(stdout_pipe[1]);
    }
    throw std::runtime_error("[THERMAL] Failed to create DeepOHeat service pipes: " +
                             std::string(std::strerror(errno)));
  }

  const pid_t pid = fork();
  if (pid < 0) {
    close(stdin_pipe[0]);
    close(stdin_pipe[1]);
    close(stdout_pipe[0]);
    close(stdout_pipe[1]);
    throw std::runtime_error("[THERMAL] Failed to fork DeepOHeat service: " +
                             std::string(std::strerror(errno)));
  }

  if (pid == 0) {
    dup2(stdin_pipe[0], STDIN_FILENO);
    dup2(stdout_pipe[1], STDOUT_FILENO);
    close(stdin_pipe[0]);
    close(stdin_pipe[1]);
    close(stdout_pipe[0]);
    close(stdout_pipe[1]);

    std::vector<std::string> args;
    args.push_back(config_.python_executable);
    args.push_back(script);
    args.push_back("--server");
    args.push_back("--model");
    args.push_back(config_.thermal_model_path);
    if (!config_.thermal_model_config.empty()) {
      args.push_back("--config");
      args.push_back(config_.thermal_model_config);
    }
    if (!config_.thermal_device.empty()) {
      args.push_back("--device");
      args.push_back(config_.thermal_device);
    }

    std::vector<char*> argv;
    argv.reserve(args.size() + 1);
    for (auto& arg : args) {
      argv.push_back(arg.data());
    }
    argv.push_back(nullptr);
    execvp(config_.python_executable.c_str(), argv.data());
    std::cerr << "[THERMAL] Failed to exec DeepOHeat service: "
              << std::strerror(errno) << std::endl;
    _exit(127);
  }

  close(stdin_pipe[0]);
  close(stdout_pipe[1]);
  service_pid_ = static_cast<int>(pid);
  service_stdin_fd_ = stdin_pipe[1];
  service_stdout_fd_ = stdout_pipe[0];
  service_script_ = script;
  std::cout << "[THERMAL] Started persistent DeepOHeat service pid="
            << service_pid_ << " backend=" << config_.thermal_backend
            << std::endl;
}

void PythonDeepOHeatAdapter::StopService() {
  if (service_stdin_fd_ >= 0) {
    const std::string shutdown = "{\"shutdown\":true}\n";
    const char* data = shutdown.data();
    size_t remaining = shutdown.size();
    while (remaining > 0) {
      const ssize_t written = write(service_stdin_fd_, data, remaining);
      if (written < 0) {
        if (errno == EINTR) {
          continue;
        }
        break;
      }
      data += written;
      remaining -= static_cast<size_t>(written);
    }
    close(service_stdin_fd_);
    service_stdin_fd_ = -1;
  }
  if (service_stdout_fd_ >= 0) {
    close(service_stdout_fd_);
    service_stdout_fd_ = -1;
  }
  if (service_pid_ > 0) {
    int status = 0;
    while (waitpid(static_cast<pid_t>(service_pid_), &status, 0) < 0 &&
           errno == EINTR) {
    }
    service_pid_ = -1;
  }
  service_script_.clear();
}

void PythonDeepOHeatAdapter::WriteServiceLine(const std::string& line) {
  if (service_stdin_fd_ < 0) {
    throw std::runtime_error("[THERMAL] DeepOHeat service stdin is closed");
  }
  std::string payload = line;
  if (payload.empty() || payload.back() != '\n') {
    payload.push_back('\n');
  }
  const char* data = payload.data();
  size_t remaining = payload.size();
  while (remaining > 0) {
    const ssize_t written = write(service_stdin_fd_, data, remaining);
    if (written < 0) {
      if (errno == EINTR) {
        continue;
      }
      throw std::runtime_error("[THERMAL] Failed to write DeepOHeat service "
                               "request: " +
                               std::string(std::strerror(errno)));
    }
    if (written == 0) {
      throw std::runtime_error("[THERMAL] DeepOHeat service write returned zero");
    }
    data += written;
    remaining -= static_cast<size_t>(written);
  }
}

std::string PythonDeepOHeatAdapter::ReadServiceLine() {
  if (service_stdout_fd_ < 0) {
    throw std::runtime_error("[THERMAL] DeepOHeat service stdout is closed");
  }
  std::string line;
  char ch = '\0';
  while (true) {
    const ssize_t count = read(service_stdout_fd_, &ch, 1);
    if (count < 0) {
      if (errno == EINTR) {
        continue;
      }
      throw std::runtime_error("[THERMAL] Failed to read DeepOHeat service "
                               "response: " +
                               std::string(std::strerror(errno)));
    }
    if (count == 0) {
      throw std::runtime_error("[THERMAL] DeepOHeat service exited before "
                               "returning a response");
    }
    if (ch == '\n') {
      if (line.find("\"ok\"") != std::string::npos) {
        return line;
      }
      line.clear();
      continue;
    }
    line.push_back(ch);
    if (line.size() > 1024 * 1024) {
      throw std::runtime_error("[THERMAL] DeepOHeat service response line is "
                               "too large");
    }
  }
}

ThermalResult PythonDeepOHeatAdapter::PredictWithPersistentService(
    const std::string& instance_path,
    const std::filesystem::path& output_path,
    const std::string& script) {
  StartService(script);
  std::ostringstream request;
  request << "{\"instance\":\"" << JsonEscape(instance_path)
          << "\",\"output\":\"" << JsonEscape(output_path.string())
          << "\",\"dump_field\":"
          << (config_.thermal_backend == "package_thermal" ? "true" : "false")
          << "}";
  WriteServiceLine(request.str());
  const std::string response = ReadServiceLine();
  if (response.find("\"ok\": true") == std::string::npos &&
      response.find("\"ok\":true") == std::string::npos) {
    const std::string error = ExtractJsonString(response, "error");
    throw std::runtime_error("[THERMAL] DeepOHeat service inference failed: " +
                             (error.empty() ? response : error));
  }

  ThermalResult result;
  result.t_max = ExtractJsonNumber(response, "t_max");
  result.t_avg = ExtractJsonNumber(response, "t_avg");
  result.field_path = ExtractJsonString(response, "field_path");
  return result;
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

  if (!service_disabled_) {
    try {
      return PredictWithPersistentService(instance_path, output_path, script);
    } catch (const std::exception& e) {
      StopService();
      service_disabled_ = true;
      std::cerr << "[THERMAL] Warning: persistent DeepOHeat service unavailable ("
                << e.what() << "); falling back to per-call subprocess"
                << std::endl;
    }
  }

  return PredictWithSubprocess(instance_path, output_path, script);
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
    block_to_graph_vertex_ =
        BuildThermalBlockToGraphVertexMapping(blocks_, library_dicts_->block_names);
    if (blocks_.size() != library_dicts_->block_names.size()) {
      std::cout << "[THERMAL] Mapped " << blocks_.size()
                << " block-level power records onto "
                << library_dicts_->block_names.size()
                << " netlist vertices for thermal encoding" << std::endl;
    }
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
  if (!VerboseThermalLogging()) {
    return;
  }
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
      std::vector<int> block_partition;
      const std::vector<int>* compute_partition = &partition;
      const std::vector<int>* io_partition = nullptr;
      if (partition.size() != blocks_.size()) {
        if (block_to_graph_vertex_.size() != blocks_.size()) {
          throw std::runtime_error("[THERMAL] Missing block-to-netlist mapping for "
                                   "hierarchical block power records");
        }
        block_partition.resize(blocks_.size(), 0);
        for (size_t block_id = 0; block_id < blocks_.size(); ++block_id) {
          const int graph_vertex = block_to_graph_vertex_[block_id];
          if (graph_vertex < 0 ||
              graph_vertex >= static_cast<int>(partition.size())) {
            throw std::runtime_error("[THERMAL] Block-to-netlist mapping references "
                                     "a vertex outside the candidate partition");
          }
          block_partition[block_id] = partition[graph_vertex];
        }
        compute_partition = &block_partition;
        io_partition = &partition;
      }

      ThermalInstance instance = encoder_.Encode(
          *compute_partition, tech_assignment, aspect_ratios, x_locations,
          y_locations, blocks_, library_dicts_, io_partition);
      if (instance.source_testcase.empty()) {
        instance.source_testcase = PathStemOrUnknown(blocks_file_);
      }
      instance.run_id = config_.thermal_run_id;
      instance.candidate_source = config_.thermal_candidate_source.empty()
                                      ? "unknown"
                                      : config_.thermal_candidate_source;
      instance.search_stage = config_.thermal_search_stage.empty()
                                  ? "unknown"
                                  : config_.thermal_search_stage;
      instance.seed = config_.thermal_seed;
      instance.candidate_index = static_cast<int>(next_candidate_index_++);
      instance.instance_hash = ShortHash(key);
      instance.thermal_enabled = config_.enable_thermal;
      instance.floorplan_feasible = floorplan_success;
      instance.io_feasible = floorplan_success;
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

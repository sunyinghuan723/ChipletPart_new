#include "ThermalAwareEvaluator.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

void Require(bool condition, const std::string& message) {
  if (!condition) {
    throw std::runtime_error(message);
  }
}

std::string ReadFile(const fs::path& path) {
  std::ifstream is(path);
  Require(is.is_open(), "cannot open " + path.string());
  std::stringstream buffer;
  buffer << is.rdbuf();
  return buffer.str();
}

double ExtractJsonNumber(const std::string& json, const std::string& key) {
  const std::string pattern = "\"" + key + "\"";
  size_t pos = json.find(pattern);
  Require(pos != std::string::npos, "missing JSON key " + key);
  pos = json.find(':', pos);
  Require(pos != std::string::npos, "malformed JSON key " + key);
  ++pos;
  const size_t end = json.find_first_of(",}\n", pos);
  Require(end != std::string::npos, "malformed JSON value " + key);
  return std::stod(json.substr(pos, end - pos));
}

std::vector<double> ExtractJsonNumberArray(const std::string& json,
                                           const std::string& key) {
  const std::string pattern = "\"" + key + "\":";
  size_t pos = json.find(pattern);
  Require(pos != std::string::npos, "missing JSON key " + key);
  pos = json.find('[', pos);
  Require(pos != std::string::npos, "malformed JSON array " + key);
  const size_t end = json.find(']', pos);
  Require(end != std::string::npos, "malformed JSON array " + key);

  std::vector<double> values;
  size_t cursor = pos + 1;
  while (cursor < end) {
    while (cursor < end &&
           (std::isspace(static_cast<unsigned char>(json[cursor])) ||
            json[cursor] == ',')) {
      ++cursor;
    }
    if (cursor >= end) {
      break;
    }
    size_t next = cursor;
    while (next < end && json[next] != ',') {
      ++next;
    }
    values.push_back(std::stod(json.substr(cursor, next - cursor)));
    cursor = next + 1;
  }
  return values;
}

fs::path FindFirstJson(const fs::path& dir) {
  for (const auto& entry : fs::directory_iterator(dir)) {
    if (entry.path().extension() == ".json") {
      return entry.path();
    }
  }
  throw std::runtime_error("no dumped thermal instance JSON in " + dir.string());
}

std::vector<int> MakeSingleChipletPartition(const std::string& blocks_file) {
  const std::vector<block> blocks = readBlocks(blocks_file);
  Require(!blocks.empty(), "test blocks file is empty");
  return std::vector<int>(blocks.size(), 0);
}

} // namespace

int main(int argc, char** argv) {
  const fs::path data_dir =
      argc > 1 ? fs::path(argv[1])
               : fs::path("../test_data/48_1_14_4_1600_1600");
  const std::string io_file = (data_dir / "io_definitions.xml").string();
  const std::string netlist_file = (data_dir / "block_level_netlist.xml").string();
  const std::string blocks_file = (data_dir / "block_definitions.txt").string();

  const std::vector<int> partition = MakeSingleChipletPartition(blocks_file);
  const std::vector<std::string> tech_assignment = {"14nm"};
  const std::vector<float> aspect_ratios = {1.0f};
  const std::vector<float> x_locations = {0.0f};
  const std::vector<float> y_locations = {0.0f};
  const double base_cost = 123.456;

  const std::vector<block> hierarchical_blocks = {
      {"sm_0", 1.0, 1.0, "7nm", false},
      {"sm_1", 1.0, 1.0, "7nm", false},
      {"l2_0", 1.0, 1.0, "7nm", true},
      {"hbm_1024_phy_0", 1.0, 1.0, "7nm", true},
      {"hbm_1536_ctrl_0", 1.0, 1.0, "7nm", true}};
  const std::vector<std::string> graph_blocks = {
      "l2_0", "l2_1", "hbm_1536_ctrl_0"};
  const auto hierarchical_mapping =
      chiplet::BuildThermalBlockToGraphVertexMapping(hierarchical_blocks,
                                                      graph_blocks);
  Require(hierarchical_mapping == std::vector<int>({0, 1, 0, 2, 2}),
          "hierarchical thermal/floorplan mapping rules diverged");

  chiplet::ThermalConfig disabled_config;
  disabled_config.enable_thermal = false;
  chiplet::ThermalAwareEvaluator disabled(disabled_config, io_file, netlist_file,
                                          blocks_file);
  const auto cost_only = disabled.Evaluate(base_cost, partition, tech_assignment,
                                           aspect_ratios, x_locations, y_locations,
                                           true);
  Require(cost_only.objective == base_cost,
          "thermal-disabled evaluation changed base cost");

  const fs::path dump_dir = fs::temp_directory_path() / "chipletpart_thermal_mvp_dump";
  fs::remove_all(dump_dir);

  chiplet::ThermalConfig mock_config;
  mock_config.enable_thermal = true;
  mock_config.use_mock_thermal_model = true;
  mock_config.thermal_cache_enable = true;
  mock_config.grid_x = 8;
  mock_config.grid_y = 8;
  mock_config.thermal_budget = 250.0;
  mock_config.lambda_peak = 1.0e-3;
  mock_config.lambda_avg = 0.0;
  mock_config.thermal_dump_instances = dump_dir.string();

  chiplet::ThermalAwareEvaluator mock(mock_config, io_file, netlist_file,
                                      blocks_file);
  const auto thermal = mock.Evaluate(base_cost, partition, tech_assignment,
                                     aspect_ratios, x_locations, y_locations, true);
  Require(thermal.objective > base_cost,
          "mock thermal penalty should increase objective under low budget");
  Require(std::abs(thermal.objective - mock.Objective(base_cost, thermal.thermal)) <
              1.0e-9,
          "central objective helper disagrees with evaluation result");

  const auto cached = mock.Evaluate(base_cost, partition, tech_assignment,
                                    aspect_ratios, x_locations, y_locations, true);
  Require(cached.cache_hit, "repeated candidate did not hit thermal cache");

  const fs::path dumped = FindFirstJson(dump_dir);
  const std::string json = ReadFile(dumped);
  Require(json.find("\"schema\": \"chipletpart.thermal_instance.v1\"") !=
              std::string::npos,
          "dumped instance has wrong schema");
  Require(json.find("\"chiplet_footprint\"") != std::string::npos,
          "dumped instance missing geometry channel");
  Require(json.find("\"power_density_w_per_mm2\"") != std::string::npos,
          "dumped instance missing power channel");
  Require(json.find("\"block_rasterization_mode\": \"synthetic_block_treemap\"") !=
              std::string::npos,
          "dumped instance missing synthetic block rasterization mode");
  Require(json.find("\"blocks\"") != std::string::npos,
          "dumped instance missing packed block metadata");
  Require(json.find("\"silicon_material\"") != std::string::npos,
          "dumped instance missing material channel");
  Require(json.find("\"heat_transfer_coefficient\"") != std::string::npos,
          "dumped instance missing boundary-condition channel");
  const double before = ExtractJsonNumber(json, "total_power_before_raster");
  const double power_error = ExtractJsonNumber(json, "power_error");
  Require(std::abs(power_error) <= std::max(1.0e-3, 0.01 * std::abs(before)),
          "rasterized power is not conserved within tolerance");
  const auto densities = ExtractJsonNumberArray(json, "power_density_w_per_mm2");
  Require(!densities.empty(), "power-density array is empty");
  const auto [min_density, max_density] =
      std::minmax_element(densities.begin(), densities.end());
  Require(densities.size() == 64 && *max_density - *min_density > 1.0e-6,
          "block-level rasterization did not create a nonuniform power map");

  std::vector<int> overlapping_partition = partition;
  overlapping_partition.back() = 1;
  const std::vector<std::string> overlapping_tech_assignment = {"14nm", "14nm"};
  const std::vector<float> overlapping_aspect_ratios = {1.0f, 1.0f};
  const std::vector<float> overlapping_x_locations = {0.0f, 0.0f};
  const std::vector<float> overlapping_y_locations = {0.0f, 0.0f};
  bool saw_overlap_failure = false;
  try {
    (void)mock.Evaluate(base_cost, overlapping_partition,
                        overlapping_tech_assignment, overlapping_aspect_ratios,
                        overlapping_x_locations, overlapping_y_locations, true);
  } catch (const std::exception& e) {
    saw_overlap_failure =
        std::string(e.what()).find("Overlapping chiplets") != std::string::npos;
  }
  Require(saw_overlap_failure,
          "overlapping chiplets were accepted by the thermal encoder");

  const std::vector<float> separated_negative_x_locations = {-10000.0f, 0.0f};
  bool translated_floorplan_accepted = true;
  try {
    (void)mock.Evaluate(base_cost, overlapping_partition,
                        overlapping_tech_assignment, overlapping_aspect_ratios,
                        separated_negative_x_locations, overlapping_y_locations,
                        true);
  } catch (const std::exception&) {
    translated_floorplan_accepted = false;
  }
  Require(translated_floorplan_accepted,
          "normalizing negative floorplan coordinates introduced an overlap");

  chiplet::ThermalConfig high_budget_config = mock_config;
  high_budget_config.thermal_budget = thermal.thermal.t_max + 100.0;
  high_budget_config.thermal_dump_instances =
      (fs::temp_directory_path() / "chipletpart_thermal_mvp_high_budget").string();
  chiplet::ThermalAwareEvaluator high_budget(high_budget_config, io_file,
                                             netlist_file, blocks_file);
  const auto relaxed = high_budget.Evaluate(base_cost, partition, tech_assignment,
                                            aspect_ratios, x_locations, y_locations,
                                            true);
  Require(std::abs(relaxed.objective - base_cost) < 1.0e-9,
          "high thermal budget should remove peak penalty when lambda_avg is zero");

  chiplet::ThermalConfig failing_config = mock_config;
  failing_config.use_mock_thermal_model = false;
  failing_config.thermal_model_path.clear();
  failing_config.thermal_cache_enable = false;
  failing_config.thermal_dump_instances =
      (fs::temp_directory_path() / "chipletpart_thermal_mvp_failure").string();
  chiplet::ThermalAwareEvaluator failing(failing_config, io_file, netlist_file,
                                         blocks_file);
  bool saw_failure = false;
  try {
    (void)failing.Evaluate(base_cost, partition, tech_assignment, aspect_ratios,
                           x_locations, y_locations, true);
  } catch (const std::exception& e) {
    saw_failure = std::string(e.what()).find("--thermal_model_path") !=
                  std::string::npos;
  }
  Require(saw_failure, "missing non-mock model path did not produce clear error");

  std::cout << "[THERMAL_TEST] thermal MVP smoke test passed" << std::endl;
  return 0;
}

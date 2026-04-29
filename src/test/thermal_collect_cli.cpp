#include "ThermalAwareEvaluator.h"
#include "evaluator_cpp.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::string GetArg(int argc, char** argv, const std::string& name,
                   const std::string& fallback = "") {
  for (int i = 1; i + 1 < argc; ++i) {
    if (argv[i] == name) {
      return argv[i + 1];
    }
  }
  return fallback;
}

int GetIntArg(int argc, char** argv, const std::string& name, int fallback) {
  const std::string value = GetArg(argc, argv, name);
  return value.empty() ? fallback : std::stoi(value);
}

std::vector<std::string> SplitCsv(const std::string& text) {
  std::vector<std::string> values;
  std::stringstream ss(text);
  std::string item;
  while (std::getline(ss, item, ',')) {
    if (!item.empty()) {
      values.push_back(item);
    }
  }
  if (values.empty()) {
    values.push_back("14nm");
  }
  return values;
}

bool IsAreaScalingTechSupported(const std::string& tech) {
  static const std::vector<std::string> supported = {
      "90nm", "65nm", "45nm", "32nm", "20nm", "16nm", "14nm", "10nm", "7nm"};
  return std::find(supported.begin(), supported.end(), tech) != supported.end();
}

double SafeAreaScaling(const std::string& initial_tech,
                       const std::string& actual_tech,
                       bool is_memory) {
  if (!IsAreaScalingTechSupported(initial_tech) ||
      !IsAreaScalingTechSupported(actual_tech)) {
    throw std::runtime_error("unsupported area scaling technology: " +
                             initial_tech + " -> " + actual_tech);
  }
  return area_scaling_factor(initial_tech, actual_tech, is_memory);
}

std::vector<int> RandomPartition(int num_blocks, int num_parts, std::mt19937& rng) {
  std::vector<int> partition(num_blocks, 0);
  for (int i = 0; i < num_blocks; ++i) {
    partition[i] = i < num_parts ? i : static_cast<int>(rng() % num_parts);
  }
  std::shuffle(partition.begin(), partition.end(), rng);
  return partition;
}

void BuildShelfFloorplan(const std::vector<block>& blocks,
                         const std::vector<int>& partition,
                         const std::vector<std::string>& tech_assignment,
                         std::vector<float>& aspect_ratios,
                         std::vector<float>& x_locations,
                         std::vector<float>& y_locations) {
  const int num_parts = static_cast<int>(tech_assignment.size());
  std::vector<double> area(num_parts, 0.0);
  for (size_t i = 0; i < blocks.size(); ++i) {
    const int part = partition[i];
    area[part] += blocks[i].area *
                  SafeAreaScaling(blocks[i].tech, tech_assignment[part],
                                  blocks[i].is_memory);
  }

  aspect_ratios.assign(num_parts, 1.0f);
  x_locations.assign(num_parts, 0.0f);
  y_locations.assign(num_parts, 0.0f);

  double max_dim = 1.0;
  for (double a : area) {
    max_dim = std::max(max_dim, std::sqrt(std::max(1.0, a)));
  }
  const double pitch = max_dim * 1.35;
  const int cols = std::max(1, static_cast<int>(std::ceil(std::sqrt(num_parts))));
  for (int part = 0; part < num_parts; ++part) {
    x_locations[part] = static_cast<float>((part % cols) * pitch);
    y_locations[part] = static_cast<float>((part / cols) * pitch);
  }
}

void Usage(const char* argv0) {
  std::cerr << "Usage: " << argv0
            << " --io <io.xml> --netlist <netlist.xml> --blocks <blocks.txt>"
            << " --out_dir <dir> --manifest <manifest.jsonl>"
            << " [--num_instances N] [--seed S] [--grid_x X] [--grid_y Y]"
            << " [--source_testcase name] [--tech_nodes 7nm,14nm]"
            << " [--max_chiplets N] [--prefix name] [--run_id id]"
            << " [--candidate_source source] [--search_stage stage]\n";
}

} // namespace

int main(int argc, char** argv) {
  try {
    const std::string io_file = GetArg(argc, argv, "--io");
    const std::string netlist_file = GetArg(argc, argv, "--netlist");
    const std::string blocks_file = GetArg(argc, argv, "--blocks");
    const std::string out_dir = GetArg(argc, argv, "--out_dir");
    const std::string manifest = GetArg(argc, argv, "--manifest");
    if (io_file.empty() || netlist_file.empty() || blocks_file.empty() ||
        out_dir.empty() || manifest.empty()) {
      Usage(argv[0]);
      return 2;
    }

    const int num_instances = GetIntArg(argc, argv, "--num_instances", 20);
    const int seed = GetIntArg(argc, argv, "--seed", 1);
    const int grid_x = GetIntArg(argc, argv, "--grid_x", 32);
    const int grid_y = GetIntArg(argc, argv, "--grid_y", 32);
    const int max_chiplets = GetIntArg(argc, argv, "--max_chiplets", 6);
    const std::string source_testcase =
        GetArg(argc, argv, "--source_testcase",
               fs::path(blocks_file).parent_path().filename().string());
    const std::string prefix = GetArg(argc, argv, "--prefix", "thermal_instance");
    const std::string run_id =
        GetArg(argc, argv, "--run_id", prefix + "_seed" + std::to_string(seed));
    const std::string candidate_source =
        GetArg(argc, argv, "--candidate_source", "synthetic_helper");
    const std::string search_stage =
        GetArg(argc, argv, "--search_stage", "synthetic_random_shelf");
    const std::vector<std::string> tech_nodes =
        SplitCsv(GetArg(argc, argv, "--tech_nodes", "14nm"));

    chiplet::ThermalConfig config;
    config.enable_thermal = true;
    config.use_mock_thermal_model = true;
    config.thermal_backend = "mock";
    config.grid_x = grid_x;
    config.grid_y = grid_y;
    config.thermal_dump_instances = out_dir;
    config.thermal_dump_manifest = manifest;
    config.thermal_dump_prefix = prefix;
    config.thermal_source_testcase = source_testcase;
    config.thermal_dump_split = "unlabeled";
    config.thermal_run_id = run_id;
    config.thermal_candidate_source = candidate_source;
    config.thermal_search_stage = search_stage;
    config.thermal_seed = std::to_string(seed);
    config.thermal_budget = 1.0e9;
    config.lambda_peak = 0.0;

    const std::vector<block> blocks = readBlocks(blocks_file);
    if (blocks.empty()) {
      throw std::runtime_error("no blocks loaded from " + blocks_file);
    }

    fs::create_directories(out_dir);
    if (fs::exists(manifest)) {
      fs::remove(manifest);
    }

    std::mt19937 rng(seed);
    for (int i = 0; i < num_instances; ++i) {
      chiplet::ThermalConfig instance_config = config;
      instance_config.thermal_dump_prefix = prefix + "_" + std::to_string(i);
      chiplet::ThermalAwareEvaluator evaluator(instance_config, io_file, netlist_file,
                                               blocks_file);
      const int upper = std::min(max_chiplets, static_cast<int>(blocks.size()));
      const int num_parts = 1 + static_cast<int>(rng() % std::max(1, upper));
      std::vector<int> partition =
          RandomPartition(static_cast<int>(blocks.size()), num_parts, rng);
      std::vector<std::string> tech_assignment(num_parts);
      for (int part = 0; part < num_parts; ++part) {
        tech_assignment[part] = tech_nodes[rng() % tech_nodes.size()];
      }

      std::vector<float> aspect_ratios;
      std::vector<float> x_locations;
      std::vector<float> y_locations;
      BuildShelfFloorplan(blocks, partition, tech_assignment, aspect_ratios,
                          x_locations, y_locations);

      (void)evaluator.Evaluate(0.0, partition, tech_assignment, aspect_ratios,
                               x_locations, y_locations, true);
      std::cout << "[THERMAL-DATA] dumped " << (i + 1) << "/" << num_instances
                << " parts=" << num_parts << std::endl;
    }
  } catch (const std::exception& e) {
    std::cerr << "[THERMAL-DATA] Error: " << e.what() << std::endl;
    return 1;
  }
  return 0;
}

#pragma once

#include <string>

namespace chiplet {

struct ThermalConfig {
  bool enable_thermal = false;
  bool use_mock_thermal_model = false;
  bool thermal_cache_enable = false;
  bool allow_thermal_fallback = false;

  std::string thermal_backend = "legacy_2d_power_map";
  std::string thermal_model_path;
  std::string thermal_model_config;
  std::string thermal_dump_instances;
  std::string thermal_dump_manifest;
  std::string thermal_dump_prefix = "thermal_instance";
  std::string thermal_dump_split = "unlabeled";
  std::string thermal_source_testcase;
  std::string thermal_inference_script;
  std::string python_executable = "python3";
  std::string thermal_device = "auto";

  double thermal_budget = 358.15; // Kelvin
  double lambda_peak = 0.0;
  double lambda_avg = 0.0;
  int grid_x = 32;
  int grid_y = 32;
  int grid_z = 1;
  double ambient_temperature = 293.15; // Kelvin
  double heat_transfer_coefficient = 0.2;

  // Default package/material constants used by the MVP encoder. Units are
  // documented in docs/thermal_integration.md.
  double silicon_conductivity = 130.0;
  double interposer_conductivity = 120.0;
  double tim_conductivity = 4.0;
  double package_conductivity = 20.0;
};

} // namespace chiplet

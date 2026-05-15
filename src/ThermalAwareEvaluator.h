#pragma once

#include "ThermalConfig.h"
#include "evaluator_cpp.h"

#include <map>
#include <memory>
#include <mutex>
#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace chiplet {

struct ThermalChipletInfo {
  int id = 0;
  std::string technology;
  double x_mm = 0.0;
  double y_mm = 0.0;
  double width_mm = 0.0;
  double height_mm = 0.0;
  double area_mm2 = 0.0;
  double compute_power = 0.0;
  double io_power = 0.0;
  double total_power = 0.0;
};

struct ThermalBlockInfo {
  int id = 0;
  std::string name;
  int chiplet_id = 0;
  std::string source_technology;
  std::string technology;
  bool is_memory = false;
  double x_mm = 0.0;
  double y_mm = 0.0;
  double width_mm = 0.0;
  double height_mm = 0.0;
  double area_mm2 = 0.0;
  double compute_power = 0.0;
};

struct ThermalInstance {
  std::string schema_version = "chipletpart.thermal_instance.v2";
  std::string instance_id;
  std::string source_testcase;
  std::string run_id;
  std::string candidate_source;
  std::string search_stage;
  std::string seed;
  std::string instance_hash;
  int candidate_index = -1;
  bool thermal_enabled = false;
  bool floorplan_feasible = false;
  bool io_feasible = false;
  int grid_x = 0;
  int grid_y = 0;
  double package_width_mm = 0.0;
  double package_height_mm = 0.0;
  double ambient_temperature = 0.0;
  double heat_transfer_coefficient = 0.0;
  double cost_objective = 0.0;
  bool has_cost_objective = false;
  double total_power_before_raster = 0.0;
  double total_power_after_raster = 0.0;
  double raster_power_error = 0.0;
  std::vector<int> partition;
  std::vector<std::string> technology_assignment;
  std::vector<std::string> channel_names;
  std::vector<ThermalChipletInfo> chiplets;
  std::vector<ThermalBlockInfo> blocks;
  std::vector<double> package_domain;
  std::vector<double> chiplet_footprint;
  std::vector<double> chiplet_boundary;
  std::vector<double> power_density;
  std::vector<double> silicon_material;
  std::vector<double> interposer_material;
  std::vector<double> tim_material;
  std::vector<double> package_material;
  std::vector<double> ambient_channel;
  std::vector<double> htc_channel;
};

struct ThermalResult {
  double t_max = 0.0;
  double t_avg = 0.0;
  std::string field_path;
};

struct ThermalEvaluation {
  double base_cost = 0.0;
  double objective = 0.0;
  double peak_penalty = 0.0;
  double avg_penalty = 0.0;
  ThermalResult thermal;
  bool cache_hit = false;
};

class ThermalInstanceEncoder {
public:
  explicit ThermalInstanceEncoder(ThermalConfig config);

  ThermalInstance Encode(const std::vector<int>& partition,
                         const std::vector<std::string>& tech_assignment,
                         const std::vector<float>& aspect_ratios,
                         const std::vector<float>& x_locations,
                         const std::vector<float>& y_locations,
                         const std::vector<block>& blocks,
                         const LibraryDicts* library_dicts,
                         const std::vector<int>* io_partition = nullptr) const;

  std::string DumpJson(const ThermalInstance& instance,
                       const std::string& dump_dir,
                       const std::string& key) const;

private:
  std::vector<std::string> NormalizeTechArray(
      const std::vector<std::string>& tech_assignment, int num_partitions) const;
  std::vector<double> ComputeIoPowerByPartition(
      const std::vector<int>& partition,
      const LibraryDicts* library_dicts,
      int num_partitions) const;
  void Rasterize(ThermalInstance& instance) const;

  ThermalConfig config_;
};

class ThermalSurrogate {
public:
  virtual ~ThermalSurrogate() = default;
  virtual ThermalResult Predict(const ThermalInstance& instance,
                                const std::string& instance_path) = 0;
};

class MockThermalSurrogate : public ThermalSurrogate {
public:
  explicit MockThermalSurrogate(ThermalConfig config);
  ThermalResult Predict(const ThermalInstance& instance,
                        const std::string& instance_path) override;

private:
  ThermalConfig config_;
};

class PythonDeepOHeatAdapter : public ThermalSurrogate {
public:
  explicit PythonDeepOHeatAdapter(ThermalConfig config);
  ~PythonDeepOHeatAdapter() override;
  ThermalResult Predict(const ThermalInstance& instance,
                        const std::string& instance_path) override;

private:
  ThermalResult PredictWithSubprocess(const std::string& instance_path,
                                      const std::filesystem::path& output_path,
                                      const std::string& script) const;
  ThermalResult PredictWithPersistentService(
      const std::string& instance_path,
      const std::filesystem::path& output_path,
      const std::string& script);
  void StartService(const std::string& script);
  void StopService();
  void WriteServiceLine(const std::string& line);
  std::string ReadServiceLine();
  std::string ResolveInferenceScript() const;
  std::string ShellQuote(const std::string& value) const;
  std::string JsonEscape(const std::string& value) const;
  double ExtractJsonNumber(const std::string& json, const std::string& key) const;
  std::string ExtractJsonString(const std::string& json, const std::string& key) const;

  ThermalConfig config_;
  int service_pid_ = -1;
  int service_stdin_fd_ = -1;
  int service_stdout_fd_ = -1;
  std::string service_script_;
  bool service_disabled_ = false;
};

class ThermalAwareEvaluator {
public:
  ThermalAwareEvaluator(ThermalConfig config,
                        const std::string& io_file,
                        const std::string& netlist_file,
                        const std::string& blocks_file);
  ~ThermalAwareEvaluator();

  bool Enabled() const { return config_.enable_thermal; }

  ThermalEvaluation Evaluate(double base_cost,
                             const std::vector<int>& partition,
                             const std::vector<std::string>& tech_assignment,
                             const std::vector<float>& aspect_ratios,
                             const std::vector<float>& x_locations,
                             const std::vector<float>& y_locations,
                             bool floorplan_success);

  double Objective(double base_cost, const ThermalResult& thermal) const;

private:
  std::string BuildCacheKey(const std::vector<int>& partition,
                            const std::vector<std::string>& tech_assignment,
                            const std::vector<float>& aspect_ratios,
                            const std::vector<float>& x_locations,
                            const std::vector<float>& y_locations) const;
  void EnsureInitialized();
  void LogEvaluation(const ThermalEvaluation& evaluation) const;

  ThermalConfig config_;
  std::string io_file_;
  std::string netlist_file_;
  std::string blocks_file_;
  std::vector<block> blocks_;
  std::vector<int> block_to_graph_vertex_;
  LibraryDicts* library_dicts_ = nullptr;
  ThermalInstanceEncoder encoder_;
  std::unique_ptr<ThermalSurrogate> surrogate_;
  std::unordered_map<std::string, ThermalResult> result_cache_;
  std::mutex mutex_;
  bool initialized_ = false;
  size_t next_candidate_index_ = 0;
};

} // namespace chiplet

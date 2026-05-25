# Codex Handoff

## Project Goal

The project integrates DeepOHeat thermal surrogate capability into ChipletPart
to form a thermal-driven chiplet partitioning flow. ChipletPart should evaluate
candidate partitions and technology assignments using both system cost and
thermal feasibility during search, not only as post-analysis.

The active objective is:

```text
J = C_sys
    + lambda_peak * max(0, T_max - T_budget)^2
    + lambda_avg * T_avg
```

Main outputs remain partition and technology assignment. Floorplan is an
internal object used for thermal encoding, feasibility, debug, and
revalidation.

## Current Task

On 2026-05-25, the user requested a new Hom-Cost/Hom-Therm/Het-Cost/Het-Therm
run using `ChipletPart/test_data/epyc7282`, saved under the requested directory
`/home/yhsun/Chiplet-Partitioning/experiment_v5_ga100` (the `ga100` output
name does not describe its EPYC input). The reproducible entry point is
`experiment_v5_ga100/analysis/commands.sh`, with defaults of seed `42`,
`T_budget=300 K`, `lambda_peak=0.1`, and heterogeneous technologies
`7nm,10nm,45nm`. It intentionally fixes the legacy `2d_power_map` backend for
comparability with prior compatibility reruns, not as `package_thermal`
signoff. Results: Hom-Cost has base `83.387100`, `T_max=306.611938 K`;
Hom-Therm has base `81.450300`, `T_max=305.911407 K`; Het-Cost has base
`75.188100`, `T_max=306.246979 K`; Het-Therm has base `81.334000`,
`T_max=305.584412 K`. Hom-Therm reduces peak temperature and comparable
objective; Het-Therm reduces peak temperature but its comparable objective is
worse than post-evaluated Het-Cost for this seed. Artifacts are in
`experiment_v5_ga100/analysis/summary.csv`, `analysis.md`, and
`figures/epyc7282_partition_temperature_comparison.{png,pdf}`.

On 2026-05-24, the requested five-benchmark v4 rerun exposed a blocker in
cost-only final-candidate thermal post-evaluation after the overlap-validation
change: homogeneous post-eval paired a refined partition with stale
pre-refinement floorplan geometry, and thermal coordinate encoding clamped
negative floorplanner locations before translating the package to the origin.
The code now re-floorplans refined homogeneous candidates whenever thermal
evaluation is enabled and preserves raw coordinates until origin translation.
The real EPYC post-eval smoke now succeeds with a 3-part cost-only winner
(`base=84.825104`, `T_max=307.117035 K`, `T_avg=301.992432 K`). V4 values
must therefore be regenerated and must not be mixed with the earlier
overlapping/stale-geometry results.

On 2026-05-23, a follow-up EPYC homogeneous experiment added
`--fixed-parts <count>` to standard partitioning and ran both Hom-Cost and
Hom-Therm with four active partitions. Hom-Cost scored `79.009962` after
thermal post-evaluation (`base=78.175713`, `T_max=302.888336 K`); Hom-Therm
selected `93.465645` (`base=89.596008`, `T_max=306.220642 K`). The thermal
run did not improve the objective, so it was intentionally not incorporated
into `main.tex` or the primary summary rows. Diagnostic artifacts live at
`/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/fixed4_homogeneous_analysis.md`.

Earlier on 2026-05-23, the user-requested milestone refreshed the EPYC paper
data using the existing commands under
`/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/commands.sh`.
The refreshed four-search result set, two supplemental cost-only thermal
post-evaluations, preserved heterogeneous-thermal final assignment, updated
summary, and updated `/home/yhsun/Chiplet-Partitioning/main.tex` all live
outside this Git repository. This refresh intentionally follows the requested
script and therefore uses the `legacy_2d_power_map` compatibility backend; it
is not evidence that the primary `package_thermal` paper methodology has been
completed or validated.

Most recent user-requested milestone reduced DeepOHeat invocation overhead in
thermal refinement by replacing repeated Python subprocess launches with a
persistent Python service path. The previous milestone pushed thermal objective
evaluation deeper into ChipletPart partition refinement and validated the
change on GA100 under `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100`.

Homogeneous thermal mode now wires `ThermalAwareEvaluator` into the FM/KL
refiners. After fast and standard floorplanner calls, the refiner refreshes the
current objective with DeepOHeat. Each executed FM/KL move is scored with a
fresh fast floorplan and the thermal-aware total objective before the pass
selects its best prefix.

Heterogeneous GA thermal mode intentionally does not run thermal for every
FM/KL move. The GA refiner remains cost-only, then a standard floorplanner is
run after the refinement round for each GA solution and thermal is added to the
solution fitness. This keeps the user's requested standard-floorplan-only
thermal placement for heterogeneous mode.

Default per-candidate cost and thermal objective logging is quiet to keep the
larger thermal runs manageable. Re-enable it with
`CHIPLET_PART_VERBOSE_COST=1` and/or `CHIPLET_PART_VERBOSE_THERMAL=1`.

DeepOHeat real inference now defaults to a persistent worker inside
`PythonDeepOHeatAdapter`: the C++ evaluator starts one Python process per
evaluator, sends JSON-line requests over pipes, and keeps Python imports, model
weights, eval mesh/coords, and CUDA context alive across FM/KL move/swap
evaluations. If the worker cannot start or exits, C++ falls back to the old
per-call subprocess path.

The broader project priority remains the paper-scale `package_thermal` path:
more reliable data, stronger labels, training, experiment automation,
revalidation, and paper-ready figures/tables.

## Confirmed Decisions

- Do not directly rewrite ChipletPart's main output interface.
- In the thermal-aware flow, floorplan is an internal evaluation object.
- `package_thermal` backend is the main research path.
- `legacy_2d_power_map` is compatibility/debug only.
- For GA100 compatibility with the legacy 2D checkpoint, map hierarchical
  block-level power records onto netlist vertices before thermal encoding.
- Use synthetic treemap block packing to preserve chiplet-internal block power
  variation in `power_density_w_per_mm2` when physical block placement is not
  available.
- The current simplified 2D effective reference solver is not a signoff solver.
- Future paper experiments should try to connect HotSpot, 3D-ICE, Celsius, FEM,
  a commercial solver, or use such tools for calibration.
- Preserve the cost-only path.
- When `--enable_thermal` is not set, use the original cost-only flow.
- Keep `--thermal_use_mock` for quick debugging.
- C++ to DeepOHeat now uses a persistent Python worker when possible, with the
  old subprocess call retained as fallback. Future options include batched
  inference, ONNX, or LibTorch.
- The latest user instruction requires updating agent files and making a local
  git commit after each verifiable milestone. Do not push.

## Key Background

### DeepOHeat

DeepOHeat's original idea is an operator-learning framework that maps PDE
configuration to temperature fields. The original `2d_power_map` checkpoint only
fits a 2D top power map and is not suitable as the final package-level thermal
surrogate.

The legacy 2D adapter at `DeepOHeat/scripts/infer_package.py` now supports
`--device auto`, preserves absolute power-map magnitude by default, accepts an
optional config JSON / `--power_scale` / `--normalize_power`, writes a small
`.field.npz` next to each `.thermal_result.json`, and supports `--server` for
JSON-line persistent inference.

The current project adds `DeepOHeat/package_thermal/`. The package-level
surrogate follows:

```text
G_theta(X, y) -> T(y)
```

`X` is the multi-channel package tensor dumped by ChipletPart. `y` is a
normalized coordinate. The branch network encodes the package tensor, the trunk
network encodes the coordinate, and the model predicts the temperature field
from which `T_max` and `T_avg` are extracted. Its inference script also
supports `--server` and caches normalized coordinate tensors by grid shape.

### ChipletPart

Original ChipletPart performs cost-driven chiplet partitioning, technology
assignment, IO reach-aware floorplanning, cost modeling, and GA/candidate
evaluation. Thermal integration belongs in candidate evaluation; it should not
rewrite the optimizer into a floorplan-first interface.

## User Preferences And Limits

- Work incrementally; avoid uncontrolled broad rewrites.
- Provide clear commands that can be copied and re-run.
- Distinguish smoke demo, pilot experiment, and paper-scale experiment.
- Keep the Approach aligned with thermal objective, package-level encoding,
  DeepOHeat-style surrogate learning, and ChipletPart integration.
- Do not push.
- Local commits are expected for small verified milestones.
- If there are uncommitted user changes, do not overwrite or stage them.

## Environment Notes

Network/proxy:

```bash
proxy-on
```

Conda setup options:

```bash
export CONDARC=/etc/conda/.condarc
source /opt/conda/miniforge3/etc/profile.d/conda.sh
```

or:

```bash
module load conda/miniforge3
source /opt/conda/miniforge3/etc/profile.d/conda.sh
```

CUDA module setup if compiler/module is needed:

```bash
source /etc/profile.d/site-modules.sh
module load cuda
```

Current checked GPU state on 2026-04-29: `nvidia-smi` works with driver
`570.124.06`, reports CUDA `12.8`, and shows two `NVIDIA GeForce RTX 4090`
GPUs. The DeepOHeat Python environment reports PyTorch `2.0.0+cu117`,
`torch.cuda.is_available() == True`, `torch.cuda.device_count() == 2`, and both
devices are `NVIDIA GeForce RTX 4090`. Always recheck before long GPU
training/evaluation because earlier sessions saw driver/PyTorch CUDA
unavailable.

## Completed Content

### 2026-05-15: Persistent DeepOHeat Inference Service

- Added a persistent service path to `PythonDeepOHeatAdapter`.
- The C++ adapter starts one long-running Python worker per
  `ThermalAwareEvaluator`, sends JSON-line requests through POSIX pipes, reads
  JSON-line responses, and stops the worker in the adapter destructor.
- The old per-call subprocess command remains as fallback if the persistent
  worker cannot be used.
- `DeepOHeat/scripts/infer_package.py` now has `Legacy2DPowerMapPredictor`,
  which loads DeepOHeat modules, checkpoint, model, eval mesh, and CUDA context
  once and reuses them for multiple requests.
- `DeepOHeat/package_thermal/infer_package.py` now has
  `PackageThermalPredictor`, which keeps the model loaded and caches normalized
  coordinate tensors by `(grid_y, grid_x)`.
- The C++ path ignores `SIGPIPE` so a crashed worker returns an error instead
  of terminating `chipletPart`.
- Validation on 2026-05-15 passed:
  `python3 -m py_compile` for both inference scripts,
  `cmake --build build --target chipletPart thermal_mvp_test -j 4`,
  `ctest -R thermal_mvp_test --output-on-failure`,
  `tests/thermal/test_thermal_pipeline.py`, direct legacy service inference,
  a GA100 C++ service smoke, and a real
  `48_1_14_4_1600_1600` refinement thermal smoke.
- Direct legacy service inference on one archived GA100 instance processed two
  requests in one Python worker; service-reported runtime was about `0.512 s`
  for the first request and `0.013 s` for the second request.
- The real refinement smoke wrote `658` thermal records under
  `/tmp/chipletpart_refinement_persistent_real_smoke` and completed in
  `203.39 s`.

### 2026-05-05: Automatic Thermal Figure Generation

- Added `tools/thermal/plot_deepoheat_npz.py` for non-GUI plotting of
  DeepOHeat field NPZ files.
- `run_chiplet_test.sh --thermal` now runs the plotter automatically after a
  successful ChipletPart run.
- Default figure output is `<thermal-output-dir>/figures`; use
  `--thermal-figure-dir <dir>` to override it.
- Legacy 2D field NPZs produce:
  - `*_power_map.png`
  - `*_sensor.png`
  - `*_temperature_bottom.png`
  - `*_temperature_middle.png`
  - `*_temperature_top.png`
  - `*_temperature_hist.png`
- Package-thermal backend invocation now includes `--dump_field`, so it can
  also leave a field NPZ for plotting. For package-thermal NPZs, the plotter
  reads the matching instance JSON for the power map.
- Validation on 2026-05-05 passed:
  `bash -n run_chiplet_test.sh`,
  `cmake --build build --target chipletPart thermal_mvp_test -j 4`,
  `ctest -R thermal_mvp_test --output-on-failure`,
  `tests/thermal/test_thermal_pipeline.py`, direct NPZ plotting, and a GA100
  `run_chiplet_test.sh` smoke at `/tmp/chipletpart_ga100_auto_figures_smoke`.
- The GA100 auto-figure smoke wrote 2 field NPZ files and 12 PNG figures under
  `/tmp/chipletpart_ga100_auto_figures_smoke/figures`.

### 2026-05-14: Thermal-Aware Refinement And GA100 V2

- Homogeneous thermal mode now evaluates refinement trajectory moves with the
  full thermal objective instead of applying DeepOHeat only to final candidate
  ranking.
- `FMRefiner` owns optional thermal evaluator state and exposes
  `RefreshCurrentObjective()` / `GetObjectiveFromScratch()` helpers so FM and
  KL can share thermal-aware scoring.
- `KLRefiner` refreshes thermal objective after floorplanner calls and rescores
  the selected swap with a fast floorplan plus thermal objective.
- Heterogeneous GA thermal mode applies thermal after a standard floorplanner
  following each GA solution's refinement round. Per-move thermal is not enabled
  inside GA refinement.
- Failed floorplans receive maximum objective before thermal-aware ranking.
- Verbose C++ per-candidate cost and thermal logs are now opt-in through
  `CHIPLET_PART_VERBOSE_COST` and `CHIPLET_PART_VERBOSE_THERMAL`.
- Validation passed:
  `cmake --build build --target chipletPart thermal_mvp_test -j 4`,
  `ctest -R thermal_mvp_test --output-on-failure`,
  `tests/thermal/test_thermal_pipeline.py`, and a mock refinement smoke.
- GA100 V2 experiment output:
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100`.
- V2 summary:
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/summary.csv`.
- V2 commands:
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/commands.sh`.

### 2026-05-05: Synthetic Block-Level Power Rasterization

- `ThermalInstanceEncoder` now stores per-block scaled area, scaled compute
  power, technology, chiplet ID, and synthetic rectangle.
- Block rectangles are generated by deterministic area-proportional treemap
  packing inside each chiplet.
- `Rasterize()` now marks chiplet geometry/material channels at chiplet level,
  adds IO power uniformly over each chiplet, and adds compute power from every
  packed block rectangle. This preserves total power while creating
  chiplet-internal power-density variation.
- Thermal instance JSON records:
  - `block_rasterization_mode: synthetic_block_treemap`
  - `rasterization.mode: synthetic_block_treemap`
  - `rasterization.io_power_mode: chiplet_uniform`
  - `blocks: [...]` with packed block rectangles.
- `thermal_mvp_test` checks block metadata, power conservation, and nonuniform
  power density for the dumped mock instance.
- `tools/thermal/validate_instance.py` validates packed block metadata when
  `block_rasterization_mode` is present.
- Validation on 2026-05-05 passed:
  `cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4`,
  `ctest -R thermal_mvp_test --output-on-failure`,
  `tests/thermal/test_thermal_pipeline.py`, and a GA100 real DeepOHeat smoke at
  `/tmp/chipletpart_ga100_block_raster_smoke`.
- The GA100 smoke wrote 8 instances and 8 thermal results. All instances had
  `179` packed blocks, `partition` length `179`,
  `block_rasterization_mode=synthetic_block_treemap`, nonzero power-map spread,
  max raster power error `2.44427e-12`, and result device `cuda:0`.

### 2026-05-05: GA100 Legacy 2D Thermal Flow

- `run_chiplet_test.sh --thermal` now defaults to:
  - model:
    `../DeepOHeat/DeepOHeat/2d_power_map/log/experiment_1/checkpoints/model_epoch_10000.pth`
  - Python:
    `../DeepOHeat/.conda/deepoheat-py38/bin/python`
  - inference script:
    `../DeepOHeat/scripts/infer_package.py`
  - backend: `legacy_2d_power_map`
  - grid: `20x20`
  - output: `results/thermal/<run_id>/`
- Thermal output layout from the script:
  - `results/thermal/<run_id>/manifest.jsonl`
  - `results/thermal/<run_id>/instances/*.json`
  - `results/thermal/<run_id>/instances/*.thermal_result.json`
  - `results/thermal/<run_id>/instances/*.thermal_result.field.npz`
- GA100 thermal encoding maps 179 block-level power rows onto 45 netlist
  vertices. Exact names map directly; `sm_*` records are distributed across
  `l2_*` vertices; `hbm_1024_phy_*` records are distributed across
  `hbm_1536_ctrl_*` vertices. The per-block area/power/type records remain
  separate when applying technology scaling.
- Validation command:

```bash
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 2 \
  --seed 42 --thermal --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_ga100_run_script_smoke_k2 \
  --thermal-cache
```

Result: passed. It evaluated 5 canonical assignments, wrote 8 thermal result
JSON files, used `cuda:0`, produced `t_max` in the range `303.064-309.173 K`,
and selected best cost `35.589993` with `[7nm, 7nm]`.

### Phase 1: Thermal-Aware ChipletPart MVP

From handoff summary and project docs:

- `ThermalConfig.h`
- `ThermalAwareEvaluator.h/.cpp`
- thermal-aware objective wrapper
- thermal instance encoder
- mock surrogate
- legacy DeepOHeat subprocess adapter
- CLI parameters including:
  - `--enable_thermal`
  - `--thermal_use_mock`
  - `--thermal_model_path`
  - `--thermal_python`
  - `--thermal_inference_script`
  - `--thermal_dump_instances`
  - `--thermal_budget`
  - `--thermal_lambda_peak`
  - `--thermal_grid_x`
  - `--thermal_grid_y`
  - `--thermal_cache`
- C++ smoke test `thermal_mvp_test`

### Phase 2: Package-Level Surrogate Mini Demo

From handoff summary and docs:

- ChipletPart package instance dump
- schema validation
- simplified reference labels
- package-level DeepOHeat-style surrogate training/evaluation
- ChipletPart invocation with `--thermal_backend package_thermal`
- Added or updated:
  - `DeepOHeat/package_thermal/dataset.py`
  - `DeepOHeat/package_thermal/model.py`
  - `DeepOHeat/package_thermal/train.py`
  - `DeepOHeat/package_thermal/evaluate.py`
  - `DeepOHeat/package_thermal/infer_package.py`
  - `DeepOHeat/package_thermal/README.md`
  - `tools/thermal/collect_instances.py`
  - `tools/thermal/validate_instance.py`
  - `tools/thermal/reference_solver.py`
  - `docs/thermal_dataset_format.md`
  - `docs/thermal_package_surrogate_mini_demo.md`

### Phase 3: Pilot Dataset V2, Surrogate V2, Experiment V1

From handoff summary and existing docs:

- Added `DeepOHeat/package_thermal/device.py`.
- `train.py`, `evaluate.py`, and `infer_package.py` support `cpu`, `cuda`,
  `cuda:0`, `cuda:1`, and `auto`.
- ChipletPart adapter added `--thermal_device`.
- Enhanced `tools/thermal/collect_instances.py`.
- Added `tools/thermal/split_manifest.py`.
- Added `tools/thermal/summarize_labels.py`.
- `tools/thermal/reference_solver.py` supports
  `auto|scipy_sparse|jacobi|sor`, tolerance, max iterations, overwrite, and
  skip-existing behavior.
- Added `experiments/thermal_partitioning/run_experiment_v1.py`.
- Added `experiments/thermal_partitioning/revalidate_final_candidates.py`.
- Enhanced `experiments/thermal_partitioning/collect_results.py`.
- Added `experiments/thermal_partitioning/make_figures.py`.
- Added `tools/thermal/plot_instance.py`.
- Added `tools/thermal/plot_prediction.py`.
- Added `docs/thermal_experiment_v1_report.md`.
- Updated thermal integration, dataset, mini-demo, package thermal, and
  experiment README docs.
- Expanded `tests/thermal/test_thermal_pipeline.py`; it now has 11 tests after
  device-policy and Dataset V3 provenance coverage.

### Device Environment Confirmation

Current checked state on 2026-04-29:

- `nvidia-smi` passed.
- NVIDIA driver: `570.124.06`.
- CUDA version reported by `nvidia-smi`: `12.8`.
- Visible GPUs: two `NVIDIA GeForce RTX 4090` devices, indices `0` and `1`.
- DeepOHeat Python: PyTorch `2.0.0+cu117`.
- PyTorch CUDA availability: `True`.
- PyTorch CUDA device count: `2`.
- Short package thermal smoke with `--device cuda:0` passed for training,
  evaluation, and inference. All outputs recorded actual device `cuda:0` and
  GPU name `NVIDIA GeForce RTX 4090`.
- `tests/thermal/test_thermal_pipeline.py` covers the mocked
  CUDA-unavailable policy: explicit CUDA requests fail, while `auto` falls back
  to CPU and records CPU metadata.

### Dataset Collection V3 Provenance

Collection audit result on 2026-04-29:

- `tools/thermal/collect_instances.py` primarily drives
  `thermal_collect_cli`.
- `thermal_collect_cli` creates randomized partitions, randomized technology
  assignments, and shelf-style helper floorplans before calling the same
  `ThermalAwareEvaluator` encoder.
- Therefore the previous dataset collection path is best described as
  synthetic/helper-generated, not a systematic record of real ChipletPart
  search trajectories.
- Real ChipletPart candidate evaluation can already dump thermal instances when
  `--enable_thermal`, `--thermal_dump_instances`, and
  `--thermal_dump_manifest` are used. Dataset V3 now makes that path easier to
  identify by recording candidate provenance.

New metadata/schema behavior:

- Thermal instance JSON and manifest entries now include `run_id`, `benchmark`,
  `seed`, `candidate_index`, `candidate_source`, `search_stage`, grid size,
  `technology_assignment_summary`, cost when available, `thermal_enabled`,
  `floorplan_feasible`, `io_feasible`, `instance_hash`, and
  `generation_time_unix_sec`.
- Instance JSON also contains a nested `provenance` object with the same
  candidate-source metadata for debug inspection.
- Old instances/manifests without these fields remain valid. Python collection
  summaries report missing source/stage as `unknown`.
- `tools/thermal/collect_instances.py` writes `manifest_summary.json` with
  raw/unique counts, duplicate/skipped counts, counts by `candidate_source`,
  counts by `search_stage`, grid-size counts, split counts, and label presence.
- `run_experiment_v1.py` now passes explicit search-candidate provenance into
  ChipletPart dumps.

### Dataset V3 Pilot

Output directory:
`/tmp/chipletpart_thermal_dataset_v3_pilot`.

Collection settings:

- Script: `tools/thermal/collect_search_dataset.py`.
- Benchmark: `test_data/48_1_14_4_1600_1600`.
- Seeds: `1 2 3`.
- Grid: `16x16`.
- Technology nodes: `7nm,14nm`.
- Max partitions: `3`.
- Candidate source: `chipletpart_search`.
- Search stage: `search_candidate`.
- Thermal collection mode: `--enable_thermal --thermal_use_mock
  --thermal_backend mock`, so collection does not depend on a trained
  surrogate.
- Reference labels: current simplified 2D effective reference solver with
  `--method auto --max_iter 1000 --tol 1e-6 --overwrite`. This remains
  pilot-only and is not signoff ground truth.

Output files:

- `raw/48_1_14_4_1600_1600/seed_*/instances/*.json`
- `raw/48_1_14_4_1600_1600/seed_*/manifest_raw.jsonl`
- `manifest_raw.jsonl`
- `labels/*.npz`
- `manifest_labeled.jsonl`
- `manifest_summary.json`
- `label_summary.json`
- `label_summary.md`
- `manifest_split.jsonl`
- `manifest_train.jsonl`, `manifest_val.jsonl`, `manifest_test.jsonl`
- `RUN_SUMMARY.md`

Manifest summary:

- Raw candidate dumps before dedup: `48`.
- Unique records: `30`.
- Skipped duplicates: `18`.
- Invalid instances: `0`.
- Candidate source distribution: `chipletpart_search: 30`.
- Search stage distribution: `search_candidate: 30`.
- Grid distribution: `16x16: 30`.
- Labels exist: `true`.

Label summary:

- Labels: `30`.
- Solver status: `converged: 30`.
- Invalid labels: `0`.
- Non-converged labels: `0`.
- `T_max`: min `317.0389 K`, mean `324.8712 K`, max `342.5247 K`.
- `T_avg`: min `308.3147 K`, mean `315.7380 K`, max `327.6581 K`.
- Total power: min `30.7403`, mean `71.27918`, max `89.163`.

Split summary:

- Train: `21`.
- Val: `4`.
- Test: `5`.

This Dataset V3 pilot is useful for pipeline and small-surrogate debugging, but
it is still single-benchmark and not a final paper-scale dataset.

## Recent Validation

Requested EPYC four-mode rerun validation on 2026-05-25:

```bash
bash /home/yhsun/Chiplet-Partitioning/experiment_v5_ga100/analysis/commands.sh
```

Result: passed. It produced four final solutions with comparable thermal data:
cost-only runs each contain one final post-evaluation; thermal-aware
homogeneous and heterogeneous runs contain `304` and `2557` thermal records,
respectively. The generated report records the soft-budget outcome (`4/4`
selected candidates remain above `300 K`) and runtime overhead (`7.87x`
homogeneous and `10.22x` heterogeneous); log scanning found no inference
failure or fallback.

Final-partition post-evaluation geometry fix validation on 2026-05-24:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
cd build && ctest -R thermal_mvp_test --output-on-failure
./run_chiplet_test.sh epyc7282 --seed 1 \
  --thermal --thermal-budget 300 --thermal-lambda-peak 0 \
  --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_epyc_post_eval_coordinate_fix \
  --thermal-post-eval-only
```

Result: passed. The C++ regression test covers negative-coordinate package
translation without artificial overlap; the EPYC smoke emits one real
DeepOHeat field for its newly re-floorplanned final cost-only candidate.

Persistent DeepOHeat service validation on 2026-05-15:

```bash
python3 -m py_compile \
  DeepOHeat/scripts/infer_package.py \
  DeepOHeat/package_thermal/infer_package.py
```

Result: passed.

```bash
cmake --build build --target chipletPart thermal_mvp_test -j 4
```

Result: passed. The build emitted the pre-existing Eigen `initParallel()`
deprecation warning.

```bash
cd build
ctest -R thermal_mvp_test --output-on-failure
```

Result: passed.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Result: passed, 13 tests.

```bash
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader
```

Result: two NVIDIA GeForce RTX 4090 GPUs visible with driver `570.124.06`.
The DeepOHeat PyTorch environment reported CUDA available and two visible
CUDA devices.

Direct legacy persistent-service smoke on an archived GA100 instance:

- Command shape:
  `python DeepOHeat/scripts/infer_package.py --server --model <2d checkpoint>
  --device auto`, with two JSON-line requests piped on stdin.
- Result: passed.
- Service-reported inference runtime: first request about `0.512 s`, second
  request about `0.013 s`.
- Total elapsed including Python/Torch/model/CUDA startup for two requests:
  `5.33 s`.

GA100 C++ service smoke:

```bash
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 1 \
  --seed 42 --thermal --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_persistent_service_smoke \
  --thermal-cache
```

Result: passed in `8.12 s`.

Real refinement thermal smoke:

```bash
./run_chiplet_test.sh 48_1_14_4_1600_1600 \
  --seed 7 --thermal --thermal-budget 250 --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_refinement_persistent_real_smoke \
  --thermal-cache
```

Result: passed in `203.39 s`. Output contained `658` manifest records,
`658` thermal result JSON files, and `658` field NPZ files.

Dataset V3 pilot validation on 2026-05-04:

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Result: passed, 12 tests in 5.354 seconds.

```bash
test -x build/bin/chipletPart && echo build/bin/chipletPart exists
test -x build/bin/thermal_collect_cli && echo build/bin/thermal_collect_cli exists
```

Result: both binaries exist.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tools/thermal/collect_search_dataset.py \
  --chipletpart_build build \
  --testcase test_data/48_1_14_4_1600_1600 \
  --out_dir /tmp/chipletpart_thermal_dataset_v3_pilot \
  --seeds 1 2 3 \
  --grid_x 16 --grid_y 16 \
  --tech_nodes 7nm,14nm \
  --max_partitions 3 \
  --method auto --max_iter 1000 --tol 1e-6 \
  --num_workers 1 --split_seed 2026
```

Result: passed. It collected raw `48`, unique `30`, skipped duplicates `18`,
invalid instances `0`, valid labels `30/30`, and train/val/test split
`21/4/5`.

Dataset Collection V3 validation on 2026-04-29:

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Result: passed, 11 tests in 4.795 seconds.

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
cd build
ctest -R thermal_mvp_test --output-on-failure
```

Result: build passed and `thermal_mvp_test` passed. The build emitted the
pre-existing Eigen `initParallel()` deprecation warning.

Real search-candidate smoke:

- Output directory: `/tmp/chipletpart_thermal_dataset_v3_smoke/search`
- Command shape: `build/bin/chipletPart ... --tech-enum --max-partitions 2
  --enable_thermal --thermal_use_mock --thermal_dump_instances ...
  --thermal_dump_manifest ... --thermal_candidate_source chipletpart_search
  --thermal_search_stage search_candidate`
- Result: 8 dumped instances and 8 valid JSON files.
- Manifest provenance: `candidate_source=chipletpart_search`,
  `search_stage=search_candidate`, `run_id=v3_search_seed7`, `seed=7`,
  grid `16x16`.
- Reference labels: `tools/thermal/reference_solver.py --method auto
  --max_iter 1000 --tol 1e-6 --overwrite` passed; all 8 labels were valid.
- Labeled summary:
  `/tmp/chipletpart_thermal_dataset_v3_smoke/search/summary_labeled.json`
  reports raw `8`, unique `8`, labels exist `true`, invalid/skipped `0`, and
  count by source/stage/grid as `chipletpart_search` /
  `search_candidate` / `16x16`.

Helper collection smoke:

- Output directory: `/tmp/chipletpart_thermal_dataset_v3_smoke/helper`
- Command shape: `tools/thermal/collect_instances.py --num_instances 5 ...`
- Result:
  `/tmp/chipletpart_thermal_dataset_v3_smoke/helper/manifest_summary.json`
  reports raw `5`, unique `5`, labels exist `false`,
  `candidate_source=synthetic_helper`, `search_stage=synthetic_random_shelf`,
  grid `16x16`, invalid/skipped `0`.

Device verification on 2026-04-29 in
`/home/yhsun/Chiplet-Partitioning/ChipletPart`:

```bash
nvidia-smi
```

Result: passed. Two `NVIDIA GeForce RTX 4090` GPUs were visible.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
print("cuda count:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i))
PY
```

Result: passed with PyTorch `2.0.0+cu117`, CUDA available `True`, count `2`,
and devices `0`/`1` both `NVIDIA GeForce RTX 4090`.

Short `--device cuda:0` package thermal smoke:

- Generated a temporary 8x8 manifest.
- Ran one-epoch `DeepOHeat/package_thermal/train.py`.
- Ran `DeepOHeat/package_thermal/evaluate.py`.
- Ran `DeepOHeat/package_thermal/infer_package.py`.

Result: passed. Train/evaluation/inference all recorded `device: cuda:0`.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Result: passed, 10 tests in 5.924 seconds.

This handoff milestone validated the persistent agent files on 2026-04-29:

```bash
python3 - <<'PY'
from pathlib import Path
required = [
    Path("AGENTS.md"),
    Path("docs/agent/ACTIVE_PLAN.md"),
    Path("docs/agent/HANDOFF.md"),
    Path("docs/agent/DECISIONS.md"),
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing files: " + ", ".join(missing))
for p in required:
    text = p.read_text(encoding="utf-8")
    if len(text.strip()) < 500:
        raise SystemExit(f"{p} looks too short")
print("agent handoff files exist and are non-trivial")
PY
```

Result: passed in `/home/yhsun/Chiplet-Partitioning/ChipletPart`.

Previous Codex-reported commands:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
ctest -R thermal_mvp_test --output-on-failure
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Previous Codex-reported result: build passed, `thermal_mvp_test` passed, and
the Python thermal pipeline tests passed. Treat this as handoff context; rerun
before relying on it after new code changes.

## Important Paths

- ChipletPart repo: `/home/yhsun/Chiplet-Partitioning/ChipletPart`
- DeepOHeat directory: `/home/yhsun/Chiplet-Partitioning/DeepOHeat`
- Package surrogate: `/home/yhsun/Chiplet-Partitioning/DeepOHeat/package_thermal`
- Python env:
  `/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python`
- Main docs:
  - `docs/thermal_integration.md`
  - `docs/thermal_dataset_format.md`
  - `docs/thermal_package_surrogate_mini_demo.md`
  - `docs/thermal_experiment_v1_report.md`
  - `experiments/thermal_partitioning/README.md`

## Important Output Directories

- Dataset V2: `/tmp/chipletpart_thermal_dataset_v2`
- Surrogate V2: `/tmp/deepoheat_package_run_v2`
- Experiment V1: `/tmp/chipletpart_thermal_experiments_v1`
- Dataset V3 smoke: `/tmp/chipletpart_thermal_dataset_v3_smoke`
- Dataset V3 pilot: `/tmp/chipletpart_thermal_dataset_v3_pilot`
- User GA100 validation experiment V1:
  `/home/yhsun/Chiplet-Partitioning/experiment_v1`
  - Summary: `analysis/summary.csv`
  - Narrative: `analysis/analysis.md`
  - Rerun commands: `analysis/commands.sh`

## Recent Experiment Results

From previous Codex-reported result and project docs:

GA100 validation experiment V1, run on 2026-05-06 with `--seed 1` and
`--thermal-budget 250` for thermal-aware cases:

- Homogeneous cost-only: best cost `31.620317`, `5` parts, feasible `Yes`,
  elapsed `81.83 s`.
- Homogeneous thermal: best objective `38.281555`, base cost `32.533447`,
  `T_max=325.816284 K`, thermal penalty `5.748109`, `3` parts, feasible `Yes`,
  elapsed `106.07 s`; wrote `18` NPZ files and `108` PNG figures.
- Heterogeneous cost-only (`--genetic --tech-nodes 7nm,10nm,45nm`): best cost
  `31.843674`, `4` parts, valid `Yes`, technologies all `7nm`, elapsed
  `528.65 s`.
- Heterogeneous thermal: best objective `35.604126`, base cost about
  `31.8581`, `T_max=311.204 K`, thermal penalty about `3.74598`, `4` parts,
  valid `Yes`, technologies all `7nm`, elapsed `2622.14 s`; wrote `468` NPZ
  files and `2808` PNG figures.
- The homogeneous thermal run clearly changes the selected partition count
  from 5 to 3. The heterogeneous thermal run changes ranking more subtly:
  it trades a small base-cost increase for about `1.9 K` lower peak temperature
  versus a near cost-only candidate.
- An earlier heterogeneous thermal attempt selected an invalid initial random
  GA solution. It is archived at
  `/home/yhsun/Chiplet-Partitioning/experiment_v1/heterogeneous_thermal_pre_fix`
  and should not be used for the final comparison.

Dataset V2:

- Raw unique instances: 230
- Labeled instances: 230
- Split: train 161 / val 34 / test 35
- `T_max`: min 317.04 K, mean 358.91 K, max 395.03 K
- `T_avg`: min 317.04 K, mean 347.19 K, max 393.01 K
- Solver: `auto -> scipy_sparse`
- Labels: 230 converged, 0 invalid

Surrogate V2:

- Output: `/tmp/deepoheat_package_run_v2`
- Device: CPU fallback from `auto`
- Epochs: 50
- Runtime: 21.10 s
- Best checkpoint: `/tmp/deepoheat_package_run_v2/checkpoint_best.pt`
- Test field MAE: 8.783 K
- Test field RMSE: 9.741 K
- `T_max` absolute error: 11.235 K
- `T_avg` absolute error: 7.855 K
- Runtime per instance: 0.00607 s

Partitioning Experiment V1:

- Output: `/tmp/chipletpart_thermal_experiments_v1`
- Settings: cost-only, thermal high-budget `T_budget=380 K`, thermal strict
  budget `T_budget=335 K`
- Seeds: 1, 2, 3
- `lambda_peak=1.0`

Summary:

- cost-only: mean cost 46.0968, mean predicted `T_max=341.714 K`, mean
  objective 46.0968
- thermal high-budget: mean cost 46.0968, mean predicted `T_max=341.714 K`,
  mean objective 46.0968
- thermal strict-budget: mean cost 56.7534, mean predicted `T_max=335.660 K`,
  mean objective 57.2265

Revalidation:

- cost-only / high-budget reference `T_max`: 322.692 K
- strict-budget reference `T_max`: 324.540-328.263 K
- surrogate `T_max` error: cost-only / high-budget about +19.022 K; strict
  about +7.670 to +10.985 K

## EPYC Paper-Data Refresh On 2026-05-23

The EPYC V3 output directory was refreshed in place after first removing prior
thermal directories because `ThermalAwareEvaluator` appends to an existing
manifest. Four searches were executed from
`/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/commands.sh`.
Cost-only temperatures in the paper table come from separate runs with
`--thermal-post-eval-only` and `--thermal-lambda-peak 0`; the table runtime is
the search runtime rather than post-evaluation time.

Refreshed EPYC paper rows:

```text
Hom-Cost   base=78.176  T_max=302.888  T_avg=299.859  parts=4  all 7nm          runtime=7.1 s
Hom-Therm  base=83.826  T_max=304.481  T_avg=300.876  parts=3  all 7nm          runtime=124.6 s
Het-Cost   base=75.089  T_max=304.550  T_avg=300.374  parts=5  5x7nm            runtime=105.8 s
Het-Therm  base=74.421  T_max=302.880  T_avg=299.953  parts=5  3x7nm+2x10nm    runtime=798.4 s
```

The heterogeneous thermal log prints only its final objective
(`75.250145`), not the associated thermal fields. The matching dumped record is
`heterogeneous_thermal/thermal/instances/epyc7282_thermal_seed1_20260523_155548_15168f2d9859afcb.thermal_result.json`;
its partition exactly matches
`heterogeneous_thermal/final_partition.parts`. The thermal final assignment
was copied into the experiment directory before the subsequent cost-only
post-evaluation overwrote ChipletPart's fixed genetic output path.

Validation notes:

- Both thermal-search manifest/NPZ counts match: homogeneous `306/306`,
  heterogeneous `2481/2481`.
- Both cost-only post-evaluation manifests contain one matching NPZ field.
- Log scans found no failure or fallback markers.
- A temporary `latexmk` build of the updated top-level `main.tex` stops at the
  pre-existing missing file `picture/thermal_factors.png`.

## EPYC Homogeneous Fixed-4 Follow-Up On 2026-05-23

Standard homogeneous mode now accepts `--fixed-parts <count>` through both
`chipletPart` and `run_chiplet_test.sh`. The option restricts the standard
initial partition count set and rejects a refined candidate if it no longer
has exactly that number of active partitions.

The requested four-chiplet comparison uses `--fixed-parts 4`,
`--thermal-budget 300`, `--thermal-lambda-peak 0.1`, and seed `1`:

```text
Hom-Cost fixed-4 post-eval  objective=79.009962 base=78.175713 T_max=302.888336 T_avg=299.859070 penalty=0.834249
Hom-Therm fixed-4            objective=93.465645 base=89.596008 T_max=306.220642 T_avg=300.552704 penalty=3.869639
```

All 55 Hom-Therm fixed-4 thermal records were inspected. Their minimum
reconstructed objective is `82.158156791`, still above the Hom-Cost
post-evaluated objective. The run therefore failed the paper-adoption
criterion; `main.tex` was not changed for this follow-up. The result suggests
that homogeneous refinement/incumbent retention and floorplan comparability
need investigation before claiming thermal improvement.

Artifacts:

- `/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/commands_fixed4_homogeneous.sh`
- `/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/fixed4_homogeneous_summary.csv`
- `/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/fixed4_homogeneous_analysis.md`

## Experiment V4 Rerun Status On 2026-05-24

The current rerun uses the v3 experiment form and the legacy
`2d_power_map` compatibility backend: Hom/Het cost-only with final thermal
post-evaluation, Hom/Het thermal-aware search, seed `1`, `T_budget=300 K`,
and `lambda_peak=0.1` for the thermal comparison.

Completed output directories with `analysis/summary.csv`, `analysis.md`,
`commands.sh`, and PNG/PDF partition/temperature comparison figures:

- `/home/yhsun/Chiplet-Partitioning/experiment_v4_48_1_14_4_1600_1600`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_48_2_14_4_1600_1600`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_epyc7282`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_mempool_group`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_ga100`

GA100 initially failed at Hom-Cost post-evaluation because its 179 mapped
block-level areas expanded chiplet rectangles relative to the 45-vertex
floorplan. `FMRefiner::GenerateNetlist` now reuses
`BuildThermalBlockToGraphVertexMapping` and accumulates technology-scaled
detailed area for hierarchical floorplans. A real GA100 Hom-Cost post-eval
smoke completed after the fix and reported `base=32.704578`,
`T_max=307.324463 K`, and `T_avg=303.450958 K`; the clean formal GA100 rerun
also completed.

Final thermal-aware minus cost-only `T_max` deltas are:

| Benchmark | Homogeneous delta (K) | Heterogeneous delta (K) |
| --- | ---: | ---: |
| `48_1_14_4_1600_1600` | `+0.127014` | `-2.700043` |
| `48_2_14_4_1600_1600` | `-2.167236` | `-1.022186` |
| `epyc7282` | `-0.145508` | `-1.816315` |
| `mempool_group` | `-1.724731` | `-0.003815` |
| `ga100` | `-0.087463` | `-0.890320` |

All ten cost-only modes have exactly one final post-evaluation thermal-result
field and all formal run logs completed without failure. WS2 Het-Cost reached
`136630256 KB` maximum RSS; its final evaluation successfully used the
existing single-call inference fallback after persistent-service `fork`
allocation failed, and the case analysis documents this operational note.

Results from v4 use corrected final and hierarchical geometry and must not be
treated as geometry-identical repeats of older v3 output.

## Unresolved Issues

1. GPU is currently available in the checked shell/Python environment, but this
   remains environment-sensitive. Recheck before long training or GPU sweeps.
2. Reference solver is too simplified for final conclusions.
3. Dataset V3 pilot is still single-benchmark and small. It is useful for
   debugging training and evaluation, but not representative enough for final
   paper claims.
4. Surrogate error remains large on final candidates and has not yet been
   retested with Dataset V3 training.
5. Persistent inference removes repeated Python/model startup, but legacy
   refinement still writes one compressed field NPZ per evaluated move/swap.
   Metrics-only refinement plus final/top-candidate field dumps would likely
   reduce runtime and disk I/O further.
6. Paper-scale experiments are still missing.
7. Only `cuda:0` received an end-to-end smoke in the latest check. `cuda:1` was
   visible via PyTorch but not separately smoked.
8. Do not casually add `28nm`; previous Codex-reported runs hit unsupported
   technology scaling for `45nm -> 28nm`. The pilot uses `7nm,14nm`.
9. The refreshed EPYC values requested for `main.tex` come from
   `legacy_2d_power_map`, while the documented final research direction is
   `package_thermal`; final paper claims still need a consistent validated
   backend.
10. EPYC Hom-Therm remains dominated by Hom-Cost even after matching its four
    chiplets; investigate homogeneous incumbent retention/refinement before
    replacing the paper's homogeneous comparison.

## Easy-To-Miss Points

- Experiment V1 is a pilot, not a final paper result.
- User GA100 validation experiment V1 under
  `/home/yhsun/Chiplet-Partitioning/experiment_v1` used the legacy
  `2d_power_map` DeepOHeat checkpoint, not the package-level research path.
- `legacy_2d_power_map` is not the final method.
- `package_thermal` uses the full channel tensor, but labels still come from a
  simplified solver.
- In `GeneticTechPartitioner`, invalid random initial candidates must retain
  maximum cost. A pre-fix run showed that otherwise an invalid finite-cost
  initial solution can become the GA best.
- Strict thermal budget increasing cost is expected.
- High-budget and cost-only producing the same result is expected.
- Final-candidate surrogate error around +19 K has been observed and must be
  addressed with revalidation and calibration.
- A server having GPUs does not mean the current Python environment can see
  them.
- Cost-only baseline must remain intact.

## Next Suggested Steps

1. Add a metrics-only thermal refinement mode or top-candidate-only field dump
   policy to avoid writing hundreds of field NPZ files during move/swap
   scoring.
2. Train a small package_thermal surrogate on
   `/tmp/chipletpart_thermal_dataset_v3_pilot/manifest_train.jsonl`,
   validate on `manifest_val.jsonl`, and test on `manifest_test.jsonl`, or
   decide to improve reference labels first based on the pilot label summary.
3. Compare Dataset V3 pilot surrogate metrics against the prior Dataset V2
   surrogate metrics.
4. Improve reference label generation or add a calibrated external solver path.
5. Expand Dataset V3 beyond one benchmark only after the small surrogate/label
   sanity check.
6. Run budget sweeps and lambda ablations with final-candidate revalidation.
7. Recheck GPU state before any long training/evaluation run.

## New Session Checklist

1. Read `AGENTS.md`.
2. Read `docs/agent/ACTIVE_PLAN.md`.
3. Read this file.
4. Read `docs/agent/DECISIONS.md`.
5. Run `git status --short`.
6. Recheck GPU state if doing training/evaluation.
7. Choose the smallest verifiable next task.
8. Update the agent files after the milestone.
9. Run relevant validation.
10. Make a local commit and do not push.

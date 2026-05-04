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

From the handoff summary: the project is moving from a pilot-scale
thermal-aware pipeline to a paper-scale experimental pipeline. The next work is
not more toy integration, but more reliable data, training, experiment
automation, revalidation, and paper-quality figures/tables.

Most recent milestone created a small provenance-aware Dataset V3 pilot from
real ChipletPart search-candidate dumps, labeled it with the simplified
reference solver, summarized it, and split it for surrogate work. The next
milestone should either train a small package_thermal surrogate on this pilot
or decide to improve reference labels first based on the label distribution.

## Confirmed Decisions

- Do not directly rewrite ChipletPart's main output interface.
- In the thermal-aware flow, floorplan is an internal evaluation object.
- `package_thermal` backend is the main research path.
- `legacy_2d_power_map` is compatibility/debug only.
- The current simplified 2D effective reference solver is not a signoff solver.
- Future paper experiments should try to connect HotSpot, 3D-ICE, Celsius, FEM,
  a commercial solver, or use such tools for calibration.
- Preserve the cost-only path.
- When `--enable_thermal` is not set, use the original cost-only flow.
- Keep `--thermal_use_mock` for quick debugging.
- C++ to DeepOHeat currently uses a Python subprocess; future options include a
  persistent server, batch inference, ONNX, or LibTorch.
- The latest user instruction requires updating agent files and making a local
  git commit after each verifiable milestone. Do not push.

## Key Background

### DeepOHeat

DeepOHeat's original idea is an operator-learning framework that maps PDE
configuration to temperature fields. The original `2d_power_map` checkpoint only
fits a 2D top power map and is not suitable as the final package-level thermal
surrogate.

The current project adds `DeepOHeat/package_thermal/`. The package-level
surrogate follows:

```text
G_theta(X, y) -> T(y)
```

`X` is the multi-channel package tensor dumped by ChipletPart. `y` is a
normalized coordinate. The branch network encodes the package tensor, the trunk
network encodes the coordinate, and the model predicts the temperature field
from which `T_max` and `T_avg` are extracted.

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

## Recent Experiment Results

From previous Codex-reported result and project docs:

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

## Unresolved Issues

1. GPU is currently available in the checked shell/Python environment, but this
   remains environment-sensitive. Recheck before long training or GPU sweeps.
2. Reference solver is too simplified for final conclusions.
3. Dataset V3 pilot is still single-benchmark and small. It is useful for
   debugging training and evaluation, but not representative enough for final
   paper claims.
4. Surrogate error remains large on final candidates and has not yet been
   retested with Dataset V3 training.
5. Subprocess inference is usable but not ideal for large sweeps.
6. Paper-scale experiments are still missing.
7. Only `cuda:0` received an end-to-end smoke in the latest check. `cuda:1` was
   visible via PyTorch but not separately smoked.
8. Do not casually add `28nm`; previous Codex-reported runs hit unsupported
   technology scaling for `45nm -> 28nm`. The pilot uses `7nm,14nm`.

## Easy-To-Miss Points

- Experiment V1 is a pilot, not a final paper result.
- `legacy_2d_power_map` is not the final method.
- `package_thermal` uses the full channel tensor, but labels still come from a
  simplified solver.
- Strict thermal budget increasing cost is expected.
- High-budget and cost-only producing the same result is expected.
- Final-candidate surrogate error around +19 K has been observed and must be
  addressed with revalidation and calibration.
- A server having GPUs does not mean the current Python environment can see
  them.
- Cost-only baseline must remain intact.

## Next Suggested Steps

1. Train a small package_thermal surrogate on
   `/tmp/chipletpart_thermal_dataset_v3_pilot/manifest_train.jsonl`,
   validate on `manifest_val.jsonl`, and test on `manifest_test.jsonl`, or
   decide to improve reference labels first based on the pilot label summary.
2. Compare Dataset V3 pilot surrogate metrics against the prior Dataset V2
   surrogate metrics.
3. Improve reference label generation or add a calibrated external solver path.
4. Expand Dataset V3 beyond one benchmark only after the small surrogate/label
   sanity check.
5. Run budget sweeps and lambda ablations with final-candidate revalidation.
6. Recheck GPU state before any long training/evaluation run.

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

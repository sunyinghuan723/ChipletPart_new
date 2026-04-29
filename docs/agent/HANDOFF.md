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

This specific milestone creates persistent agent files so future Codex sessions
can cold-start from repository files instead of the conversation window.

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

Previous Codex-reported GPU state: the server should have `cuda:0` and
`cuda:1`, but in the last recorded shell `nvidia-smi` could not communicate
with the driver and PyTorch reported `torch.cuda.is_available() == False`.
Always recheck before GPU training/evaluation.

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
- Expanded `tests/thermal/test_thermal_pipeline.py` to 9 tests.

## Recent Validation

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

1. GPU is currently unavailable or unconfirmed.
2. Reference solver is too simplified for final conclusions.
3. Training data is not representative enough of full search.
4. Surrogate error remains large on final candidates.
5. Subprocess inference is usable but not ideal for large sweeps.
6. Paper-scale experiments are still missing.
7. Do not casually add `28nm`; previous Codex-reported runs hit unsupported
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

1. Recheck GPU state and update docs with current device availability.
2. Make dataset collection draw more directly from real ChipletPart search
   candidate distributions.
3. Improve reference label generation or add a calibrated external solver path.
4. Train a larger package-level surrogate once labels and device are reliable.
5. Run budget sweeps and lambda ablations with final-candidate revalidation.
6. Generate paper-oriented tables and figures from CSV/JSON outputs.

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

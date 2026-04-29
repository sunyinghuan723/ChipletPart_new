# Thermal Experiment V1 Report

This is a pilot experiment for the paper pipeline, not a paper-scale result.
It verifies reproducible dataset generation, package surrogate training,
thermal-aware ChipletPart invocation, final candidate revalidation, and figure
generation.

## Environment

- `nvidia-smi`: executable present, but cannot communicate with the NVIDIA
  driver in this shell.
- PyTorch: `2.0.0+cu117`
- `torch.cuda.is_available()`: `False`
- Visible CUDA devices: `0`
- Training/evaluation device used: `auto`, which fell back to CPU with a clear
  warning.

## Dataset V2

- Testcase: `48_1_14_4_1600_1600`
- Grid: `32 x 32`
- Raw unique instances: `230`
- Labeled instances: `230`
- Split: train `161`, val `34`, test `35`
- Solver: simplified 2D effective reference solver, `method=auto`
  (`scipy_sparse` here)
- Label status: `230` converged, `0` invalid
- `T_max`: min `317.04 K`, mean `358.91 K`, max `395.03 K`
- `T_avg`: min `317.04 K`, mean `347.19 K`, max `393.01 K`

Dataset commands:

```bash
cd ChipletPart
../DeepOHeat/.conda/deepoheat-py38/bin/python tools/thermal/collect_instances.py \
  --chipletpart_build build \
  --testcase test_data/48_1_14_4_1600_1600 \
  --out_dir /tmp/chipletpart_thermal_dataset_v2/raw \
  --num_instances 200 \
  --seeds 1 2 3 4 5 6 7 8 9 10 \
  --grid_x 32 --grid_y 32 \
  --tech_nodes 7nm,14nm \
  --max_chiplets 2 3 4 5 6

../DeepOHeat/.conda/deepoheat-py38/bin/python tools/thermal/reference_solver.py \
  --manifest /tmp/chipletpart_thermal_dataset_v2/raw/manifest.jsonl \
  --out_dir /tmp/chipletpart_thermal_dataset_v2/labels \
  --manifest_out /tmp/chipletpart_thermal_dataset_v2/manifest_labeled.jsonl \
  --method auto --max_iter 5000 --tol 1e-6 --overwrite
```

The first collection pass produced only `91` unique instances because deduping
removed many repeated candidates. A second `7nm,14nm` collection over more seeds
was merged, yielding `230` unique records. A trial `28nm` tech set was skipped
because the current ChipletPart technology scaling reported unsupported
`45nm -> 28nm`.

## Surrogate V2

Training command:

```bash
cd DeepOHeat
./.conda/deepoheat-py38/bin/python package_thermal/train.py \
  --train_manifest /tmp/chipletpart_thermal_dataset_v2/manifest_train.jsonl \
  --val_manifest /tmp/chipletpart_thermal_dataset_v2/manifest_val.jsonl \
  --test_manifest /tmp/chipletpart_thermal_dataset_v2/manifest_test.jsonl \
  --out_dir /tmp/deepoheat_package_run_v2 \
  --epochs 50 --batch_size 16 \
  --grid_x 32 --grid_y 32 \
  --device auto \
  --branch_dim 96 --trunk_dim 96 --hidden_dim 160 --num_layers 3 \
  --dropout 0.05 --lambda_peak 0.05 --lambda_mean 0.01 \
  --seed 2026 --early_stop_patience 12
```

Training summary:

- Device: CPU fallback from `auto`
- Runtime: `21.10 s`
- Best epoch: `44`
- Best checkpoint: `/tmp/deepoheat_package_run_v2/checkpoint_best.pt`

Test evaluation:

- Instances: `35`
- Field MAE: `8.783 K`
- Field RMSE: `9.741 K`
- T_max absolute error: `11.235 K`
- T_avg absolute error: `7.855 K`
- MAPE: `2.566%`
- Runtime per instance: `0.00607 s` on CPU

## Partitioning Experiment V1

Command:

```bash
cd ChipletPart
../DeepOHeat/.conda/deepoheat-py38/bin/python \
  experiments/thermal_partitioning/run_experiment_v1.py \
  --chipletpart_build build \
  --testcase test_data/48_1_14_4_1600_1600 \
  --thermal_model /tmp/deepoheat_package_run_v2/checkpoint_best.pt \
  --thermal_python ../DeepOHeat/.conda/deepoheat-py38/bin/python \
  --deepoheat_root ../DeepOHeat \
  --out_dir /tmp/chipletpart_thermal_experiments_v1 \
  --seeds 1 2 3 \
  --tech_nodes 7nm,14nm \
  --max_partitions 3 \
  --device auto \
  --lambda_peak 1.0 \
  --high_budget 380 \
  --strict_budget 335
```

Summary:

| setting | seeds | mean cost | mean predicted T_max | mean objective |
| --- | ---: | ---: | ---: | ---: |
| cost_only | 3 | 46.0968 | 341.714 K | 46.0968 |
| thermal_high_budget | 3 | 46.0968 | 341.714 K | 46.0968 |
| thermal_strict_budget | 3 | 56.7534 | 335.660 K | 57.2265 |

The strict-budget run selected cooler, higher-cost candidates once
`lambda_peak=1.0` made the temperature penalty comparable to cost differences.

## Revalidation

Reference revalidation output:

- CSV: `/tmp/chipletpart_thermal_experiments_v1/final_revalidation.csv`
- Labels: `/tmp/chipletpart_thermal_experiments_v1/revalidation_labels`

Summary:

| setting | reference T_max range | surrogate T_max error range |
| --- | ---: | ---: |
| cost_only | 322.692 K | +19.022 K |
| thermal_high_budget | 322.692 K | +19.022 K |
| thermal_strict_budget | 324.540-328.263 K | +7.670 to +10.985 K |

This pilot shows the closed loop works, but the final-candidate surrogate error
is still material. Larger and more representative data, stronger labels, and
calibration are required before drawing paper conclusions.

## Outputs

- Raw experiment records:
  `/tmp/chipletpart_thermal_experiments_v1/results_raw.jsonl`
- Summary CSV:
  `/tmp/chipletpart_thermal_experiments_v1/results_summary.csv`
- Revalidation CSV:
  `/tmp/chipletpart_thermal_experiments_v1/final_revalidation.csv`
- Markdown summary:
  `/tmp/chipletpart_thermal_experiments_v1/experiment_report.md`
- Figures:
  `/tmp/chipletpart_thermal_experiments_v1/figures`

## Current Approximations

- The reference solver is simplified and is not a signoff solver.
- Chiplet-internal power is still uniform over each footprint because the
  current flow lacks block-level placement.
- Dataset collection uses a quick random/shelf-layout helper for scalability;
  final experiments should collect candidates from the real search/floorplanner
  loop.
- ChipletPart uses subprocess inference; batching or a persistent server is
  needed for large sweeps.
- Legacy 2D DeepOHeat remains only a compatibility/debug baseline. The
  `package_thermal` backend is the main research path.

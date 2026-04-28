# Package Thermal Surrogate Mini Demo

This report records the small end-to-end smoke experiment used to validate the
package-level thermal surrogate flow. It is not a paper-scale experiment.

## Environment

- Testcase: `48_1_14_4_1600_1600`
- Dataset size: 20 instances
- Grid: `32 x 32`
- Device: CPU
- DeepOHeat env: `DeepOHeat/.conda/deepoheat-py38`

## Commands

Build:

```bash
cd ChipletPart
cmake --build build --target chipletPart thermal_mvp_test -j 4
cmake --build build --target thermal_collect_cli -j 4
ctest -R thermal_mvp_test --output-on-failure
```

Collect instances:

```bash
python3 tools/thermal/collect_instances.py \
  --chipletpart_build build \
  --testcase test_data/48_1_14_4_1600_1600 \
  --out_dir /tmp/chipletpart_thermal_dataset/raw \
  --num_instances 20 \
  --seeds 1 2 3 \
  --grid_x 32 --grid_y 32 \
  --tech_nodes 7nm,14nm \
  --max_chiplets 6
```

Validate:

```bash
python3 tools/thermal/validate_instance.py \
  /tmp/chipletpart_thermal_dataset/raw/seed_1/*.json \
  /tmp/chipletpart_thermal_dataset/raw/seed_2/*.json \
  /tmp/chipletpart_thermal_dataset/raw/seed_3/*.json
```

Generate labels:

```bash
../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  tools/thermal/reference_solver.py \
  --manifest /tmp/chipletpart_thermal_dataset/raw/manifest.jsonl \
  --out_dir /tmp/chipletpart_thermal_dataset/labels \
  --grid_x 32 --grid_y 32
```

Train:

```bash
../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  ../../DeepOHeat/package_thermal/train.py \
  --manifest /tmp/chipletpart_thermal_dataset/manifest_labeled.jsonl \
  --out_dir /tmp/deepoheat_package_run \
  --epochs 5 \
  --batch_size 2 \
  --grid_x 32 --grid_y 32 \
  --device cpu
```

Evaluate:

```bash
../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  ../../DeepOHeat/package_thermal/evaluate.py \
  --manifest /tmp/chipletpart_thermal_dataset/manifest_labeled.jsonl \
  --checkpoint /tmp/deepoheat_package_run/checkpoint_best.pt \
  --device cpu
```

ChipletPart package backend:

```bash
cd ChipletPart/build
./bin/chipletPart canonical_ga_result.parts.5 \
  ../test_data/48_1_14_4_1600_1600/io_definitions.xml \
  ../test_data/48_1_14_4_1600_1600/layer_definitions.xml \
  ../test_data/48_1_14_4_1600_1600/wafer_process_definitions.xml \
  ../test_data/48_1_14_4_1600_1600/assembly_process_definitions.xml \
  ../test_data/48_1_14_4_1600_1600/test_definitions.xml \
  ../test_data/48_1_14_4_1600_1600/block_level_netlist.xml \
  ../test_data/48_1_14_4_1600_1600/block_definitions.txt \
  0.50 0.25 14nm \
  --enable_thermal \
  --thermal_backend package_thermal \
  --thermal_model_path /tmp/deepoheat_package_run/checkpoint_best.pt \
  --thermal_python /home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  --thermal_inference_script /home/yhsun/Chiplet-Partitioning/DeepOHeat/package_thermal/infer_package.py \
  --thermal_dump_instances /tmp/chipletpart_package_eval \
  --thermal_budget 330 \
  --thermal_lambda_peak 0.001 \
  --thermal_grid_x 32 --thermal_grid_y 32
```

## Results

- Raw instances: 20 JSON files, 20 manifest records.
- Reference solver total runtime: `1.301 s`; average `0.065 s/instance`.
- Training runtime: `0.871 s` for 5 epochs.
- Best validation MSE during training: `144.264750`.
- Evaluation metrics:
  - Field MAE: `9.0876 K`
  - Field RMSE: `9.6798 K`
  - T_max absolute error: `13.2362 K`
  - T_avg absolute error: `8.3190 K`
  - MAPE: `2.9074%`
  - Runtime per instance: `0.00438 s`
- ChipletPart package backend output:
  - cost: `42.2452`
  - predicted `t_max=321.902 K`
  - predicted `t_avg=319.184 K`
  - objective: `42.2452` with `T_budget=330 K`

## Notes

- The reference solver is a simplified deterministic 2D effective solver, not a
  signoff solver.
- Chiplet power is still uniformly rasterized inside each chiplet footprint.
- The package surrogate consumes the full channel tensor listed in
  `docs/thermal_dataset_format.md`.
- The legacy 2D checkpoint remains only as a compatibility/debug backend.
- The next paper-scale step is larger candidate collection, stronger labels,
  hyperparameter sweeps, and reference revalidation of final candidates.

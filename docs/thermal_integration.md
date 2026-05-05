# Thermal-Driven Partitioning MVP

This MVP adds thermal-aware candidate evaluation to ChipletPart without changing
the primary output contract: partition and technology assignment remain the main
results. Floorplans are used internally to encode package geometry and can be
dumped for debug through thermal instance JSON files.

## Objective

When thermal evaluation is enabled, ChipletPart evaluates:

```text
J = C_sys
    + lambda_peak * max(0, T_max - T_budget)^2
    + lambda_avg * T_avg
```

`lambda_avg` defaults to `0`, so mean-temperature pressure is opt-in.
When `--enable_thermal` is absent, the evaluator returns the original cost-only
score and does not instantiate the thermal encoder or surrogate.

## Added Modules

- `src/ThermalConfig.h`: thermal CLI/config state.
- `src/ThermalAwareEvaluator.h/.cpp`: objective wrapper, instance encoder,
  surrogate interface, mock surrogate, Python DeepOHeat adapter, and cache.
- `DeepOHeat/scripts/infer_package.py`: Python adapter from ChipletPart package
  JSON to the existing DeepOHeat 2D power-map DeepONet checkpoint.
- `DeepOHeat/package_thermal/`: package-level surrogate that consumes the full
  multi-channel package tensor and predicts a temperature field.
- `tools/thermal/collect_instances.py`: quick batch thermal instance collection.
- `tools/thermal/reference_solver.py`: simplified deterministic label generator.
- `tools/thermal/split_manifest.py`: reproducible train/val/test split tool.
- `tools/thermal/summarize_labels.py`: label distribution and convergence report.
- `tools/thermal/plot_instance.py` and `plot_prediction.py`: non-GUI debug plots.
- `tools/thermal/validate_instance.py`: schema checker for dumped instances.
- `experiments/thermal_partitioning/`: pilot and paper-scale experiment scripts.
- `src/test/test_thermal_mvp.cpp`: smoke test for disabled regression, mock
  objective, instance dump, cache, and failure behavior.

## Instance Encoding

The encoder creates a fixed package-aligned grid with JSON metadata:

- Geometry: `package_domain`, `chiplet_footprint`, `chiplet_boundary`.
- Power: `power_density_w_per_mm2`.
- Material: `silicon_material`, `interposer_material`, `tim_material`,
  `package_material`.
- Boundary conditions: `ambient_temperature`, `heat_transfer_coefficient`.
- Metadata: units, package size, chiplet boxes, per-chiplet compute/IO/total
  power, and raster power conservation.

Power is computed per chiplet as:

```text
P_c = sum scaled block compute power + sum incident partition IO power
```

The block compute power uses ChipletPart's existing technology scaling helpers.
The IO term mirrors the cost model's IO definitions, bandwidth utilization, and
energy-per-bit fields.

For GA100, the netlist partition operates on 45 vertices while
`block_definitions.txt` contains 179 block-level power records. Thermal
encoding maps those power records onto the netlist vertices first, then expands
the candidate partition back to all power records before rasterization. Exact
names map directly; `sm_*` records map across `l2_*` vertices; and
`hbm_1024_phy_*` records map across `hbm_1536_ctrl_*` vertices.

## Current Approximations

- Chiplet-internal block placement is not available in the partitioning flow, so
  each chiplet's power is uniformly rasterized over its footprint.
- `power_density_w_per_mm2` uses the cost-model power unit divided by mm^2. The
  JSON records this explicitly because the original cost model does not expose a
  separate SI power unit contract.
- The DeepOHeat legacy adapter currently consumes only the 2D top
  power-density map, preserves its absolute magnitude by default, and resamples
  it to the 21x21 branch sensor used by the pretrained `2d_power_map`
  checkpoint. Optional config/CLI flags can scale or normalize the power map
  for compatibility experiments. Geometry/material/boundary channels are
  preserved in the JSON for future retraining but are not yet consumed by that
  checkpoint.
- The `package_thermal` backend consumes the full channel tensor and is the
  intended research path. It is currently trained from the simplified reference
  solver labels described in `docs/thermal_dataset_format.md`.
- `legacy_2d_power_map` remains available only as a compatibility/debug
  baseline. It is not the final paper path.
- The C++ DeepOHeat integration uses a subprocess. The interface is isolated so
  it can be replaced later with a persistent server, ONNX, LibTorch, or batched
  inference.

## Build

From `ChipletPart`:

```bash
cmake -S . -B build
cmake --build build --target chipletPart -j 4
cmake --build build --target thermal_mvp_test -j 4
```

## Run Tests

```bash
cd ChipletPart/build
ctest -R thermal_mvp_test --output-on-failure
```

The test covers:

- Thermal disabled regression: objective equals base cost.
- Mock thermal integration: objective equals the centralized penalty formula.
- Thermal instance dump: required channels and raster power conservation.
- Cache: repeated evaluation returns a cache hit.
- Failure behavior: non-mock inference without a model path throws a clear error.

## Cost-Only Baseline

Example evaluation of a saved partition. Replace `canonical_ga_result.parts.5`
with any partition file produced by a previous ChipletPart run:

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
  0.50 0.25 14nm --seed 42
```

## Thermal Mock Mode

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
  0.50 0.25 14nm --seed 42 \
  --enable_thermal --thermal_use_mock \
  --thermal_budget 250 --thermal_lambda_peak 0.001 \
  --thermal_grid_x 8 --thermal_grid_y 8 \
  --thermal_dump_instances /tmp/chipletpart_cli_thermal \
  --thermal_cache
```

Thermal logs are grep-friendly and start with `[THERMAL]`.

## DeepOHeat Adapter Mode

The legacy compatibility backend uses the original 2D power-map checkpoint:

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
  --thermal_model_path ../../DeepOHeat/DeepOHeat/2d_power_map/log/experiment_1/checkpoints/model_epoch_10000.pth \
  --thermal_python ../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  --thermal_inference_script ../../DeepOHeat/scripts/infer_package.py \
  --thermal_dump_instances /tmp/chipletpart_cli_real \
  --thermal_budget 310 --thermal_lambda_peak 0.001 \
  --thermal_grid_x 8 --thermal_grid_y 8
```

`--thermal_dump_instances` is required for non-mock inference because the C++
adapter passes the dumped JSON path to Python.

The `run_chiplet_test.sh` helper now wires the GA100-compatible legacy 2D
checkpoint automatically:

```bash
cd ChipletPart
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 2 \
  --thermal --thermal-device auto --thermal-cache
```

By default this writes thermal JSON, per-candidate inference result JSON, and
field `.npz` files under `results/thermal/<run_id>/`.

## Package Thermal Backend

Collect a small dataset:

```bash
cd ChipletPart
python3 tools/thermal/collect_instances.py \
  --chipletpart_build build \
  --testcase test_data/48_1_14_4_1600_1600 \
  --out_dir /tmp/chipletpart_thermal_dataset/raw \
  --num_instances 20 \
  --seeds 1 2 3 \
  --grid_x 32 --grid_y 32
```

Generate labels:

```bash
../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  tools/thermal/reference_solver.py \
  --manifest /tmp/chipletpart_thermal_dataset/raw/manifest.jsonl \
  --out_dir /tmp/chipletpart_thermal_dataset/labels
```

Train and evaluate:

```bash
cd ChipletPart/build
../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  ../../DeepOHeat/package_thermal/train.py \
  --manifest /tmp/chipletpart_thermal_dataset/manifest_labeled.jsonl \
  --out_dir /tmp/deepoheat_package_run \
  --epochs 5 --batch_size 2 \
  --grid_x 32 --grid_y 32 \
  --device auto

../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  ../../DeepOHeat/package_thermal/evaluate.py \
  --manifest /tmp/chipletpart_thermal_dataset/manifest_labeled.jsonl \
  --checkpoint /tmp/deepoheat_package_run/checkpoint_best.pt \
  --device auto
```

Run ChipletPart with the package surrogate:

```bash
./bin/chipletPart <partition_file> \
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
  --thermal_python ../../DeepOHeat/.conda/deepoheat-py38/bin/python \
  --thermal_inference_script ../../DeepOHeat/package_thermal/infer_package.py \
  --thermal_dump_instances /tmp/chipletpart_package_eval \
  --thermal_budget 330 --thermal_lambda_peak 0.001 \
  --thermal_device auto
```

`--thermal_use_mock` remains supported and takes precedence as a compatibility
shortcut; otherwise `--thermal_backend` selects `legacy_2d_power_map` or
`package_thermal`.

## Device Selection

Package-level train/evaluate/inference scripts accept:

- `--device cpu`
- `--device cuda`
- `--device cuda:0`
- `--device cuda:1`
- `--device auto`

`auto` chooses `cuda:0` when PyTorch can initialize CUDA, otherwise CPU with a
clear warning. Explicit CUDA requests fail clearly if the requested device is
not visible; they do not silently fall back.

ChipletPart passes this through with `--thermal_device`, for example:

```bash
--thermal_backend package_thermal \
--thermal_device cuda:0
```

On the current server, `nvidia-smi` cannot communicate with the NVIDIA driver
and PyTorch reports `torch.cuda.is_available() == False`, so experiment V1 used
CPU fallback even though the code paths support GPUs.

## Environment Observed On This Server

- CMake: `3.26.5`
- C++ compiler: GCC `13.3.1`
- System Python: `3.12.12`
- DeepOHeat env Python: `3.8.16`
- PyTorch: `2.0.0+cu117`
- NumPy: `1.24.3`
- CUDA available to PyTorch: `False` in this shell because the NVIDIA driver is
  not reachable.
- `nvcc` and bare `conda` were not on `PATH`; the existing DeepOHeat env Python
  was used directly.

## TODO

- Train or fine-tune a DeepOHeat package-level surrogate on larger and stronger
  reference labels.
- Replace subprocess inference with batched or persistent inference for large
  GA/BO runs.
- Plumb exact IO power directly from the cost-model result if that becomes a
  public API, rather than mirroring the signal-power calculation.
- Add optional dump of the final/best candidate's thermal field once the
  surrogate returns a spatial temperature field.
- Improve the training data collection helper so it samples real
  IO-feasible/search candidates rather than the current quick shelf floorplan
  generator.

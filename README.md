# Thermal-ChipletPart

Thermal-ChipletPart extends the cost-driven [ChipletPart](https://github.com/ABKGroup/ChipletPart)
flow with thermal feedback for early 2.5D chiplet partitioning. For every
floorplanned candidate, it can encode package geometry, technology-scaled block
power, cut-induced I/O power, material fields, and boundary conditions on a
fixed grid. A DeepOHeat-based surrogate predicts peak and average temperature,
which are combined with system cost as

```text
J = C_sys
    + lambda_peak * max(0, T_max - T_budget)^2
    + lambda_avg * T_avg.
```

Thermal evaluation is optional. With no thermal flags, the original cost-only
objective is preserved. The project overview is maintained in the
[Thermal-ChipletPart umbrella repository](https://github.com/sunyinghuan723/Thermal-ChipletPart).

## Relationship to DeepOHeat

This repository contains the C++ partitioner, cost model, floorplanner, thermal
instance encoder, experiment drivers, and validation tools. The companion
[DeepOHeat repository](https://github.com/sunyinghuan723/DeepOHeat_new) contains
the Python inference adapters, original 2D checkpoint flow, and the
package-level neural surrogate. Real thermal inference therefore expects the
two repositories to be sibling directories:

```text
workspace/
├── ChipletPart/
└── DeepOHeat/
```

The two repositories intentionally have separate environments. The
`environment.yml` here builds Thermal-ChipletPart and runs its NumPy/SciPy and
plotting utilities. PyTorch and model-specific dependencies belong to the
DeepOHeat environment; pass its Python executable with `--thermal-python`.

## Clone and environment

Clone this repository with its METIS and GKlib submodules, then clone DeepOHeat
beside it if real inference is needed:

```bash
git clone --recurse-submodules \
  https://github.com/sunyinghuan723/ChipletPart_new.git ChipletPart
git clone https://github.com/sunyinghuan723/DeepOHeat_new.git DeepOHeat
```

For an existing clone whose submodules are empty:

```bash
git submodule update --init --recursive
```

Create the portable core environment:

```bash
cd ChipletPart
conda env create -f environment.yml
conda activate thermal-chipletpart
```

The direct native dependencies are CMake 3.14+, a C/C++17 compiler, Boost
1.71+, Eigen3, and optional OpenMP. Pugixml is vendored in `src/`; METIS and
GKlib are pinned by gitlink. Python utilities directly use NumPy, SciPy, and
Matplotlib. Follow the companion DeepOHeat README to create its inference
environment and obtain or train the appropriate checkpoint.

## Build and test

From the repository root:

```bash
cmake -S . -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$CONDA_PREFIX"
cmake --build build -j 4
ctest --test-dir build --output-on-failure
```

The main executable is `build/bin/chipletPart`. CTest covers the thermal
objective/encoding smoke path and floorplan-state retention. OpenMP is used
when found and is otherwise disabled by CMake.

## Inputs

Each testcase directory under `test_data/<case>/` must contain these seven
files:

| File | Purpose |
| --- | --- |
| `io_definitions.xml` | I/O types, reach, bandwidth, and energy parameters |
| `layer_definitions.xml` | Fabrication layer definitions |
| `wafer_process_definitions.xml` | Wafer process and yield/cost parameters |
| `assembly_process_definitions.xml` | Package assembly parameters |
| `test_definitions.xml` | Test process parameters |
| `block_level_netlist.xml` | Block connectivity and communication demand |
| `block_definitions.txt` | Block name, area, power, and source technology |

Bundled examples include wafer-scale, MemPool, EPYC, and GA100-derived cases.
To normalize a case from `cost_model/test_cases` into `test_data`, run:

```bash
./setup_test_cases.sh 48_1_14_4_1600_1600
```

An alternate source may be a parent of the named case or the case directory
itself:

```bash
./setup_test_cases.sh <case> /path/to/source-root-or-case
```

## Common runs

`run_chiplet_test.sh` validates the testcase, constructs the executable CLI,
and stores thermal artifacts under `results/thermal/`. Run it from any working
directory; all repository paths are resolved relative to the script.

### Cost-only partitioning

Thermal evaluation is disabled unless a thermal option is supplied:

```bash
./run_chiplet_test.sh ga100 --seed 42
```

Useful search modes include:

```bash
# Homogeneous search at one technology node
./run_chiplet_test.sh ga100 --tech 7nm --fixed-parts 4 --seed 42

# Heterogeneous genetic search
./run_chiplet_test.sh ga100 --genetic \
  --tech-nodes 7nm,10nm,45nm --generations 50 --population 50 --seed 42

# Canonical technology assignment or exhaustive canonical enumeration
./run_chiplet_test.sh ga100 --canonical-ga --tech-nodes 7nm,10nm,45nm
./run_chiplet_test.sh ga100 --tech-enum \
  --tech-nodes 7nm,10nm,45nm --max-partitions 4
```

Evaluate an existing partition without searching:

```bash
./run_chiplet_test.sh ga100 \
  --evaluate-partition /path/to/partition.parts --tech 7nm --seed 42
```

### Deterministic thermal mock

Mock mode exercises instance encoding, penalties, manifests, and caching
without Python, a checkpoint, or a GPU:

```bash
./run_chiplet_test.sh ga100 --tech-enum \
  --tech-nodes 7nm,10nm,45nm --max-partitions 4 --seed 42 \
  --thermal-mock --thermal-budget 300 --thermal-lambda-peak 0.01 \
  --thermal-grid 21 --thermal-cache \
  --thermal-output-dir results/mock-ga100
```

### Original DeepOHeat 2D model (legacy real-model mode)

The legacy backend adapts the package power-density map to the original
DeepOHeat `2d_power_map` checkpoint. It is a compatibility/debug baseline, not
the package model used for the reported research path.

```bash
./run_chiplet_test.sh ga100 --tech-enum \
  --tech-nodes 7nm,10nm,45nm --max-partitions 4 --seed 42 \
  --thermal --thermal-backend legacy_2d_power_map \
  --thermal-model ../DeepOHeat/DeepOHeat/2d_power_map/log/experiment_1/checkpoints/model_epoch_10000.pth \
  --thermal-python /path/to/deepoheat-py38/bin/python \
  --thermal-script ../DeepOHeat/scripts/infer_package.py \
  --thermal-budget 300 --thermal-lambda-peak 0.01 --thermal-grid 21 \
  --thermal-cache --thermal-output-dir results/legacy-ga100
```

If the conventional sibling-local Python path does not exist,
`run_chiplet_test.sh` falls back to the `python3` found on `PATH`. Real-model
runs still require that interpreter to contain the DeepOHeat dependencies.

### Package-level DeepOHeat surrogate

The `package_thermal` backend consumes the complete multi-channel package
tensor. Train a package checkpoint using `DeepOHeat/package_thermal/train.py`
(see the companion `package_thermal/README.md`), then run:

```bash
./run_chiplet_test.sh ga100 --genetic \
  --tech-nodes 7nm,10nm,45nm --generations 50 --population 50 --seed 42 \
  --thermal --thermal-backend package_thermal \
  --thermal-model /absolute/path/to/checkpoint_best.pt \
  --thermal-python /path/to/deepoheat-py38/bin/python \
  --thermal-script ../DeepOHeat/package_thermal/infer_package.py \
  --thermal-budget 300 --thermal-lambda-peak 0.01 --thermal-grid 21 \
  --thermal-cache --thermal-output-dir results/package-ga100
```

Add `--thermal-plot-figures` to render generated `.npz` fields. Add
`--thermal-post-eval-only` to keep the search cost-only and invoke the thermal
model only for the final best candidate. `--thermal-allow-fallback` changes an
inference failure into a cost-only evaluation; omit it when failures must stop
the experiment.

## Outputs

Outputs depend on the selected algorithm:

- Homogeneous search writes `<netlist>.cpart.<N>` next to the input netlist and
  writes `best_partition.aspect_ratios`, `best_partition.coords`, and
  `output.map` in the process working directory.
- Genetic and canonical searches write partition, technology, and summary
  files such as `*.parts.<N>`, `*.techs.<N>`, and `*.summary.txt`.
- Technology enumeration writes `<netlist>.best_partition.txt` and reports the
  best technology assignment on stdout.
- Thermal runs write instance JSON, a JSONL manifest, inference-result JSON,
  optional temperature-field NPZ, and optional figures below the selected
  thermal output directory.

Generated files, local environments, build trees, logs, and model checkpoints
are ignored by Git. Keep any result needed for a paper in an explicitly curated
artifact location rather than force-adding an entire `results/` tree.

## Paper configuration versus defaults

The accompanying Thermal-ChipletPart manuscript describes the reported
experiments. Those values are research settings and are deliberately not
silently imposed by the convenience CLI:

| Setting | Reported paper configuration | `run_chiplet_test.sh` default | Direct C++ default |
| --- | --- | --- | --- |
| Thermal backend | Package-level DeepOHeat surrogate | `legacy_2d_power_map` | `legacy_2d_power_map` |
| Grid | `21 x 21` | `20 x 20` | `32 x 32` |
| Peak budget | `300 K` | `330 K` | `358.15 K` |
| `lambda_peak` | `0.01` | `0.001` | `0` |
| `lambda_avg` | `0` | `0` | `0` |
| Homogeneous technology | `7nm` | `7nm` | positional argument |
| Heterogeneous technologies | `7nm,10nm,45nm` | mode-dependent; pass explicitly | pass explicitly |
| Genetic search | 50 generations, population 50 | 50, 50 | 50, 50 |
| Randomness | ten seeds per configuration; report best | seed 42 | seed 42 |

For paper-aligned runs, always pass backend, checkpoint, grid, budget, penalty
weights, technology set, population/generations, and each seed explicitly, as
shown in the package-level example. Cost-only final candidates in the paper are
post-evaluated with DeepOHeat for a like-for-like temperature comparison.

## Research limitations

- This is an early-design research flow, not a thermal signoff tool.
- Detailed within-chiplet placement is unavailable during partitioning; the
  encoder uses deterministic area-proportional treemap rasterization as a
  spatial prior.
- The bundled reference solver is a simplified deterministic 2D effective
  solver. A package surrogate trained only on those labels inherits that
  approximation and should be revalidated against higher-fidelity data.
- The legacy backend consumes only a resampled top power-density map; geometry,
  material, and boundary channels require the package backend.
- Python inference is invoked out of process. Caching and the persistent
  package service reduce overhead, but thermal-aware searches remain slower
  than cost-only searches.
- The paper discusses a 3DBlox interface; the currently documented public CLI
  consumes the seven XML/TXT inputs above and does not package a standalone
  3DBlox converter.
- Checkpoints, large generated datasets, and paper result archives are not
  embedded in this repository.

More detailed format and experiment notes are in `docs/thermal_integration.md`,
`docs/thermal_dataset_format.md`, and `experiments/thermal_partitioning/README.md`.

## Citation

A final bibliographic record for the Thermal-ChipletPart manuscript is not yet
provided in this repository. When using this code, cite that manuscript once
available and cite the two foundations of the implementation:

```bibtex
@article{graening2026chipletpart,
  title   = {ChipletPart: Cost-Aware Partitioning for 2.5D Systems},
  author  = {Graening, A. and Gupta, P. and Kahng, A. B. and
             Pramanik, B. and Wang, Z.},
  journal = {ACM Transactions on Design Automation of Electronic Systems},
  volume  = {31},
  number  = {5},
  pages   = {88:1--88:29},
  year    = {2026}
}

@inproceedings{liu2023deepoheat,
  title     = {DeepOHeat: Operator Learning-Based Ultra-Fast Thermal
               Simulation in 3D-IC Design},
  author    = {Liu, Ziyue and Li, Yixing and Hu, Jing and Yu, Xinling and
               Shiau, Shinyu and Ai, Xin and Zeng, Zhiyu and Zhang, Zheng},
  booktitle = {Proceedings of the 60th ACM/IEEE Design Automation Conference},
  pages     = {1--6},
  year      = {2023}
}
```

## License

The repository's current licensing terms are in `LICENSE`. That file is
labeled BSD 3-Clause but also contains additional review-purpose wording, so
confirm redistribution terms with the upstream copyright holders rather than
assuming it is an unmodified standard BSD-3-Clause grant. Third-party and
submodule license information is summarized in `THIRD_PARTY_NOTICES.md`;
upstream license files remain authoritative. DeepOHeat is a separate project
with its own license.

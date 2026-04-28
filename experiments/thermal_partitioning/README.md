# Thermal Partitioning Experiments

Skeleton scripts for paper-scale experiments. They are intentionally lightweight
and are not run as part of the mini demo.

Planned studies:

- Cost-only ChipletPart vs thermal-aware ChipletPart.
- Thermal budget sweeps for cost / T_max / T_avg tradeoff.
- `lambda_peak` and `lambda_avg` ablations.
- Surrogate inference overhead.
- Surrogate prediction accuracy against reference labels.
- Final candidate revalidation with the reference solver.
- Visualizations of power map, temperature map, and chiplet layout.

Set these environment variables before running:

```bash
export CHIPLET_BUILD=/path/to/ChipletPart/build
export TESTCASE=/path/to/ChipletPart/test_data/48_1_14_4_1600_1600
export PARTITION_FILE=/path/to/partition.parts
export THERMAL_MODEL=/tmp/deepoheat_package_run/checkpoint_best.pt
export THERMAL_PYTHON=/path/to/DeepOHeat/.conda/deepoheat-py38/bin/python
export DEEPOHEAT_ROOT=/path/to/DeepOHeat
```

These scripts are command skeletons. Review output directories and budgets
before launching large sweeps.

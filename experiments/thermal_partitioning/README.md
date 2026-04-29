# Thermal Partitioning Experiments

Pilot and paper-scale experiment scripts for thermal-driven partitioning. The
scripts are intentionally parameterized so the same structure can scale from
quick smoke runs to larger sweeps.

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
export THERMAL_DEVICE=auto
```

V1 pilot command:

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

Then:

```bash
python experiments/thermal_partitioning/revalidate_final_candidates.py \
  --results_raw /tmp/chipletpart_thermal_experiments_v1/results_raw.jsonl \
  --out_csv /tmp/chipletpart_thermal_experiments_v1/final_revalidation.csv \
  --label_dir /tmp/chipletpart_thermal_experiments_v1/revalidation_labels

python experiments/thermal_partitioning/collect_results.py \
  --raw_jsonl /tmp/chipletpart_thermal_experiments_v1/results_raw.jsonl \
  --out_csv /tmp/chipletpart_thermal_experiments_v1/results_summary.csv \
  --out_report /tmp/chipletpart_thermal_experiments_v1/experiment_report.md

python experiments/thermal_partitioning/make_figures.py \
  --results_raw /tmp/chipletpart_thermal_experiments_v1/results_raw.jsonl \
  --revalidation_csv /tmp/chipletpart_thermal_experiments_v1/final_revalidation.csv \
  --out_dir /tmp/chipletpart_thermal_experiments_v1/figures
```

The V1 pilot is not a paper-scale result. It verifies reproducible CSV/JSON/MD
outputs, final candidate revalidation, and visualization generation.

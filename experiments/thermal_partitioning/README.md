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

## Dataset V3 Search-Candidate Smoke

Use this before scaling dataset collection. It exercises the real ChipletPart
candidate-evaluation dump path with mock thermal inference, records provenance
metadata, and keeps the run small.

```bash
cd ChipletPart
rm -rf /tmp/chipletpart_thermal_dataset_v3_smoke
mkdir -p /tmp/chipletpart_thermal_dataset_v3_smoke/search

build/bin/chipletPart \
  test_data/48_1_14_4_1600_1600/io_definitions.xml \
  test_data/48_1_14_4_1600_1600/layer_definitions.xml \
  test_data/48_1_14_4_1600_1600/wafer_process_definitions.xml \
  test_data/48_1_14_4_1600_1600/assembly_process_definitions.xml \
  test_data/48_1_14_4_1600_1600/test_definitions.xml \
  test_data/48_1_14_4_1600_1600/block_level_netlist.xml \
  test_data/48_1_14_4_1600_1600/block_definitions.txt \
  0.5 0.25 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 2 --seed 7 \
  --enable_thermal --thermal_use_mock --thermal_backend mock \
  --thermal_budget 1000000000 --thermal_lambda_peak 0 \
  --thermal_grid_x 16 --thermal_grid_y 16 \
  --thermal_dump_instances /tmp/chipletpart_thermal_dataset_v3_smoke/search/instances \
  --thermal_dump_manifest /tmp/chipletpart_thermal_dataset_v3_smoke/search/manifest.jsonl \
  --thermal_dump_prefix v3_search_seed7 \
  --thermal_dump_split v3_smoke \
  --thermal_source_testcase 48_1_14_4_1600_1600 \
  --thermal_run_id v3_search_seed7 \
  --thermal_candidate_source chipletpart_search \
  --thermal_search_stage search_candidate \
  --thermal_seed 7 \
  --thermal_cache

python3 tools/thermal/validate_instance.py \
  /tmp/chipletpart_thermal_dataset_v3_smoke/search/instances/*.json

../DeepOHeat/.conda/deepoheat-py38/bin/python tools/thermal/reference_solver.py \
  --manifest /tmp/chipletpart_thermal_dataset_v3_smoke/search/manifest.jsonl \
  --out_dir /tmp/chipletpart_thermal_dataset_v3_smoke/search/labels \
  --manifest_out /tmp/chipletpart_thermal_dataset_v3_smoke/search/manifest_labeled.jsonl \
  --method auto --max_iter 1000 --tol 1e-6 --overwrite
```

Expected smoke scale: about 5-30 dumped instances. A successful run should show
manifest counts by `candidate_source`, `search_stage`, grid size, and label
presence in the generated summary.

## Dataset V3 Pilot

Use the Dataset V3 pilot before training or comparing package surrogates. It
collects real ChipletPart search-candidate thermal dumps with mock thermal
inference, labels them with the simplified reference solver, writes summaries,
and creates train/val/test manifests.

```bash
cd ChipletPart
rm -rf /tmp/chipletpart_thermal_dataset_v3_pilot

../DeepOHeat/.conda/deepoheat-py38/bin/python \
  tools/thermal/collect_search_dataset.py \
  --chipletpart_build build \
  --testcase test_data/48_1_14_4_1600_1600 \
  --out_dir /tmp/chipletpart_thermal_dataset_v3_pilot \
  --seeds 1 2 3 \
  --grid_x 16 --grid_y 16 \
  --tech_nodes 7nm,14nm \
  --max_partitions 3 \
  --method auto --max_iter 1000 --tol 1e-6 \
  --split_seed 2026
```

The pilot is intentionally small and is not a paper-scale dataset. Check
`manifest_summary.json`, `label_summary.json`, and `manifest_train/val/test`
before deciding whether to train a small surrogate or improve reference labels
first.

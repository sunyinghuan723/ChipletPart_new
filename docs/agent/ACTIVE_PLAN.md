# Active Plan

## Current Phase

Paper-scale experimental pipeline preparation.

## Phase Goal

Move beyond the pilot-scale thermal-aware pipeline toward reproducible,
scalable experiments that can produce paper tables, figures, CSV/JSON records,
and revalidation reports. The work should remain incremental: each milestone
must be small, verifiable, documented, and locally committed.

## Startup Protocol For Each Task

1. Read `AGENTS.md`.
2. Read `docs/agent/ACTIVE_PLAN.md`.
3. Read `docs/agent/HANDOFF.md`.
4. Read `docs/agent/DECISIONS.md`.
5. Run `git status --short` in the repo being edited.
6. Select the smallest verifiable next task from this plan.

During work, update this file after each small milestone. Update
`DECISIONS.md` for architecture decisions and `HANDOFF.md` for new important
commands, paths, results, or risks. Do not leave project memory only in chat.

## Current Priorities

1. Confirm GPU/device environment.
2. Make dataset collection closer to real ChipletPart search candidate
   distribution.
3. Improve or replace reference labels.
4. Scale dataset size beyond the pilot run.
5. Train a more reliable package-level surrogate.
6. Run cost-only vs thermal-aware multi-seed comparisons.
7. Run thermal budget sweeps.
8. Run `lambda_peak` / `lambda_avg` ablations.
9. Revalidate final candidates with the reference solver or a stronger solver.
10. Generate paper-ready CSVs, figures, tables, and experiment reports.

## Active Small Task

Complete the user-requested GA100 block-level spatial thermal encoding update:
preserve GA100 block-level power, synthesize block positions inside chiplets,
rasterize each block into the DeepOHeat power map, and document how to run and
inspect the flow.

## Completed Small Tasks

- Created `docs/agent/` directory for persistent agent state.
- Added this active plan with startup, update, validation, and commit protocol.
- Added `AGENTS.md` as repository-level Codex rules.
- Added `docs/agent/HANDOFF.md` with project status, known results, and
  cold-start checklist.
- Added `docs/agent/DECISIONS.md` with ADR-style decision log.
- Rechecked GPU state on 2026-04-29: `nvidia-smi` is working, two NVIDIA
  GeForce RTX 4090 GPUs are visible, and the DeepOHeat PyTorch environment
  reports CUDA available with two devices.
- Ran a short package thermal smoke on `--device cuda:0`; training,
  evaluation, and inference all completed and recorded actual device
  `cuda:0`.
- Hardened Python thermal device tests so explicit CUDA requests fail under a
  mocked CUDA-unavailable environment, while `auto` falls back to CPU and
  records CPU metadata.
- Audited Dataset V2 collection and confirmed `tools/thermal/collect_instances.py`
  primarily used `thermal_collect_cli`, which creates synthetic/helper
  randomized partitions and shelf-style floorplans rather than systematically
  recording real ChipletPart search trajectories.
- Added provenance metadata to thermal instance JSON and manifest dumps:
  `run_id`, `benchmark`, `seed`, `candidate_index`, `candidate_source`,
  `search_stage`, feasibility flags, technology summary, grid size,
  `instance_hash`, and generation time.
- Added `collect_instances.py` manifest summary support for raw/unique counts,
  duplicate/skipped counts, counts by `candidate_source`, counts by
  `search_stage`, grid-size distribution, split distribution, and label
  presence.
- Ran a small Dataset V3 smoke from the real `chipletPart --tech-enum`
  candidate-evaluation dump path with mock thermal inference. The smoke wrote 8
  valid 16x16 search-candidate instances, labeled all 8 with the simplified
  reference solver, and produced a labeled summary.
- Added `tools/thermal/collect_search_dataset.py`, a light Dataset V3 pilot
  collector that runs real `chipletPart` search-candidate dumps across seeds,
  merges/deduplicates manifests, validates instances, labels them with the
  simplified reference solver, writes summaries, and creates train/val/test
  manifests.
- Collected Dataset V3 pilot in
  `/tmp/chipletpart_thermal_dataset_v3_pilot` from benchmark
  `48_1_14_4_1600_1600`, seeds `1 2 3`, grid `16x16`, tech nodes
  `7nm,14nm`, and `max_partitions=3`.
- Dataset V3 pilot result: raw `48`, unique `30`, skipped duplicates `18`,
  invalid instances `0`, `candidate_source=chipletpart_search`,
  `search_stage=search_candidate`, labels valid `30/30`, and split
  train/val/test `21/4/5`.
- Wired `run_chiplet_test.sh --thermal` to the pretrained legacy DeepOHeat
  2D checkpoint at
  `DeepOHeat/DeepOHeat/2d_power_map/log/experiment_1/checkpoints/model_epoch_10000.pth`.
- Fixed the legacy 2D adapter's `--device auto` handling and made it preserve
  absolute power-map magnitude by default, with optional scale/normalization
  controls.
- Added GA100 hierarchical block-power mapping for thermal encoding: 179
  `block_definitions.txt` power records are mapped onto the 45 netlist vertices
  before being lifted through the candidate partition, so SM/L2/PCIe/HBM power
  contributes to the thermal instance.
- Validated a GA100 `--tech-enum --max-partitions 2` run with real DeepOHeat
  inference. It produced 8 thermal results on `cuda:0`, all dumped instances
  had `partition` length 179, and total candidate power varied with
  technology/IO from about `398` to `502.704`.
- Added synthetic block treemap packing for thermal rasterization. Each scaled
  block now receives a deterministic rectangle inside its chiplet and its
  compute power is rasterized over that rectangle; IO power remains uniformly
  spread over the chiplet footprint. Thermal dumps record `blocks` metadata and
  `block_rasterization_mode=synthetic_block_treemap`.

## Next Small Verifiable Task

Train a small package_thermal surrogate on the Dataset V3 pilot and compare
metrics against the Dataset V2 surrogate, or decide to improve reference labels
first based on the Dataset V3 label summary:

- Use `/tmp/chipletpart_thermal_dataset_v3_pilot/manifest_train.jsonl`,
  `manifest_val.jsonl`, and `manifest_test.jsonl`.
- Keep training small and explicitly label it as a pilot, not paper-scale.
- Compare field MAE/RMSE and `T_max`/`T_avg` errors against the prior Dataset
  V2 surrogate numbers.
- If Dataset V3 label distribution looks too narrow or biased, prioritize
  reference-label/data improvement before larger training.

## Recent Validation

Synthetic block-level rasterization validation on 2026-05-05:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
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

Result: passed, 13 tests in 5.743 seconds.

```bash
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 2 \
  --seed 42 --thermal --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_ga100_block_raster_smoke \
  --thermal-cache
```

Result: passed. The run evaluated 5 canonical assignments, wrote 8 thermal
instance JSON files and 8 DeepOHeat result JSON files, used `cuda:0`, reported
`t_max` from `303.618 K` to `310.698 K`, and selected best cost `35.589993`
with technology assignment `[7nm, 7nm]`.

```bash
find /tmp/chipletpart_ga100_block_raster_smoke/instances \
  -maxdepth 1 -name '*.json' ! -name '*.thermal_result.json' -print0 |
  xargs -0 python3 tools/thermal/validate_instance.py
```

Result: passed for all 8 thermal instance JSON files. Additional JSON checks
confirmed `block_counts=[179]`, `partition_lengths=[179]`,
`block_rasterization_mode=synthetic_block_treemap`, nonzero power-map spread
from `0.2175589025` to `1.07823155114`, max raster power error
`2.44427e-12`, and DeepOHeat result device `cuda:0`.

GA100 legacy 2D thermal integration validation on 2026-05-05:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
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

Result: passed, 13 tests in 5.275 seconds.

```bash
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 2 \
  --seed 42 --thermal --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_ga100_run_script_smoke_k2 \
  --thermal-cache
```

Result: passed. The run evaluated 5 canonical assignments, wrote 8 thermal
result JSON files, used `cuda:0`, reported `t_max` from `303.064 K` to
`309.173 K`, and selected best cost `35.589993` with technology assignment
`[7nm, 7nm]`.

Planned for this documentation milestone:

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

Result: passed on 2026-04-29 in
`/home/yhsun/Chiplet-Partitioning/ChipletPart`.

Previous Codex-reported validation from the pilot pipeline:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
ctest -R thermal_mvp_test --output-on-failure
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Reported result: build passed, `thermal_mvp_test` passed, and the Python
thermal pipeline tests passed. Re-run before relying on those results for new
code changes.

Current device validation on 2026-04-29 in
`/home/yhsun/Chiplet-Partitioning/ChipletPart`:

```bash
nvidia-smi
```

Result: passed. Driver `570.124.06`, CUDA runtime reported by `nvidia-smi`
`12.8`, and two `NVIDIA GeForce RTX 4090` GPUs were visible.

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

Result: passed. PyTorch `2.0.0+cu117`, CUDA available `True`, device count `2`,
devices `0` and `1` both `NVIDIA GeForce RTX 4090`.

Short package thermal smoke:

- Generated a temporary 8x8 package thermal manifest.
- Ran `DeepOHeat/package_thermal/train.py` for one epoch with
  `--device cuda:0`.
- Ran `DeepOHeat/package_thermal/evaluate.py` with `--device cuda:0`.
- Ran `DeepOHeat/package_thermal/infer_package.py` with `--device cuda:0`.

Result: passed. Train, evaluation, and inference outputs all recorded
`device: cuda:0` and GPU name `NVIDIA GeForce RTX 4090`.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Result: passed, 10 tests in 5.924 seconds.

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

Search-candidate smoke output:
`/tmp/chipletpart_thermal_dataset_v3_smoke/search`.

- Command: `build/bin/chipletPart ... --tech-enum --max-partitions 2
  --enable_thermal --thermal_use_mock --thermal_dump_manifest ...`
- Result: 8 dumped instances, 8 valid JSON files, source/stage distribution
  `chipletpart_search/search_candidate`, grid `16x16`.
- Reference labels: `tools/thermal/reference_solver.py --method auto
  --max_iter 1000 --tol 1e-6 --overwrite` passed; all 8 labels were valid.
- Summary: `summary_labeled.json` reports raw `8`, unique `8`, labels exist
  `true`, invalid/skipped `0`.

Helper collection smoke output:
`/tmp/chipletpart_thermal_dataset_v3_smoke/helper`.

- Command: `tools/thermal/collect_instances.py --num_instances 5 ...`
- Result: `manifest_summary.json` reports raw `5`, unique `5`,
  `candidate_source=synthetic_helper`, `search_stage=synthetic_random_shelf`,
  grid `16x16`, labels exist `false`.

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

Result: passed on 2026-04-29 in
`/home/yhsun/Chiplet-Partitioning/ChipletPart`.

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

Result: passed. Output directory:
`/tmp/chipletpart_thermal_dataset_v3_pilot`.

- Raw candidate dumps before dedup: `48`.
- Unique manifest records: `30`.
- Skipped duplicates: `18`.
- Invalid instances: `0`.
- Candidate source distribution: `chipletpart_search: 30`.
- Search stage distribution: `search_candidate: 30`.
- Grid distribution: `16x16: 30`.
- Labels: `30`, all converged and valid; invalid labels `0`.
- `T_max`: min `317.0389 K`, mean `324.8712 K`, max `342.5247 K`.
- `T_avg`: min `308.3147 K`, mean `315.7380 K`, max `327.6581 K`.
- Split: train `21`, val `4`, test `5`.

## Current Blockers

- GPU state is currently good in this shell/Python environment, but it remains
  environment-sensitive. Recheck before long training or GPU sweeps.
- Reference labels are still generated by a simplified 2D effective solver, not
  a signoff-quality thermal solver.
- Dataset V3 pilot is still small and single-benchmark. It is better than the
  smoke for surrogate debugging, but not a final paper-scale dataset.
- Surrogate error on final candidates is still significant and requires
  calibration, larger data, and revalidation.

## Current Do-Not-Do List

- Do not break cost-only ChipletPart behavior.
- Do not make floorplan the primary output.
- Do not treat `legacy_2d_power_map` as the research method.
- Do not present the simplified reference solver as final ground truth.
- Do not add unsupported technology nodes casually; previous Codex-reported
  runs hit unsupported scaling for `45nm -> 28nm`.
- Do not push.
- Do not combine unrelated user changes into milestone commits.

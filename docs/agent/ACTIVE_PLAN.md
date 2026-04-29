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

Prepare a small Dataset V3 labeling/splitting run from provenance-aware
ChipletPart search-candidate dumps, then decide whether the next improvement is
surrogate retraining or reference label quality.

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

## Next Small Verifiable Task

Generate a small provenance-aware Dataset V3 pilot, then label and summarize it:

- Use the real ChipletPart search-candidate dump path with
  `candidate_source=chipletpart_search`.
- Keep the run small, for example tens of instances across a few seeds and one
  or two benchmarks.
- Label with the current simplified reference solver, write manifest summaries,
  and split into train/val/test.
- Use the summary to decide whether the following milestone should retrain a
  small package surrogate or first improve/calibrate reference labels.

## Recent Validation

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

## Current Blockers

- GPU state is currently good in this shell/Python environment, but it remains
  environment-sensitive. Recheck before long training or GPU sweeps.
- Reference labels are still generated by a simplified 2D effective solver, not
  a signoff-quality thermal solver.
- Dataset V3 provenance now distinguishes helper vs real search-candidate
  dumps, but the smoke is tiny and not yet representative of the full
  ChipletPart optimizer candidate distribution.
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

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

Prepare dataset collection to better match real ChipletPart search candidate
distributions, while preserving the current cost-only baseline and package
thermal device policy.

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

## Next Small Verifiable Task

Make dataset collection closer to the real ChipletPart search distribution:

- Inspect `tools/thermal/collect_instances.py` and the current candidate dump
  path used by `thermal_collect_cli`.
- Identify the smallest change that samples more realistic GA/search
  candidates without running a large experiment sweep.
- Add or update one focused test or smoke command for the new collection path.
- Update the dataset/agent docs and commit the verified milestone.

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

## Current Blockers

- GPU state is currently good in this shell/Python environment, but it remains
  environment-sensitive. Recheck before long training or GPU sweeps.
- Reference labels are still generated by a simplified 2D effective solver, not
  a signoff-quality thermal solver.
- Pilot dataset generation is not yet representative enough of the full
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

# Codex Agent Guide

## Project Summary

Thermal-Aware Chiplet Partitioning integrates DeepOHeat-style fast thermal
surrogate inference into ChipletPart so candidate search can optimize system
cost and thermal feasibility together instead of doing thermal analysis only
after partitioning.

The active objective is:

```text
J = C_sys
    + lambda_peak * max(0, T_max - T_budget)^2
    + lambda_avg * T_avg
```

`C_sys` is ChipletPart's original system cost. `T_max` and `T_avg` come from a
package-level thermal surrogate or reference solver. `lambda_avg` defaults to
zero and is reserved for explicit ablation.

## Required Startup Flow

Every new Codex session must start by reading these files, in this order:

1. `AGENTS.md`
2. `docs/agent/ACTIVE_PLAN.md`
3. `docs/agent/HANDOFF.md`
4. `docs/agent/DECISIONS.md`

Then run `git status --short` in the active repository before making changes.
Do not rely on chat-window memory. Important project state, commands, decisions,
and experiment results must be written to the agent files or project docs.

The top-level workspace may contain multiple repositories. At the time this
file was added, `/home/yhsun/Chiplet-Partitioning` itself was not a git repo;
`ChipletPart` and `DeepOHeat` are separate project directories. Check the repo
root you are about to edit before staging or committing.

## Persistent Agent Files

- `AGENTS.md`: repository-level working rules and command index.
- `docs/agent/ACTIVE_PLAN.md`: current phase, active tasks, status, validation,
  blockers, and the next smallest verifiable task.
- `docs/agent/HANDOFF.md`: cold-start project summary, recent state, important
  paths, known results, unresolved risks, and checklist for the next session.
- `docs/agent/DECISIONS.md`: architecture and method decisions in ADR style.

## Continuous Update Protocol

Each new task:

1. Read the four agent files above.
2. Check `git status --short`.
3. Choose the smallest verifiable next step from `ACTIVE_PLAN.md`.

During implementation:

- After each small milestone, update `docs/agent/ACTIVE_PLAN.md`.
- If an architecture or methodology choice is made, update
  `docs/agent/DECISIONS.md`.
- If a command, path, result, or limitation becomes important for the next
  session, update `docs/agent/HANDOFF.md`.
- If the context window is getting full, update `docs/agent/HANDOFF.md` before
  continuing or stopping.
- Do not explain critical state only in chat.

Before ending a task:

1. Run the smallest validation relevant to the files changed.
2. Record the latest validation result in `ACTIVE_PLAN.md`.
3. Update `HANDOFF.md` if project state changed.
4. Run `git diff --stat`.
5. Make a local git commit for the verifiable milestone.
6. Do not push.

## Non-Negotiable Rules

- Do not break the cost-only ChipletPart baseline.
- When `--enable_thermal` is absent, ChipletPart must preserve the original
  cost-only behavior.
- The main ChipletPart output remains partition and technology assignment.
- Floorplan is an internal evaluation, encoding, debug, and revalidation object;
  it is not the new primary optimization output.
- `package_thermal` is the current research path for the paper.
- `legacy_2d_power_map` is compatibility/debug only, not the final paper method.
- Keep `--thermal_use_mock` available for fast debugging.
- The simplified 2D effective reference solver is not a signoff solver. Do not
  present it as final ground truth.
- Explicit requests for `cuda`, `cuda:0`, or `cuda:1` must fail clearly when the
  device is unavailable. Do not silently fall back.
- `device=auto` may fall back to CPU with a clear warning.
- The server is expected to have `cuda:0` and `cuda:1`, but previous
  Codex-reported checks found `nvidia-smi` could not communicate with the driver
  and `torch.cuda.is_available()` was `False`. Recheck GPU state before GPU work.
- Do not push.
- Local commits are allowed and expected after each verifiable milestone.
- If there are existing uncommitted user changes, do not overwrite or stage them
  into your commit. Mention them in the final response.

## Validation Requirements

For documentation-only changes, at minimum verify required files exist and are
non-trivial:

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

For ChipletPart C++ changes:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
cd build
ctest -R thermal_mvp_test --output-on-failure
```

For Python thermal pipeline changes:

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

## Environment Notes

If network access is needed, try `proxy-on` first and explain why network is
needed. Do not blindly install large packages.

For conda:

```bash
export CONDARC=/etc/conda/.condarc
source /opt/conda/miniforge3/etc/profile.d/conda.sh
```

or:

```bash
module load conda/miniforge3
source /opt/conda/miniforge3/etc/profile.d/conda.sh
```

For CUDA compiler/module setup:

```bash
source /etc/profile.d/site-modules.sh
module load cuda
```

## Command Index

Check GPU and PyTorch CUDA:

```bash
nvidia-smi
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
print("cuda count:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    print(i, torch.cuda.get_device_name(i))
PY
```

Build and test ChipletPart thermal MVP:

```bash
cd /home/yhsun/Chiplet-Partitioning/ChipletPart
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
cd build
ctest -R thermal_mvp_test --output-on-failure
```

Run Python thermal pipeline tests:

```bash
cd /home/yhsun/Chiplet-Partitioning/ChipletPart
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Pilot package surrogate training uses `DeepOHeat/package_thermal/train.py`.
Use `--device auto` for opportunistic GPU use, or explicit `--device cuda:0` /
`--device cuda:1` only after confirming availability.

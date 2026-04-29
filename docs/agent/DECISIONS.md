# Decision Log

This file records architecture and method decisions for Thermal-Aware Chiplet
Partitioning. Use ADR-style entries. Update it whenever a new architecture,
methodology, or experiment-policy decision is made.

## ADR-0001: Keep ChipletPart Main Output Contract

- Date: 2026-04-29
- Decision: Preserve ChipletPart's primary output as partition and technology
  assignment.
- Status: Accepted
- Context: The research goal is thermal-driven chiplet partitioning, not a
  floorplan-first replacement of ChipletPart. Original ChipletPart already
  optimizes cost and technology assignment with IO feasibility.
- Alternatives considered: Redesign the flow so floorplan is the primary output.
- Consequences: Thermal logic must integrate into candidate evaluation while
  leaving the cost-only API and main result semantics intact.
- Validation / follow-up: Keep `--enable_thermal` disabled by default and
  preserve cost-only regression tests.

## ADR-0002: Treat Floorplan As Internal Evaluation State

- Date: 2026-04-29
- Decision: Use floorplan for IO reach feasibility, thermal instance encoding,
  debug dumps, and final revalidation, but not as the main paper output.
- Status: Accepted
- Context: Thermal evaluation needs chiplet geometry and package placement.
  However, the paper target remains partitioning and technology assignment.
- Alternatives considered: Expose floorplan as the central optimizer product.
- Consequences: Encoders and evaluators may consume floorplan data, but reports
  should focus on partition, technology assignment, cost, thermal metrics, and
  objective.
- Validation / follow-up: Experiment reports should save floorplan-related
  paths for reproducibility without changing the primary output contract.

## ADR-0003: Use Package Thermal Backend As Main Research Path

- Date: 2026-04-29
- Decision: `package_thermal` is the primary DeepOHeat-style surrogate path.
- Status: Accepted
- Context: The old DeepOHeat `2d_power_map` checkpoint only consumes a top 2D
  power map and cannot use geometry, material, or boundary channels dumped by
  ChipletPart.
- Alternatives considered: Continue using the legacy 2D checkpoint as the
  central model.
- Consequences: Training, evaluation, and paper experiments should target
  `DeepOHeat/package_thermal/`, which consumes full multi-channel package
  tensors.
- Validation / follow-up: Keep improving package-level labels, data scale, and
  final-candidate revalidation.

## ADR-0004: Keep Legacy 2D Backend Only For Compatibility

- Date: 2026-04-29
- Decision: Retain `legacy_2d_power_map` only as a compatibility/debug baseline.
- Status: Accepted
- Context: The legacy checkpoint is useful for adapter debugging and regression,
  but does not match the final package-level method.
- Alternatives considered: Remove the backend, or use it as the final method.
- Consequences: Do not delete it, but do not present it as the paper method.
- Validation / follow-up: Documentation must label it as compatibility/debug.

## ADR-0005: Thermal Objective Uses Peak Penalty With Optional Mean Term

- Date: 2026-04-29
- Decision: Use
  `J = C_sys + lambda_peak * max(0, T_max - T_budget)^2 + lambda_avg * T_avg`.
- Status: Accepted
- Context: The peak term enforces thermal feasibility pressure while preserving
  cost as the base objective. Mean temperature is useful for ablation but should
  not be forced by default.
- Alternatives considered: Hard thermal rejection, linear penalty only, or
  always including mean temperature.
- Consequences: Objective calculation should stay centralized in the thermal
  evaluator. `lambda_avg` defaults to zero.
- Validation / follow-up: Budget sweeps and lambda ablations are needed for the
  final paper.

## ADR-0006: Cost-Only Baseline Must Remain Unbroken

- Date: 2026-04-29
- Decision: `--enable_thermal` must be opt-in. Without it, ChipletPart follows
  the original cost-only path.
- Status: Accepted
- Context: Regressing the original optimizer would invalidate comparisons and
  make thermal improvements hard to interpret.
- Alternatives considered: Always instantiate thermal code with zero weights.
- Consequences: Thermal evaluator, surrogate, dumps, and subprocess calls should
  not run when thermal is disabled.
- Validation / follow-up: Keep `thermal_mvp_test` and cost-only regression
  checks passing.

## ADR-0007: Simplified 2D Reference Solver Is Pilot-Only

- Date: 2026-04-29
- Decision: The current simplified 2D effective heat-spreading solver is for
  pilot labels and surrogate development only; it is not signoff ground truth.
- Status: Accepted
- Context: The solver is deterministic, lightweight, and useful for closed-loop
  development, but it is not a commercial FEM or validated package thermal
  signoff tool.
- Alternatives considered: Block all training until a stronger solver is
  integrated.
- Consequences: Reports must clearly label the solver as simplified. Final paper
  experiments need stronger labels, calibration, or external solver
  revalidation.
- Validation / follow-up: Add HotSpot, 3D-ICE, Celsius, FEM, commercial solver,
  or calibrated reference path when available.

## ADR-0008: Support CPU, CUDA, Explicit CUDA Indices, And Auto Device

- Date: 2026-04-29
- Decision: Training, evaluation, and inference support `cpu`, `cuda`,
  `cuda:0`, `cuda:1`, and `auto`.
- Status: Accepted
- Context: The server is expected to have two GPUs, but previous checks found
  CUDA unavailable in the active shell/Python environment. Scripts need both
  portability and explicit control.
- Alternatives considered: CPU-only scripts, or always using CUDA when present.
- Consequences: Device parsing is shared by package thermal tools. Logs and JSON
  outputs should record the actual device.
- Validation / follow-up: Recheck GPU environment before GPU runs and keep CPU
  smoke tests mandatory.

## ADR-0009: Explicit CUDA Failure, Auto CPU Fallback

- Date: 2026-04-29
- Decision: Explicit CUDA requests fail clearly if unavailable; `auto` can fall
  back to CPU with a warning.
- Status: Accepted
- Context: Silent fallback from `cuda:1` to CPU would hide experiment mistakes,
  but `auto` is useful for portable scripts.
- Alternatives considered: Always fallback to CPU, or always fail if CUDA is not
  available.
- Consequences: `--device cuda`, `--device cuda:0`, and `--device cuda:1` must
  validate availability. `--device auto` should log the chosen device.
- Validation / follow-up: Maintain device parser tests and document current GPU
  availability in experiment reports.

## ADR-0010: Use Local Commits For Verifiable Milestones

- Date: 2026-04-29
- Decision: After each small verified milestone, update agent files and make a
  local git commit. Do not push.
- Status: Accepted
- Context: The user wants project memory and progress durable across Codex
  sessions while keeping remote history under user control.
- Alternatives considered: No commits until the end, or pushing automatically.
- Consequences: Keep commits narrow. Do not stage unrelated user modifications.
- Validation / follow-up: Final responses should include commit hash, validation
  run, and any uncommitted changes left behind.

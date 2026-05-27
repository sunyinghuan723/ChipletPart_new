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

## ADR-0011: Require Provenance For Paper-Scale Thermal Datasets

- Date: 2026-04-29
- Decision: Paper-scale thermal datasets should record search-candidate
  provenance in instance JSON and manifest entries.
- Status: Accepted
- Context: Earlier dataset collection could generate package thermal instances
  through a helper that randomized partitions, technology assignments, and a
  shelf-style floorplan. That is useful for smoke tests, but paper experiments
  need to distinguish helper-generated samples from real ChipletPart candidate
  evaluations and final solutions.
- Alternatives considered: Infer provenance from directory names after the
  fact, or leave provenance only in run logs.
- Consequences: Thermal dumps and manifests should carry fields such as
  `run_id`, `seed`, `candidate_index`, `candidate_source`, `search_stage`,
  feasibility flags, grid size, technology summary, and an instance hash. Older
  records without these fields remain compatible and summarize as `unknown`.
- Validation / follow-up: Dataset collection summaries must include counts by
  `candidate_source` and `search_stage`; future Dataset V3 runs should prefer
  `candidate_source=chipletpart_search` for training/evaluation data.

## ADR-0012: Map GA100 Block-Level Power Onto Netlist Vertices For Legacy 2D Thermal Runs

- Date: 2026-05-05
- Decision: For GA100 thermal compatibility runs, keep every
  `block_definitions.txt` power record and map it onto the smaller netlist
  vertex set before applying the candidate partition.
- Status: Accepted
- Context: `test_data/ga100/block_level_netlist.xml` exposes 45 partition
  vertices, while `test_data/ga100/block_definitions.txt` contains 179
  block-level power records. The old thermal encoder assumed a one-to-one
  partition/block relationship and failed on GA100. The user's advisor
  specifically called out that block-level power should be considered.
- Mapping policy: exact block names map directly; `sm_*` blocks are distributed
  proportionally across `l2_*` vertices; `hbm_1024_phy_*` blocks are
  distributed proportionally across `hbm_1536_ctrl_*` vertices; any future
  unmapped records are distributed across all netlist vertices with a warning.
- Consequences: Thermal compute power and area use all GA100 block records and
  retain their individual technology-scaling type. IO power continues to use
  the original netlist partition and adjacency matrices. Cost-only behavior is
  unchanged.
- Validation / follow-up: A GA100 `--tech-enum --max-partitions 2` run with the
  pretrained legacy 2D checkpoint completed, wrote 8 thermal result JSON files,
  and every dumped thermal instance had `partition` length 179.

## ADR-0013: Use Synthetic Treemap Packing For Block-Level Power Rasterization

- Date: 2026-05-05
- Decision: When real block placement is unavailable, pack blocks
  deterministically inside each chiplet with an area-proportional treemap and
  rasterize each block's scaled compute power over its own rectangle.
- Status: Accepted
- Context: GA100 block-level powers were already mapped into thermal
  evaluation, but the power map sent to DeepOHeat still used chiplet-level
  uniform density. This preserved total power but erased chiplet-internal
  spatial variation from SM, L2, PCIe, HBM controller, and HBM PHY records.
- Rasterization policy: block compute power uses the same technology scaling as
  before, block rectangle area follows scaled block area, and IO power remains a
  chiplet-level term spread uniformly across the chiplet footprint.
- Consequences: Thermal instance JSON now records packed `blocks` metadata and
  `block_rasterization_mode=synthetic_block_treemap`. The `power_density_w_per_mm2`
  channel contains block-level spatial variation while preserving total
  rasterized power. This is a synthetic spatial prior, not signoff block
  placement.
- Validation / follow-up: `thermal_mvp_test` now checks that dumped instances
  include block packing metadata, conserve raster power, and produce a
  nonuniform power-density map.

## ADR-0014: Generate Thermal Figures During Script Runs

- Date: 2026-05-05
- Decision: `run_chiplet_test.sh --thermal` should post-process DeepOHeat field
  NPZ files into PNG figures after a successful run.
- Status: Accepted
- Context: The thermal flow already writes `.thermal_result.field.npz` files,
  but users had to run a separate plotting script to inspect the temperature
  field and power map. The requested GA100 flow should leave directly viewable
  figures in the result directory.
- Implementation policy: `run_chiplet_test.sh` writes figures under
  `<thermal-output-dir>/figures` by default, with `--thermal-figure-dir` as an
  override. Figure generation is a post-processing step; if it fails, the
  successful ChipletPart run is preserved and a warning is printed.
- Consequences: Legacy 2D runs produce power, sensor, temperature slice, and
  histogram PNGs. Package-thermal runs request field NPZ dumps and can plot
  temperature maps plus power maps loaded from the matching instance JSON.

## ADR-0015: Penalize Invalid Initial GA Candidates

- Date: 2026-05-06
- Decision: Random solutions created during `GeneticTechPartitioner`
  population initialization must receive maximum cost when the floorplanner
  reports infeasible/invalid placement.
- Status: Accepted
- Context: A GA100 heterogeneous thermal validation run exposed an invalid
  initial random candidate with a finite base cost. Because the initial
  population path did not enforce maximum cost for failed floorplans, that
  candidate could become the reported GA best even though final output marked
  `Valid Solution: No`.
- Consequences: The random-initial-solution path now mirrors the later
  `EvaluateFitness` safeguard: invalid candidates are kept invalid and assigned
  `std::numeric_limits<float>::max()`. This preserves the cost-only baseline
  intent while preventing infeasible initial solutions from winning either
  cost-only or thermal-aware GA runs.
- Validation / follow-up: Rebuilt `chipletPart`, reran GA100 heterogeneous
  cost-only and thermal validation runs, and both reported `Valid Solution:
  Yes`. The pre-fix invalid run is archived outside the repo at
  `/home/yhsun/Chiplet-Partitioning/experiment_v1/heterogeneous_thermal_pre_fix`.

## ADR-0016: Push Thermal Objective Into Partition Refinement

- Date: 2026-05-14
- Decision: In homogeneous thermal mode, FM/KL refinement evaluates each
  executed move with a fresh fast floorplan and the full thermal objective.
  The refiner also refreshes the current objective after both fast and
  standard floorplanner calls. In heterogeneous GA thermal mode, the FM/KL
  refiner stays cost-only and thermal is applied only after the standard
  post-refinement floorplanner for each GA solution.
- Status: Accepted
- Context: The previous thermal flow only called DeepOHeat after a candidate
  partition/technology assignment already had a final floorplan. That made
  thermal affect final ranking, but not the FM/KL refinement path used to
  create the candidate.
- Runtime policy: Homogeneous mode pays the extra DeepOHeat cost for the
  refinement trajectory. Heterogeneous mode avoids per-move thermal inside GA
  because the population already creates many refined floorplans. Thermal cache
  remains enabled by script option, and default per-evaluation C++ logging is
  quiet unless `CHIPLET_PART_VERBOSE_COST` or
  `CHIPLET_PART_VERBOSE_THERMAL` is set.
- Consequences: Cost-only behavior remains gated by `--enable_thermal`. Failed
  floorplans receive maximum objective before thermal-aware ranking, so invalid
  candidates cannot win. Homogeneous thermal runs are expected to be slower
  because refinement now calls the thermal backend many more times.
- Validation / follow-up: Rebuilt `chipletPart`, passed `thermal_mvp_test`,
  passed the Python thermal pipeline tests, ran a mock refinement smoke, and
  started GA100 validation under
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100`.

## ADR-0017: Use Persistent Python Workers For DeepOHeat Inference

- Date: 2026-05-15
- Decision: Real DeepOHeat inference from C++ should use a persistent Python
  worker per `ThermalAwareEvaluator` when possible, instead of launching a new
  Python process for every thermal evaluation.
- Status: Accepted
- Context: After ADR-0016, homogeneous thermal refinement calls DeepOHeat for
  selected FM/KL moves and swaps. Launching Python, importing Torch/DeepOHeat,
  loading the checkpoint, and initializing CUDA for every move made runtime
  impractically high.
- Implementation policy: `PythonDeepOHeatAdapter` starts the configured
  inference script with `--server`, sends one JSON object per request through
  stdin, reads one JSON object per response from stdout, and stops the worker
  on adapter destruction. The old subprocess invocation remains as fallback.
  Both `legacy_2d_power_map` and `package_thermal` inference scripts must keep
  single-shot CLI behavior and support `--server`.
- Consequences: FM/KL refinement keeps the V2 thermal objective placement while
  amortizing Python/Torch/model/CUDA startup across many move evaluations.
  Thermal inference is still serialized by the evaluator mutex, which avoids
  concurrent writes through a single worker. Cost-only and mock thermal paths
  are unchanged.
- Validation / follow-up: Direct legacy service inference on one archived GA100
  instance processed two requests in one Python worker; service-reported
  runtime dropped from about `0.512 s` on the first request to about `0.013 s`
  on the second. A real `48_1_14_4_1600_1600` refinement thermal smoke wrote
  `658` real DeepOHeat result records and completed successfully in
  `203.39 s`. Next runtime target is reducing per-move field NPZ writes or
  adding batched requests.

## ADR-0018: Support Fixed Partition Counts For Controlled Homogeneous Comparisons

- Date: 2026-05-23
- Decision: Standard homogeneous partitioning exposes `--fixed-parts <count>`
  so cost-only and thermal-aware comparisons can be constrained to the same
  number of active chiplets when required by an experiment.
- Status: Accepted
- Context: An EPYC homogeneous thermal run selected three parts while its
  cost-only comparator selected four, and the thermal result was worse on
  both cost and temperature. The user requested a controlled four-part rerun.
- Implementation policy: Restrict standard initial candidate generation to the
  requested count and reject a final refined candidate unless it still
  contains exactly that number of active partitions. This option is opt-in and
  does not alter the unconstrained or heterogeneous paths.
- Consequences: Fixed-count experiments isolate thermal/refinement behavior
  from changes in chiplet count. The EPYC fixed-4 rerun still failed to improve
  objective (`93.465645` versus the cost-only post-evaluated `79.009962`), so
  it is a diagnostic record rather than a paper-table replacement.
- Validation / follow-up: Build and `thermal_mvp_test` passed; an EPYC real
  DeepOHeat fixed-4 comparison completed. Investigate homogeneous incumbent
  retention and floorplan/refinement comparability before using Hom-Therm as
  an improvement claim.

## ADR-0019: Require Matched Final Geometry For Thermal Post-Evaluation

- Date: 2026-05-24
- Decision: Final-candidate thermal post-evaluation must encode a floorplan
  generated for the final refined partition. Thermal coordinates retain their
  signed floorplanner values until the entire package is translated to an
  origin-aligned coordinate system.
- Status: Accepted
- Context: The new overlap rejection exposed two stale-geometry defects during
  an EPYC Hom-Cost post-evaluation. The homogeneous post-eval-only path could
  reuse geometry from before FM/KL changed the partition, and the encoder
  individually clamped negative coordinates before translation, potentially
  converting separated chiplets into overlapping ones.
- Consequences: Opt-in homogeneous thermal and post-eval-only runs perform a
  final floorplan for their refined candidates before evaluation. Cost-only
  search remains cost-driven, but any reported thermal result now refers to
  matching, non-overlapping final geometry. Newly generated v4 numbers should
  not be compared as if they were identical reruns of older stale-geometry
  outputs.
- Validation / follow-up: `thermal_mvp_test` rejects true overlap and accepts
  separated negative-coordinate geometry after translation. A real EPYC
  cost-only post-evaluation now completes with one field and reports
  `base=84.825104`, `T_max=307.117035 K`, `T_avg=301.992432 K`.

## ADR-0020: Floorplan Hierarchical Benchmarks Using Mapped Detailed Areas

- Date: 2026-05-24
- Decision: When a benchmark has more detailed block definitions than netlist
  partition vertices, floorplanning must accumulate the detailed block areas
  through the same block-to-vertex mapping used by thermal encoding.
- Status: Accepted
- Context: GA100 maps 179 power/area records onto 45 netlist vertices.
  Thermal encoding correctly expanded the candidate to detailed records, but
  `FMRefiner::GenerateNetlist` floorplanned only the netlist-vertex areas.
  Final chiplet rectangles reconstructed from detailed area then overlapped
  at thermal post-evaluation.
- Implementation policy: Expose
  `BuildThermalBlockToGraphVertexMapping` as the shared deterministic mapping
  policy and use it to expand a vertex partition before summing
  technology-scaled physical area for floorplanning. Continue packing
  detailed block power within each chiplet using the synthetic treemap.
- Consequences: GA100 floorplans and thermal instances now describe the same
  physical chiplet area. Corrected GA100 costs, geometry, and temperatures may
  change relative to old results computed from undersized footprints.
- Validation / follow-up: A mapping assertion was added to
  `thermal_mvp_test`; build and `ctest -R thermal_mvp_test` passed. A real
  GA100 Hom-Cost post-evaluation completed with one thermal field and reports
  `base=32.704578`, `T_max=307.324463 K`, `T_avg=303.450958 K`.

## ADR-0021: Preserve Original Homogeneous Cost Ranking During Post-Evaluation

- Date: 2026-05-25
- Decision: `--thermal-post-eval-only` must preserve the original homogeneous
  cost-only ranking. After that winner is selected, it may report thermal
  data only if a newly constructed matching final floorplan is feasible.
- Status: Superseded by ADR-0022
- Context: On EPYC with seed `42`, the historical no-thermal path reported a
  four-part cost `79.741852`, while the post-evaluation path reported
  `83.387138` because it re-ranked candidates after thermal-enabled final
  floorplanning. A final floorplan attempt on the fixed original winner,
  including a `10000 x 10000` run, does not produce feasible geometry.
- Consequences: Hom-Cost remains the original base-cost winner even if its
  thermal output is unavailable. Reports must use `N/A` rather than silently
  substituting a more expensive thermally evaluable candidate. A separate
  feasible-geometry variant may be retained for diagnosis, but it is not the
  original baseline.
- Validation / follow-up: Build and `thermal_mvp_test` passed. Matching EPYC
  seed-`42` no-thermal and post-eval-only runs select byte-identical
  four-part partitions at base cost `79.741852`; post-evaluation emits no
  thermal field because the matching final floorplan is infeasible.

## ADR-0022: Certify Homogeneous Cost Candidates With Matching Final Geometry

- Date: 2026-05-25
- Decision: After FM/KL refinement, every standard homogeneous candidate must
  receive a final floorplan generated for that refined partition before it is
  eligible for cost-only ranking. `--thermal-post-eval-only` evaluates the
  validity-certified cost-only winner's stored matching geometry and does not
  introduce a thermal ranking term.
- Status: Superseded by ADR-0023
- Context: ADR-0021 exposed that the historical EPYC seed-`42` four-part
  `79.741852` winner could not be final-floorplanned. Inspection showed the
  no-thermal path retained floorplan coordinates and success from before
  FM/KL modified the partition. A `10000 x 10000` final-floorplan diagnostic,
  enhanced to retain any feasible SA state encountered, still found no valid
  geometry for that fixed four-part partition. It was therefore an
  incorrectly certified result rather than a valid baseline that merely
  lacked temperature output.
- Implementation policy: Final-validation floorplanning may retain the
  lowest-cost feasible state visited during simulated annealing so a later
  invalid endpoint cannot erase an already discovered legal layout. This
  retention is opt-in for final validation; it is not enabled for the
  ordinary refinement trajectory.
- Consequences: Both no-thermal and post-eval-only homogeneous flows apply the
  same physical-feasibility gate, preserving cost-only ordering among valid
  final candidates while excluding stale-geometry candidates. Historical v5
  summaries generated before this fix must be rerun before use.
- Validation / follow-up: `floorplan_retention_test` and `thermal_mvp_test`
  pass. For EPYC seed `42`, no-thermal and post-eval-only choose the same
  three-part candidate at base cost `83.387138`; the post-evaluation produces
  `T_max=305.581329 K` and `T_avg=302.149750 K` under the legacy
  compatibility backend.

## ADR-0023: Apply Final-Floorplan Feasibility During Hom-Cost Refinement

- Date: 2026-05-26
- Decision: Homogeneous cost-only FM/KL refinement must reject move endpoints
  without a matching feasible floorplan while continuing to rank feasible
  moves using base cost alone. Thermal post-evaluation remains absent from
  cost-only ranking.
- Status: Accepted
- Context: The ADR-0022 EPYC rerun produced a legal Hom-Cost result at base
  cost `83.387138`, but Hom-Therm found a legal solution with lower base cost
  `82.660767`. Both started from the same 18 retained initial partitions.
  Hom-Cost previously followed unconstrained base-cost moves and validated
  floorplanning only after FM/KL, so an invalid endpoint could cause a better
  feasible trajectory to be lost. Hom-Therm already evaluated refinement
  moves with matching floorplans as part of thermal objective computation.
- Implementation policy: Add a floorplan-constrained cost-evaluation mode to
  `ChipletRefiner` and enable it for standard homogeneous non-thermal and
  post-eval-only search. The mode uses floorplanning only as a feasibility
  constraint; accepted candidates are still ranked exclusively by base cost.
  Preserve failed-floorplan objective state rather than refreshing it with
  stale coordinates in either constrained-cost or thermal refinement.
- Consequences: Hom-Cost is now a physical-feasibility-constrained cost
  baseline comparable to Hom-Therm. It costs more runtime than the old
  endpoint-only validation path. This correction does not turn heuristic
  refinement into a proof of global optimality.
- Validation / follow-up: Build, `thermal_mvp_test`, and
  `floorplan_retention_test` pass. Temporary EPYC seed-`42` no-thermal and
  post-eval-only runs select the identical four-part solution at base cost
  `82.660767`; post-evaluation reports `T_max=305.534332 K` and
  `T_avg=301.782715 K`. A same-binary Hom-Therm run selects the identical
  partition, geometry, and base cost with penalized objective `85.723648`.
  The regenerated complete v5 four-mode artifacts are in
  `/home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/analysis`.

## ADR-0024: Admit The Cost Winner To Thermal Final Selection

- Date: 2026-05-27
- Decision: A thermal-aware run may accept the matching Cost winner as a fixed
  final candidate through `--thermal-incumbent-partition` and, for
  heterogeneous search, `--thermal-incumbent-techs`. The admitted candidate
  is evaluated under the Thermal run's final floorplan and surrogate
  configuration, and final output is selected by exact final `J` over the
  admitted Cost candidate and thermally searched candidates.
- Status: Accepted
- Context: In EPYC experiment v5, `Het-Cost` post-evaluated to comparable
  objective `75.030888`, while `Het-Therm` selected a cooler but worse
  objective `77.873742`. Thermal search alone does not guarantee that a
  heuristic trajectory retains an already known baseline solution.
- Implementation policy: Keep the Cost partition and technology assignment
  fixed during incumbent evaluation; generate a final matching floorplan and
  invoke the same thermal backend/configuration as the thermal run. Standard
  homogeneous search appends it to final candidates. Heterogeneous GA
  compares it after search and does not run refinement on it.
- Consequences: For an admitted, evaluable Cost candidate, the reported
  Thermal final objective cannot exceed that candidate's final-condition
  objective. The cost-only behavior without thermal remains unchanged.
- Validation / follow-up: Build and both CTest tests passed. Mock incumbent
  smokes selected the admitted candidate in both standard and short genetic
  flows. Run and analyze `experiment_v6_epyc7282` with real compatibility
  thermal inference.

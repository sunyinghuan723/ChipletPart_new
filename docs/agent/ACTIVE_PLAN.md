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

The requested GA100 v6 follow-up is complete under
`/home/yhsun/Chiplet-Partitioning/experiment_v6_ga100`. It uses seed `42`,
budget `300 K`, `lambda_peak=0.1`, the legacy `2d_power_map` compatibility
backend, and input data from `ChipletPart/test_data/ga100`. Both thermal
final outputs retain searched improvements while satisfying the new
no-worse-final-`J` protocol against admitted Cost candidates. `main.tex` was
intentionally not changed.

## Completed Small Tasks

- Completed GA100 experiment v6 on 2026-05-27 under the incumbent protocol.
  Hom-Cost reports comparable objective `38.180714` and
  `T_max=307.387634 K`; Hom-Therm retains its searched winner at objective
  `38.068913` and `T_max=307.330902 K`. Het-Cost reports comparable
  objective `36.633680` and `T_max=306.968414 K`; Het-Therm retains its
  searched winner at objective `36.354332` and `T_max=306.186462 K`, after
  logging fixed incumbent objective `37.380592`. Thus same-run thermal minus
  cost deltas are `-0.111801` (Hom) and `-0.279348` (Het). The run wrote
  `4211` thermal result JSON records plus summary/report/PNG/PDF artifacts and
  `analysis/comparison_with_v5.md`. Relative to v5, homogeneous output is
  identical; heterogeneous v6 results are higher by `+0.041472` (Cost) and
  `+0.388594` (Therm) in objective, consistent with heuristic/parallel GA
  trajectory variation rather than a final-selection regression.
- Completed EPYC experiment v6 on 2026-05-27 under the new incumbent
  protocol. Hom-Cost/Hom-Therm both select the four-part all-7nm candidate
  with comparable objective `85.723683` and `T_max=305.534332 K`.
  Het-Cost selects a six-part mixed-node candidate with comparable objective
  `73.971741` and `T_max=305.695648 K`; Het-Therm's searched winner ended at
  objective `79.808777`, then final selection correctly retained the fixed
  cost incumbent at objective `73.971710` in the log (`73.971741` from the
  rounded CSV fields). Artifacts include `analysis/summary.csv`,
  `analysis/analysis.md`, `analysis/comparison_with_v5.md`, and comparison
  PNG/PDF figures. Relative to v5 selected Het-Therm, v6 reduces comparable
  objective by `3.902001` but is `0.378937 K` hotter because it now honors
  the objective rather than retaining a cooler, dominated solution.
- Implemented thermal final-selection incumbent retention on 2026-05-27.
  New `--thermal-incumbent-partition` and optional
  `--thermal-incumbent-techs` inputs allow a Cost winner to be evaluated as
  a fixed final candidate under the Thermal run's final floorplan and
  surrogate configuration. Standard homogeneous search appends that exact
  endpoint to its final result set; heterogeneous genetic search evaluates
  it after the GA without refining it and replaces the searched winner only
  when its final `J` is lower. This supplies the requested guarantee that a
  Thermal final result cannot be worse than its admitted Cost candidate on
  the final thermal objective. The v6 EPYC command entrypoint is
  `/home/yhsun/Chiplet-Partitioning/experiment_v6_epyc7282/analysis/commands.sh`.
- Completed four additional corrected v5 benchmark reruns on 2026-05-27.
  All sixteen Hom-Cost/Hom-Therm/Het-Cost/Het-Therm modes completed with
  final selected thermal records and PNG/PDF comparisons. Thermal-aware minus
  cost-only `T_max` changes are `-1.646912/-0.982574 K` for
  `48_1_14_4_1600_1600` (Hom/Het), `+0.029266/+0.074188 K` for
  `48_2_14_4_1600_1600`, `-0.056732/-1.020447 K` for `ga100`, and
  `+0.000000/+0.100067 K` for `mempool_group`. The WS2 memory guard from v4
  was retained; its largest mode, Het-Therm, completed at `159822960 KB`
  maximum RSS without allocation failure or inference fallback.
- Fixed the EPYC Hom-Cost baseline ordering inconsistency on 2026-05-26.
  Under endpoint-only final validation, Hom-Cost reported a legal
  three-part `83.387138` solution while Hom-Therm found a legal four-part
  solution with lower base cost `82.660767`: Hom-Cost had discarded
  trajectories only after reaching an invalid final floorplan. Standard
  homogeneous cost-only refinement now applies floorplan feasibility during
  FM/KL move scoring while ranking feasible candidates only by base cost. A
  temporary EPYC seed-`42` validation shows no-thermal, post-eval-only, and
  Hom-Therm choosing the identical four-part solution at base cost
  `82.660767`, with `T_max=305.534332 K` and `T_avg=301.782715 K`.
- Completed a clean repaired EPYC v5 four-mode rerun on 2026-05-26 after
  removing the previous `experiment_v5_epyc7282` outputs. With seed `42`,
  budget `300 K`, and `lambda_peak=0.1`, Hom-Cost/Hom-Therm report base costs
  `82.660800`/`82.660800` and identical peaks `305.534332 K`;
  Het-Cost/Het-Therm report base costs `71.312300`/`75.047000` and peaks
  `306.098022 K`/`305.316711 K`. All four saved final partitions match their
  selected thermal instances and fields. Summary artifacts and the readable
  two-panel comparison figure are under
  `/home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/analysis`.
- Implemented the endpoint-only ADR-0022 repair for the EPYC Hom-Cost
  missing-temperature root cause on 2026-05-25; this step is superseded by
  the refinement-feasibility correction above.
  Ordinary homogeneous search previously ranked a partition after FM/KL while
  retaining its pre-refinement floorplan success flag and coordinates; the
  reported four-part `79.741852` winner consequently had no matching feasible
  final floorplan. Standard homogeneous candidates now receive a matched
  final-floorplan feasibility check after refinement in both no-thermal and
  `--thermal-post-eval-only` runs. Thermal post-evaluation reuses the selected
  winner's matching geometry, so thermal still does not rank cost-only
  candidates. A final-validation-only SA option retains the best feasible
  floorplan encountered during annealing. At that intermediate step, EPYC
  seed `42` no-thermal and post-eval-only selected the same valid three-part winner at base cost
  `83.387138`; post-evaluation reports `T_max=305.581329 K` and
  `T_avg=302.149750 K`. That intermediate experiment output was removed when
  the final floorplan-constrained four-mode rerun replaced it.
- The pre-fix user-requested EPYC rerun on 2026-05-25 established the original
  failure symptom: Hom-Cost selected base cost `79.741852`, but that selected
  final partition had no feasible matching floorplan for thermal
  post-evaluation. Its experiment output directory was deliberately removed
  for the clean repaired rerun on 2026-05-26; these values remain historical
  diagnostic context only.
- Initially corrected EPYC v5 Hom-Cost ranking on 2026-05-25; superseded by
  matched final-geometry certification above.
  `--thermal-post-eval-only` now preserves original homogeneous cost-only
  ranking and attempts a matching final floorplan only after fixing the
  winner. With seed `42`, both no-thermal and post-eval-only select the same
  four-part winner at `79.741852`; post-evaluation cannot produce temperature
  because that fixed final partition remains floorplan-infeasible even with
  `10000 x 10000` floorplanning. The subsequent final-geometry certification
  fix supersedes this intermediate state; its temporary output was removed in
  the clean 2026-05-26 rerun.
- Fixed final-partition thermal post-evaluation geometry on 2026-05-24.
  `ThermalInstanceEncoder` now translates raw floorplanner coordinates to the
  package origin without first clamping negative coordinates, which could
  introduce an artificial overlap. Standard homogeneous
  The initial post-eval fix re-floorplanned each refined final candidate before
  evaluation, preventing stale geometry from being encoded. The 2026-05-25
  baseline correction supersedes candidate re-ranking for post-eval-only:
  it now builds matching geometry only for the already selected original-cost
  winner. Thermal-aware search still re-floorplans refined candidates for
  ranking.
- Added fixed-count control for standard homogeneous experiments on 2026-05-23:
  `run_chiplet_test.sh epyc7282 --fixed-parts 4` now restricts generated and
  accepted standard-search candidates to four active partitions. A requested
  EPYC fixed-4 comparison was run under
  `/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282`: Hom-Cost
  post-evaluates to objective `79.009962`, while Hom-Therm selects objective
  `93.465645` and is also hotter. It was recorded as a negative diagnostic and
  not adopted into `main.tex`.
- Refreshed the user-requested EPYC paper experiment on 2026-05-23 using
  `/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/commands.sh`
  and supplemental final-candidate thermal post-evaluations for both cost-only
  winners. The refreshed heterogeneous thermal run selects five chiplets with
  `3x7nm+2x10nm`, base cost approximately `74.421`, `T_max=302.880 K`,
  `T_avg=299.953 K`, and search runtime `798.43 s`. Results and the updated
  paper source are outside this repository under
  `/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282` and
  `/home/yhsun/Chiplet-Partitioning/main.tex`. This requested run uses the
  `legacy_2d_power_map` compatibility backend, not the primary
  `package_thermal` research path.
- Added a persistent DeepOHeat Python service path on 2026-05-15. C++
  `PythonDeepOHeatAdapter` now starts one long-running Python worker per
  evaluator, sends JSON-line inference requests over pipes, and falls back to
  the old subprocess path if the service is unavailable. Both legacy
  `2d_power_map` and `package_thermal` adapters support `--server` mode and
  keep imports, model weights, eval mesh/coords, and CUDA context alive across
  requests.
- Completed GA100 validation experiment V2 on 2026-05-14 after pushing thermal
  objective evaluation into partition refinement. Summary artifacts:
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/summary.csv`,
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/analysis.md`,
  and
  `/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/commands.sh`.
- Updated homogeneous refinement so thermal mode refreshes the full objective
  after fast/standard floorplanner calls and evaluates executed FM/KL moves
  with a fresh fast floorplan plus DeepOHeat thermal objective. Updated
  heterogeneous GA thermal mode so thermal is applied after the standard
  post-refinement floorplanner for each GA solution, without per-move thermal
  inside GA refinement.
- Reduced default thermal-mode log volume by hiding per-candidate cost and
  thermal objective prints unless `CHIPLET_PART_VERBOSE_COST` or
  `CHIPLET_PART_VERBOSE_THERMAL` is set.
- Completed GA100 validation experiment V1 on 2026-05-06 comparing
  homogeneous/heterogeneous cost-only runs against `--thermal` runs using
  `--thermal-budget 250`, `--seed 1`, and the pretrained legacy 2D DeepOHeat
  checkpoint. Summary artifacts:
  `/home/yhsun/Chiplet-Partitioning/experiment_v1/analysis/summary.csv`,
  `/home/yhsun/Chiplet-Partitioning/experiment_v1/analysis/analysis.md`, and
  `/home/yhsun/Chiplet-Partitioning/experiment_v1/analysis/commands.sh`.
- Fixed `GeneticTechPartitioner` initial population handling so random
  candidates with failed floorplans are assigned maximum cost and cannot become
  the GA best solution. The issue was exposed by an archived pre-fix thermal
  run at `/home/yhsun/Chiplet-Partitioning/experiment_v1/heterogeneous_thermal_pre_fix`.
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
- Added automatic thermal figure generation to `run_chiplet_test.sh --thermal`.
  After successful runs, field NPZ files are plotted into
  `<thermal-output-dir>/figures` by default, with `--thermal-figure-dir` as an
  override.

## Next Small Verifiable Task

Continue toward reliable `package_thermal` paper experiments with stronger
labels and multi-seed comparisons; keep legacy-backend reruns clearly labeled
as compatibility results.

## Recent Validation

GA100 final-selection-incumbent v6 experiment validation on 2026-05-27:

```bash
bash /home/yhsun/Chiplet-Partitioning/experiment_v6_ga100/analysis/commands.sh
```

Result: passed. All four summary rows completed and produced `4211` thermal
result JSON records plus PNG/PDF comparison figures. Hom-Therm and Het-Therm
select `temperature_source=in_search`, with comparable objectives
`38.068913 <= 38.180714` and `36.354332 <= 36.633680`, respectively. The
heterogeneous thermal log records fixed incumbent objective `37.380592`,
searched winner objective `36.354294`, and retention of the searched winner.
No error, exception, failed, or inference-fallback marker was found in the
four run logs.

EPYC final-selection-incumbent v6 experiment validation on 2026-05-27:

```bash
bash /home/yhsun/Chiplet-Partitioning/experiment_v6_epyc7282/analysis/commands.sh
```

Result: passed. The run produced four completed summary rows, four saved
final solutions, `2930` thermal result JSON records in total, and PNG/PDF
comparison figures. Selected instances for Hom-Therm and Het-Therm carry
`search_stage=cost_incumbent_final_candidate`. No error, exception, failed,
or inference-fallback marker was found in the four run logs. Het-Therm
logged searched objective `79.808777`, fixed incumbent objective
`73.971710`, and selection of the fixed incumbent as the final winner.

Thermal incumbent protocol implementation validation on 2026-05-27:

```bash
bash -n run_chiplet_test.sh
cmake --build build --target chipletPart thermal_mvp_test floorplan_retention_test thermal_collect_cli -j 4
ctest --test-dir build --output-on-failure
./run_chiplet_test.sh epyc7282 --seed 42 --thermal-mock \
  --thermal-budget 300 --thermal-lambda-peak 0.1 \
  --thermal-output-dir /tmp/chipletpart_v6_hom_incumbent_mock \
  --thermal-incumbent-partition /home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/homogeneous_cost_only/final_partition.parts
./run_chiplet_test.sh epyc7282 --genetic --tech-nodes 7nm,10nm,45nm \
  --generations 1 --population 4 --seed 42 --thermal-mock \
  --thermal-budget 300 --thermal-lambda-peak 0.1 \
  --thermal-output-dir /tmp/chipletpart_v6_het_incumbent_mock \
  --thermal-incumbent-partition /home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/heterogeneous_cost_only/final_partition.parts \
  --thermal-incumbent-techs /home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/heterogeneous_cost_only/final_partition.techs
```

Result: passed. Both CTest tests passed; the existing Eigen deprecation
warning remains. The homogeneous mock run logged and selected its added
fixed incumbent at objective `82.660767`. The short heterogeneous mock run
selected its fixed incumbent at `71.312340` over a searched objective of
`109.146767`. `nvidia-smi` and the DeepOHeat PyTorch environment also report
two available NVIDIA GeForce RTX 4090 devices before the real rerun.

Additional corrected v5 benchmark rerun validation on 2026-05-27:

```bash
bash /home/yhsun/Chiplet-Partitioning/experiment_v5_48_1_14_4_1600_1600/analysis/commands.sh
bash /home/yhsun/Chiplet-Partitioning/experiment_v5_ga100/analysis/commands.sh
bash /home/yhsun/Chiplet-Partitioning/experiment_v5_mempool_group/analysis/commands.sh
bash /home/yhsun/Chiplet-Partitioning/experiment_v5_48_2_14_4_1600_1600/analysis/commands.sh
```

Result: all sixteen summary rows report `completed`; all selected thermal
result JSON files, field NPZ files, final solution artifacts, and comparison
figures exist. A structured consistency check matched final partitions to
selected instances directly for the two waferscale cases and validated the
established hierarchical expansions for `mempool_group` (`36 -> 40`) and
`ga100` (`45 -> 179`), along with final technology assignments. WS2 completed
under the retained one-worker/one-thread allocator guard with driver maximum
RSS `159822960 KB`; no OOM or thermal-service fallback was found. Intermediate
GA candidate-size diagnostics were present in `48_1_14_4_1600_1600` and
`mempool_group`, but both runs saved valid final solutions.

Homogeneous floorplan-constrained baseline validation on 2026-05-26:

```bash
cmake --build build --target chipletPart thermal_mvp_test floorplan_retention_test thermal_collect_cli -j 4
ctest --test-dir build --output-on-failure
./run_chiplet_test.sh epyc7282 --seed 42
./run_chiplet_test.sh epyc7282 --seed 42 \
  --thermal --thermal-backend legacy_2d_power_map \
  --thermal-budget 300 --thermal-lambda-peak 0 \
  --thermal-device auto \
  --thermal-output-dir /home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/homogeneous_cost_only/thermal_post_eval \
  --thermal-post-eval-only
```

Result: build passed with the pre-existing Eigen `initParallel()`
deprecation warning; both CTest tests passed. The no-thermal and
post-eval-only paths select the identical four-part, matching-final-geometry
winner with base cost `82.660767`. Hom-Therm selects that identical solution
with penalized objective `85.723648`. The post-evaluation persisted one real
legacy DeepOHeat thermal field and reports `T_max=305.534332 K`,
`T_avg=301.782715 K`; inference used `cuda:0`.

Requested clean EPYC four-mode rerun validation on 2026-05-26:

```bash
bash /home/yhsun/Chiplet-Partitioning/experiment_v5_epyc7282/analysis/commands.sh
```

Result: passed. The output directory contains four final solutions, one
thermal post-evaluation for each cost-only winner, `307` homogeneous thermal
search records, `2816` heterogeneous thermal search records, a CSV summary,
an analysis report, and PNG/PDF comparison figures. The four selected
thermal records exactly match their saved final partition and technology
files. The runs used the legacy compatibility backend on available RTX 4090
GPU inference; no thermal inference failure or fallback was found in the run
logs.

Final-partition post-evaluation geometry fix validation on 2026-05-24:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
cd build && ctest -R thermal_mvp_test --output-on-failure
```

Result: passed. The thermal MVP test now confirms that true overlaps are
rejected while a separated layout with a negative floorplanner coordinate is
accepted after package-origin translation.

```bash
./run_chiplet_test.sh epyc7282 --seed 1 \
  --thermal --thermal-budget 300 --thermal-lambda-peak 0 \
  --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_epyc_post_eval_coordinate_fix \
  --thermal-post-eval-only
```

Result: passed with one real DeepOHeat field. The newly re-floorplanned
cost-only final candidate has three parts, base cost `84.825104`,
`T_max=307.117035 K`, and `T_avg=301.992432 K`.

Cost-only baseline final-geometry validation on 2026-05-25:

```bash
./run_chiplet_test.sh epyc7282 --seed 42
./run_chiplet_test.sh epyc7282 --seed 42 \
  --thermal --thermal-backend legacy_2d_power_map \
  --thermal-budget 300 --thermal-lambda-peak 0 \
  --thermal-device auto --thermal-output-dir /tmp/chipletpart_epyc_hom_original_post_eval/thermal_post_eval \
  --thermal-post-eval-only
```

Result: passed. Both paths select identical four-part partition files and
base cost `79.741852`; the post-evaluation path reports that the fixed
original winner has no feasible matching final floorplan and emits no
thermal field. This preserves original cost-only behavior and prevents a
three-part feasible substitute from being mislabeled as the baseline.

EPYC homogeneous fixed-4 follow-up validation on 2026-05-23:

```bash
./run_chiplet_test.sh epyc7282 --seed 1 --fixed-parts 4
./run_chiplet_test.sh epyc7282 --seed 1 --fixed-parts 4 \
  --thermal --thermal-budget 300 --thermal-lambda-peak 0.1 \
  --thermal-device auto --thermal-post-eval-only
./run_chiplet_test.sh epyc7282 --seed 1 --fixed-parts 4 \
  --thermal --thermal-budget 300 --thermal-lambda-peak 0.1 \
  --thermal-device auto --thermal-cache
```

Result: passed as runs, but failed the adoption criterion. Hom-Cost thermal
post-evaluation gives objective `79.009962` (`T_max=302.888336 K`), whereas
Hom-Therm gives objective `93.465645` (`T_max=306.220642 K`). The 55 visited
Hom-Therm thermal records have minimum reconstructed objective `82.158156791`,
still worse than the baseline. Outputs are documented at
`/home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/fixed4_homogeneous_analysis.md`.

```bash
bash -n run_chiplet_test.sh
cmake --build build --target chipletPart thermal_mvp_test -j 4
cd build && ctest -R thermal_mvp_test --output-on-failure
```

Result: passed; the build emitted the pre-existing Eigen `initParallel()`
deprecation warning.

EPYC paper-data refresh validation on 2026-05-23:

```bash
bash /home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/analysis/commands.sh
```

Result: passed. Homogeneous thermal output contains `306` matching manifest
records and NPZ fields; heterogeneous thermal output contains `2481` matching
manifest records and NPZ fields. Both cost-only final-candidate
post-evaluations completed and contain one thermal field each.

```bash
diff -u \
  /home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/heterogeneous_thermal/final_partition.parts \
  <(jq -r '.partition[]' /home/yhsun/Chiplet-Partitioning/experiment_v3_epyc7282/heterogeneous_thermal/thermal/instances/epyc7282_thermal_seed1_20260523_155548_15168f2d9859afcb.json)
```

Result: passed with no differences; the thermal-result record used for the
paper table corresponds to the preserved final partition.

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -outdir=/tmp/chiplet_partitioning_latex_epyc_rerun \
  /home/yhsun/Chiplet-Partitioning/main.tex
```

Result: blocked by the pre-existing missing input file
`picture/thermal_factors.png`; PDF generation does not reach a failure caused
by the EPYC text/table edits.

Persistent DeepOHeat service validation on 2026-05-15:

```bash
python3 -m py_compile \
  DeepOHeat/scripts/infer_package.py \
  DeepOHeat/package_thermal/infer_package.py
```

Result: passed.

```bash
cmake --build build --target chipletPart thermal_mvp_test -j 4
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

Result: passed, 13 tests.

```bash
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader
```

Result: two NVIDIA GeForce RTX 4090 GPUs visible with driver `570.124.06`.
The DeepOHeat environment reports PyTorch `2.0.0+cu117`, CUDA available, and
two visible CUDA devices.

```bash
/usr/bin/time -f 'SERVICE_TWO_CALLS_ELAPSED_SEC=%e' bash -c '... | \
  /home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  /home/yhsun/Chiplet-Partitioning/DeepOHeat/scripts/infer_package.py \
  --server \
  --model /home/yhsun/Chiplet-Partitioning/DeepOHeat/DeepOHeat/2d_power_map/log/experiment_1/checkpoints/model_epoch_10000.pth \
  --device auto'
```

Result: passed on an archived GA100 thermal instance. The service processed
two requests in one worker; service-reported inference runtime was about
`0.512 s` for the first request and `0.013 s` for the second request, showing
that the model/CUDA setup was reused.

```bash
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 1 \
  --seed 42 --thermal --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_persistent_service_smoke \
  --thermal-cache
```

Result: passed in `8.12 s`; C++ started the persistent DeepOHeat service and
completed two single-partition thermal evaluations.

```bash
./run_chiplet_test.sh 48_1_14_4_1600_1600 \
  --seed 7 --thermal --thermal-budget 250 --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_refinement_persistent_real_smoke \
  --thermal-cache
```

Result: passed in `203.39 s`. The run wrote `658` manifest records,
`658` thermal result JSON files, and `658` field NPZ files under
`/tmp/chipletpart_refinement_persistent_real_smoke`.

GA100 refinement-thermal validation on 2026-05-14:

```bash
cmake --build build --target chipletPart thermal_mvp_test -j 4
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

Result: passed, 13 tests.

```bash
./run_chiplet_test.sh 48_1_14_4_1600_1600 \
  --seed 7 --thermal-mock --thermal-budget 250 \
  --thermal-output-dir /tmp/chipletpart_refinement_thermal_mock2 \
  --thermal-cache
```

Result: passed and wrote 652 mock thermal manifest records.

```bash
/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/commands.sh
```

Result: passed. V2 summary is archived under
`/home/yhsun/Chiplet-Partitioning/experiment_v2_ga100/analysis/summary.csv`.

Thermal figure post-processing validation on 2026-05-05:

```bash
bash -n run_chiplet_test.sh
```

Result: passed.

```bash
cmake --build build --target chipletPart thermal_mvp_test -j 4
```

Result: passed.

```bash
cd build
ctest -R thermal_mvp_test --output-on-failure
```

Result: passed.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tests/thermal/test_thermal_pipeline.py
```

Result: passed, 13 tests in 4.772 seconds.

```bash
/home/yhsun/Chiplet-Partitioning/DeepOHeat/.conda/deepoheat-py38/bin/python \
  tools/thermal/plot_deepoheat_npz.py \
  --out-dir /tmp/chipletpart_ga100_block_raster_smoke/figures_test \
  /tmp/chipletpart_ga100_block_raster_smoke/instances/*.thermal_result.field.npz
```

Result: passed and wrote PNG figures.

```bash
./run_chiplet_test.sh ga100 \
  --tech-enum --tech-nodes 7nm,14nm --max-partitions 1 \
  --seed 42 --thermal --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_ga100_auto_figures_smoke \
  --thermal-cache
```

Result: passed. The run wrote 2 thermal instance JSON files, 2 thermal result
JSON files, 2 field NPZ files, and 12 PNG figures under
`/tmp/chipletpart_ga100_auto_figures_smoke/figures`.

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

## Experiment V4 Rerun And GA100 Hierarchical Floorplan Fix On 2026-05-24

The v4 rerun follows the v3 protocol with seed `1`, homogeneous and
heterogeneous `cost-only`/`thermal` modes, and final-winner thermal
post-evaluation for both cost-only modes. Completed and analyzed results are
available for all five requested benchmarks:

- `/home/yhsun/Chiplet-Partitioning/experiment_v4_48_1_14_4_1600_1600`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_48_2_14_4_1600_1600`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_epyc7282`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_mempool_group`
- `/home/yhsun/Chiplet-Partitioning/experiment_v4_ga100`

Each directory contains `analysis/commands.sh`, `analysis/summary.csv`,
`analysis/analysis.md`, and PNG/PDF partition-plus-temperature comparison
figures. Verification found one final thermal-result field for each of the ten
cost-only post-evaluations and no failed formal run logs.

The first formal GA100 attempt failed during homogeneous cost-only final
post-evaluation with `Overlapping chiplets in encoded floorplan: 0 and 1`.
GA100 maps 179 detailed block records to 45 netlist vertices; the thermal
encoder used detailed block area while `GenerateNetlist` still floorplanned
only the smaller netlist-vertex area. The resulting stored coordinates could
not contain the physical chiplet rectangles.

The fix exposes the established thermal block-to-vertex mapping for reuse by
`FMRefiner::GenerateNetlist` and constructs hierarchical floorplan weights by
accumulating mapped, technology-scaled detailed block areas. This retains
block-level power rasterization while making the physical footprint consistent
with thermal encoding.

Validation:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
ctest --test-dir build -R thermal_mvp_test --output-on-failure
./run_chiplet_test.sh ga100 --seed 1 \
  --thermal --thermal-budget 300 --thermal-lambda-peak 0 \
  --thermal-device auto \
  --thermal-output-dir /tmp/chipletpart_ga100_hierarchical_floorplan_smoke_20260524 \
  --thermal-post-eval-only
```

Result: build and test passed. The real GA100 post-evaluation completed with
one block-level thermal field and reported `base=32.704578`,
`T_max=307.324463 K`, and `T_avg=303.450958 K`. The formal GA100 directory
was subsequently cleared and rerun successfully with the fixed binary.

Peak-temperature changes for thermal-aware minus cost-only final solutions:

| Benchmark | Homogeneous delta (K) | Heterogeneous delta (K) |
| --- | ---: | ---: |
| `48_1_14_4_1600_1600` | `+0.127014` | `-2.700043` |
| `48_2_14_4_1600_1600` | `-2.167236` | `-1.022186` |
| `epyc7282` | `-0.145508` | `-1.816315` |
| `mempool_group` | `-1.724731` | `-0.003815` |
| `ga100` | `-0.087463` | `-0.890320` |

Operational note: WS2 (`48_2_14_4_1600_1600`) Het-Cost reached
`136630256 KB` maximum RSS. Its final post-evaluation could not fork the
persistent Python service under that pressure, fell back to the single-call
inference path, and completed with a valid selected result; this is recorded
in that case's `analysis/analysis.md`.

## Current Blockers

- GPU state is currently good in this shell/Python environment, but it remains
  environment-sensitive. Recheck before long training or GPU sweeps.
- Reference labels are still generated by a simplified 2D effective solver, not
  a signoff-quality thermal solver.
- Dataset V3 pilot is still small and single-benchmark. It is better than the
  smoke for surrogate debugging, but not a final paper-scale dataset.
- Surrogate error on final candidates is still significant and requires
  calibration, larger data, and revalidation.

## Latest Validation

2026-05-06:

```bash
cmake --build build --target chipletPart thermal_mvp_test thermal_collect_cli -j 4
```

Result: passed.

```bash
cd build
ctest -R thermal_mvp_test --output-on-failure
```

Result: passed, 1/1 test.

## Current Do-Not-Do List

- Do not break cost-only ChipletPart behavior.
- Do not make floorplan the primary output.
- Do not treat `legacy_2d_power_map` as the research method.
- Do not present the simplified reference solver as final ground truth.
- Do not add unsupported technology nodes casually; previous Codex-reported
  runs hit unsupported scaling for `45nm -> 28nm`.
- Do not push.
- Do not combine unrelated user changes into milestone commits.

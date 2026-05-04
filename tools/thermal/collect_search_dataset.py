#!/usr/bin/env python3
"""Collect a small provenance-aware thermal dataset from ChipletPart search dumps."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import collect_instances
import reference_solver
import split_manifest
import summarize_labels
import validate_instance


TESTCASE_FILES = [
    "io_definitions.xml",
    "layer_definitions.xml",
    "wafer_process_definitions.xml",
    "assembly_process_definitions.xml",
    "test_definitions.xml",
    "block_level_netlist.xml",
    "block_definitions.txt",
]


def read_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def testcase_paths(testcase: Path) -> dict[str, Path]:
    paths = {name: testcase / name for name in TESTCASE_FILES}
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise SystemExit(f"missing testcase files: {missing}")
    return paths


def snapshot_side_effects(testcase: Path) -> dict[Path, bytes | None]:
    netlist = testcase / "block_level_netlist.xml"
    paths = [
        netlist.with_name(netlist.name + ".best_tech_assignment.txt"),
        netlist.with_name(netlist.name + ".canonical_forms.log"),
        netlist.with_name(netlist.name + ".best_partition.txt"),
    ]
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def restore_side_effects(snapshot: dict[Path, bytes | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)


def run_chipletpart(
    *,
    chipletpart: Path,
    testcase: Path,
    run_dir: Path,
    seed: int,
    run_id: str,
    reach: float,
    separation: float,
    tech_nodes: str,
    max_partitions: int,
    grid_x: int,
    grid_y: int,
) -> Path:
    files = testcase_paths(testcase)
    instances_dir = run_dir / "instances"
    manifest = run_dir / "manifest_raw.jsonl"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest.unlink(missing_ok=True)
    log_path = run_dir / "chipletpart.log"

    cmd = [
        str(chipletpart),
        str(files["io_definitions.xml"]),
        str(files["layer_definitions.xml"]),
        str(files["wafer_process_definitions.xml"]),
        str(files["assembly_process_definitions.xml"]),
        str(files["test_definitions.xml"]),
        str(files["block_level_netlist.xml"]),
        str(files["block_definitions.txt"]),
        str(reach),
        str(separation),
        "--tech-enum",
        "--tech-nodes",
        tech_nodes,
        "--max-partitions",
        str(max_partitions),
        "--seed",
        str(seed),
        "--enable_thermal",
        "--thermal_use_mock",
        "--thermal_backend",
        "mock",
        "--thermal_budget",
        "1000000000",
        "--thermal_lambda_peak",
        "0",
        "--thermal_grid_x",
        str(grid_x),
        "--thermal_grid_y",
        str(grid_y),
        "--thermal_dump_instances",
        str(instances_dir),
        "--thermal_dump_manifest",
        str(manifest),
        "--thermal_dump_prefix",
        run_id,
        "--thermal_dump_split",
        "raw",
        "--thermal_source_testcase",
        testcase.name,
        "--thermal_run_id",
        run_id,
        "--thermal_candidate_source",
        "chipletpart_search",
        "--thermal_search_stage",
        "search_candidate",
        "--thermal_seed",
        str(seed),
        "--thermal_cache",
    ]
    snapshot = snapshot_side_effects(testcase)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
    finally:
        restore_side_effects(snapshot)
    return manifest


def merge_manifests(manifests: list[Path], out_manifest: Path) -> tuple[list[dict], int, int]:
    records: list[dict] = []
    seen_hashes: set[str] = set()
    raw_count = 0
    skipped_duplicates = 0
    for manifest in manifests:
        for record in read_jsonl(manifest):
            raw_count += 1
            augmented = collect_instances.augment_record(record)
            instance_hash = augmented["instance_hash"]
            if instance_hash in seen_hashes:
                skipped_duplicates += 1
                continue
            seen_hashes.add(instance_hash)
            records.append(augmented)
    write_jsonl(out_manifest, records)
    return records, raw_count, skipped_duplicates


def validate_records(records: list[dict]) -> int:
    invalid = 0
    for record in records:
        try:
            validate_instance.validate_instance(Path(record["json_path"]))
        except Exception as exc:
            invalid += 1
            record["validation_error"] = str(exc)
    return invalid


def label_manifest(manifest: Path, out_dir: Path, args: argparse.Namespace) -> Path:
    solver_args = argparse.Namespace(
        max_iter=args.max_iter,
        tol=args.tol,
        method=args.method,
        omega=args.omega,
        source_scale=args.source_scale,
        h_scale=args.h_scale,
        overwrite=True,
        skip_existing=False,
        invalid_residual=args.invalid_residual,
        num_workers=args.num_workers,
    )
    return reference_solver.solve_manifest(
        manifest,
        out_dir,
        args.out_dir / "manifest_labeled.jsonl",
        solver_args,
    )


def write_split_outputs(manifest: Path, out_dir: Path, args: argparse.Namespace) -> dict[str, int]:
    records = split_manifest.read_jsonl(manifest)
    split_records = split_manifest.split_records(
        records,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.split_seed,
    )
    split_manifest.write_jsonl(out_dir / "manifest_split.jsonl", split_records)
    counts: dict[str, int] = {}
    for split in ["train", "val", "test"]:
        subset = [record for record in split_records if record.get("split") == split]
        counts[split] = len(subset)
        split_manifest.write_jsonl(out_dir / f"manifest_{split}.jsonl", subset)
    return counts


def write_summary_markdown(path: Path, summary: dict, label_summary: dict | None) -> None:
    lines = [
        "# Dataset V3 Pilot Summary",
        "",
        f"- raw instances: {summary['raw_instance_count']}",
        f"- unique instances: {summary['unique_instance_count']}",
        f"- skipped duplicates: {summary['skipped_duplicate_count']}",
        f"- invalid instances: {summary['invalid_count']}",
        f"- candidate_source: {summary['count_by_candidate_source']}",
        f"- search_stage: {summary['count_by_search_stage']}",
        f"- grid size: {summary['count_by_grid_size']}",
        f"- split: {summary.get('split_counts', {})}",
        f"- labels exist: {summary['labels_exist']}",
    ]
    if label_summary:
        lines.extend(
            [
                "",
                "## Labels",
                "",
                f"- num labels: {label_summary['num_labels']}",
                f"- invalid labels: {label_summary['invalid_labels']}",
                f"- T_max: {label_summary['t_max']}",
                f"- T_avg: {label_summary['t_avg']}",
                "",
                "These labels use the simplified 2D effective reference solver "
                "for pilot development only; they are not signoff ground truth.",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chipletpart_build", type=Path, required=True)
    parser.add_argument("--testcase", type=Path, nargs="+", required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--grid_x", type=int, default=16)
    parser.add_argument("--grid_y", type=int, default=16)
    parser.add_argument("--tech_nodes", default="7nm,14nm")
    parser.add_argument("--max_partitions", type=int, default=3)
    parser.add_argument("--reach", type=float, default=0.5)
    parser.add_argument("--separation", type=float, default=0.25)
    parser.add_argument("--skip_labels", action="store_true")
    parser.add_argument("--method", choices=["scipy_sparse", "jacobi", "sor", "auto"], default="auto")
    parser.add_argument("--max_iter", type=int, default=1000)
    parser.add_argument("--tol", type=float, default=1.0e-6)
    parser.add_argument("--omega", type=float, default=0.85)
    parser.add_argument("--source_scale", type=float, default=2.0)
    parser.add_argument("--h_scale", type=float, default=0.05)
    parser.add_argument("--invalid_residual", type=float, default=5.0e-2)
    parser.add_argument("--num_workers", type=int, default=1)
    parser.add_argument("--train_ratio", type=float, default=0.7)
    parser.add_argument("--val_ratio", type=float, default=0.15)
    parser.add_argument("--test_ratio", type=float, default=0.15)
    parser.add_argument("--split_seed", type=int, default=2026)
    args = parser.parse_args()

    args.chipletpart_build = args.chipletpart_build.resolve()
    args.out_dir = args.out_dir.resolve()
    args.testcase = [path.resolve() for path in args.testcase]
    chipletpart = args.chipletpart_build / "bin" / "chipletPart"
    if not chipletpart.exists():
        raise SystemExit(f"{chipletpart} not found; build chipletPart first")
    if args.out_dir.exists():
        shutil.rmtree(args.out_dir)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifests = []
    for testcase in args.testcase:
        testcase_paths(testcase)
        for seed in args.seeds:
            run_id = f"v3_{testcase.name}_seed{seed}"
            run_dir = args.out_dir / "raw" / testcase.name / f"seed_{seed}"
            print(f"[THERMAL-DATA] collecting run_id={run_id}", flush=True)
            manifests.append(
                run_chipletpart(
                    chipletpart=chipletpart,
                    testcase=testcase,
                    run_dir=run_dir,
                    seed=seed,
                    run_id=run_id,
                    reach=args.reach,
                    separation=args.separation,
                    tech_nodes=args.tech_nodes,
                    max_partitions=args.max_partitions,
                    grid_x=args.grid_x,
                    grid_y=args.grid_y,
                )
            )

    manifest_raw = args.out_dir / "manifest_raw.jsonl"
    records, raw_count, skipped_duplicates = merge_manifests(manifests, manifest_raw)
    invalid_count = validate_records(records)
    write_jsonl(manifest_raw, records)

    manifest_for_summary = manifest_raw
    label_summary = None
    if not args.skip_labels:
        manifest_labeled = label_manifest(manifest_raw, args.out_dir / "labels", args)
        manifest_for_summary = manifest_labeled
        label_summary = summarize_labels.summarize(summarize_labels.read_jsonl(manifest_labeled))
        with (args.out_dir / "label_summary.json").open("w", encoding="utf-8") as f:
            json.dump(label_summary, f, indent=2, sort_keys=True)
        summarize_labels.write_markdown(args.out_dir / "label_summary.md", label_summary)

    split_counts = write_split_outputs(manifest_for_summary, args.out_dir, args)
    final_records = read_jsonl(args.out_dir / "manifest_split.jsonl")
    summary = collect_instances.summarize_records(
        final_records,
        raw_instance_count=raw_count,
        skipped_duplicate_count=skipped_duplicates,
        invalid_count=invalid_count,
    )
    summary.update(
        {
            "pilot": "dataset_v3_search_candidate",
            "out_dir": str(args.out_dir),
            "raw_manifest_path": str(manifest_raw),
            "manifest_path": str(manifest_for_summary),
            "label_summary_json": str(args.out_dir / "label_summary.json") if label_summary else "",
            "split_manifest_path": str(args.out_dir / "manifest_split.jsonl"),
            "split_counts": split_counts,
            "benchmarks": [path.name for path in args.testcase],
            "seeds": args.seeds,
            "grid_x": args.grid_x,
            "grid_y": args.grid_y,
            "tech_nodes": args.tech_nodes,
            "max_partitions": args.max_partitions,
            "reference_solver": "simplified_2d_effective" if label_summary else "",
        }
    )
    with (args.out_dir / "manifest_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_summary_markdown(args.out_dir / "RUN_SUMMARY.md", summary, label_summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

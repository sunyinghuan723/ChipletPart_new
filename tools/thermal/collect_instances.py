#!/usr/bin/env python3
"""Collect package-level thermal instances through ChipletPart's encoder."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _split_for_index(index: int, total: int) -> str:
    if total <= 2:
        return "train"
    frac = index / float(total)
    if frac < 0.7:
        return "train"
    if frac < 0.85:
        return "val"
    return "test"


def _required_testcase_files(testcase: Path) -> dict:
    files = {
        "io": testcase / "io_definitions.xml",
        "netlist": testcase / "block_level_netlist.xml",
        "blocks": testcase / "block_definitions.txt",
    }
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise SystemExit(f"missing testcase files: {missing}")
    return files


def _parse_grid_sizes(values: list[str] | None, grid_x: int, grid_y: int) -> list[tuple[int, int]]:
    if not values:
        return [(grid_x, grid_y)]
    grids = []
    for value in values:
        if "x" not in value.lower():
            raise SystemExit(f"invalid --grid_sizes entry {value!r}; expected e.g. 32x32")
        gx, gy = value.lower().split("x", 1)
        grids.append((int(gx), int(gy)))
    return grids


def _stable_instance_hash(instance_path: Path) -> str:
    with instance_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    grid_y = int(data.get("grid_y", data.get("grid", {}).get("y")))
    grid_x = int(data.get("grid_x", data.get("grid", {}).get("x")))
    power = data.get("channels", {}).get("power_density_w_per_mm2", [])
    payload = {
        "partition": data.get("partition", []),
        "technology_assignment": data.get("technology_assignment", []),
        "grid_x": grid_x,
        "grid_y": grid_y,
        "chiplets": [
            {
                "technology": chip.get("technology", ""),
                "x_mm": round(float(chip.get("x_mm", 0.0)), 6),
                "y_mm": round(float(chip.get("y_mm", 0.0)), 6),
                "width_mm": round(float(chip.get("width_mm", 0.0)), 6),
                "height_mm": round(float(chip.get("height_mm", 0.0)), 6),
                "total_power": round(float(chip.get("total_power", 0.0)), 6),
            }
            for chip in data.get("chiplets", [])
        ],
        "power": [round(float(v), 9) for v in power],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _technology_assignment_summary(technology_assignment: list[str]) -> dict:
    return dict(Counter(str(tech) for tech in technology_assignment))


def _first_present(*values, default=None):
    for value in values:
        if value is not None:
            return value
    return default


def augment_record(record: dict) -> dict:
    instance_path = Path(record["json_path"])
    with instance_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    chiplets = data.get("chiplets", [])
    provenance = data.get("provenance", {})
    record = dict(record)
    dump_instance_hash = record.get("instance_hash") or data.get("instance_hash")
    if dump_instance_hash:
        record["dump_instance_hash"] = dump_instance_hash
    record["instance_hash"] = _stable_instance_hash(instance_path)
    record["grid_x"] = int(data.get("grid_x", data.get("grid", {}).get("x", 0)))
    record["grid_y"] = int(data.get("grid_y", data.get("grid", {}).get("y", 0)))
    record["num_chiplets"] = int(record.get("num_chiplets", len(chiplets)))
    record["testcase"] = record.get("testcase", data.get("source_testcase", "unknown"))
    record["benchmark"] = record.get("benchmark", data.get("source_testcase", "unknown"))
    record["technology_assignment"] = record.get(
        "technology_assignment", data.get("technology_assignment", [])
    )
    record["technology_assignment_summary"] = record.get(
        "technology_assignment_summary",
        data.get(
            "technology_assignment_summary",
            provenance.get(
                "technology_assignment_summary",
                _technology_assignment_summary(record["technology_assignment"]),
            ),
        ),
    )
    record["total_power"] = float(
        record.get("total_power", data.get("total_power_before_raster", 0.0))
    )
    if "cost" not in record and data.get("cost_objective") is not None:
        record["cost"] = data.get("cost_objective")
    record["run_id"] = _first_present(
        record.get("run_id"), data.get("run_id"), provenance.get("run_id"), default=""
    )
    record["seed"] = _first_present(
        record.get("seed"), data.get("seed"), provenance.get("seed"), default=""
    )
    record["candidate_index"] = _first_present(
        record.get("candidate_index"),
        data.get("candidate_index"),
        provenance.get("candidate_index"),
        default=None,
    )
    record["candidate_source"] = _first_present(
        record.get("candidate_source"),
        data.get("candidate_source"),
        provenance.get("candidate_source"),
        default="unknown",
    )
    record["search_stage"] = _first_present(
        record.get("search_stage"),
        data.get("search_stage"),
        provenance.get("search_stage"),
        default="unknown",
    )
    record["thermal_enabled"] = bool(
        _first_present(
            record.get("thermal_enabled"),
            data.get("thermal_enabled"),
            provenance.get("thermal_enabled"),
            default=False,
        )
    )
    record["floorplan_feasible"] = bool(
        _first_present(
            record.get("floorplan_feasible"),
            data.get("floorplan_feasible"),
            provenance.get("floorplan_feasible"),
            default=False,
        )
    )
    record["io_feasible"] = bool(
        _first_present(
            record.get("io_feasible"),
            data.get("io_feasible"),
            provenance.get("io_feasible"),
            default=False,
        )
    )
    generation_time = _first_present(
        record.get("generation_time_unix_sec"),
        data.get("generation_time_unix_sec"),
        provenance.get("generation_time_unix_sec"),
        default=None,
    )
    if generation_time is not None:
        record["generation_time_unix_sec"] = generation_time
    return record


def _augment_record(record: dict) -> dict:
    return augment_record(record)


def summarize_records(
    records: list[dict],
    *,
    raw_instance_count: int | None = None,
    skipped_duplicate_count: int = 0,
    invalid_count: int = 0,
) -> dict:
    raw_count = len(records) if raw_instance_count is None else raw_instance_count
    unique_hashes = {record.get("instance_hash") for record in records if record.get("instance_hash")}
    label_count = 0
    for record in records:
        label_path = record.get("label_path")
        if label_path and Path(label_path).exists():
            label_count += 1
    source_counts = Counter(record.get("candidate_source") or "unknown" for record in records)
    stage_counts = Counter(record.get("search_stage") or "unknown" for record in records)
    grid_counts = Counter(
        f"{record.get('grid_x', 0)}x{record.get('grid_y', 0)}" for record in records
    )
    split_counts = Counter(record.get("split") or "unsplit" for record in records)
    return {
        "raw_instance_count": int(raw_count),
        "unique_instance_count": int(len(records)),
        "unique_instance_hash_count": int(len(unique_hashes)),
        "skipped_duplicate_count": int(skipped_duplicate_count),
        "invalid_count": int(invalid_count),
        "invalid_or_skipped_count": int(invalid_count + skipped_duplicate_count),
        "count_by_candidate_source": dict(sorted(source_counts.items())),
        "count_by_search_stage": dict(sorted(stage_counts.items())),
        "count_by_grid_size": dict(sorted(grid_counts.items())),
        "count_by_split": dict(sorted(split_counts.items())),
        "num_labeled_records": int(label_count),
        "labels_exist": bool(records and label_count == len(records)),
        "any_labels_exist": bool(label_count > 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chipletpart_build", type=Path, required=True)
    parser.add_argument("--testcase", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--num_instances", type=int, default=20)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--grid_x", type=int, default=32)
    parser.add_argument("--grid_y", type=int, default=32)
    parser.add_argument("--grid_sizes", nargs="+")
    parser.add_argument("--tech_nodes", default="7nm,14nm")
    parser.add_argument("--tech_node_sets", nargs="+")
    parser.add_argument("--max_chiplets", type=int, nargs="+", default=[6])
    parser.add_argument("--prefix", default="thermal_instance")
    parser.add_argument("--run_id", default="")
    parser.add_argument("--candidate_source", default="synthetic_helper")
    parser.add_argument("--search_stage", default="synthetic_random_shelf")
    parser.add_argument("--summary_json", type=Path)
    args = parser.parse_args()

    helper = args.chipletpart_build / "bin" / "thermal_collect_cli"
    if not helper.exists():
        raise SystemExit(
            f"{helper} not found. Build it with: "
            f"cmake --build {args.chipletpart_build} --target thermal_collect_cli"
        )

    testcase = args.testcase.resolve()
    files = _required_testcase_files(testcase)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    final_manifest = args.out_dir / "manifest.jsonl"
    final_manifest.unlink(missing_ok=True)

    tech_sets = args.tech_node_sets or [args.tech_nodes]
    grids = _parse_grid_sizes(args.grid_sizes, args.grid_x, args.grid_y)
    jobs = [
        (seed, max_chiplets, tech_nodes, grid)
        for seed in args.seeds
        for max_chiplets in args.max_chiplets
        for tech_nodes in tech_sets
        for grid in grids
    ]
    if not jobs:
        raise SystemExit("no collection jobs requested")
    count_per_job = max(1, math.ceil(args.num_instances / len(jobs)))

    records = []
    seen_hashes: set[str] = set()
    raw_instance_count = 0
    skipped_duplicate_count = 0
    for job_index, (seed, max_chiplets, tech_nodes, grid) in enumerate(jobs):
        if len(records) >= args.num_instances:
            break
        gx, gy = grid
        count = min(count_per_job, args.num_instances - len(records))
        job_dir = (
            args.out_dir
            / f"seed_{seed}"
            / f"chiplets_{max_chiplets}"
            / f"tech_{tech_nodes.replace(',', '_').replace('/', '_')}"
            / f"grid_{gx}x{gy}"
        )
        if job_dir.exists():
            shutil.rmtree(job_dir)
        seed_manifest = job_dir / "manifest.jsonl"
        run_id = args.run_id or f"{args.prefix}_seed{seed}_job{job_index}"
        cmd = [
            str(helper),
            "--io",
            str(files["io"]),
            "--netlist",
            str(files["netlist"]),
            "--blocks",
            str(files["blocks"]),
            "--out_dir",
            str(job_dir),
            "--manifest",
            str(seed_manifest),
            "--num_instances",
            str(count),
            "--seed",
            str(seed),
            "--grid_x",
            str(gx),
            "--grid_y",
            str(gy),
            "--source_testcase",
            testcase.name,
            "--tech_nodes",
            tech_nodes,
            "--max_chiplets",
            str(max_chiplets),
            "--prefix",
            f"{args.prefix}_s{seed}_c{max_chiplets}_g{gx}x{gy}_j{job_index}",
            "--run_id",
            run_id,
            "--candidate_source",
            args.candidate_source,
            "--search_stage",
            args.search_stage,
        ]
        print(f"[THERMAL-DATA] running {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, check=True)
        with seed_manifest.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    raw_instance_count += 1
                    record = augment_record(json.loads(line))
                    if not record.get("run_id"):
                        record["run_id"] = run_id
                    if not record.get("seed"):
                        record["seed"] = seed
                    if record.get("candidate_source", "unknown") == "unknown":
                        record["candidate_source"] = args.candidate_source
                    if record.get("search_stage", "unknown") == "unknown":
                        record["search_stage"] = args.search_stage
                    if record["instance_hash"] in seen_hashes:
                        skipped_duplicate_count += 1
                        print(
                            f"[THERMAL-DATA] duplicate skipped "
                            f"instance_id={record.get('instance_id')} "
                            f"hash={record['instance_hash'][:12]}"
                        )
                        continue
                    seen_hashes.add(record["instance_hash"])
                    record["seed"] = seed
                    record["collection_max_chiplets"] = max_chiplets
                    record["collection_tech_nodes"] = tech_nodes
                    records.append(record)
                    if len(records) >= args.num_instances:
                        break

    with final_manifest.open("w", encoding="utf-8") as f:
        for index, record in enumerate(records):
            record["split"] = _split_for_index(index, len(records))
            f.write(json.dumps(record) + "\n")

    summary = summarize_records(
        records,
        raw_instance_count=raw_instance_count,
        skipped_duplicate_count=skipped_duplicate_count,
    )
    summary["requested_instance_count"] = int(args.num_instances)
    summary["manifest_path"] = str(final_manifest)
    summary_path = args.summary_json or (args.out_dir / "manifest_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print(f"[THERMAL-DATA] wrote {len(records)} records to {final_manifest}")
    print(f"[THERMAL-DATA] wrote summary to {summary_path}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

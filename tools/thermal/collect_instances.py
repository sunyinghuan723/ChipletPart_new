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


def _augment_record(record: dict) -> dict:
    instance_path = Path(record["json_path"])
    with instance_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    chiplets = data.get("chiplets", [])
    record = dict(record)
    record["instance_hash"] = _stable_instance_hash(instance_path)
    record["grid_x"] = int(data.get("grid_x", data.get("grid", {}).get("x", 0)))
    record["grid_y"] = int(data.get("grid_y", data.get("grid", {}).get("y", 0)))
    record["num_chiplets"] = int(record.get("num_chiplets", len(chiplets)))
    record["technology_assignment"] = record.get(
        "technology_assignment", data.get("technology_assignment", [])
    )
    record["total_power"] = float(
        record.get("total_power", data.get("total_power_before_raster", 0.0))
    )
    if "cost" not in record and data.get("cost_objective") is not None:
        record["cost"] = data.get("cost_objective")
    return record


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
        ]
        print(f"[THERMAL-DATA] running {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        with seed_manifest.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = _augment_record(json.loads(line))
                    if record["instance_hash"] in seen_hashes:
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

    print(f"[THERMAL-DATA] wrote {len(records)} records to {final_manifest}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

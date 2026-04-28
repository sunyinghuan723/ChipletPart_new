#!/usr/bin/env python3
"""Collect package-level thermal instances through ChipletPart's encoder."""

from __future__ import annotations

import argparse
import json
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chipletpart_build", type=Path, required=True)
    parser.add_argument("--testcase", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--num_instances", type=int, default=20)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--grid_x", type=int, default=32)
    parser.add_argument("--grid_y", type=int, default=32)
    parser.add_argument("--tech_nodes", default="7nm,14nm")
    parser.add_argument("--max_chiplets", type=int, default=6)
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

    remaining = args.num_instances
    seed_counts = []
    for i, seed in enumerate(args.seeds):
        count = remaining // (len(args.seeds) - i)
        seed_counts.append((seed, count))
        remaining -= count

    records = []
    for seed, count in seed_counts:
        if count <= 0:
            continue
        seed_dir = args.out_dir / f"seed_{seed}"
        if seed_dir.exists():
            shutil.rmtree(seed_dir)
        seed_manifest = seed_dir / "manifest.jsonl"
        cmd = [
            str(helper),
            "--io",
            str(files["io"]),
            "--netlist",
            str(files["netlist"]),
            "--blocks",
            str(files["blocks"]),
            "--out_dir",
            str(seed_dir),
            "--manifest",
            str(seed_manifest),
            "--num_instances",
            str(count),
            "--seed",
            str(seed),
            "--grid_x",
            str(args.grid_x),
            "--grid_y",
            str(args.grid_y),
            "--source_testcase",
            testcase.name,
            "--tech_nodes",
            args.tech_nodes,
            "--max_chiplets",
            str(args.max_chiplets),
            "--prefix",
            f"{args.prefix}_s{seed}",
        ]
        print(f"[THERMAL-DATA] running {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        with seed_manifest.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    record["seed"] = seed
                    records.append(record)

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

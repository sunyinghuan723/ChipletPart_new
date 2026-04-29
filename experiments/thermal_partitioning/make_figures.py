#!/usr/bin/env python3
"""Create debugging/paper-prep figures from experiment V1 outputs."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def read_revalidation(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return {row["run_id"]: row for row in csv.DictReader(f)}


def select_rows(records: list[dict]) -> list[dict]:
    selected = []
    for setting in ["cost_only", "thermal_strict_budget", "thermal_high_budget"]:
        candidates = [row for row in records if row.get("setting") == setting]
        if candidates:
            selected.append(min(candidates, key=lambda row: float(row.get("objective", 1.0e99))))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_raw", type=Path, required=True)
    parser.add_argument("--revalidation_csv", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    reval = read_revalidation(args.revalidation_csv)
    plot_instance = ROOT / "tools" / "thermal" / "plot_instance.py"
    plot_prediction = ROOT / "tools" / "thermal" / "plot_prediction.py"
    for row in select_rows(read_jsonl(args.results_raw)):
        run_id = row["run_id"]
        instance_path = row.get("json_path")
        if not instance_path:
            continue
        subprocess.run(
            [
                args.python,
                str(plot_instance),
                "--instance",
                instance_path,
                "--out_dir",
                str(args.out_dir),
            ],
            check=True,
        )
        label_path = reval.get(run_id, {}).get("label_path")
        if label_path:
            subprocess.run(
                [
                    args.python,
                    str(plot_prediction),
                    "--instance",
                    instance_path,
                    "--label",
                    label_path,
                    "--out",
                    str(args.out_dir / f"{run_id}_reference_temperature.png"),
                ],
                check=True,
            )
    print(f"[THERMAL-FIG] wrote figures to {args.out_dir}")


if __name__ == "__main__":
    main()

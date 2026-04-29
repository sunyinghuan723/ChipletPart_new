#!/usr/bin/env python3
"""Collect grep-friendly thermal logs into a small CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


THERMAL_RE = re.compile(
    r"\[THERMAL\] cost=(?P<cost>\S+) t_max=(?P<t_max>\S+) "
    r"t_avg=(?P<t_avg>\S+) peak_penalty=(?P<peak>\S+) "
    r"avg_penalty=(?P<avg>\S+) objective=(?P<objective>\S+)"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", type=Path, nargs="+")
    parser.add_argument("--raw_jsonl", type=Path)
    parser.add_argument("--out_csv", type=Path, required=True)
    parser.add_argument("--out_report", type=Path)
    args = parser.parse_args()

    rows = []
    if args.raw_jsonl:
        with args.raw_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    rows.append(
                        {
                            "run_id": record.get("run_id", ""),
                            "setting": record.get("setting", ""),
                            "seed": record.get("seed", ""),
                            "cost": record.get("cost", ""),
                            "t_max": record.get("predicted_t_max", ""),
                            "t_avg": record.get("predicted_t_avg", ""),
                            "peak": record.get("thermal_penalty", ""),
                            "avg": "",
                            "objective": record.get("objective", ""),
                            "runtime_sec": record.get("runtime_sec", ""),
                            "num_evaluated_instances": record.get("num_evaluated_instances", ""),
                            "instance_path": record.get("json_path", ""),
                        }
                    )
    if args.logs:
        for log in args.logs:
            for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
                match = THERMAL_RE.search(line)
                if match:
                    row = {"run_id": log.stem, "setting": "", "seed": "", "runtime_sec": "", "num_evaluated_instances": "", "instance_path": ""}
                    row.update(match.groupdict())
                    row["t_max"] = row.pop("t_max")
                    row["t_avg"] = row.pop("t_avg")
                    rows.append(row)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "setting",
                "seed",
                "cost",
                "t_max",
                "t_avg",
                "peak",
                "avg",
                "objective",
                "runtime_sec",
                "num_evaluated_instances",
                "instance_path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    if args.out_report:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("setting", ""))].append(row)
        lines = ["# Thermal Partitioning Experiment V1", ""]
        for setting, subset in sorted(grouped.items()):
            values = [float(row["objective"]) for row in subset if row.get("objective") not in ("", None)]
            tmax = [float(row["t_max"]) for row in subset if row.get("t_max") not in ("", None)]
            lines.append(f"## {setting or 'logs'}")
            lines.append(f"- runs: {len(subset)}")
            if values:
                lines.append(f"- objective mean: {sum(values) / len(values):.6f}")
                lines.append(f"- objective min: {min(values):.6f}")
            if tmax:
                lines.append(f"- predicted T_max mean: {sum(tmax) / len(tmax):.3f} K")
            lines.append("")
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        args.out_report.write_text("\n".join(lines), encoding="utf-8")
    print(f"[THERMAL-EXP] wrote {len(rows)} rows to {args.out_csv}")


if __name__ == "__main__":
    main()

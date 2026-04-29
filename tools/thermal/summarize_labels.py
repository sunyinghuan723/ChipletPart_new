#!/usr/bin/env python3
"""Summarize package thermal labels and write JSON/Markdown reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def stats(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {"min": None, "mean": None, "max": None, "p50": None, "p90": None}
    return {
        "min": float(np.min(arr)),
        "mean": float(np.mean(arr)),
        "max": float(np.max(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
    }


def summarize(records: list[dict]) -> dict:
    t_max = [float(r["t_max"]) for r in records if r.get("t_max") is not None]
    t_avg = [float(r["t_avg"]) for r in records if r.get("t_avg") is not None]
    power = [float(r["total_power"]) for r in records if r.get("total_power") is not None]
    residual = [float(r["residual"]) for r in records if r.get("residual") is not None]
    statuses = {}
    for record in records:
        status = str(record.get("solver_status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
    correlation = None
    if len(power) == len(t_max) and len(power) >= 2 and np.std(power) > 0.0 and np.std(t_max) > 0.0:
        correlation = float(np.corrcoef(power, t_max)[0, 1])
    return {
        "num_labels": len(records),
        "t_max": stats(t_max),
        "t_avg": stats(t_avg),
        "total_power": stats(power),
        "residual": stats(residual),
        "solver_status_counts": statuses,
        "non_converged_labels": int(sum(1 for r in records if r.get("solver_status") != "converged")),
        "invalid_labels": int(sum(1 for r in records if r.get("valid_label") is False)),
        "power_tmax_correlation": correlation,
    }


def write_markdown(path: Path, summary: dict) -> None:
    lines = [
        "# Thermal Label Summary",
        "",
        f"- number of labels: {summary['num_labels']}",
        f"- non-converged labels: {summary['non_converged_labels']}",
        f"- invalid labels: {summary['invalid_labels']}",
        f"- power vs T_max correlation: {summary['power_tmax_correlation']}",
        "",
        "| metric | min | mean | p50 | p90 | max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ["t_max", "t_avg", "total_power", "residual"]:
        s = summary[name]
        lines.append(
            f"| {name} | {s['min']} | {s['mean']} | {s['p50']} | {s['p90']} | {s['max']} |"
        )
    lines.extend(["", "## Solver Status", ""])
    for status, count in sorted(summary["solver_status_counts"].items()):
        lines.append(f"- {status}: {count}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out_json", type=Path, required=True)
    parser.add_argument("--out_md", type=Path, required=True)
    args = parser.parse_args()

    summary = summarize(read_jsonl(args.manifest))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    write_markdown(args.out_md, summary)
    print(f"[THERMAL-DATA] wrote {args.out_json}")
    print(f"[THERMAL-DATA] wrote {args.out_md}")


if __name__ == "__main__":
    main()

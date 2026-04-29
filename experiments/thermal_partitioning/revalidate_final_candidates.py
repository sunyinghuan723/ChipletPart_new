#!/usr/bin/env python3
"""Revalidate experiment final candidates with the reference thermal solver."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "thermal"))

import reference_solver  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_raw", type=Path, required=True)
    parser.add_argument("--out_csv", type=Path, required=True)
    parser.add_argument("--label_dir", type=Path, required=True)
    parser.add_argument("--method", choices=["scipy_sparse", "jacobi", "sor", "auto"], default="auto")
    parser.add_argument("--max_iter", type=int, default=2000)
    parser.add_argument("--tol", type=float, default=1.0e-5)
    parser.add_argument("--omega", type=float, default=0.85)
    args = parser.parse_args()

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.label_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in read_jsonl(args.results_raw):
        if not record.get("json_path"):
            continue
        instance_path = Path(record["json_path"])
        data = reference_solver.load_instance(instance_path)
        result = reference_solver.solve_instance(
            data,
            max_iter=args.max_iter,
            tol=args.tol,
            method=args.method,
            omega=args.omega,
        )
        label_path = args.label_dir / f"{record['run_id']}_{data['instance_id']}_reference.npz"
        import numpy as np

        np.savez_compressed(label_path, **result)
        pred_tmax = float(record.get("predicted_t_max", 0.0))
        pred_tavg = float(record.get("predicted_t_avg", 0.0))
        rows.append(
            {
                "run_id": record.get("run_id"),
                "setting": record.get("setting"),
                "seed": record.get("seed"),
                "instance_id": record.get("instance_id"),
                "instance_path": str(instance_path),
                "label_path": str(label_path),
                "predicted_t_max": pred_tmax,
                "predicted_t_avg": pred_tavg,
                "reference_t_max": result["t_max"],
                "reference_t_avg": result["t_avg"],
                "t_max_error": pred_tmax - result["t_max"],
                "t_avg_error": pred_tavg - result["t_avg"],
                "solver_status": result["solver_status"],
                "residual": result["residual"],
                "method": result["method"],
            }
        )
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "run_id",
            "setting",
            "seed",
            "instance_id",
            "instance_path",
            "label_path",
            "predicted_t_max",
            "predicted_t_avg",
            "reference_t_max",
            "reference_t_avg",
            "t_max_error",
            "t_avg_error",
            "solver_status",
            "residual",
            "method",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[THERMAL-EXP] wrote {len(rows)} rows to {args.out_csv}")


if __name__ == "__main__":
    main()

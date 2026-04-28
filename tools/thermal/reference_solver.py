#!/usr/bin/env python3
"""Lightweight deterministic reference thermal solver for package instances.

This is a training-label generator, not a signoff solver. It solves a simplified
2D steady-state effective model:

    -k_eff * Laplacian(T) + h_eff * (T - T_amb) = q_eff

The package boundary uses zero-flux side boundaries via edge padding, while the
vertical term models effective convection to ambient. Units are inherited from
ChipletPart instance JSON: mm, cost_model_power/mm^2, and Kelvin.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np


CHANNEL_POWER = "power_density_w_per_mm2"


def load_instance(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _grid(data: dict) -> tuple[int, int]:
    return int(data.get("grid_y", data.get("grid", {}).get("y"))), int(
        data.get("grid_x", data.get("grid", {}).get("x"))
    )


def solve_instance(
    data: dict,
    *,
    max_iter: int = 2000,
    tol: float = 1.0e-5,
    omega: float = 0.85,
    source_scale: float = 2.0,
    h_scale: float = 0.05,
) -> dict:
    gy, gx = _grid(data)
    channels = data["channels"]
    power = np.asarray(channels[CHANNEL_POWER], dtype=np.float64).reshape(gy, gx)
    ambient_map = np.asarray(channels["ambient_temperature"], dtype=np.float64).reshape(gy, gx)
    htc_map = np.asarray(channels["heat_transfer_coefficient"], dtype=np.float64).reshape(gy, gx)
    silicon = np.asarray(channels["silicon_material"], dtype=np.float64).reshape(gy, gx)
    interposer = np.asarray(channels["interposer_material"], dtype=np.float64).reshape(gy, gx)
    package = np.asarray(channels["package_material"], dtype=np.float64).reshape(gy, gx)
    footprint = np.asarray(channels["chiplet_footprint"], dtype=np.float64).reshape(gy, gx)

    package_w = float(data.get("package_width_mm", data.get("package", {}).get("width_mm", gx)))
    package_h = float(data.get("package_height_mm", data.get("package", {}).get("height_mm", gy)))
    dx = max(package_w / max(gx, 1), 1.0e-6)
    dy = max(package_h / max(gy, 1), 1.0e-6)

    ambient = float(np.mean(ambient_map))
    # Effective lateral conduction: silicon where chiplets exist, otherwise the
    # interposer/package background. Normalize to keep the finite-difference
    # system well-conditioned for the current cost-model power scale.
    k_map = package + interposer + silicon * np.maximum(footprint, 0.0)
    k_eff = max(float(np.mean(k_map)) / 100.0, 1.0e-3)
    h_eff = max(float(np.mean(htc_map)) * h_scale, 1.0e-6)
    source = power * source_scale

    coef_x = k_eff / (dx * dx)
    coef_y = k_eff / (dy * dy)
    denom = 2.0 * coef_x + 2.0 * coef_y + h_eff

    temperature = np.full((gy, gx), ambient, dtype=np.float64)
    residual = 0.0
    start = time.perf_counter()
    status = "max_iter"
    for iteration in range(1, max_iter + 1):
        padded = np.pad(temperature, ((1, 1), (1, 1)), mode="edge")
        left = padded[1:-1, :-2]
        right = padded[1:-1, 2:]
        up = padded[:-2, 1:-1]
        down = padded[2:, 1:-1]
        updated = (
            coef_x * (left + right)
            + coef_y * (up + down)
            + h_eff * ambient
            + source
        ) / denom
        relaxed = omega * updated + (1.0 - omega) * temperature
        residual = float(np.max(np.abs(relaxed - temperature)))
        temperature = relaxed
        if residual < tol:
            status = "converged"
            break
    runtime = time.perf_counter() - start

    return {
        "temperature_map": temperature.astype(np.float32),
        "t_max": float(np.max(temperature)),
        "t_avg": float(np.mean(temperature)),
        "solver_status": status,
        "solver_runtime_sec": float(runtime),
        "iterations": int(iteration),
        "residual": float(residual),
    }


def solve_manifest(manifest: Path, out_dir: Path, manifest_out: Path | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if manifest_out is None:
        manifest_out = manifest.parent.parent / "manifest_labeled.jsonl"
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    records = []
    with manifest.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    with manifest_out.open("w", encoding="utf-8") as out:
        for record in records:
            instance_path = Path(record["json_path"])
            data = load_instance(instance_path)
            result = solve_instance(data)
            label_path = out_dir / f"{record['instance_id']}_label.npz"
            np.savez_compressed(
                label_path,
                temperature_map=result["temperature_map"],
                t_max=np.asarray(result["t_max"], dtype=np.float32),
                t_avg=np.asarray(result["t_avg"], dtype=np.float32),
                solver_status=np.asarray(result["solver_status"]),
                solver_runtime_sec=np.asarray(result["solver_runtime_sec"], dtype=np.float32),
                residual=np.asarray(result["residual"], dtype=np.float32),
                iterations=np.asarray(result["iterations"], dtype=np.int32),
            )
            record = dict(record)
            record["label_path"] = str(label_path)
            record["t_max"] = result["t_max"]
            record["t_avg"] = result["t_avg"]
            out.write(json.dumps(record) + "\n")
            print(
                f"[THERMAL-DATA] label {record['instance_id']} "
                f"t_max={result['t_max']:.3f} t_avg={result['t_avg']:.3f} "
                f"status={result['solver_status']} residual={result['residual']:.3e}"
            )
    print(f"[THERMAL-DATA] wrote labeled manifest {manifest_out}")
    return manifest_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--manifest_out", type=Path)
    parser.add_argument("--grid_x", type=int, default=None, help="Accepted for CLI compatibility")
    parser.add_argument("--grid_y", type=int, default=None, help="Accepted for CLI compatibility")
    args = parser.parse_args()

    if args.instance:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        data = load_instance(args.instance)
        result = solve_instance(data)
        label_path = args.out_dir / f"{data['instance_id']}_label.npz"
        np.savez_compressed(label_path, **result)
        print(json.dumps({k: v for k, v in result.items() if k != "temperature_map"}, indent=2))
        print(f"[THERMAL-DATA] wrote {label_path}")
    elif args.manifest:
        solve_manifest(args.manifest, args.out_dir, args.manifest_out)
    else:
        raise SystemExit("provide --instance or --manifest")


if __name__ == "__main__":
    main()

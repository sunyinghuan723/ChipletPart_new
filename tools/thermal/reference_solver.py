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
import math
import time
from concurrent.futures import ThreadPoolExecutor
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
    method: str = "auto",
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

    chosen_method = method
    if method == "auto":
        chosen_method = "scipy_sparse" if _scipy_available() else "jacobi"

    if chosen_method == "scipy_sparse":
        sparse_result = _solve_sparse(
            gy,
            gx,
            coef_x=coef_x,
            coef_y=coef_y,
            h_eff=h_eff,
            ambient=ambient,
            source=source,
            tol=tol,
            max_iter=max_iter,
        )
        sparse_result.update(
            {
                "method": chosen_method,
                "convergence_tol": float(tol),
                "max_iter": int(max_iter),
            }
        )
        return sparse_result

    temperature = np.full((gy, gx), ambient, dtype=np.float64)
    residual = 0.0
    start = time.perf_counter()
    status = "max_iter"
    for iteration in range(1, max_iter + 1):
        if chosen_method == "sor":
            relaxed = temperature.copy()
            for iy in range(gy):
                for ix in range(gx):
                    left = relaxed[iy, ix - 1] if ix > 0 else relaxed[iy, ix]
                    right = temperature[iy, ix + 1] if ix + 1 < gx else temperature[iy, ix]
                    up = relaxed[iy - 1, ix] if iy > 0 else relaxed[iy, ix]
                    down = temperature[iy + 1, ix] if iy + 1 < gy else temperature[iy, ix]
                    updated = (
                        coef_x * (left + right)
                        + coef_y * (up + down)
                        + h_eff * ambient
                        + source[iy, ix]
                    ) / denom
                    relaxed[iy, ix] = omega * updated + (1.0 - omega) * temperature[iy, ix]
        elif chosen_method == "jacobi":
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
        else:
            raise ValueError(f"unsupported solver method: {method}")
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
        "method": chosen_method,
        "convergence_tol": float(tol),
        "max_iter": int(max_iter),
    }


def _scipy_available() -> bool:
    try:
        import scipy.sparse  # noqa: F401
        import scipy.sparse.linalg  # noqa: F401

        return True
    except Exception:
        return False


def _solve_sparse(
    gy: int,
    gx: int,
    *,
    coef_x: float,
    coef_y: float,
    h_eff: float,
    ambient: float,
    source: np.ndarray,
    tol: float,
    max_iter: int,
) -> dict:
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla

    n = gy * gx
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    rhs = np.zeros(n, dtype=np.float64)

    def idx(iy: int, ix: int) -> int:
        return iy * gx + ix

    for iy in range(gy):
        for ix in range(gx):
            center = idx(iy, ix)
            diag = h_eff
            if ix > 0:
                rows.append(center)
                cols.append(idx(iy, ix - 1))
                vals.append(-coef_x)
                diag += coef_x
            if ix + 1 < gx:
                rows.append(center)
                cols.append(idx(iy, ix + 1))
                vals.append(-coef_x)
                diag += coef_x
            if iy > 0:
                rows.append(center)
                cols.append(idx(iy - 1, ix))
                vals.append(-coef_y)
                diag += coef_y
            if iy + 1 < gy:
                rows.append(center)
                cols.append(idx(iy + 1, ix))
                vals.append(-coef_y)
                diag += coef_y
            rows.append(center)
            cols.append(center)
            vals.append(diag)
            rhs[center] = h_eff * ambient + source[iy, ix]

    matrix = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    start = time.perf_counter()
    try:
        solution, info = spla.cg(matrix, rhs, rtol=tol, atol=0.0, maxiter=max_iter)
    except TypeError:
        solution, info = spla.cg(matrix, rhs, tol=tol, atol=0.0, maxiter=max_iter)
    runtime = time.perf_counter() - start
    temperature = solution.reshape(gy, gx)
    residual = float(np.linalg.norm(matrix @ solution - rhs, ord=np.inf))
    status = "converged" if info == 0 else "max_iter"
    iterations = max_iter if info > 0 else int(max_iter if math.isnan(residual) else 0)
    return {
        "temperature_map": temperature.astype(np.float32),
        "t_max": float(np.max(temperature)),
        "t_avg": float(np.mean(temperature)),
        "solver_status": status,
        "solver_runtime_sec": float(runtime),
        "iterations": int(iterations),
        "residual": float(residual),
    }


def _load_records(manifest: Path) -> list[dict]:
    records = []
    with manifest.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def _label_one(record: dict, out_dir: Path, args: argparse.Namespace) -> dict:
    instance_path = Path(record["json_path"])
    data = load_instance(instance_path)
    label_path = out_dir / f"{record['instance_id']}_label.npz"
    if args.skip_existing and label_path.exists() and not args.overwrite:
        with np.load(label_path, allow_pickle=True) as existing:
            record = dict(record)
            record["label_path"] = str(label_path)
            record["t_max"] = float(existing["t_max"])
            record["t_avg"] = float(existing["t_avg"])
            record["residual"] = float(
                existing["residual"] if "residual" in existing.files else np.asarray(float("nan"))
            )
            record["solver_status"] = str(
                existing["solver_status"] if "solver_status" in existing.files else np.asarray("existing")
            )
            record["valid_label"] = bool(record["residual"] <= args.invalid_residual)
            return record
    if label_path.exists() and not args.overwrite and not args.skip_existing:
        raise FileExistsError(f"{label_path} exists; pass --overwrite or --skip_existing")
    result = solve_instance(
        data,
        max_iter=args.max_iter,
        tol=args.tol,
        method=args.method,
        omega=args.omega,
        source_scale=args.source_scale,
        h_scale=args.h_scale,
    )
    valid_label = bool(np.isfinite(result["residual"]) and result["residual"] <= args.invalid_residual)
    np.savez_compressed(
        label_path,
        temperature_map=result["temperature_map"],
        t_max=np.asarray(result["t_max"], dtype=np.float32),
        t_avg=np.asarray(result["t_avg"], dtype=np.float32),
        solver_status=np.asarray(result["solver_status"]),
        solver_runtime_sec=np.asarray(result["solver_runtime_sec"], dtype=np.float32),
        residual=np.asarray(result["residual"], dtype=np.float32),
        iterations=np.asarray(result["iterations"], dtype=np.int32),
        method=np.asarray(result["method"]),
        convergence_tol=np.asarray(result["convergence_tol"], dtype=np.float32),
        max_iter=np.asarray(result["max_iter"], dtype=np.int32),
        valid_label=np.asarray(valid_label),
    )
    record = dict(record)
    record["label_path"] = str(label_path)
    record["t_max"] = result["t_max"]
    record["t_avg"] = result["t_avg"]
    record["residual"] = result["residual"]
    record["solver_status"] = result["solver_status"]
    record["solver_method"] = result["method"]
    record["valid_label"] = valid_label
    return record


def solve_manifest(
    manifest: Path,
    out_dir: Path,
    manifest_out: Path | None = None,
    args: argparse.Namespace | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if manifest_out is None:
        manifest_out = manifest.parent.parent / "manifest_labeled.jsonl"
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    if args is None:
        args = argparse.Namespace(
            max_iter=2000,
            tol=1.0e-5,
            method="auto",
            omega=0.85,
            source_scale=2.0,
            h_scale=0.05,
            overwrite=True,
            skip_existing=False,
            invalid_residual=5.0e-2,
            num_workers=1,
        )
    records = _load_records(manifest)

    def run(record: dict) -> dict:
        return _label_one(record, out_dir, args)

    if args.num_workers and args.num_workers > 1:
        with ThreadPoolExecutor(max_workers=args.num_workers) as executor:
            labeled_records = list(executor.map(run, records))
    else:
        labeled_records = [run(record) for record in records]

    with manifest_out.open("w", encoding="utf-8") as out:
        for record in labeled_records:
            out.write(json.dumps(record) + "\n")
            print(
                f"[THERMAL-DATA] label {record['instance_id']} "
                f"t_max={record['t_max']:.3f} t_avg={record['t_avg']:.3f} "
                f"status={record['solver_status']} residual={record['residual']:.3e} "
                f"valid={record['valid_label']}"
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
    parser.add_argument("--max_iter", type=int, default=2000)
    parser.add_argument("--tol", type=float, default=1.0e-5)
    parser.add_argument("--method", choices=["scipy_sparse", "jacobi", "sor", "auto"], default="auto")
    parser.add_argument("--omega", type=float, default=0.85)
    parser.add_argument("--source_scale", type=float, default=2.0)
    parser.add_argument("--h_scale", type=float, default=0.05)
    parser.add_argument("--num_workers", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip_existing", action="store_true")
    parser.add_argument("--invalid_residual", type=float, default=5.0e-2)
    args = parser.parse_args()

    if args.instance:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        data = load_instance(args.instance)
        result = solve_instance(
            data,
            max_iter=args.max_iter,
            tol=args.tol,
            method=args.method,
            omega=args.omega,
            source_scale=args.source_scale,
            h_scale=args.h_scale,
        )
        label_path = args.out_dir / f"{data['instance_id']}_label.npz"
        np.savez_compressed(label_path, **result)
        print(json.dumps({k: v for k, v in result.items() if k != "temperature_map"}, indent=2))
        print(f"[THERMAL-DATA] wrote {label_path}")
    elif args.manifest:
        solve_manifest(args.manifest, args.out_dir, args.manifest_out, args)
    else:
        raise SystemExit("provide --instance or --manifest")


if __name__ == "__main__":
    main()

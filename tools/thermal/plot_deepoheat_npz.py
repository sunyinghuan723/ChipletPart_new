#!/usr/bin/env python3
"""Plot DeepOHeat field NPZ files produced by ChipletPart runs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-cache")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _stem(npz_path: Path) -> str:
    return npz_path.name.replace(".thermal_result.field.npz", "")


def _instance_json_path(npz_path: Path) -> Path:
    return npz_path.with_name(_stem(npz_path) + ".json")


def _save_map(array: np.ndarray, title: str, path: Path, cmap: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=180)
    image = ax.imshow(np.asarray(array), origin="lower", cmap=cmap)
    ax.set_title(title)
    ax.set_xlabel("grid x")
    ax.set_ylabel("grid y")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label=label)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _save_hist(values: np.ndarray, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.2, 4.0), dpi=180)
    ax.hist(np.asarray(values).reshape(-1), bins=50)
    ax.set_title(title)
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _load_power_from_instance(npz_path: Path) -> np.ndarray | None:
    instance_path = _instance_json_path(npz_path)
    if not instance_path.exists():
        return None
    with instance_path.open("r", encoding="utf-8") as f:
        instance = json.load(f)
    grid_y = int(instance.get("grid_y", instance.get("grid", {}).get("y")))
    grid_x = int(instance.get("grid_x", instance.get("grid", {}).get("x")))
    power = instance.get("channels", {}).get("power_density_w_per_mm2")
    if power is None:
        return None
    return np.asarray(power, dtype=np.float32).reshape(grid_y, grid_x)


def _temperature_layers(coords: np.ndarray, temperature: np.ndarray) -> dict[str, np.ndarray]:
    coords = np.asarray(coords)
    temperature = np.asarray(temperature).reshape(-1)
    if coords.ndim != 2 or coords.shape[1] < 2 or coords.shape[0] != temperature.size:
        raise ValueError("coords/temperature arrays do not form a structured field")

    if coords.shape[1] >= 3:
        xs, x_inv = np.unique(coords[:, 0], return_inverse=True)
        ys, y_inv = np.unique(coords[:, 1], return_inverse=True)
        zs, z_inv = np.unique(coords[:, 2], return_inverse=True)
        field = np.full((len(ys), len(xs), len(zs)), np.nan, dtype=np.float32)
        field[y_inv, x_inv, z_inv] = temperature.astype(np.float32)
        return {
            "bottom": field[:, :, 0],
            "middle": field[:, :, len(zs) // 2],
            "top": field[:, :, -1],
        }

    xs, x_inv = np.unique(coords[:, 0], return_inverse=True)
    ys, y_inv = np.unique(coords[:, 1], return_inverse=True)
    field = np.full((len(ys), len(xs)), np.nan, dtype=np.float32)
    field[y_inv, x_inv] = temperature.astype(np.float32)
    return {"map": field}


def plot_npz(npz_path: Path, out_dir: Path) -> list[Path]:
    data = np.load(npz_path)
    stem = _stem(npz_path)
    written: list[Path] = []

    if "scaled_power_grid" in data:
        path = out_dir / f"{stem}_power_map.png"
        _save_map(data["scaled_power_grid"], "Rasterized power map", path, "inferno", "Power density")
        written.append(path)
    else:
        power = _load_power_from_instance(npz_path)
        if power is not None:
            path = out_dir / f"{stem}_power_map.png"
            _save_map(power, "Rasterized power map", path, "inferno", "Power density")
            written.append(path)

    if "sensor" in data:
        path = out_dir / f"{stem}_sensor.png"
        _save_map(data["sensor"], "DeepOHeat sensor", path, "viridis", "Sensor value")
        written.append(path)

    if "temperature_map" in data:
        temperature = np.asarray(data["temperature_map"], dtype=np.float32)
        path = out_dir / f"{stem}_temperature_map.png"
        _save_map(temperature, "Temperature field", path, "magma", "Temperature (K)")
        written.append(path)
        hist_path = out_dir / f"{stem}_temperature_hist.png"
        _save_hist(temperature, "Temperature distribution", hist_path)
        written.append(hist_path)
    elif "coords" in data and "temperature" in data:
        temperature = np.asarray(data["temperature"], dtype=np.float32)
        for layer_name, layer in _temperature_layers(data["coords"], temperature).items():
            path = out_dir / f"{stem}_temperature_{layer_name}.png"
            _save_map(layer, f"Temperature field - {layer_name}", path, "magma", "Temperature (K)")
            written.append(path)
        hist_path = out_dir / f"{stem}_temperature_hist.png"
        _save_hist(temperature, "Temperature distribution", hist_path)
        written.append(hist_path)
    else:
        raise ValueError(f"{npz_path} does not contain a recognized temperature field")

    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("npz", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    total = 0
    for npz_path in args.npz:
        written = plot_npz(npz_path, args.out_dir)
        total += len(written)
    print(f"[THERMAL-FIG] wrote {total} figure(s) to {args.out_dir}")


if __name__ == "__main__":
    main()

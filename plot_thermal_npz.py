#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def plot_field(npz_path: Path, out_dir: Path):
    data = np.load(npz_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = npz_path.name.replace(".thermal_result.field.npz", "")

    if "scaled_power_grid" in data:
        power = data["scaled_power_grid"]
        plt.figure(figsize=(6, 5))
        plt.imshow(power, origin="lower", cmap="inferno")
        plt.colorbar(label="Power density")
        plt.title("Rasterized Power Map")
        plt.tight_layout()
        plt.savefig(out_dir / f"{stem}_power_map.png", dpi=200)
        plt.close()

    if "sensor" in data:
        sensor = data["sensor"]
        plt.figure(figsize=(6, 5))
        plt.imshow(sensor, origin="lower", cmap="viridis")
        plt.colorbar(label="DeepOHeat sensor value")
        plt.title("DeepOHeat 21x21 Sensor")
        plt.tight_layout()
        plt.savefig(out_dir / f"{stem}_sensor.png", dpi=200)
        plt.close()

    coords = data["coords"]
    temp = data["temperature"]

    xs = np.unique(coords[:, 0])
    ys = np.unique(coords[:, 1])
    zs = np.unique(coords[:, 2])

    nx, ny, nz = len(xs), len(ys), len(zs)
    temp_3d = temp.reshape(nx, ny, nz)

    top = temp_3d[:, :, -1]
    mid = temp_3d[:, :, nz // 2]
    bottom = temp_3d[:, :, 0]

    for name, layer in [
        ("top", top),
        ("middle", mid),
        ("bottom", bottom),
    ]:
        plt.figure(figsize=(6, 5))
        plt.imshow(layer.T, origin="lower", cmap="hot")
        plt.colorbar(label="Temperature (K)")
        plt.title(f"Temperature Field - {name}")
        plt.tight_layout()
        plt.savefig(out_dir / f"{stem}_temperature_{name}.png", dpi=200)
        plt.close()

    plt.figure(figsize=(7, 5))
    plt.hist(temp, bins=50)
    plt.xlabel("Temperature (K)")
    plt.ylabel("Count")
    plt.title("Temperature Distribution")
    plt.tight_layout()
    plt.savefig(out_dir / f"{stem}_temperature_hist.png", dpi=200)
    plt.close()

    print(f"wrote figures to {out_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("npz", type=Path)
    parser.add_argument("--out_dir", type=Path, default=Path("thermal_figures"))
    args = parser.parse_args()
    plot_field(args.npz, args.out_dir)


if __name__ == "__main__":
    main()

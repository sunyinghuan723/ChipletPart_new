#!/usr/bin/env python3
"""Plot power, footprint, and optional channel maps from a thermal instance."""

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


def load_grid(instance: dict, channel: str) -> np.ndarray:
    gy = int(instance.get("grid_y", instance.get("grid", {}).get("y")))
    gx = int(instance.get("grid_x", instance.get("grid", {}).get("x")))
    return np.asarray(instance["channels"][channel], dtype=np.float32).reshape(gy, gx)


def save_map(array: np.ndarray, title: str, path: Path, cmap: str = "viridis") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(4.2, 3.6), dpi=160)
    image = ax.imshow(array, origin="lower", cmap=cmap)
    ax.set_title(title)
    ax.set_xlabel("grid x")
    ax.set_ylabel("grid y")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--channels", nargs="*", default=[])
    args = parser.parse_args()

    with args.instance.open("r", encoding="utf-8") as f:
        instance = json.load(f)
    prefix = args.instance.stem
    save_map(
        load_grid(instance, "power_density_w_per_mm2"),
        "Power density",
        args.out_dir / f"{prefix}_power_density.png",
        cmap="inferno",
    )
    save_map(
        load_grid(instance, "chiplet_footprint"),
        "Chiplet footprint",
        args.out_dir / f"{prefix}_chiplet_footprint.png",
        cmap="gray",
    )
    for channel in args.channels:
        if channel in instance.get("channels", {}):
            save_map(load_grid(instance, channel), channel, args.out_dir / f"{prefix}_{channel}.png")
    print(f"[THERMAL-FIG] wrote instance plots to {args.out_dir}")


if __name__ == "__main__":
    main()

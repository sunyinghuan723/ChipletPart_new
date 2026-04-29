#!/usr/bin/env python3
"""Plot reference/predicted temperature maps and absolute error."""

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


def instance_channel(path: Path, channel: str) -> np.ndarray:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    gy = int(data.get("grid_y", data.get("grid", {}).get("y")))
    gx = int(data.get("grid_x", data.get("grid", {}).get("x")))
    return np.asarray(data["channels"][channel], dtype=np.float32).reshape(gy, gx)


def save_panel(arrays: list[tuple[str, np.ndarray, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(arrays), figsize=(4.0 * len(arrays), 3.6), dpi=160)
    if len(arrays) == 1:
        axes = [axes]
    for ax, (title, array, cmap) in zip(axes, arrays):
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
    parser.add_argument("--label", type=Path, required=True)
    parser.add_argument("--prediction", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    power = instance_channel(args.instance, "power_density_w_per_mm2")
    label = np.asarray(np.load(args.label)["temperature_map"], dtype=np.float32)
    panels = [("power", power, "inferno"), ("reference T", label, "magma")]
    if args.prediction:
        pred = np.asarray(np.load(args.prediction)["temperature_map"], dtype=np.float32)
        panels.extend(
            [
                ("predicted T", pred, "magma"),
                ("abs error", np.abs(pred - label), "viridis"),
            ]
        )
    save_panel(panels, args.out)
    print(f"[THERMAL-FIG] wrote {args.out}")


if __name__ == "__main__":
    main()

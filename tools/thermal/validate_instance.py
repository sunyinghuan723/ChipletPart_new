#!/usr/bin/env python3
"""Validate ChipletPart thermal instance JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CHANNELS = [
    "package_domain",
    "chiplet_footprint",
    "chiplet_boundary",
    "power_density_w_per_mm2",
    "silicon_material",
    "interposer_material",
    "tim_material",
    "package_material",
    "ambient_temperature",
    "heat_transfer_coefficient",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_instance(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    schema_version = data.get("schema_version", data.get("schema"))
    _require(schema_version is not None, "missing schema_version/schema")
    _require("instance_id" in data, "missing instance_id")
    _require("source_testcase" in data, "missing source_testcase")

    grid_x = int(data.get("grid_x", data.get("grid", {}).get("x", 0)))
    grid_y = int(data.get("grid_y", data.get("grid", {}).get("y", 0)))
    _require(grid_x > 0 and grid_y > 0, "invalid grid dimensions")
    size = grid_x * grid_y

    _require("package_width_mm" in data or "package" in data, "missing package width")
    _require("package_height_mm" in data or "package" in data, "missing package height")
    _require("chiplets" in data and isinstance(data["chiplets"], list), "missing chiplets")
    _require("channels" in data and isinstance(data["channels"], dict), "missing channels")

    channels = data["channels"]
    for channel in REQUIRED_CHANNELS:
        _require(channel in channels, f"missing channel {channel}")
        _require(len(channels[channel]) == size, f"channel {channel} has wrong size")

    channel_names = data.get("channel_names", list(channels.keys()))
    for channel in REQUIRED_CHANNELS:
        _require(channel in channel_names, f"channel_names missing {channel}")

    for chiplet in data["chiplets"]:
        for key in [
            "id",
            "technology",
            "x_mm",
            "y_mm",
            "width_mm",
            "height_mm",
            "compute_power",
            "io_power",
            "total_power",
        ]:
            _require(key in chiplet, f"chiplet missing {key}")

    if data.get("block_rasterization_mode") == "synthetic_block_treemap":
        _require("blocks" in data and isinstance(data["blocks"], list), "missing packed blocks")
        _require(len(data["blocks"]) > 0, "packed blocks list is empty")
        for block in data["blocks"]:
            for key in [
                "id",
                "name",
                "chiplet_id",
                "x_mm",
                "y_mm",
                "width_mm",
                "height_mm",
                "area_mm2",
                "compute_power",
            ]:
                _require(key in block, f"packed block missing {key}")

    before = float(
        data.get(
            "total_power_before_raster",
            data.get("rasterization", {}).get("total_power_before_raster", 0.0),
        )
    )
    after = float(
        data.get(
            "total_power_after_raster",
            data.get("rasterization", {}).get("total_power_after_raster", 0.0),
        )
    )
    error = float(
        data.get("raster_power_error", data.get("rasterization", {}).get("power_error", after - before))
    )
    _require(abs(error) <= max(1.0e-3, 0.01 * abs(before)), "raster power error too large")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("instances", nargs="+", type=Path)
    args = parser.parse_args()

    for instance in args.instances:
        data = validate_instance(instance)
        print(
            f"[THERMAL-DATA] valid {instance} "
            f"id={data.get('instance_id')} grid={data.get('grid_x', data.get('grid', {}).get('x'))}x"
            f"{data.get('grid_y', data.get('grid', {}).get('y'))}"
        )


if __name__ == "__main__":
    main()

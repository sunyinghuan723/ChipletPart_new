#!/usr/bin/env python3
"""Python smoke tests for the package thermal pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
CHIPLET_ROOT = ROOT / "ChipletPart"
DEEPOHEAT_ROOT = ROOT / "DeepOHeat"
sys.path.insert(0, str(CHIPLET_ROOT / "tools" / "thermal"))
sys.path.insert(0, str(DEEPOHEAT_ROOT / "package_thermal"))

import reference_solver  # noqa: E402
from dataset import PackageThermalDataset  # noqa: E402
from model import PackageThermalDeepONet  # noqa: E402


CHANNELS = [
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


def make_instance(power: np.ndarray, path: Path) -> dict:
    gy, gx = power.shape
    zeros = np.zeros((gy, gx), dtype=np.float32)
    ones = np.ones((gy, gx), dtype=np.float32)
    data = {
        "schema_version": "chipletpart.thermal_instance.v2",
        "instance_id": path.stem,
        "source_testcase": "unit",
        "grid_x": gx,
        "grid_y": gy,
        "package_width_mm": float(gx),
        "package_height_mm": float(gy),
        "channel_names": CHANNELS,
        "chiplets": [
            {
                "id": 0,
                "technology": "14nm",
                "x_mm": 0,
                "y_mm": 0,
                "width_mm": float(gx),
                "height_mm": float(gy),
                "area_mm2": float(gx * gy),
                "compute_power": float(power.sum()),
                "io_power": 0.0,
                "total_power": float(power.sum()),
            }
        ],
        "channels": {
            "package_domain": ones.reshape(-1).tolist(),
            "chiplet_footprint": ones.reshape(-1).tolist(),
            "chiplet_boundary": zeros.reshape(-1).tolist(),
            "power_density_w_per_mm2": power.astype(np.float32).reshape(-1).tolist(),
            "silicon_material": (ones * 130.0).reshape(-1).tolist(),
            "interposer_material": (ones * 120.0).reshape(-1).tolist(),
            "tim_material": (ones * 4.0).reshape(-1).tolist(),
            "package_material": (ones * 20.0).reshape(-1).tolist(),
            "ambient_temperature": (ones * 293.15).reshape(-1).tolist(),
            "heat_transfer_coefficient": (ones * 0.2).reshape(-1).tolist(),
        },
        "total_power_before_raster": float(power.sum()),
        "total_power_after_raster": float(power.sum()),
        "raster_power_error": 0.0,
        "partition": [0],
        "technology_assignment": ["14nm"],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    return data


class ThermalPipelineTests(unittest.TestCase):
    def test_reference_solver_zero_power(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = make_instance(np.zeros((8, 8), dtype=np.float32), Path(tmp) / "zero.json")
            result = reference_solver.solve_instance(data, max_iter=200)
            self.assertAlmostEqual(result["t_max"], 293.15, places=3)
            self.assertAlmostEqual(result["t_avg"], 293.15, places=3)

    def test_reference_solver_power_monotonicity(self) -> None:
        low = make_instance(np.ones((8, 8), dtype=np.float32) * 0.1, Path("/tmp/low.json"))
        high = make_instance(np.ones((8, 8), dtype=np.float32) * 1.0, Path("/tmp/high.json"))
        self.assertGreater(
            reference_solver.solve_instance(high, max_iter=500)["t_max"],
            reference_solver.solve_instance(low, max_iter=500)["t_max"],
        )

    def test_reference_solver_hotspot(self) -> None:
        uniform = np.ones((8, 8), dtype=np.float32)
        hotspot = np.zeros((8, 8), dtype=np.float32)
        hotspot[4, 4] = float(uniform.sum())
        u = make_instance(uniform, Path("/tmp/uniform.json"))
        h = make_instance(hotspot, Path("/tmp/hotspot.json"))
        self.assertGreater(
            reference_solver.solve_instance(h, max_iter=500)["t_max"],
            reference_solver.solve_instance(u, max_iter=500)["t_max"],
        )

    def test_dataset_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            instance_path = tmp_path / "inst.json"
            data = make_instance(np.ones((8, 8), dtype=np.float32), instance_path)
            label_path = tmp_path / "label.npz"
            np.savez_compressed(label_path, temperature_map=np.ones((8, 8), dtype=np.float32) * 300)
            manifest = tmp_path / "manifest.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "instance_id": data["instance_id"],
                        "json_path": str(instance_path),
                        "label_path": str(label_path),
                        "split": "train",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            sample = PackageThermalDataset(manifest)[0]
            self.assertEqual(tuple(sample["x"].shape), (len(CHANNELS), 8, 8))
            self.assertEqual(tuple(sample["temperature"].shape), (8, 8))

    def test_package_surrogate_forward(self) -> None:
        model = PackageThermalDeepONet(len(CHANNELS), feature_dim=16, hidden_dim=32)
        x = torch.randn(2, len(CHANNELS), 8, 8)
        coords = torch.rand(64, 2)
        out = model(x, coords)
        self.assertEqual(tuple(out.shape), (2, 64))

    def test_package_infer_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            instance_path = tmp_path / "inst.json"
            make_instance(np.ones((8, 8), dtype=np.float32), instance_path)
            checkpoint = tmp_path / "checkpoint.pt"
            model = PackageThermalDeepONet(len(CHANNELS))
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "config": {
                        "channel_names": CHANNELS,
                        "grid_x": 8,
                        "grid_y": 8,
                        "feature_dim": 64,
                        "hidden_dim": 128,
                    },
                },
                checkpoint,
            )
            output = tmp_path / "result.json"
            script = DEEPOHEAT_ROOT / "package_thermal" / "infer_package.py"
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--instance",
                    str(instance_path),
                    "--model",
                    str(checkpoint),
                    "--output",
                    str(output),
                    "--device",
                    "cpu",
                ],
                check=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("t_max", result)
            self.assertIn("t_avg", result)

            missing = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--instance",
                    str(instance_path),
                    "--model",
                    str(tmp_path / "missing.pt"),
                    "--output",
                    str(output),
                    "--device",
                    "cpu",
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("checkpoint not found", missing.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Python smoke tests for the package thermal pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
CHIPLET_ROOT = ROOT / "ChipletPart"
DEEPOHEAT_ROOT = ROOT / "DeepOHeat"
sys.path.insert(0, str(CHIPLET_ROOT / "tools" / "thermal"))
sys.path.insert(0, str(DEEPOHEAT_ROOT / "package_thermal"))

import reference_solver  # noqa: E402
import split_manifest  # noqa: E402
import summarize_labels  # noqa: E402
import collect_instances  # noqa: E402
import collect_search_dataset  # noqa: E402
from device import device_metadata, resolve_device  # noqa: E402
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
    def test_device_parser(self) -> None:
        self.assertEqual(str(resolve_device("cpu")), "cpu")
        auto = resolve_device("auto")
        self.assertIn(str(auto), {"cpu", "cuda:0"})
        if torch.cuda.is_available():
            self.assertEqual(str(resolve_device("cuda")), "cuda:0")
            self.assertEqual(str(resolve_device("cuda:0")), "cuda:0")

    def test_device_parser_cuda_unavailable_policy(self) -> None:
        with mock.patch("torch.cuda.is_available", return_value=False), mock.patch(
            "torch.cuda.device_count", return_value=0
        ):
            with self.assertRaisesRegex(RuntimeError, "requested --device cuda"):
                resolve_device("cuda")
            with self.assertRaisesRegex(RuntimeError, "requested --device cuda:0"):
                resolve_device("cuda:0")
            with self.assertWarnsRegex(RuntimeWarning, "--device auto selected CPU"):
                auto = resolve_device("auto")
            self.assertEqual(str(auto), "cpu")
            self.assertEqual(
                device_metadata(auto),
                {
                    "device": "cpu",
                    "cuda_available": False,
                    "cuda_device_count": 0,
                    "gpu_name": "",
                },
            )

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

    def test_manifest_split_and_label_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            records = []
            for i in range(10):
                instance_path = tmp_path / f"inst_{i}.json"
                data = make_instance(np.ones((8, 8), dtype=np.float32) * (i + 1), instance_path)
                label_path = tmp_path / f"label_{i}.npz"
                np.savez_compressed(
                    label_path,
                    temperature_map=np.ones((8, 8), dtype=np.float32) * (300 + i),
                    t_max=np.asarray(300 + i, dtype=np.float32),
                    t_avg=np.asarray(300 + i, dtype=np.float32),
                    residual=np.asarray(1.0e-6, dtype=np.float32),
                    solver_status=np.asarray("converged"),
                )
                records.append(
                    {
                        "instance_id": data["instance_id"],
                        "json_path": str(instance_path),
                        "label_path": str(label_path),
                        "testcase": "unit",
                        "total_power": float(i + 1),
                        "t_max": float(300 + i),
                        "t_avg": float(300 + i),
                        "residual": 1.0e-6,
                        "solver_status": "converged",
                    }
                )
            manifest = tmp_path / "manifest_labeled.jsonl"
            manifest.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            split_records = split_manifest.split_records(
                records,
                train_ratio=0.6,
                val_ratio=0.2,
                test_ratio=0.2,
                seed=7,
            )
            self.assertEqual(len(split_records), 10)
            self.assertTrue(all(record.get("split") for record in split_records))
            summary = summarize_labels.summarize(records)
            self.assertEqual(summary["num_labels"], 10)
            self.assertEqual(summary["non_converged_labels"], 0)

    def test_collection_provenance_summary_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            old_instance = tmp_path / "old_inst.json"
            make_instance(np.ones((8, 8), dtype=np.float32), old_instance)
            old_record = collect_instances.augment_record(
                {"instance_id": "old_inst", "json_path": str(old_instance)}
            )
            self.assertEqual(old_record["candidate_source"], "unknown")
            self.assertEqual(old_record["search_stage"], "unknown")
            self.assertIn("instance_hash", old_record)

            new_instance = tmp_path / "new_inst.json"
            new_data = make_instance(np.ones((8, 8), dtype=np.float32) * 2, new_instance)
            new_data.update(
                {
                    "run_id": "v3_smoke_seed7",
                    "seed": "7",
                    "candidate_index": 3,
                    "candidate_source": "chipletpart_search",
                    "search_stage": "search_candidate",
                    "thermal_enabled": True,
                    "floorplan_feasible": True,
                    "io_feasible": True,
                    "generation_time_unix_sec": 123456,
                    "technology_assignment_summary": {"14nm": 1},
                }
            )
            new_instance.write_text(json.dumps(new_data), encoding="utf-8")
            new_record = collect_instances.augment_record(
                {"instance_id": "new_inst", "json_path": str(new_instance)}
            )
            self.assertEqual(new_record["candidate_source"], "chipletpart_search")
            self.assertEqual(new_record["search_stage"], "search_candidate")
            self.assertEqual(new_record["candidate_index"], 3)
            self.assertTrue(new_record["floorplan_feasible"])

            summary = collect_instances.summarize_records(
                [old_record, new_record],
                raw_instance_count=3,
                skipped_duplicate_count=1,
            )
            self.assertEqual(summary["raw_instance_count"], 3)
            self.assertEqual(summary["unique_instance_count"], 2)
            self.assertEqual(summary["skipped_duplicate_count"], 1)
            self.assertEqual(summary["count_by_candidate_source"]["unknown"], 1)
            self.assertEqual(summary["count_by_candidate_source"]["chipletpart_search"], 1)
            self.assertEqual(summary["count_by_search_stage"]["search_candidate"], 1)
            self.assertEqual(summary["count_by_search_stage"]["unknown"], 1)

    def test_search_dataset_manifest_merge_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            instance_a = tmp_path / "search_a.json"
            data_a = make_instance(np.ones((8, 8), dtype=np.float32), instance_a)
            data_a.update(
                {
                    "run_id": "v3_unit_seed1",
                    "seed": "1",
                    "candidate_index": 0,
                    "candidate_source": "chipletpart_search",
                    "search_stage": "search_candidate",
                    "thermal_enabled": True,
                    "floorplan_feasible": True,
                    "io_feasible": True,
                }
            )
            instance_a.write_text(json.dumps(data_a), encoding="utf-8")

            instance_b = tmp_path / "search_b.json"
            data_b = dict(data_a)
            data_b["instance_id"] = "search_b"
            data_b["candidate_index"] = 1
            instance_b.write_text(json.dumps(data_b), encoding="utf-8")

            manifest = tmp_path / "manifest.jsonl"
            manifest.write_text(
                json.dumps({"instance_id": "search_a", "json_path": str(instance_a)}) + "\n"
                + json.dumps({"instance_id": "search_b", "json_path": str(instance_b)}) + "\n",
                encoding="utf-8",
            )
            out_manifest = tmp_path / "merged.jsonl"
            records, raw_count, skipped = collect_search_dataset.merge_manifests(
                [manifest], out_manifest
            )
            self.assertEqual(raw_count, 2)
            self.assertEqual(skipped, 1)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["candidate_source"], "chipletpart_search")
            self.assertEqual(records[0]["search_stage"], "search_candidate")
            self.assertEqual(collect_search_dataset.validate_records(records), 0)

    def test_package_surrogate_forward(self) -> None:
        model = PackageThermalDeepONet(len(CHANNELS), feature_dim=16, hidden_dim=32)
        x = torch.randn(2, len(CHANNELS), 8, 8)
        coords = torch.rand(64, 2)
        out = model(x, coords)
        self.assertEqual(tuple(out.shape), (2, 64))
        if torch.cuda.is_available():
            device = resolve_device("cuda:0")
            model = PackageThermalDeepONet(len(CHANNELS), feature_dim=16, hidden_dim=32).to(device)
            out = model(x.to(device), coords.to(device))
            self.assertEqual(tuple(out.shape), (2, 64))

    def test_training_and_visualization_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = tmp_path / "manifest.jsonl"
            records = []
            for i, split in enumerate(["train", "train", "val"]):
                instance_path = tmp_path / f"train_inst_{i}.json"
                data = make_instance(np.ones((8, 8), dtype=np.float32) * (i + 1), instance_path)
                label_path = tmp_path / f"train_label_{i}.npz"
                np.savez_compressed(
                    label_path,
                    temperature_map=np.ones((8, 8), dtype=np.float32) * (300 + i),
                    t_max=np.asarray(300 + i, dtype=np.float32),
                    t_avg=np.asarray(300 + i, dtype=np.float32),
                )
                records.append(
                    {
                        "instance_id": data["instance_id"],
                        "json_path": str(instance_path),
                        "label_path": str(label_path),
                        "split": split,
                    }
                )
            manifest.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            train_script = DEEPOHEAT_ROOT / "package_thermal" / "train.py"
            subprocess.run(
                [
                    sys.executable,
                    str(train_script),
                    "--manifest",
                    str(manifest),
                    "--out_dir",
                    str(tmp_path / "run"),
                    "--epochs",
                    "1",
                    "--batch_size",
                    "1",
                    "--grid_x",
                    "8",
                    "--grid_y",
                    "8",
                    "--device",
                    "cpu",
                    "--branch_dim",
                    "8",
                    "--trunk_dim",
                    "8",
                    "--hidden_dim",
                    "16",
                    "--early_stop_patience",
                    "0",
                ],
                check=True,
            )
            self.assertTrue((tmp_path / "run" / "checkpoint_best.pt").exists())
            plot_script = CHIPLET_ROOT / "tools" / "thermal" / "plot_instance.py"
            subprocess.run(
                [
                    sys.executable,
                    str(plot_script),
                    "--instance",
                    str(tmp_path / "train_inst_0.json"),
                    "--out_dir",
                    str(tmp_path / "figs"),
                ],
                check=True,
            )
            self.assertTrue((tmp_path / "figs" / "train_inst_0_power_density.png").exists())

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
            self.assertEqual(result["device"], "cpu")

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

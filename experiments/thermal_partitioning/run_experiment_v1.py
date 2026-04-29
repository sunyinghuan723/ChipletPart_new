#!/usr/bin/env python3
"""Run a small reproducible cost-only vs thermal-aware pilot experiment."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def testcase_files(testcase: Path) -> list[str]:
    names = [
        "io_definitions.xml",
        "layer_definitions.xml",
        "wafer_process_definitions.xml",
        "assembly_process_definitions.xml",
        "test_definitions.xml",
        "block_level_netlist.xml",
        "block_definitions.txt",
    ]
    paths = [testcase / name for name in names]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise SystemExit(f"missing testcase files: {missing}")
    return [str(path) for path in paths]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def thermal_result_path(instance_path: str) -> Path:
    return Path(instance_path).with_suffix(".thermal_result.json")


def load_prediction(record: dict) -> dict:
    path = thermal_result_path(record["json_path"])
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def choose_best(manifest: Path, thermal_budget: float, lambda_peak: float, lambda_avg: float) -> dict:
    records = read_jsonl(manifest)
    if not records:
        return {}
    best = None
    for record in records:
        prediction = load_prediction(record)
        cost = float(record.get("cost", record.get("cost_objective", 0.0)))
        t_max = float(prediction.get("t_max", record.get("t_max", 0.0)))
        t_avg = float(prediction.get("t_avg", record.get("t_avg", 0.0)))
        peak_penalty = lambda_peak * max(0.0, t_max - thermal_budget) ** 2
        avg_penalty = lambda_avg * t_avg
        objective = cost + peak_penalty + avg_penalty
        row = dict(record)
        row.update(
            {
                "predicted_t_max": t_max,
                "predicted_t_avg": t_avg,
                "thermal_penalty": peak_penalty + avg_penalty,
                "objective": objective,
                "prediction_path": str(thermal_result_path(record["json_path"])),
            }
        )
        if best is None or objective < best["objective"]:
            best = row
    return best or {}


def run_setting(args: argparse.Namespace, setting: dict, seed: int) -> dict:
    run_id = f"{setting['name']}_seed{seed}"
    run_dir = args.out_dir / run_id
    dump_dir = run_dir / "instances"
    manifest = run_dir / "manifest.jsonl"
    run_dir.mkdir(parents=True, exist_ok=True)
    if manifest.exists():
        manifest.unlink()

    cmd = [
        str(args.chipletpart_build / "bin" / "chipletPart"),
        *testcase_files(args.testcase),
        str(args.reach),
        str(args.separation),
        "--tech-enum",
        "--tech-nodes",
        args.tech_nodes,
        "--max-partitions",
        str(args.max_partitions),
        "--seed",
        str(seed),
        "--enable_thermal",
        "--thermal_backend",
        "package_thermal",
        "--thermal_model_path",
        str(args.thermal_model),
        "--thermal_python",
        str(args.thermal_python),
        "--thermal_inference_script",
        str(args.deepoheat_root / "package_thermal" / "infer_package.py"),
        "--thermal_budget",
        str(setting["budget"]),
        "--thermal_lambda_peak",
        str(setting["lambda_peak"]),
        "--thermal_lambda_avg",
        str(setting["lambda_avg"]),
        "--thermal_grid_x",
        str(args.grid_x),
        "--thermal_grid_y",
        str(args.grid_y),
        "--thermal_dump_instances",
        str(dump_dir),
        "--thermal_dump_manifest",
        str(manifest),
        "--thermal_dump_prefix",
        run_id,
        "--thermal_dump_split",
        "experiment_v1",
        "--thermal_source_testcase",
        args.testcase.name,
        "--thermal_run_id",
        run_id,
        "--thermal_candidate_source",
        "chipletpart_search",
        "--thermal_search_stage",
        "search_candidate",
        "--thermal_seed",
        str(seed),
        "--thermal_device",
        args.device,
        "--thermal_cache",
    ]
    log_path = run_dir / "chipletpart.log"
    start = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        print(f"[THERMAL-EXP] running {run_id}")
        subprocess.run(cmd, cwd=run_dir, stdout=log, stderr=subprocess.STDOUT, check=True)
    runtime = time.perf_counter() - start
    best = choose_best(manifest, setting["budget"], setting["lambda_peak"], setting["lambda_avg"])
    best.update(
        {
            "run_id": run_id,
            "setting": setting["name"],
            "seed": seed,
            "thermal_budget": setting["budget"],
            "lambda_peak": setting["lambda_peak"],
            "lambda_avg": setting["lambda_avg"],
            "runtime_sec": runtime,
            "log_path": str(log_path),
            "manifest_path": str(manifest),
            "num_evaluated_instances": len(read_jsonl(manifest)),
        }
    )
    return best


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chipletpart_build", type=Path, required=True)
    parser.add_argument("--testcase", type=Path, required=True)
    parser.add_argument("--thermal_model", type=Path, required=True)
    parser.add_argument("--thermal_python", type=Path, required=True)
    parser.add_argument("--deepoheat_root", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, default=Path("/tmp/chipletpart_thermal_experiments_v1"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--tech_nodes", default="7nm,14nm")
    parser.add_argument("--max_partitions", type=int, default=3)
    parser.add_argument("--reach", type=float, default=0.50)
    parser.add_argument("--separation", type=float, default=0.25)
    parser.add_argument("--grid_x", type=int, default=32)
    parser.add_argument("--grid_y", type=int, default=32)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--lambda_peak", type=float, default=0.001)
    parser.add_argument("--lambda_avg", type=float, default=0.0)
    parser.add_argument("--high_budget", type=float, default=340.0)
    parser.add_argument("--strict_budget", type=float, default=315.0)
    args = parser.parse_args()

    args.chipletpart_build = args.chipletpart_build.resolve()
    args.testcase = args.testcase.resolve()
    args.thermal_model = args.thermal_model.resolve()
    args.thermal_python = args.thermal_python.resolve()
    args.deepoheat_root = args.deepoheat_root.resolve()
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    settings = [
        {"name": "cost_only", "budget": args.high_budget, "lambda_peak": 0.0, "lambda_avg": 0.0},
        {
            "name": "thermal_high_budget",
            "budget": args.high_budget,
            "lambda_peak": args.lambda_peak,
            "lambda_avg": args.lambda_avg,
        },
        {
            "name": "thermal_strict_budget",
            "budget": args.strict_budget,
            "lambda_peak": args.lambda_peak,
            "lambda_avg": args.lambda_avg,
        },
    ]
    results = []
    raw_path = args.out_dir / "results_raw.jsonl"
    raw_path.unlink(missing_ok=True)
    with raw_path.open("w", encoding="utf-8") as raw:
        for setting in settings:
            for seed in args.seeds:
                row = run_setting(args, setting, seed)
                results.append(row)
                raw.write(json.dumps(row) + "\n")
                raw.flush()
                print(
                    "[THERMAL-EXP] result "
                    f"run_id={row.get('run_id')} objective={row.get('objective')} "
                    f"cost={row.get('cost')} t_max={row.get('predicted_t_max')}"
                )
    print(f"[THERMAL-EXP] wrote {raw_path}")


if __name__ == "__main__":
    main()

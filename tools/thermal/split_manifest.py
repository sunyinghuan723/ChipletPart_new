#!/usr/bin/env python3
"""Create reproducible train/val/test JSONL manifests for thermal datasets."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def split_records(
    records: list[dict],
    *,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> list[dict]:
    total = train_ratio + val_ratio + test_ratio
    if total <= 0.0:
        raise SystemExit("split ratios must sum to a positive value")
    train_ratio /= total
    val_ratio /= total
    rng = random.Random(seed)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("testcase", record.get("source_testcase", "unknown")))].append(record)

    split_records_out: list[dict] = []
    for testcase in sorted(grouped):
        group = list(grouped[testcase])
        rng.shuffle(group)
        n = len(group)
        train_end = int(round(n * train_ratio))
        val_end = train_end + int(round(n * val_ratio))
        if n >= 3:
            train_end = min(max(train_end, 1), n - 2)
            val_end = min(max(val_end, train_end + 1), n - 1)
        for index, record in enumerate(group):
            out = dict(record)
            if index < train_end:
                out["split"] = "train"
            elif index < val_end:
                out["split"] = "val"
            else:
                out["split"] = "test"
            split_records_out.append(out)
    split_records_out.sort(key=lambda r: str(r.get("instance_id", "")))
    return split_records_out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--train_ratio", type=float, default=0.7)
    parser.add_argument("--val_ratio", type=float, default=0.15)
    parser.add_argument("--test_ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=1234)
    args = parser.parse_args()

    records = read_jsonl(args.manifest)
    split_records_out = split_records(
        records,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    by_split = {name: [r for r in split_records_out if r.get("split") == name] for name in ["train", "val", "test"]}
    write_jsonl(args.out_dir / "manifest_split.jsonl", split_records_out)
    for split, subset in by_split.items():
        write_jsonl(args.out_dir / f"manifest_{split}.jsonl", subset)
    print(
        "[THERMAL-DATA] split manifest "
        f"train={len(by_split['train'])} val={len(by_split['val'])} "
        f"test={len(by_split['test'])} out_dir={args.out_dir}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Collect grep-friendly thermal logs into a small CSV."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


THERMAL_RE = re.compile(
    r"\[THERMAL\] cost=(?P<cost>\S+) t_max=(?P<t_max>\S+) "
    r"t_avg=(?P<t_avg>\S+) peak_penalty=(?P<peak>\S+) "
    r"avg_penalty=(?P<avg>\S+) objective=(?P<objective>\S+)"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", type=Path, nargs="+", required=True)
    parser.add_argument("--out_csv", type=Path, required=True)
    args = parser.parse_args()

    rows = []
    for log in args.logs:
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = THERMAL_RE.search(line)
            if match:
                row = {"log": str(log)}
                row.update(match.groupdict())
                rows.append(row)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["log", "cost", "t_max", "t_avg", "peak", "avg", "objective"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"[THERMAL-EXP] wrote {len(rows)} rows to {args.out_csv}")


if __name__ == "__main__":
    main()

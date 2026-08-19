"""Validate the applicability engine against Development_Labels.csv."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from applicability import decide_all
from extract import load_package

CHALLENGE = Path(__file__).resolve().parents[1] / "Contract_Clause_Risk_Flagging"
DEV = CHALLENGE / "Development"
LABELS = DEV / "Development_Labels.csv"


def load_labels() -> dict[tuple[str, str], str]:
    expected: dict[tuple[str, str], str] = {}
    with LABELS.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            expected[(row["Package_ID"], row["Requirement_ID"])] = row["Expected_Applicability"]
    return expected


def main() -> None:
    expected = load_labels()
    packages = [p for p in sorted(DEV.iterdir()) if p.is_dir()]

    hits = misses = 0
    failures = defaultdict(list)

    for package_dir in packages:
        package = load_package(package_dir)
        for req_id, decision in decide_all(package).items():
            key = (package.package_id, req_id)
            if key not in expected:
                continue
            if decision.decision == expected[key]:
                hits += 1
            else:
                misses += 1
                failures[package.package_id].append(
                    f"{req_id}: expected {expected[key]}, got {decision.decision} "
                    f"({decision.source}) - {decision.reason}"
                )

    total = hits + misses
    print(f"Applicability accuracy: {hits}/{total} ({hits / total:.1%})")
    for package_id, rows in failures.items():
        print(f"\n{package_id}")
        for row in rows:
            print(f"  MISMATCH {row}")


if __name__ == "__main__":
    main()

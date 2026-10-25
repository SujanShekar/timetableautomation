#!/usr/bin/env python3
"""Independently verify an exported timetable slot table.

    python verify_timetable.py output/timetable_slots.csv --max-first-hour 2

The script re-reads the generated CSV (it does not reuse the solver state) and
re-checks the three hard constraints.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an exported timetable CSV.")
    parser.add_argument("csv_path", help="timetable_slots.csv produced by the generator")
    parser.add_argument("--max-first-hour", type=int, default=2, help="1st hour limit per faculty")
    args = parser.parse_args()

    path = Path(args.csv_path)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2

    faculty_slots: dict = defaultdict(list)
    section_slots: dict = defaultdict(list)
    first_hour: dict = defaultdict(int)

    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["faculty"], row["day"], row["period"])
            section_key = (row["semester"], row["section"], row["day"], row["period"])
            faculty_slots[key].append(row["subject"])
            section_slots[section_key].append(row["subject"])
            if int(row["period"]) == 1:
                first_hour[row["faculty"]] += 1

    problems = 0
    for (faculty, day, period), subjects in sorted(faculty_slots.items()):
        if len(subjects) > 1:
            problems += 1
            print(f"FACULTY OVERLAP: {faculty} on {day} P{period} -> {', '.join(subjects)}")

    for (semester, section, day, period), subjects in sorted(section_slots.items()):
        if len(subjects) > 1:
            problems += 1
            print(f"SECTION OVERLAP: {semester} {section} on {day} P{period} -> {', '.join(subjects)}")

    for faculty, count in sorted(first_hour.items()):
        if count > args.max_first_hour:
            problems += 1
            print(f"FIRST HOUR CAP: {faculty} holds the 1st hour {count} times")

    print("-" * 70)
    print(f" faculty slots checked : {len(faculty_slots)}")
    print(f" section slots checked : {len(section_slots)}")
    print(f" faculty with 1st hour : {len(first_hour)}")
    print(f" problems              : {problems}")
    print(" RESULT                : " + ("PASS - conflict free" if problems == 0 else "FAIL"))
    print("-" * 70)
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

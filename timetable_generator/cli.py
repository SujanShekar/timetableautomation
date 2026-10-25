"""Command line entry point for the timetable generator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from .config import DEFAULT_DAYS, DEFAULT_PERIOD_TIMES, TimetableConfig
from .parser import parse_workbook
from .reporting import TimetableView, render_text_report, write_csv, write_excel_report
from .solver import TimetableSolver
from .validator import validate


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        prog="generate_timetable",
        description=(
            "Build a conflict free weekly timetable for the Odd Semester 2026 "
            "course allotment workbook."
        ),
    )
    parser.add_argument(
        "--excel",
        default=str(root / "Course Allotment Odd Sem-2026.xlsx"),
        help="source workbook (default: %(default)s)",
    )
    parser.add_argument(
        "--out",
        default=str(root / "output"),
        help="output directory for the report, workbook and csv (default: %(default)s)",
    )
    parser.add_argument(
        "--days",
        default=",".join(DEFAULT_DAYS),
        help="comma separated working days (default: %(default)s)",
    )
    parser.add_argument(
        "--periods",
        type=int,
        default=len(DEFAULT_PERIOD_TIMES),
        help="teaching periods per day (default: %(default)s)",
    )
    parser.add_argument(
        "--period-times",
        default=",".join(DEFAULT_PERIOD_TIMES),
        help="comma separated time windows, one per period (default: %(default)s)",
    )
    parser.add_argument(
        "--max-first-hour",
        type=int,
        default=2,
        help="maximum number of 1st hour sessions per faculty per week (default: %(default)s)",
    )
    parser.add_argument(
        "--lab-block",
        type=int,
        default=2,
        help="length of a laboratory block in periods (default: %(default)s)",
    )
    parser.add_argument("--seed", type=int, default=2026, help="random seed (default: %(default)s)")
    parser.add_argument(
        "--restarts", type=int, default=30, help="solver restarts (default: %(default)s)"
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=20.0,
        help="solver time budget in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--no-improve",
        action="store_true",
        help="skip the local search polish pass",
    )
    parser.add_argument("--alias-file", default=None, help="JSON file mapping faculty aliases")
    parser.add_argument(
        "--hours-file", default=None, help="JSON file overriding weekly hours per subject"
    )
    parser.add_argument("--no-excel", action="store_true", help="skip the Excel export")
    parser.add_argument("--no-csv", action="store_true", help="skip the CSV export")
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    return parser


def build_config(args: argparse.Namespace) -> TimetableConfig:
    days = tuple(d.strip() for d in args.days.split(",") if d.strip())
    times = tuple(t.strip() for t in args.period_times.split(",") if t.strip())
    if len(times) != args.periods:
        times = DEFAULT_PERIOD_TIMES[: args.periods]
    config = TimetableConfig(
        excel_path=Path(args.excel),
        output_dir=Path(args.out),
        days=days,
        periods_per_day=args.periods,
        period_times=times,
        max_first_hour=args.max_first_hour,
        lab_block_hours=args.lab_block,
        seed=args.seed,
        restarts=args.restarts,
        time_budget_s=args.time_budget,
        improve=not args.no_improve,
    )
    config.load_overrides(
        Path(args.hours_file) if args.hours_file else None,
        Path(args.alias_file) if args.alias_file else None,
    )
    return config


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    config = build_config(args)

    if not Path(config.excel_path).exists():
        print(f"ERROR: workbook not found -> {config.excel_path}", file=sys.stderr)
        return 2

    print(f"Reading {Path(config.excel_path).name} ...")
    parse = parse_workbook(config)
    print(
        f"  {len(parse.assignments)} allotments | {len(parse.faculty_names)} faculty | "
        f"{len(parse.sections)} sections"
    )

    print("Solving ...")
    solver = TimetableSolver(parse.assignments, config)
    solve = solver.solve()
    if not solve.ok:
        print("ERROR: no conflict free timetable found with the current settings.", file=sys.stderr)
        print("       Try more days/periods or a higher --max-first-hour.", file=sys.stderr)
        return 3

    view = TimetableView(solve.placements, config)
    validation = validate(solve.placements, parse.assignments, config)

    report = render_text_report(config, parse, solve, view, validation)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "timetable_report.txt"
    report_path.write_text(report, encoding="utf-8")

    if not args.quiet:
        print()
        print(report)

    written = [report_path]
    if not args.no_excel:
        excel_path = output_dir / "Timetable_Odd_Sem_2026.xlsx"
        write_excel_report(excel_path, config, parse, solve, view, validation)
        written.append(excel_path)
    if not args.no_csv:
        csv_path = output_dir / "timetable_slots.csv"
        write_csv(csv_path, config, view)
        written.append(csv_path)

    print()
    print("=" * 70)
    print(f" Status      : {'CONFLICT FREE' if validation.ok else 'CONFLICTS FOUND'}")
    print(
        f" Sessions    : {len(solve.placements)}  |  Faculty: {len(view.faculty_names)}  "
        f"|  Sections: {len(view.sections)}"
    )
    print(f" Conflicts   : faculty {len([v for v in validation.violations if v.kind == 'faculty overlap'])}, "
          f"section {len([v for v in validation.violations if v.kind == 'section overlap'])}, "
          f"1st-hour {len([v for v in validation.violations if v.kind == 'first hour cap'])}")
    print(f" Solve time  : {solve.elapsed_s:.2f}s (cost {solve.cost:.1f})")
    for path in written:
        print(f" Written     : {path}")
    print("=" * 70)
    return 0 if validation.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

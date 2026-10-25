#!/usr/bin/env python3
"""Run the Odd Semester 2026 timetable generator.

    python generate_timetable.py
    python generate_timetable.py --max-first-hour 2 --days Mon,Tue,Wed,Thu,Fri,Sat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from timetable_generator.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

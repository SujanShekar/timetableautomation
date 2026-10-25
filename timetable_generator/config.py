"""Configuration objects for the odd-semester timetable generator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

DEFAULT_DAYS: Tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

DEFAULT_PERIOD_TIMES: Tuple[str, ...] = (
    "09:00-10:00",
    "10:00-11:00",
    "11:15-12:15",
    "13:00-14:00",
    "14:00-15:00",
    "15:00-16:00",
)

# Relative importance of the soft (quality) constraints used by the solver.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "same_day_subject": 40.0,
    "section_gap": 6.0,
    "faculty_gap": 2.0,
    "morning_gap": 12.0,
    "lab_early": 8.0,
    "first_hour_spread": 3.0,
}

# Weekly teaching hours for subjects that cannot be matched against the
# "Courses" sheet. Keys are normalised subject names.
DEFAULT_SUBJECT_HOURS: Dict[str, float] = {
    "design thinking": 2.0,
    "iot skill lab": 2.0,
    "open elective (basics of ai/ml)": 3.0,
    "uhv": 1.0,
    "rmipr": 1.0,
}


@dataclass
class TimetableConfig:
    """Every knob the generator exposes."""

    excel_path: Path
    output_dir: Path

    days: Tuple[str, ...] = DEFAULT_DAYS
    periods_per_day: int = 6
    period_times: Tuple[str, ...] = DEFAULT_PERIOD_TIMES

    # Hard constraint 3: a faculty may hold the 1st hour of the day at most
    # this many times per week.
    max_first_hour: int = 2

    # Laboratory sessions are scheduled as one contiguous block of this size.
    lab_block_hours: int = 2

    # 0-based period index from which a slot counts as "afternoon".
    afternoon_start: int = 3

    seed: int = 2026
    restarts: int = 30
    time_budget_s: float = 20.0
    node_budget: int = 40000
    beam_width: int = 4
    improve: bool = True

    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    subject_hours_overrides: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SUBJECT_HOURS))
    faculty_aliases: Dict[str, str] = field(default_factory=dict)

    # Sheet names inside the source workbook.
    sheet_subject_wise: str = "Subject wise"
    sheet_allotted: str = "Allotted New"
    sheet_courses: str = "Courses"

    def __post_init__(self) -> None:
        self.excel_path = Path(self.excel_path)
        self.output_dir = Path(self.output_dir)
        self.days = tuple(self.days)
        if len(self.period_times) != self.periods_per_day:
            raise ValueError(
                f"period_times has {len(self.period_times)} entries but "
                f"periods_per_day is {self.periods_per_day}"
            )
        if self.afternoon_start >= self.periods_per_day:
            self.afternoon_start = max(0, self.periods_per_day - 1)

    # ------------------------------------------------------------------
    @property
    def n_days(self) -> int:
        return len(self.days)

    def period_label(self, index: int) -> str:
        return self.period_times[index]

    def period_span(self, start: int, end: int) -> str:
        """Time window of a block, e.g. 11:15-14:00 for periods 3 and 4."""

        if end <= start:
            return self.period_times[start]
        first = self.period_times[start].split("-")[0].strip()
        last = self.period_times[end].split("-")[-1].strip()
        return f"{first}-{last}"

    def load_overrides(self, hours_file: Path | None, alias_file: Path | None) -> None:
        """Merge optional JSON override files into the configuration."""

        if hours_file and Path(hours_file).exists():
            payload = json.loads(Path(hours_file).read_text(encoding="utf-8"))
            for key, value in payload.items():
                self.subject_hours_overrides[key.strip().lower()] = float(value)

        if alias_file and Path(alias_file).exists():
            payload = json.loads(Path(alias_file).read_text(encoding="utf-8"))
            for key, value in payload.items():
                self.faculty_aliases[key.strip()] = str(value).strip()

    def apply_faculty_aliases(self, name: str) -> str:
        return self.faculty_aliases.get(name, name)

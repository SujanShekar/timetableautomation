from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

DEFAULT_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
DEFAULT_PERIOD_TIMES = ("09:00-10:00", "10:00-11:00", "11:30-12:30", "12:30-13:30", "14:00-15:00", "15:00-16:00")
TEA_BREAK = ("11:00", "11:30")
LUNCH_BREAK = ("13:30", "14:00")
LAB_BLOCKS = ((0, 1), (2, 3), (4, 5))
LAB_BLOCK_SLOTS = LAB_BLOCKS
DEFAULT_SUBJECT_HOURS = {"design thinking": 2.0, "iot skill lab": 2.0, "open elective (basics of ai/ml)": 3.0, "uhv": 1.0, "rmipr": 1.0}
SUBJECT_HOUR_RULES = {(3, "uhv"): 1.0, (3, "maths"): 5.0, (5, "iks"): 1.0, (5, "rmipr"): 1.0, (5, "computer networks"): 4.0}
SEVENTH_SEMESTER_DAYS = (0, 1, 2)
DEFAULT_WEIGHTS = {"section_gap": 3.0, "faculty_gap": 2.0, "morning_gap": 1.0, "same_day_subject": 1.5, "first_hour_spread": 0.5, "lab_early": 0.8}


@dataclass
class TimetableConfig:
    excel_path: Path
    output_dir: Path
    days: Tuple[str, ...] = DEFAULT_DAYS
    periods_per_day: int = 6
    period_times: Tuple[str, ...] = DEFAULT_PERIOD_TIMES
    max_first_hour: int = 2
    max_last_hour: int = 2
    last_hour_cap: int = 2
    max_daily_hours: int = 4
    max_consecutive_hours: int = 2
    lab_block_hours: int = 2
    lab_block_slots: Tuple[Tuple[int, int], ...] = field(default_factory=lambda: LAB_BLOCKS)
    seed: int = 2026
    restarts: int = 30
    time_budget_s: float = 20.0
    node_budget: int = 40000
    beam_width: int = 4
    improve: bool = True
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    subject_hours_overrides: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SUBJECT_HOURS))
    subject_hour_rules: Dict[Tuple[int, str], float] = field(default_factory=lambda: dict(SUBJECT_HOUR_RULES))
    seventh_semester_days: Tuple[int, ...] = field(default_factory=lambda: tuple(SEVENTH_SEMESTER_DAYS))
    faculty_aliases: Dict[str, str] = field(default_factory=dict)
    sheet_subject_wise: str = "Subject wise"
    sheet_allotted: str = "Allotted New"
    sheet_courses: str = "Courses"
    morning_start: int = 0
    morning_end: int = 1
    afternoon_start: int = 2
    afternoon_end: int = 5
    lab_morning_start: int = 0
    lab_morning_end: int = 2
    lab_afternoon_start: int = 4
    lab_afternoon_end: int = 6
    first_hour_indices: Tuple[int, ...] = (0,)
    last_hour_indices: Tuple[int, ...] = (5,)
    tea_break_start: int = 2
    tea_break_end: int = 2
    lunch_break_start: int = 3
    lunch_break_end: int = 4
    periods_per_day_count: int = 6

    def __post_init__(self):
        self.excel_path = Path(self.excel_path)
        self.output_dir = Path(self.output_dir)
        self.days = tuple(self.days)
        if len(self.period_times) != self.periods_per_day:
            raise ValueError("bad")
        self.seventh_semester_days = tuple(self.seventh_semester_days)
        if getattr(self, "lab_block_slots", None) is None:
            self.lab_block_slots = LAB_BLOCKS
        self.lab_block_slots = tuple(self.lab_block_slots)
        if getattr(self, "last_hour_cap", None) is None:
            self.last_hour_cap = getattr(self, "max_last_hour", 2)
        if getattr(self, "max_last_hour", None) is None:
            self.max_last_hour = getattr(self, "last_hour_cap", 2)
        if not hasattr(self, "periods_per_day_count") or self.periods_per_day_count is None:
            self.periods_per_day_count = self.periods_per_day

    @property
    def n_days(self):
        return len(self.days)

    def period_label(self, index):
        return self.period_times[index]

    def period_span(self, start, end):
        if end <= start:
            return self.period_times[start]
        first = self.period_times[start].split("-")[0].strip()
        last = self.period_times[end].split("-")[-1].strip()
        return f"{first}-{last}"

    def allowed_days(self, semester):
        if semester == 7:
            return self.seventh_semester_days
        return tuple(range(self.n_days))

    def lab_block_starts(self):
        blocks = getattr(self, "lab_block_slots", None) or LAB_BLOCKS
        return tuple(s for s, _ in blocks)

    def load_overrides(self, hours_file, alias_file):
        if hours_file and Path(hours_file).exists():
            payload = json.loads(Path(hours_file).read_text(encoding="utf-8"))
            for k, v in payload.items():
                self.subject_hours_overrides[k.strip().lower()] = float(v)
        if alias_file and Path(alias_file).exists():
            payload = json.loads(Path(alias_file).read_text(encoding="utf-8"))
            for k, v in payload.items():
                self.faculty_aliases[k.strip()] = str(v).strip()

    def apply_faculty_aliases(self, name):
        return self.faculty_aliases.get(name, name)

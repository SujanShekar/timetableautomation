"""Independent verification of the produced timetable.

The validator does not trust the solver: it rebuilds the occupancy tables
from the final placement list and re-checks every hard constraint.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .config import TimetableConfig
from .models import Assignment, Placement, Violation


@dataclass
class ValidationReport:
    violations: List[Violation] = field(default_factory=list)
    faculty_first_hour: Dict[str, int] = field(default_factory=dict)
    faculty_hours: Dict[str, float] = field(default_factory=dict)
    section_hours: Dict[Tuple[int, str], float] = field(default_factory=dict)
    faculty_days: Dict[str, int] = field(default_factory=dict)
    section_days: Dict[Tuple[int, str], int] = field(default_factory=dict)
    checked_placements: int = 0

    @property
    def errors(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == "ERROR"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> Dict[str, int]:
        return {
            "placements": self.checked_placements,
            "faculty": len(self.faculty_hours),
            "sections": len(self.section_hours),
            "errors": len(self.errors),
        }


def validate(
    placements: Sequence[Placement],
    assignments: Sequence[Assignment],
    config: TimetableConfig,
) -> ValidationReport:
    report = ValidationReport()
    faculty_slots: Dict[Tuple[str, int, int], List[str]] = defaultdict(list)
    section_slots: Dict[Tuple, List[str]] = defaultdict(list)
    faculty_day_set: set = set()
    faculty_day_map: Dict[str, set] = defaultdict(set)
    section_day_map: Dict[Tuple, set] = defaultdict(set)

    for placement in placements:
        meeting = placement.meeting
        report.checked_placements += 1
        report.faculty_hours[meeting.faculty] = report.faculty_hours.get(meeting.faculty, 0.0) + meeting.duration
        section_key = (meeting.section.semester, meeting.section.letter)
        report.section_hours[section_key] = report.section_hours.get(section_key, 0.0) + meeting.duration

        if placement.day < 0 or placement.day >= config.n_days:
            report.violations.append(
                Violation("grid", f"{meeting.subject} for {meeting.faculty} is outside the working week")
            )
            continue
        if placement.start < 0 or placement.end >= config.periods_per_day:
            report.violations.append(
                Violation(
                    "grid",
                    f"{meeting.subject} for {meeting.faculty} exceeds period {config.periods_per_day}",
                )
            )
            continue

        for period in placement.periods:
            faculty_slots[(meeting.faculty, placement.day, period)].append(
                f"{meeting.subject} ({meeting.section.label})"
            )
            section_slots[(section_key, placement.day, period)].append(
                f"{meeting.subject} ({meeting.faculty})"
            )
        if placement.start == 0:
            report.faculty_first_hour[meeting.faculty] = report.faculty_first_hour.get(meeting.faculty, 0) + 1
        faculty_day_set.add(meeting.faculty)
        faculty_day_map[meeting.faculty].add(placement.day)
        section_day_map[section_key].add(placement.day)

    # H1 - a faculty may not teach two classes at the same time
    for (faculty, day, period), items in sorted(faculty_slots.items()):
        if len(items) > 1:
            report.violations.append(
                Violation(
                    "faculty overlap",
                    f"{faculty} has {len(items)} classes on {config.days[day]} period {period + 1}: "
                    + ", ".join(items),
                )
            )

    # H2 - a section may not follow two subjects at the same time
    for (section_key, day, period), items in sorted(section_slots.items()):
        if len(items) > 1:
            label = f"{section_key[0]} Sem Sec {section_key[1]}"
            report.violations.append(
                Violation(
                    "section overlap",
                    f"{label} has {len(items)} subjects on {config.days[day]} period {period + 1}: "
                    + ", ".join(items),
                )
            )

    # H3 - the 1st hour must be distributed across the faculty
    for faculty, count in sorted(report.faculty_first_hour.items()):
        if count > config.max_first_hour:
            report.violations.append(
                Violation(
                    "first hour cap",
                    f"{faculty} holds the 1st hour {count} times (limit {config.max_first_hour})",
                )
            )

    # H5 - every required hour must be scheduled
    report.faculty_days = {f: len(days) for f, days in faculty_day_map.items()}
    report.section_days = {s: len(days) for s, days in section_day_map.items()}

    scheduled: Dict[Tuple[str, Tuple[int, str]], float] = defaultdict(float)
    for placement in placements:
        meeting = placement.meeting
        key = (meeting.subject, (meeting.section.semester, meeting.section.letter))
        scheduled[key] += meeting.duration
    for assignment in assignments:
        key = (assignment.subject, assignment.section.key)
        got = scheduled.get(key, 0.0)
        if abs(got - assignment.total_hours) > 1e-6:
            report.violations.append(
                Violation(
                    "coverage",
                    f"{assignment.subject} for {assignment.section.label} needs "
                    f"{assignment.total_hours}h but {got:.0f}h are scheduled",
                )
            )
    return report

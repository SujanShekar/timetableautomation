"""Domain model shared by the parser, the solver and the reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_ORDINALS = {
    1: "1st",
    2: "2nd",
    3: "3rd",
    4: "4th",
    5: "5th",
    6: "6th",
    7: "7th",
    8: "8th",
    9: "9th",
    10: "10th",
}


def semester_ordinal(semester: int) -> str:
    return _ORDINALS.get(semester, f"{semester}th")


def semester_label(semester: int) -> str:
    return f"{semester_ordinal(semester)} Sem"


@dataclass(frozen=True)
class Course:
    """A course row taken from the "Courses" sheet."""

    code: str
    name: str
    credits: float
    semester: int


@dataclass(frozen=True)
class Section:
    """A section of a semester, e.g. 3rd Sem Sec A."""

    semester: int
    letter: str

    @property
    def key(self) -> Tuple[int, str]:
        return (self.semester, self.letter)

    @property
    def label(self) -> str:
        return f"{semester_label(self.semester)} - Sec {self.letter}"

    @property
    def short(self) -> str:
        return f"{semester_ordinal(self.semester)} Sem/Sec {self.letter}"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.label


@dataclass
class Assignment:
    """One subject delivered by one faculty to one section."""

    subject: str
    section: Section
    faculty: str
    hours: float
    is_lab: bool = False
    course_code: Optional[str] = None
    hours_source: str = "default"

    @property
    def total_hours(self) -> int:
        return int(round(self.hours))

    @property
    def label(self) -> str:
        return f"{self.subject} ({self.section.label})"


@dataclass(eq=False)
class Meeting:
    """A scheduled block: one or more contiguous periods in the grid."""

    assignment: Assignment
    duration: int = 1
    kind: str = "theory"

    @property
    def subject(self) -> str:
        return self.assignment.subject

    @property
    def faculty(self) -> str:
        return self.assignment.faculty

    @property
    def section(self) -> Section:
        return self.assignment.section


@dataclass
class FacultyProfile:
    """Everything known about one faculty member."""

    name: str
    subjects_by_semester: Dict[int, List[str]] = field(default_factory=dict)
    allotted_subjects: List[str] = field(default_factory=list)
    allotted_sem_hints: Dict[str, List[int]] = field(default_factory=dict)
    workload_units: Optional[float] = None
    is_placeholder: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def subjects(self) -> List[str]:
        out: List[str] = []
        for sem in sorted(self.subjects_by_semester):
            for subject in self.subjects_by_semester[sem]:
                if subject not in out:
                    out.append(subject)
        return out

    @property
    def semesters(self) -> List[int]:
        return sorted(self.subjects_by_semester)


@dataclass
class Placement:
    """Concrete slot of a meeting inside the weekly grid."""

    meeting: Meeting
    day: int
    start: int

    @property
    def periods(self) -> range:
        return range(self.start, self.start + self.meeting.duration)

    @property
    def end(self) -> int:
        return self.start + self.meeting.duration - 1


@dataclass
class Violation:
    kind: str
    detail: str
    severity: str = "ERROR"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"[{self.severity}] {self.kind}: {self.detail}"

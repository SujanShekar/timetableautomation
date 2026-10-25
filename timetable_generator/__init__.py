"""Automated, conflict free timetable generation for the Odd Semester 2026."""

from .config import TimetableConfig
from .models import Assignment, Course, FacultyProfile, Meeting, Placement, Section
from .parser import parse_workbook
from .reporting import TimetableView, render_text_report, write_csv, write_excel_report
from .solver import SolveResult, TimetableSolver
from .validator import ValidationReport, validate

__all__ = [
    "Assignment",
    "Course",
    "FacultyProfile",
    "Meeting",
    "Placement",
    "Section",
    "SolveResult",
    "TimetableConfig",
    "TimetableSolver",
    "TimetableView",
    "ValidationReport",
    "parse_workbook",
    "render_text_report",
    "validate",
    "write_csv",
    "write_excel_report",
]

__version__ = "1.0.0"

"""Constraint satisfaction solver for the weekly timetable.

The problem is modelled as a finite-domain CSP: every *meeting* (a single
theory hour or a contiguous laboratory block) is a variable whose domain is
the set of weekly grid slots.

Hard constraints
    H1  no faculty teaches two classes in the same slot
    H2  no section follows two subjects in the same slot
    H3  a faculty holds the 1st hour of the day at most ``max_first_hour``
        times per week
    H4  laboratory sessions occupy two contiguous periods of one day
    H5  every scheduled period stays inside the working grid

Soft constraints (minimised, weighted)
    S1  a subject is spread over as many different days as possible
    S2  a section's day is not fragmented by gaps
    S3  a faculty's day is not fragmented by gaps
    S4  laboratory blocks prefer the afternoon
    S5  the 1st hour is spread over the faculty, not concentrated
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .config import TimetableConfig
from .models import Assignment, Meeting, Placement


def _gaps(periods: set) -> int:
    """Number of empty periods inside the span of a day."""

    if len(periods) < 2:
        return 0
    return (max(periods) - min(periods) + 1) - len(periods)


def _morning(periods: set) -> int:
    """Free periods before the first class of a day (0 when the day is empty)."""

    if not periods:
        return 0
    return min(periods)


@dataclass
class SolveResult:
    placements: List[Placement] = field(default_factory=list)
    cost: float = 0.0
    attempts: int = 0
    nodes: int = 0
    elapsed_s: float = 0.0
    status: str = "unknown"
    first_hour_cap: int = 2

    @property
    def ok(self) -> bool:
        return self.status == "solved"


class TimetableSolver:
    def __init__(self, assignments: Sequence[Assignment], config: TimetableConfig) -> None:
        self.config = config
        self.assignments = list(assignments)
        self.days = config.n_days
        self.periods = config.periods_per_day
        self.w = config.weights
        self.meetings: List[Meeting] = []
        self._build_meetings()
        self._init_state()

    # ------------------------------------------------------------------
    # setup
    # ------------------------------------------------------------------
    def _build_meetings(self) -> None:
        for assignment in self.assignments:
            hours = assignment.total_hours
            if hours <= 0:
                continue
            if assignment.is_lab and hours >= self.config.lab_block_hours:
                self.meetings.append(
                    Meeting(assignment, duration=self.config.lab_block_hours, kind="lab")
                )
                for _ in range(hours - self.config.lab_block_hours):
                    self.meetings.append(Meeting(assignment, duration=1, kind="theory"))
            else:
                for _ in range(hours):
                    self.meetings.append(Meeting(assignment, duration=1, kind="theory"))

    def _init_state(self) -> None:
        self.occ_faculty: Dict[Tuple[str, int, int], Meeting] = {}
        self.occ_section: Dict[Tuple, Meeting] = {}
        self.section_day_periods: Dict[Tuple, set] = {}
        self.faculty_day_periods: Dict[Tuple, set] = {}
        self.subject_day_count: Dict[Tuple, int] = {}
        self.first_hour_count: Dict[str, int] = {}
        self.placement: Dict[Meeting, Tuple[int, int]] = {}
        self.cost = 0.0
        self.nodes = 0
        self.total_nodes = 0

    # ------------------------------------------------------------------
    # cost model
    # ------------------------------------------------------------------
    def _entity_terms(self, meeting: Meeting, day: int) -> float:
        terms = 0.0
        section_periods = self.section_day_periods.get((meeting.section, day), set())
        terms += self.w["section_gap"] * _gaps(section_periods)
        terms += self.w["morning_gap"] * _morning(section_periods)
        faculty_periods = self.faculty_day_periods.get((meeting.faculty, day), set())
        terms += self.w["faculty_gap"] * _gaps(faculty_periods)
        repeats = self.subject_day_count.get((meeting.section, meeting.subject, day), 0)
        terms += self.w["same_day_subject"] * max(0, repeats - 1)
        terms += self.w["first_hour_spread"] * self.first_hour_count.get(meeting.faculty, 0) ** 2
        return terms

    def _lab_term(self, meeting: Meeting, start: int) -> float:
        if meeting.kind == "lab" and start + meeting.duration <= self.config.afternoon_start:
            return self.w["lab_early"]
        return 0.0

    def _delta_cost(self, meeting: Meeting, day: int, start: int) -> float:
        """Cost added by placing ``meeting`` at (day, start) in the current state."""

        periods = set(range(start, start + meeting.duration))
        delta = 0.0

        section_periods = self.section_day_periods.get((meeting.section, day), set())
        delta += self.w["section_gap"] * (_gaps(section_periods | periods) - _gaps(section_periods))
        delta += self.w["morning_gap"] * (
            _morning(section_periods | periods) - _morning(section_periods)
        )

        faculty_periods = self.faculty_day_periods.get((meeting.faculty, day), set())
        delta += self.w["faculty_gap"] * (_gaps(faculty_periods | periods) - _gaps(faculty_periods))

        repeats = self.subject_day_count.get((meeting.section, meeting.subject, day), 0)
        delta += self.w["same_day_subject"] * (max(0, repeats) - max(0, repeats - 1))

        first = self.first_hour_count.get(meeting.faculty, 0)
        if start == 0:
            delta += self.w["first_hour_spread"] * ((first + 1) ** 2 - first ** 2)

        delta += self._lab_term(meeting, start)
        return delta

    # ------------------------------------------------------------------
    # placement primitives
    # ------------------------------------------------------------------
    def _feasible(self, meeting: Meeting, day: int, start: int) -> bool:
        if day < 0 or day >= self.days:
            return False
        if start < 0 or start + meeting.duration > self.periods:
            return False
        for period in range(start, start + meeting.duration):
            if (meeting.faculty, day, period) in self.occ_faculty:
                return False
            if (meeting.section, day, period) in self.occ_section:
                return False
        if start == 0:
            if self.first_hour_count.get(meeting.faculty, 0) + 1 > self.config.max_first_hour:
                return False
        return True

    def _apply(self, meeting: Meeting, day: int, start: int, add: bool) -> None:
        periods = set(range(start, start + meeting.duration))
        before = self._entity_terms(meeting, day)

        if add:
            for period in periods:
                self.occ_faculty[(meeting.faculty, day, period)] = meeting
                self.occ_section[(meeting.section, day, period)] = meeting
            self.section_day_periods.setdefault((meeting.section, day), set()).update(periods)
            self.faculty_day_periods.setdefault((meeting.faculty, day), set()).update(periods)
            key = (meeting.section, meeting.subject, day)
            self.subject_day_count[key] = self.subject_day_count.get(key, 0) + 1
            if start == 0:
                self.first_hour_count[meeting.faculty] = self.first_hour_count.get(meeting.faculty, 0) + 1
            self.placement[meeting] = (day, start)
        else:
            for period in periods:
                self.occ_faculty.pop((meeting.faculty, day, period), None)
                self.occ_section.pop((meeting.section, day, period), None)
            section_periods = self.section_day_periods.get((meeting.section, day))
            if section_periods is not None:
                section_periods.difference_update(periods)
            faculty_periods = self.faculty_day_periods.get((meeting.faculty, day))
            if faculty_periods is not None:
                faculty_periods.difference_update(periods)
            key = (meeting.section, meeting.subject, day)
            self.subject_day_count[key] = max(0, self.subject_day_count.get(key, 0) - 1)
            if start == 0:
                self.first_hour_count[meeting.faculty] = max(
                    0, self.first_hour_count.get(meeting.faculty, 0) - 1
                )
            self.placement.pop(meeting, None)

        after = self._entity_terms(meeting, day)
        self.cost += after - before
        self.cost += self._lab_term(meeting, start) if add else -self._lab_term(meeting, start)

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def _candidates(self, meeting: Meeting) -> List[Tuple[int, int, float]]:
        out: List[Tuple[int, int, float]] = []
        for day in range(self.days):
            for start in range(self.periods - meeting.duration + 1):
                if not self._feasible(meeting, day, start):
                    continue
                out.append((day, start, self._delta_cost(meeting, day, start)))
        return out

    def _order(self, rng: random.Random) -> List[Meeting]:
        faculty_load: Dict[str, int] = {}
        section_load: Dict[Tuple, int] = {}
        for meeting in self.meetings:
            faculty_load[meeting.faculty] = faculty_load.get(meeting.faculty, 0) + 1
            section_load[meeting.section] = section_load.get(meeting.section, 0) + 1

        ordered = list(self.meetings)
        rng.shuffle(ordered)
        # most constrained first: busy faculty and busy sections commit early
        ordered.sort(key=lambda m: -(faculty_load.get(m.faculty, 0) + section_load.get(m.section, 0)))
        return ordered

    def _dfs(self, order: List[Meeting], rng: random.Random, budget: int) -> bool:
        def rec(index: int) -> bool:
            if index == len(order):
                return True
            self.nodes += 1
            self.total_nodes += 1
            if self.nodes > budget:
                return False
            meeting = order[index]
            candidates = self._candidates(meeting)
            if not candidates:
                return False
            candidates.sort(key=lambda item: item[2])
            pool = candidates[: max(1, self.config.beam_width)]
            if len(pool) > 1 and rng.random() < 0.3:
                rng.shuffle(pool)
            for day, start, _ in pool:
                self._apply(meeting, day, start, add=True)
                if rec(index + 1):
                    return True
                self._apply(meeting, day, start, add=False)
            return False

        return rec(0)

    # ------------------------------------------------------------------
    # local search
    # ------------------------------------------------------------------
    def _all_slots(self, meeting: Meeting) -> List[Tuple[int, int]]:
        return [
            (day, start)
            for day in range(self.days)
            for start in range(self.periods - meeting.duration + 1)
        ]

    def _improve(self, rng: random.Random, deadline: float) -> bool:
        """Hill climbing on slot moves and swaps; returns True when changed."""

        changed = False
        order = list(self.meetings)
        rng.shuffle(order)
        for meeting in order:
            if time.monotonic() > deadline:
                break
            current = self.placement.get(meeting)
            if current is None:
                continue
            best_cost = self.cost
            best_move = None

            for day, start in self._all_slots(meeting):
                if (day, start) == current:
                    continue
                if not self._feasible(meeting, day, start):
                    continue
                self._apply(meeting, *current, add=False)
                self._apply(meeting, day, start, add=True)
                if self.cost < best_cost - 1e-9:
                    best_cost = self.cost
                    best_move = ("move", day, start, None)
                self._apply(meeting, day, start, add=False)
                self._apply(meeting, *current, add=True)

            for other in self.meetings:
                if other is meeting or other.duration != meeting.duration:
                    continue
                other_slot = self.placement.get(other)
                if other_slot is None:
                    continue
                self._apply(other, *other_slot, add=False)
                self._apply(meeting, *current, add=False)
                if self._feasible(meeting, *other_slot) and self._feasible(other, *current):
                    self._apply(other, *current, add=True)
                    self._apply(meeting, *other_slot, add=True)
                    if self.cost < best_cost - 1e-9:
                        best_cost = self.cost
                        best_move = ("swap", other_slot, None, other)
                    self._apply(meeting, *other_slot, add=False)
                    self._apply(other, *current, add=False)
                self._apply(other, *other_slot, add=True)
                self._apply(meeting, *current, add=True)

            if best_move is not None:
                kind = best_move[0]
                if kind == "move":
                    _, day, start, _ = best_move
                    self._apply(meeting, *current, add=False)
                    self._apply(meeting, day, start, add=True)
                else:
                    _, target, _, other = best_move
                    self._apply(other, *self.placement[other], add=False)
                    self._apply(meeting, *current, add=False)
                    self._apply(other, *current, add=True)
                    self._apply(meeting, *target, add=True)
                changed = True
        return changed

    # ------------------------------------------------------------------
    # driver
    # ------------------------------------------------------------------
    def solve(self) -> SolveResult:
        started = time.monotonic()
        deadline = started + self.config.time_budget_s
        result = SolveResult(first_hour_cap=self.config.max_first_hour)

        if not self.meetings:
            result.status = "solved"
            result.elapsed_s = time.monotonic() - started
            return result

        best_cost = float("inf")
        best_snapshot: Optional[Dict[Meeting, Tuple[int, int]]] = None
        attempts = 0

        while attempts < self.config.restarts and time.monotonic() < deadline:
            attempts += 1
            rng = random.Random(self.config.seed * 7919 + attempts)
            self._init_state()
            order = self._order(rng)
            if self._dfs(order, rng, self.config.node_budget):
                if self.cost < best_cost:
                    best_cost = self.cost
                    best_snapshot = dict(self.placement)
                if best_cost <= 0:
                    break

        if best_snapshot is None:
            result.attempts = attempts
            result.nodes = self.total_nodes
            result.elapsed_s = time.monotonic() - started
            result.status = "infeasible"
            return result

        self._init_state()
        for meeting, slot in best_snapshot.items():
            self._apply(meeting, slot[0], slot[1], add=True)
        best_cost = self.cost

        if self.config.improve:
            rng = random.Random(self.config.seed + 999)
            for _ in range(200):
                if time.monotonic() > deadline or self.cost <= 0:
                    break
                if not self._improve(rng, deadline):
                    break

        placements = [
            Placement(meeting=meeting, day=slot[0], start=slot[1])
            for meeting, slot in self.placement.items()
        ]
        result.placements = placements
        result.cost = self.cost
        result.attempts = attempts
        result.nodes = self.total_nodes
        result.elapsed_s = time.monotonic() - started
        result.status = "solved"
        return result

# Timetable Generator - Odd Semester 2026

Automated, conflict-free weekly timetable for the course allotment workbook
`Course Allotment Odd Sem-2026.xlsx`.

The generator parses the workbook, builds a `Faculty -> Subject -> Section` map and
solves the week with a backtracking constraint solver that honours every hard
constraint. It then writes a section-wise timetable, a faculty-wise timetable and
an independent validation report.

```
python -m pip install -r requirements.txt
python generate_timetable.py
```

## What it reads

| Sheet | Role |
| --- | --- |
| `Subject wise` | authoritative grid: `Subject | Semester | Sec A..Sec F | Faculty` |
| `Allotted New` | faculty load sheet, used for cross-checking and the data-gap report |
| `Courses` | credit catalogue, used to derive the weekly hours of every subject |

Parsing is defensive: merged header cells, `NaN`, empty cells, `-` placeholders,
trailing spaces, headers in unexpected rows and numeric cells mixed into the
subject columns are all tolerated.

### Weekly hours

Hours come from the `Courses` sheet (`Credits` column), matched by normalised
subject name and semester. Subjects that cannot be matched fall back to
`subject_hours.example.json` / `config.DEFAULT_SUBJECT_HOURS` and are listed in
the report under *"Subjects using the default weekly hours"*.

Laboratory subjects (2 credits) are scheduled as one contiguous two-period block.

## Constraints

### Hard (never violated, re-checked after the solve)

| Id | Constraint | Enforcement |
| --- | --- | --- |
| H1 | A faculty member may not teach two classes at the same time | `occ_faculty[(faculty, day, period)]` |
| H2 | A section may not follow two subjects at the same time | `occ_section[(section, day, period)]` |
| H3 | A faculty member holds the 1st hour at most `--max-first-hour` times per week (default 2) | `first_hour_count[faculty]`, checked before every placement |
| H4 | A laboratory session occupies two contiguous periods of one day | block meetings, duration 2 |
| H5 | Every session stays inside the working grid | slot enumeration bounds |

H1 and H2 apply across **all** semesters, so a teacher handling 1st, 5th and 7th
semester classes can never be double booked.

### Soft (minimised by the solver, weights in `config.py`)

`same_day_subject` (spread a subject over different days) - `section_gap` -
`faculty_gap` - `morning_gap` (no late start, this is what makes the 1st hour
used) - `lab_early` (labs in the afternoon) - `first_hour_spread` (a convex
penalty, so the 1st hour is spread over the faculty instead of concentrated).

## Algorithm

1. **Parse** the three sheets into `Course`, `SubjectRow`, `Assignment` and
   `FacultyProfile` objects.
2. **Resolve hours** per subject (credits -> weekly hours) with alias and fuzzy
   name matching.
3. **Build meetings** - a theory subject of `n` credits becomes `n` one-period
   meetings, a lab becomes one two-period block.
4. **Solve** - randomised depth-first search with backtracking and a beam of the
   best candidate slots per level, variables ordered by constraint degree
   (busy faculty and busy sections first). Each restart uses a new seed; the best
   complete solution is kept.
5. **Polish** - hill climbing over slot moves and slot swaps until the time
   budget is exhausted or no improvement is possible.
6. **Validate** - `validator.py` rebuilds the occupancy tables from the final
   placement list and re-checks H1-H5, so the report never trusts the solver.
7. **Report** - text report, Excel workbook and flat CSV.

## Output

```
output/
├── timetable_report.txt          # section view, faculty view, validation, master map
├── Timetable_Odd_Sem_2026.xlsx   # section grid, faculty grid, summaries, validation
└── timetable_slots.csv           # flat slot table (semester, section, day, period, ...)
```

The Excel workbook contains the sheets `Timetable by Section`, `Timetable by
Faculty`, `Section Summary`, `Faculty Load`, `Subject Master`, `Validation` and
`Data Notes`.

The faculty view is the proof of H1: each faculty is a row, each day a line, so a
double booking would show up immediately as two entries in the same slot.

## Options

```
python generate_timetable.py --help

  --excel PATH            source workbook
  --out DIR               output directory
  --days Mon,Tue,...      working days
  --periods N             periods per day
  --period-times "..."    time window per period
  --max-first-hour N      1st hour limit per faculty per week (default 2)
  --lab-block N           laboratory block length (default 2)
  --seed N                random seed (default 2026)
  --restarts N            solver restarts
  --time-budget S         solver time budget
  --no-improve            skip the hill climbing pass
  --alias-file PATH       JSON map for placeholder faculty names
  --hours-file PATH       JSON overrides for weekly hours
  --no-excel / --no-csv   skip an export
  --quiet                 only print the summary
```

## Overrides

`faculty_aliases.example.json` maps the placeholder names used in `Subject wise`
(`New Faculty 1` ... `New Faculty 4`) to real faculty:

```json
{ "New Faculty 1": "Dr. A. B. C" }
```

`subject_hours.example.json` overrides the weekly hours of subjects that are not
present in the `Courses` sheet.

## Independent check

```bash
python verify_timetable.py output/timetable_slots.csv --max-first-hour 2
```

Re-reads the exported CSV (not the solver state) and re-checks the three hard
constraints.

## Layout

```
generate_timetable.py        entry point
verify_timetable.py          standalone checker for the exported CSV
timetable_generator/
├── config.py                all knobs: days, periods, weights, hour defaults
├── models.py                Course, Section, Assignment, Meeting, Placement
├── parser.py                Excel parsing, hours resolution, cross-check
├── solver.py                CSP backtracking solver + hill climbing
├── validator.py             independent constraint verification
├── reporting.py             text report, Excel workbook, CSV
└── cli.py                   argument handling and orchestration
```

## Known data gaps in the source workbook

The report lists these automatically (section 6 *Data Notes*):

* `New Faculty 1..4` in `Subject wise` are placeholders; they are scheduled as
  separate pseudo faculty until an alias file maps them.
* Subjects present in `Allotted New` but without a section in `Subject wise`
  (for example the newly added `Veena`, `Shalini M S`, `Sumathi S K`) cannot be
  placed - a section is required to build the grid.
* The 1st semester sections only carry three subjects each (6 h/week), which is
  what the allotment sheet provides.

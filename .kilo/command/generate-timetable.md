---
description: Generate a conflict-free weekly timetable from the Odd Semester 2026 course allotment workbook.
argument-hint: "[--max-first-hour N] [--days Mon,Tue,...] [--out DIR]"
---

Generate the Odd Semester 2026 timetable from `Course Allotment Odd Sem-2026.xlsx`.

Run the generator with the arguments supplied by the user (if any):

```bash
python generate_timetable.py $ARGUMENTS
```

Then:

1. Report the console summary: status (CONFLICT FREE / conflicts), the number of
   sessions, faculty and sections, and the conflict counters.
2. Point the user to the generated artefacts in the output directory:
   - `timetable_report.txt` (section view, faculty view, validation, master mapping)
   - `Timetable_Odd_Sem_2026.xlsx` (section grid, faculty grid, summaries, validation)
   - `timetable_slots.csv` (flat slot table)
3. If the run reports conflicts or fails, explain which constraint was violated and
   suggest the relevant knob (`--max-first-hour`, `--days`, `--periods`, `--time-budget`).
4. Never edit the source workbook; only the generator and the JSON override files.

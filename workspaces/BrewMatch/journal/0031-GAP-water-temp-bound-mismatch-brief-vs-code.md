# GAP — Water-temp bound mismatch between brief and code

**Date**: 2026-06-13
**Type**: GAP

## The gap

Brief §6.4 (Recipe Optimization) constrains optimization to **water temp 85–96°C**. The
`Recipe` validation in `src/data_models.py::Recipe.__post_init__` allows **water_temp_c
85.0–100.0**. The two bounds disagree (96 vs 100) and the discrepancy is undocumented.

## Likely cause (unconfirmed)

Probably INTENTIONAL layering: the data-validation band (85–100) is the wider "what is a
storable recipe" envelope, while the optimizer search band (85–96) is deliberately tighter to
keep recommendations in a safe pour-over range. If so, both bounds are correct for their layer
— they are just never stated together, so a reader sees a contradiction.

## Follow-up needed

1. Confirm with the human whether 85–96 (optimizer) vs 85–100 (validation) is intentional.
2. If intentional: document BOTH bounds in `specs/recipe-optimization.md` (search band) and
   `specs/data-models.md` (validation band), noting why they differ.
3. If not intentional: reconcile to a single bound.

Not blocking current work; flagged so it does not silently drift. See
`01-analysis/01-research/05-brief-reanalysis-2026-06-13.md` §4.

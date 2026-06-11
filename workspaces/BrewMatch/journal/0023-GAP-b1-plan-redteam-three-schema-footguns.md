# GAP — B1 plan red-team caught three schema/persistence footguns

Date: 2026-06-11
Phase: /redteam (the plan first — pre-implementation audit)

## What was checked

Verified every factual claim in `02-plans/03-bag-based-logging.md` and
`todos/active/b1-bag-based-logging.md` against the real codebase via grep/Read.
Full assertion table in `04-validate/b1-plan-redteam.md`. Posture L5_DELEGATED.

## Gaps found (all in the todo text, fixed before any code)

1. **Dose-storage ambiguity (M1).** `BrewRecord` (data_models.py:209) has no dose
   field — dose lives in `recipe_used.dose_g`. The todos didn't say whether the
   saved recipe snapshot is the original template or the scaled actual brew.
   Resolved: store the scaled recipe (so history shows the true cup), with a
   denormalized `actual_dose_g` column for the cheap countdown SUM.

2. **Placeholder convention (M2).** Bag CRUD must use `?` placeholders; db.py:151
   rewrites `?`→`%s` for Postgres. A hand-written `%s` would break local SQLite.

3. **Migration syntax wrong for SQLite (M3).** My own B1.2 trap prescribed
   `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — SQLite does not support that on
   ADD COLUMN. Corrected to backend-specific handling (SQLite PRAGMA+try/except
   per db.py:309–317; Postgres `IF NOT EXISTS` behind `_is_pg`).

## Out-of-scope observation (L1)

`specs/data-models.md` §1 says dose 12–22 g; code (`data_models.py:110`) allows
12–35 g. Pre-existing spec/code divergence, not introduced by B1. Recommend a
separate spec reconciliation; B1.5 bounds the dose input to the code's real range.

## Why this matters

All three M-findings would have surfaced mid-`/implement` as either a live-app
crash (M3, first bag-linked brew on Supabase), a local-vs-live behavior split
(M2), or inconsistent history (M1). Catching them at plan-time cost a few todo
edits; catching them at implement-time would have cost a failed shard against
the live database. The "self red-team your own todos before launch" discipline
(specs-authority Rule 5c) paid off here — two of the three were errors I wrote.

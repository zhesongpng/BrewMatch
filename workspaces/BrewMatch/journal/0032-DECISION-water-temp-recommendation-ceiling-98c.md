---
type: DECISION
date: 2026-06-14
created_at: 2026-06-14T00:00:00Z
author: human
session_id: session-2026-06-14
session_turn: 4
project: BrewMatch
topic: Resolve the water-temp bound mismatch (journal 0031) with a 98C recommendation ceiling
phase: implement
tags: [recipe-optimization, diagnosis, bounds, water-temp]
---

# DECISION — Water-temp recommendation ceiling is 98°C; storage envelope stays 100°C

Resolves the GAP raised in `0031-GAP-water-temp-bound-mismatch-brief-vs-code.md`.

## The decision

There are two distinct water-temperature limits, and they were conflated:

1. **Recommendation ceiling = 98°C.** What BrewMatch _prescribes_ (recipe optimizer
   search band + diagnosis perturbation clamp) is now capped at 98°C. Previously the
   code allowed up to 100°C and the brief said 96°C — neither matched intent.
2. **Storage envelope = 85–100°C.** What BrewMatch _accepts when a user logs a brew
   they actually made_ is unchanged. A real near-boil pour (up to 100°C) is recorded
   honestly rather than rejected.

Human guidance (2026-06-14): "it usually shouldn't be 100 most of the time, but there
are times where it can go up to 98."

## Rationale

A recommendation engine that suggests 99–100°C contradicts the human's stated ceiling —
that was the bug. But rejecting a logged 100°C brew would discard real training data, so
the validation envelope deliberately stays wider than the recommendation band. The
optimizer's existing soft constraints (light roast ≥92°C, dark roast ≤94°C) mean the
98°C hard ceiling rarely binds in practice; it exists to stop the rare runaway suggestion.

## Changes shipped

- `src/recipe_optimizer/optimizer.py` — Optuna search band 100→98; warm-start clamp 100→98.
- `src/diagnosis/engine.py` — `PARAM_RANGES["water_temp_c"]` upper bound 100→98.
- `specs/recipe-optimization.md` — decision-variable range, hard constraint C4, and code
  snippet updated to 98; C4 now documents the 98-vs-100 two-layer split.
- `specs/data-models.md` — `water_temp_c` row annotated as the storage envelope, pointing
  to recipe-optimization.md C4 for the recommendation ceiling.
- `workspaces/BrewMatch/briefs/01-product-brief.md` §6.4 — 85–96 → 85–98 with a note.
- `tests/regression/test_water_temp_recommendation_ceiling.py` — new; pushes both paths
  toward the hottest recommendation and asserts the 98°C ceiling holds.

Left unchanged on purpose: synthetic data generation, retrieval feature normalization,
the demo chart axis (all describe/encode stored brews, not recommendations), and the
soft preferred-temp defaults (90–96, well within 98).

## For Discussion

1. Counterfactual: if a future user base brews predominantly with fully-boiling water
   (100°C, e.g. for very dark robusta), would a fixed 98°C recommendation ceiling become
   a liability — and should the ceiling instead be derived per-roast rather than global?
2. The optimizer's soft dark-roast pull (≤94°C) means the 98°C hard cap almost never
   binds for dark roasts. Is there any roast/origin combination in the current 50–80
   recipe set where the 98°C cap actually changes the recommended temperature?
3. We kept storage at 100°C to preserve real logged data. Should the UI nonetheless warn
   a user who logs a brew above 98°C that they're outside the recommended band, or is that
   noise that discourages honest logging?

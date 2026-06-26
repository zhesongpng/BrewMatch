# GAP — Web grind translation lacked Streamlit's defensive round/clamp

**Date:** 2026-06-26
**Phase:** /redteam (grinder-specific grind feature, B3-grinder)
**Severity:** LOW (no user-facing bug; robustness/parity)

## Finding

The web grind translator `grindForGrinder` (apps/web/lib/recipe.ts) looked up
`grinder.mapping[String(genericSetting)]` directly. Streamlit's equivalent
`_format_grind` (src/app/pages/recommend.py:42-57) first does
`step = max(1, min(10, int(round(grind_value))))` — rounding a continuous value
to the nearest whole step and clamping to 1-10 — because "the optimizer produces
continuous values" and the grinder mappings are keyed to whole steps.

## Why it was not a user-facing bug

`Recipe.grind_setting` is typed `int` and validated `1 <= grind_setting <= 10`
in `data_models.py::__post_init__` (raises `ValueError` otherwise). So
`/recommend` always returns an integer in range, and the web mapping lookup
always succeeds on the real data path. The gap only mattered if a future path
(log-a-brew, diagnosis-adjusted grind) ever surfaced a fractional grind — then
the web would silently fall back to the generic "x / 10" instead of translating.

## Fix

Added round+clamp inside `grindForGrinder` to mirror `_format_grind`, with a
comment noting backend recipes are already validated ints (defensive). tsc +
eslint clean; 11 backend API tests pass.

## Related observations (no fix)

- The web drops the word label ("Medium") that Streamlit shows alongside the
  number; the numeric grind + grinder translation (the valuable part) is
  preserved. Treated as intentional-redesign-adjacent, not a finding.
- The web app has no JS unit-test harness, so the TS formatter's parity with
  the Python catalog is verified by inspection + the `/grinders` endpoint test,
  not a JS unit test. Out of scope to add a framework for this feature.

## Positive red-team results

- `GET /grinders` takes no input and has no DB/model dependency — serves 200
  even on a cold or partially-broken brain (resilient by construction).
- React escapes all rendered catalog values; a tampered localStorage grinder id
  degrades gracefully to the generic scale. No XSS surface.
- POST-transport refactor preserved existing behavior (/recommend, /diagnose
  tests pass). No stubs, mock data, or secrets in the diff.

# RISK — "Brew this" hand-off clobbered by Strict Mode double-invoke

Date: 2026-07-04
Phase: /redteam (Task 2 — brewer-as-gear, Recipes screen selection)
Severity: HIGH (dev-breaking; production unaffected)
Status: FIXED in the same red-team round

## What

Task 2 refactored the Recipes flow so the "Brew this" hand-off (from the Coffees
screen) waits for the brewer catalog to settle before recommending — so the brew
uses the user's owned brewer, not a hardcoded "V60". The refactor split the
original single effect into two:

1. mount effect: `setPendingBag(takePendingBag())`
2. gated effect: fire `runRecommend` once `catalogSettled`

`takePendingBag()` is one-shot — it reads AND clears the sessionStorage stash.
Next.js runs React Strict Mode in dev by default, which invokes mount effects
twice. Second invocation of effect (1) read the now-empty stash and overwrote
the captured bag with `null`, so effect (2) never fired. Result: in dev, tapping
"Brew this" landed on an empty bean form instead of recommending. Production
(no double-invoke) worked, which is exactly why this class of bug is easy to ship.

The original pre-Task-2 code avoided this by consuming AND acting in the same
effect body (the second invocation's early-return was harmless).

## Fix

Guarded the one-shot read with a `useRef(false)` latch so `takePendingBag()`
runs exactly once regardless of Strict Mode double-invoke. The ref persists
across the simulated unmount/remount (same component instance).

`components/RecipesFlow.tsx` — `pendingRead` ref around the mount effect.

## Follow-up (not blocking)

`apps/web` has NO test harness (no _.test._ / _.spec._ files, no Jest/Vitest).
This finding would have been caught by a component test of the hand-off. Standing
up a web test harness is a larger decision left to the user — flagged, not done.
See [[0034-GAP-web-grind-translation-defensive-rounding]] for the sibling
web-side gap pattern.

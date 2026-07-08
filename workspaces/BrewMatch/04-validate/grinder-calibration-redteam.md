# Red Team — Grinder Calibration Rebuild (2026-07-06)

Adversarial review of the grinder catalog rebuild + per-user calibration feature,
before commit/deploy. Spec: `workspaces/BrewMatch/grinder-calibration-spec.md`.

## Scope of what was reviewed

- `src/grinder_catalog.py` — micron-anchored, variant-aware, native-unit catalog;
  electric grinders hidden from the picker (kept in `GRINDERS`).
- `apps/web/lib/recipe.ts` — band helpers + `grindRelativeToUsual`.
- `apps/web/lib/grinderCalibration.ts` — per-grinder on-device baseline storage.
- `apps/web/components/ProfileFlow.tsx` — "your usual pour-over setting" input.
- `apps/web/components/RecipesFlow.tsx` — recipe-card grind display (3 states).
- Tests: `tests/unit/test_grinder_catalog.py`, `tests/integration/test_api_endpoints.py`.

## Findings

| ID  | Sev                | Finding                                                                                                                                                                                                                                                                                    | Status                                                                                                                                                                                             |
| --- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H1  | High (operational) | Brain (Render) and front-end (Vercel) deploy independently. Catalog shape changed (`mapping` values numbers→objects; `scale`→`reading`). During the deploy window the _live_ old front-end **throws** (`value.toFixed` on an object) until Vercel catches up. Self-heals when both finish. | OPEN — accept brief blip; deploy at a quiet moment, watch both deploys go green                                                                                                                    |
| H2  | Medium             | Recipe screen still showed "Generic scale (1–10)" / "not just 1–10" — the exact framing flagged as confusing (fixed in Profile, missed here).                                                                                                                                              | FIXED (same commit)                                                                                                                                                                                |
| M1  | Medium             | No web test infra (no test script). New TS logic (`grindRelativeToUsual`, band labels, calibration storage) has zero coverage. Python↔TS band/micron consistency unguarded — edit one, not the other, and they silently diverge.                                                           | OPEN — needs a JS test harness (own small task)                                                                                                                                                    |
| M2  | Low-Med            | Relative labels assume the user's "usual pour-over" = a medium V60 (internal step 5). If a user's habitual grind is unusually coarse/fine, "a bit coarser than your usual" can mislabel by a notch. Reasonable given the question wording; undocumented assumption.                        | OPEN — documented here                                                                                                                                                                             |
| L1  | Low                | Uncalibrated hand grinders lost the "zero the dial first" instruction (replaced with a generic "starting point" hint). The how-to-set text is still computed, just not shown.                                                                                                              | FIXED 2026-07-07 — `RecipesFlow.tsx` vhint now leads with `grind.howToSet` (the per-grinder zero/read instruction), keeping the "adjust to taste" + Profile nudge after it. `npm run build` clean. |
| L2  | Low                | A previously-saved _electric_ grinder id (now hidden) degrades gracefully to the generic band, but the picker `<select>` shows blank.                                                                                                                                                      | OPEN — accept                                                                                                                                                                                      |
| L3  | Low                | Calibrated mode drops the grinder name from the recipe-card subtext.                                                                                                                                                                                                                       | OPEN — accept                                                                                                                                                                                      |
| L4  | Low                | Recipe-picker sub-copy implies "dial" even when calibrated mode shows relative-to-usual.                                                                                                                                                                                                   | OPEN — minor copy                                                                                                                                                                                  |

## Verified clean

- Python band boundaries (`coarseness_label`) + micron formula (`microns_for_generic`)
  match the TypeScript copies (`genericGrindBand` / `genericMicrons`) — checked directly.
- `tests/unit/test_grinder_catalog.py` 13/13 pass; catalog serves 7 hand grinders.
- `tsc --noEmit` clean; eslint exit 0 (one advisory at `RecipesFlow.tsx:184` is
  pre-existing bag-handoff code, not introduced here).
- Legacy Streamlit `get_grinder_display` path preserved (`~26 clicks on Comandante C40`);
  `test_demo_mode_persistence.py::TestGrindDisplayConsistency` logic still holds.
- Hiding electric breaks no Python callers (`get_grinder_options` now hand-only;
  Streamlit onboarding/profile unaffected).

## Not yet done

- **In-browser verification** — the whole feature compiles + type-checks but has NOT
  been clicked live (calibration save, recipe-card relative display).
- **Integration test** (`test_api_endpoints.py::test_grinders_returns_catalog`, updated
  to expect 7 hand grinders) could not run locally (DB hang, iCloud path). Assertions
  verified directly against `get_grinder_catalog()`.

## Disposition recommendation

Nothing is a code-correctness blocker. L1 is fixed. Suggested order: verify
in-browser → deploy at a quiet moment (H1). M1 (test harness) and M2
(baseline assumption) are known and documented, not blocking.

## Timemore C3 dial fact (2026-07-07)

User confirmed: the C3's printed dial reads **1 through 15 for one full
rotation** (not the 12 clicks/rotation this catalog's `notes` field and the
calibration spec assumed; corrected from an initial "1–14" to "1–15" in the
same exchange). This contradicts the spec's sourced "12 clicks/rot" figure
and confirms the earlier session-note observation ("23 clicks ≈ dial 7") was
pointing at a real discrepancy, not a fluke.

**Actioned 2026-07-08:** user confirmed their real V60 (James Hoffmann recipe)
setting is **14 clicks**. Updated `src/grinder_catalog.py` — `timemore-c3`
anchors' 650-micron point changed from a guessed `15` to the grounded `14`;
`notes` corrected from "83 um/click" (unverified, dropped) to "15 clicks per
full rotation (confirmed on a real unit)". Mirrored in
`workspaces/BrewMatch/grinder-calibration-spec.md` (row + new ‡ footnote).
`tests/unit/test_grinder_catalog.py` doesn't hardcode the old value — all
assertions are range/monotonicity checks, so no test changes needed.

**Still open:** espresso (7–10), 4:6 (16–18), and French press (18–20) anchors
for this grinder remain the original review-site-sourced ranges — not yet
confirmed against a real C3. The `reading` format is still a flat click count
("14 clicks") rather than "rotation + dial" — acceptable since 14 is within one
rotation (15 clicks), but values above 15 (4:6, French press) will still show
as e.g. "18 clicks" rather than "1 rotation + 3". Not blocking; a display-format
change, not a correctness bug — flagged for a future task if the user wants it.

# Phase 2 — Brewer Becomes Gear (owned, selectable), not a bean attribute

Created: 2026-07-01
Status: **Task 1 DONE (2026-07-02). Task 2 DONE (2026-07-04).** Plan of record.

## The idea in one sentence

A brewer (V60, Kalita Wave, Origami) is **equipment you own** — like your
grinder — not a property of the beans. The app should let you register the
brewers you own and pick which one you're using, then give the recipe for that
brewer + those beans.

## Why this change

- Today the brewer is buried inside the Recipes form, sitting next to bean
  details (roast, process). That implies the brewer belongs to the beans. It
  doesn't — the same beans can go through any brewer.
- The grinder is already modelled correctly: it lives in Profile, is saved, and
  every recipe uses it. The brewer should work the same way.
- Users own more than one brewer, and this will expand to new brewer types
  later, so the design must grow cleanly.

## Decided (do not re-litigate)

- **Users own MULTIPLE brewers**, chosen from a catalog.
- **No "best brewer for the beans" recommendation.** Specialty-coffee recipes
  are published per brewer; there is no solid bean-to-brewer verdict. Brewer is
  a personal/gear choice, so the app lets you _select_, it does not _recommend_.
- **The brewer catalog lives in the brain (Python API)**, served to the website
  the same way the grinder catalog is (`GET /grinders` → mirror as brewers).
  One source of truth; the website can only offer brewers the engine has recipes
  for; new brewer types are added in one place.

## Tasks (build one at a time, in order)

### Task 1 — Brewer catalog in the brain + "Your brewers" in Profile ✅ DONE

**Delivered 2026-07-02:**

- `src/brewer_catalog.py` — V60 / Kalita Wave / Origami, each carrying the exact
  `BrewMethod` string (`get_brewer_method` helper for id → method). Verified every
  method matches the `BrewMethod` enum.
- `GET /brewers` in `api/main.py:237` (mirrors `/grinders`) → `{"brewers": [...]}`.
- `getBrewers()` + `Brewer` type in `apps/web/lib/api.ts`.
- `apps/web/lib/brewerPref.ts` — stores an owned-brewer LIST on-device (mirrors
  `grinderPref`, list instead of single value).
- "Your brewers" checkbox section in `ProfileFlow.tsx`, beside "Your grinder".
- `tsc --noEmit` clean; `/brewers` endpoint returns the 3 brewers.

- Add a brewer catalog module in the brain, mirroring `src/grinder_catalog.py`,
  and serve it from a new endpoint mirroring `/grinders` (`api/main.py:224`).
- Website fetches + caches it the way `lib/api.ts` fetches grinders.
- Profile gets a "Your brewers" section beside "Your grinder": tick the brewers
  you own. Saved on-device now, synced to the account like the grinder pref
  (mirror `lib/grinderPref.ts`).
- Delivers: the app knows your gear, from one central catalog that can grow.

### Task 2 — Recipes screen uses owned brewers as a selection

- Remove the standalone "Brewer" dropdown from the bean-details cluster in
  `apps/web/components/RecipesFlow.tsx`.
- If you own one brewer, it's used automatically. Own several → pick which one
  you're brewing with this time (a quick top-level choice).
- The recipe request stays the same shape — the brain already accepts a list of
  brew methods and returns ranked recipes (`api/main.py:261`).
- Fallback: if no brewers are set yet, nudge to Profile (or consider all catalog
  brewers) so nobody hits a dead end.
- Delivers: the screen matches the model — beans are the coffee, brewer is gear.

## Open question for later (not blocking)

- Should the grinder also become multi-owned for consistency? Deferred — user
  only asked for multiple brewers.

## Reference points in the current code

- Grinder catalog (the pattern to copy): `src/grinder_catalog.py`,
  endpoint `api/main.py:224`, website fetch `apps/web/lib/api.ts` (`getGrinders`).
- Grinder preference storage: `apps/web/lib/grinderPref.ts`,
  Profile UI `apps/web/components/ProfileFlow.tsx`.
- Brewer today (to move): `apps/web/components/RecipesFlow.tsx:48` (`METHODS`),
  brewer `<select>` around line 309.
- Recommend endpoint: `api/main.py:241` (`/recommend`, takes `brew_methods` list).

# B1 — Bag-Based Brew Logging (detailed task list)

Created: 2026-06-11
Status: **AWAITING YOUR APPROVAL — nothing built yet**
Plan: `workspaces/BrewMatch/02-plans/03-bag-based-logging.md`
Parent: expands "B1" in `todos/active/p1-live-persistence-and-learning-loop.md`

## What this delivers (plain language)

Save a bag of coffee once (roaster, coffee name, bag size), then pick it from a
list every time you brew instead of re-typing it. On the brew screen you confirm
the dose you actually used, and the recipe's water + pours rescale to match. The
app counts down how much coffee is left in the bag from those real doses.

## How the work is split

Seven steps, in dependency order. Steps marked **(build)** create the screen or
logic; steps marked **(wire)** connect it to real saved data — they are separate
on purpose, because "the screen renders" and "real data flows through it" are
different finish lines. Each step is sized to one autonomous build-and-test cycle.

---

### B1.1 — Add the bag to the data model (build) ✅ DONE 2026-06-11

Add a `CoffeeBag` dataclass to `src/data_models.py`: `bag_id`, `roaster`,
`name`, `bag_size_g` (default 250.0), `date_opened`, `active` (bool), and the
bean details it carries (reuse `BeanProfile` plus the two new identity fields).
Also add `roaster` and `name` (both optional, default `None`) to `BeanProfile`
so they flow into history and diagnosis. Keep both backward-compatible — old
brew records with no roaster/name must still deserialize.

- Implements: `specs/data-models.md` §2 (Bean Profile — adds roaster/name); new
  CoffeeBag entity to be added to `specs/data-models.md` when this code lands.
- Touches: `src/data_models.py`
- Done when: `CoffeeBag` exists, `BeanProfile` has optional roaster/name, and a
  unit test confirms an old bean dict (no roaster/name) still loads.
- Size: ~60 LOC + tests. Invariants: backward-compat of BeanProfile.

### B1.2 — Create the bag table, link brews to bags + storage helpers (build)

Add a `coffee_bags` table to `src/app/db.py` `init_db` using the same
`CREATE TABLE IF NOT EXISTS` pattern as `_CREATE_USERS` / `_CREATE_BREW_HISTORY`
so it creates on **both** local SQLite and live Postgres. Columns: `bag_id` PK,
`user_id` FK, `roaster`, `name`, `bag_size_g`, `bean_json`, `date_opened`,
`active`, `created_at`.

**Also add two columns to `brew_history`** so a brew can be tied to its bag and
its real dose: `bag_id` (nullable — old brews and one-off brews have none) and
`actual_dose_g` (nullable float). The running-low countdown needs both: it sums
`actual_dose_g` over the brews whose `bag_id` matches.

Add CRUD helpers: `create_bag`, `list_active_bags(user_id)`,
`mark_bag_finished(bag_id)`, and `grams_used_for_bag(bag_id)` (sums
`actual_dose_g` from `brew_history` where `bag_id` matches). All helpers MUST use
SQLite-style `?` placeholders — the Postgres adapter rewrites `?`→`%s` via
`sql.replace` (db.py:151); a hand-written `%s` would break local SQLite.

- Implements: new CoffeeBag storage; `specs/data-models.md` §5 (Storage) +
  §3 (brew_history fields) to be updated when code lands.
- Touches: `src/app/db.py`
- Depends on: B1.1
- Done when: both tables/columns exist on a fresh SQLite **and** a Postgres test
  DB; every CRUD helper has a unit test that writes then reads back the value.
- Size: ~170 LOC + tests. Invariants: dual-backend creation, FK to users,
  active-flag filter on list, nullable bag link (old/one-off brews unaffected),
  `?`-placeholder convention.
- **Trap — live-DB column migration is backend-specific.** The `coffee_bags`
  table is created by `CREATE TABLE IF NOT EXISTS` on both backends. But the two
  **new brew_history columns** must be ADDED to already-deployed tables, and the
  two backends need different code:
  - **SQLite** does NOT support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
    Follow the existing pattern at db.py:309–317 — check `PRAGMA table_info`,
    then `ALTER TABLE ... ADD COLUMN` inside `try/except sqlite3.OperationalError`.
  - **Postgres** DOES support `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — use it
    behind the `_is_pg(conn)` branch (the SQLite `_MIGRATIONS` loop is skipped on
    Postgres today).
    Without the Postgres branch, the live Supabase app errors on the first
    bag-linked brew. Verify against a real Postgres instance, not just SQLite.

### B1.3 — Build the "Your Coffees" picker screen (build)

Rebuild `src/app/pages/bean_input.py` as a picker: show the user's open bags as
selectable cards/list (roaster + coffee name + "≈N brews left"), with an
"Add a new bag" button that opens today's bean form **plus** roaster, coffee
name, and bag size (default 250 g, editable). Selecting a bag sets it as the
current bean for the brew flow. Renders against session state first; real
persistence is B1.4.

- Implements: `specs/user-interface.md` §4.3 (Bean Input → Your Coffees)
- Touches: `src/app/pages/bean_input.py`
- Depends on: B1.1
- Done when: the page lists bags and the add-bag form collects roaster/name/size
  with the 250 g default; picking a bag populates the current bean.
- Size: ~120 LOC. Invariants: at-least-one-flavor validation preserved, size
  default + editable.

### B1.4 — Wire the picker to real bag storage (wire)

Connect the B1.3 picker to the B1.2 helpers: "Add a new bag" calls `create_bag`,
the list reads `list_active_bags`, "running low" reads `grams_used_for_bag`, and
a "Mark finished" control calls `mark_bag_finished`. Picking a bag sets BOTH the
current bean AND a `current_bag_id` in session state, so the brew screen (B1.6)
knows which bag the cup came from. No session-only / mock bag data remains — a
saved bag survives logout and reappears on next login.

- Implements: `specs/user-interface.md` §4.3
- Touches: `src/app/pages/bean_input.py`
- Depends on: B1.2, B1.3
- Done when: a bag created in one session is visible after logout/login on the
  live app; finished bags drop off the active list; selecting a bag sets
  `current_bag_id`.
- Size: ~40 LOC. Invariant: zero mock bag data; reads/writes go to db helpers;
  bag identity threaded into session state.

### B1.5 — Build editable dose + recipe rescaling on the brew screen (build)

Add an editable dose field at the top of `src/app/pages/brew_session.py`,
pre-filled with the recipe's `dose_g`. When changed, rescale the displayed water
total and **every pour step** by `your_dose ÷ recipe_dose`, keeping the ratio
intact. Pure display/computation — no storage yet. The pour-rendering currently
prints raw recipe numbers (`_render_pour_steps`, `_render_summary_bar`); these
read from the scaled values instead.

- Implements: `specs/user-interface.md` §4.5 (Brew Session); honors recipe
  ratio invariant in `specs/data-models.md` §1 (ratio = water_total / dose).
- Touches: `src/app/pages/brew_session.py`
- Done when: changing the dose updates water + all pours proportionally, the
  ratio stays constant, and a unit test asserts the scaling math
  (e.g. 15 g→18 g at 1:16 gives 288 g water, pours scaled, ratio 16.0).
- Size: ~80 LOC + tests. Invariants: ratio preservation, pour-sum within 5% of
  water_total (existing recipe validation rule), bloom unaffected by scaling.
- **Bound the dose input** so a rescaled `Recipe` still passes its `__post_init__`
  validation (`src/data_models.py:110` — dose 12–35 g; water/ratio ranges). The
  field MUST clamp/validate within the Recipe dose bounds (12–35 g per
  `data_models.py:110`; suggest a tighter pour-over UX range like 12–25 g) and
  reject values that would build an invalid Recipe, rather than crashing the
  page. Note: `specs/data-models.md` §1 states dose 12–22 g but the code allows
  12–35 g — a pre-existing spec/code divergence, out of B1 scope, flagged in the
  validation report.

### B1.6 — Wire bag + actual dose + running-low into the brew record (wire)

Connect the brew screen to real data: read `current_bag_id` (from B1.4), save it
plus the **actual dose** (from B1.5) into `brew_history.bag_id` /
`actual_dose_g`, carry the bag's roaster/name into the brew record, and show
"≈N brews left" using `grams_used_for_bag`. The personalization engine and saved
`BrewRecord` receive the real dose, not the recipe's assumed dose.

**Dose storage — resolve the ambiguity (decided):** `BrewRecord` has no dose
field of its own today; the dose lives inside `recipe_used` (`data_models.py:209`,
dose at `recipe_used.dose_g`). So the saved `recipe_used` snapshot MUST be the
**scaled (actual) recipe** from B1.5 — its `dose_g`/water/pours equal what was
actually brewed, so history and diagnosis show the true cup, not the original
template. `brew_history.actual_dose_g` is a denormalized mirror of
`recipe_used.dose_g`, kept as its own column purely so `grams_used_for_bag` can
`SUM(actual_dose_g)` cheaply without JSON extraction (which differs across
SQLite vs Postgres). `save_brew` MUST be extended to write `bag_id` +
`actual_dose_g`; the existing 6-column INSERT at db.py:590 becomes 8-column.

**No-bag-selected case:** brewing without picking a bag (e.g. the existing
`_fallback_bean_from_recipe` path) MUST still work — `bag_id` is null, no
running-low counter shows, nothing decrements. The bag link is additive, never
required.

- Implements: `specs/user-interface.md` §4.5; `specs/personalization.md` (real
  dose improves data quality)
- Touches: `src/app/pages/brew_session.py`, `src/app/db.py` (`save_brew` writes
  the two new columns), possibly `src/data_models.py` (`BrewRecord` carries
  `actual_dose_g` + `bag_id`)
- Depends on: B1.2, B1.4, B1.5
- Done when: a bag-linked brew stores real dose + bag_id + roaster/name and the
  bag's remaining grams drop by that dose; a no-bag brew still saves cleanly with
  null bag_id; history shows "Roaster — Coffee".
- Size: ~80 LOC. Invariants: actual dose persisted, running-low subtracts real
  dose, roaster/name carried into history, no-bag path unaffected.

### B1.7 — Regression test: bag reusable + real-dose decrement (test)

Add a regression test proving the whole loop: create a bag, brew from it twice
with different actual doses, confirm the bag is reusable across sessions and its
remaining grams decrease by the **sum of actual doses** (not recipe doses).
Place in `tests/regression/` so a future change can't silently break it.

- Implements: validates the B1 feature end-to-end.
- Touches: `tests/regression/`
- Depends on: B1.1–B1.6
- Done when: the test passes and all existing tests stay green.
- Size: ~60 LOC. Invariant: end-to-end real-dose subtraction across sessions.

---

## Spec updates required during build (don't skip)

When B1.1/B1.2 land, add the CoffeeBag entity to `specs/data-models.md` (§2/§5)
and the editable-dose behavior to `specs/user-interface.md` §4.5 — describing
what shipped, in the same change. Specs describe shipped behavior only, so these
updates happen at implement time, not now.

## Out of scope for B1 (already tracked elsewhere)

- B2 retrain button, B3 learning indicator — in `p1-live-persistence-...md`
- A "quick one-off bean without saving a bag" escape hatch — deferred (plan §
  Open follow-ups); default is bags-first.

## Gate

Per `/todos`: this list STOPS here for your approval. Nothing is implemented
until you say go.

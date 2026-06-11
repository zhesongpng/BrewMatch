# Red Team — B1 Plan & Todos (pre-implementation)

Date: 2026-06-11
Scope: `/redteam the plan first` — validate the B1 plan + todo list against the
real codebase BEFORE implementation. No code exists yet, so this is a
claims-and-completeness audit (Steps 2–6 E2E/Playwright/test-run N/A).
Posture: **L5_DELEGATED** (Round 1 optional; run at user request).

## Claim verification table (every row = literal command + actual result)

| #   | Plan/todo claim                                                        | Verification                                                                                                               | Result                                                                 |
| --- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 1   | brew_session.py is a read-only printout (no editable dose)             | `Read src/app/pages/brew_session.py` — `_render_summary_bar` shows `st.metric("Dose", ...)`, no `st.number_input` for dose | ✅ TRUE                                                                |
| 2   | db.py uses `CREATE TABLE IF NOT EXISTS` dual-backend                   | `grep -n "CREATE TABLE IF NOT EXISTS" src/app/db.py` → users/brew_history/sessions                                         | ✅ TRUE                                                                |
| 3   | `_MIGRATIONS` is SQLite-only PRAGMA-based                              | `db.py:309` `if not _is_pg(conn): ... PRAGMA table_info(users)` + `try/except sqlite3.OperationalError`                    | ✅ TRUE                                                                |
| 4   | BeanProfile has no roaster/name                                        | `grep -n "roaster" src/data_models.py` → 0 hits; `class BeanProfile` at :155                                               | ✅ TRUE — B1.1 needed                                                  |
| 5   | BrewRecord carries dose for storage                                    | `sed -n '209,220p' data_models.py` → fields: brew_id, timestamp, bean_profile, recipe_used, feedback. **No dose field**    | ⚠️ dose only inside `recipe_used.dose_g` — todo ambiguity (FINDING M1) |
| 6   | save_brew INSERT can take new columns                                  | `db.py:590` 6-column INSERT (`brew_id,user_id,timestamp,bean_json,recipe_json,feedback_json`), positional `?`              | ✅ must extend to 8-col (B1.6 updated)                                 |
| 7   | Postgres uses `?`→`%s` placeholder translation                         | `db.py:151` `cur.execute(sql.replace("?", "%s"), ...)`                                                                     | ✅ TRUE — bag CRUD must use `?` (FINDING M2)                           |
| 8   | `ALTER TABLE ADD COLUMN IF NOT EXISTS` works for the live-DB migration | SQLite spec: **not supported** on ADD COLUMN; Postgres: supported                                                          | ❌ todo syntax wrong for SQLite (FINDING M3)                           |
| 9   | Recipe dose bound matches spec                                         | `data_models.py:110` allows 12.0–35.0; `specs/data-models.md:15` says 12.0–22.0                                            | ⚠️ pre-existing spec/code divergence (FINDING L1, out of scope)        |
| 10  | `_render_pour_steps` / `_render_summary_bar` exist                     | `Read brew_session.py` :71 / :122                                                                                          | ✅ TRUE                                                                |

## Findings (all fixed in todo text — pre-implementation)

- **M1 (MED) — Dose-storage ambiguity.** `BrewRecord` has no own dose field;
  dose lives in `recipe_used`. Resolved in B1.6: save the _scaled_ recipe as
  `recipe_used` (its dose = actual), with `actual_dose_g` as a denormalized
  column for the countdown SUM. Prevents history showing 15 g while the bag
  counts 18 g. **Fixed.**
- **M2 (MED) — Placeholder convention.** Bag CRUD must use `?` placeholders
  (db.py:151 rewrites to `%s` for Postgres); hand-written `%s` breaks SQLite.
  Added to B1.2 invariants. **Fixed.**
- **M3 (MED) — Migration syntax wrong for SQLite.** My B1.2 trap prescribed
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — unsupported by SQLite. Corrected
  to backend-specific: SQLite via existing PRAGMA + try/except pattern
  (db.py:309–317), Postgres via `ADD COLUMN IF NOT EXISTS` behind `_is_pg`.
  **Fixed.**
- **L1 (LOW, out of scope) — Spec/code dose-range divergence.** `specs/data-
models.md` §1 says dose 12–22 g; code allows 12–35 g. Pre-existing, not
  introduced by B1. Flagged here; B1.5 bounds the editable-dose input to the
  code's real constraint. Recommend reconciling the spec separately.

## Completeness check (no new gaps)

- Build/wire split present for both data-flowing screens (B1.3→B1.4, B1.5→B1.6). ✅
- Bag identity threaded picker→brew via `current_bag_id` session state. ✅
- No-bag-selected path preserved (additive bag link, nullable column). ✅
- Regression test covers reuse-across-sessions + real-dose decrement (B1.7). ✅
- Spec-update obligations noted for implement time (data-models, user-interface). ✅

## Disposition

No CRITICAL/HIGH. Three MED findings were errors in the todo text itself, all
corrected before implementation. One LOW is a pre-existing out-of-scope spec
divergence. The B1 plan is **ready for `/implement` on user approval.**

# Phase 1 — Permanent Storage on the Live App + Learning From Your Brews

Created: 2026-06-10
Reconciled against actual repo state: 2026-06-15
Goal in one sentence: **the live online app stops forgetting your data, and
starts getting smarter from the brews you log.**

> **Status reconciliation (2026-06-15).** Several checkboxes below were stale —
> the work shipped but the boxes were never ticked. Verified against the repo:
> Supabase is chosen, created, and connected (the live app reads/writes
> production Supabase via `DATABASE_URL` in `.streamlit/secrets.toml`); the
> bag-logging flow (B1) shipped and is tested; and the personalization
> **learning engine already exists and runs automatically**
> (`src/personalization/engine.py` — `record_brew`, `compute_learned_preferences`,
> phase auto-derived from brew count, shown in the sidebar). What is genuinely
> left: a recorded restart-survival proof, a one-click export, and the design
> call on whether the auto-learning needs an explicit "retrain" button. Each
> item is marked below.

How to read this list: each `[ ]` is one trackable step. Steps are grouped into
three goals. Goal A stops the resetting (the urgent pain). Goal B is the payoff
you chose — the app learning from your real brews. Goal C keeps everything safe
and proven.

---

## Decisions needed from you (small, one-time)

- [x] **Pick the permanent-database provider.** _(decided: Supabase, 2026-06)_
      My recommendation: **Supabase** (free, no credit card). It is a permanent
      PostgreSQL database — which fixes the resetting — AND it comes with a
      real, production-grade login system and the building blocks for a
      multi-user community. Given you want a proper login, possible
      commercialisation, and recipe-sharing among a group, Supabase lays that
      foundation now so we don't rebuild it later. (Earlier I recommended Neon,
      which is great for a solo tool; the community + commercial goal is why
      Supabase is now the better fit.) I'll walk you through the signup — you
      click through it, I do the wiring. _This is the only thing blocking Goal A
      from starting._

---

## Goal A — Stop the live app resetting (the urgent fix)

The point of this goal: your account and brew history survive forever, even
when Streamlit restarts the app.

- [x] **A1. Teach the app to use a permanent database.** _(code done 2026-06-10)_
      Extended `src/app/db.py` to talk to PostgreSQL when `DATABASE_URL` is set,
      while the local-file path is unchanged. All 661 tests still pass; the new
      PostgreSQL helpers are unit-checked. The live connection is proven against
      the real database in A4. Driver `psycopg[binary]` added to `pyproject.toml`;
      hosted secrets bridged to the app in `src/app/app.py`.

- [x] **A2. Create the free permanent database.** _(done — Supabase project live)_
      Supabase project created; the secure connection address is captured. We use
      only its database in Phase 1 — its login and community features come in
      later phases, but choosing Supabase now means they're ready when we are.

- [x] **A3. Connect the live app to it.** _(done — `DATABASE_URL` wired)_
      Connection address lives in `.streamlit/secrets.toml` as `DATABASE_URL`;
      the live app reads/writes the permanent Supabase database instead of its
      temporary memory.

- [x] **A4. Prove it survives a restart.** _(done 2026-06-24 — automated proof; same work as C2)_
      Proven by the automated restart-survival test (see C2): it writes an
      account + onboarding + coffee bag + brews to a real PostgreSQL database,
      simulates the restart (drops all in-process state), reconnects from
      scratch, and confirms everything is still there. A one-time manual
      click-through against the live Supabase app is the optional human-witnessed
      companion (Option B) and can still be recorded if desired.

**Goal A is done when:** you can log into the live app, close it, come back the
next day, and everything is still there.

---

## Goal B — Learn from your real brews (the payoff you chose)

The point of this goal: recommendations stop being generic and start matching
your palate as you log real cups.

- [x] **B1. Make logging + rating a brew quick and consistent.** _(shipped + tested)_
      The "here's what I brewed, here's how it tasted" flow shipped across
      commits B1.2–B1.7: a "Your Coffees" bag picker, editable dose that
      rescales the recipe, and persistence of the real dose + bag link into
      each brew record, with end-to-end regression tests.

- [x] **B2. Add a "retrain on my brews" action.** _(decided 2026-06-16: no button — automatic retrain is sufficient)_
      The learning itself already works: `PersonalizationEngine.record_brew`
      updates your personal model on every logged brew, blends with the general
      model early, and shifts toward your own data as history grows — **fully
      automatic, no button needed**. **Decision (2026-06-16):** skip the explicit
      "retrain now" button. The model already retrains on every logged brew, so a
      button would do nothing the automatic learning isn't already doing. The
      honest "learned from N brews" indicator (B3) provides the visible
      proof-of-learning instead.

- [x] **B3. Show that it's learning.** _(done 2026-06-18 — sidebar now shows "Learned from N brews")_
      The sidebar shows your personalization **phase** AND, beneath it, an honest
      "Learned from N brews so far" line (graceful wording for 0 and 1 brew). The
      count is stored in session state whenever the phase is recomputed (login,
      session restore, onboarding) and refreshes immediately after each logged
      brew, so the number is never stale. Guarded by
      `tests/regression/test_brew_count_shown_in_sidebar.py`.

**Goal B is done when:** after you log a handful of real brews, the
recommendations visibly reflect your logged preferences (already automatic) and
the app honestly shows how much it has learned.

**Honest expectation:** this compounds. You'll likely need ~15–30 real logged
brews before your personal model clearly beats the generic one. It starts
helping immediately but gets better the more you use it.

---

## Goal C — Keep it safe and proven

The point of this goal: nothing breaks, and your data is always yours.

- [>] **C1. Your data is exportable.** _(deferred 2026-06-18 — KIV for a future phase)_
  A one-click export so your brew log is always downloadable and yours,
  independent of any host. **Decision (2026-06-18):** not important now;
  shelved for later. Nice-to-have safety feature, not blocking Phase 1.

- [x] **C2. Automated checks for the permanent database.** _(done 2026-06-24)_
      The gap is now closed: `tests/regression/test_postgres_restart_survival.py`
      writes an account + onboarding + coffee bag + brews to a **real, disposable
      PostgreSQL** (spun up by the `pgserver` dev dependency — bundles its own
      Postgres binary, no Docker, never touches production Supabase), simulates a
      restart by dropping all in-process state, reconnects from scratch, and asserts
      every record survived. It runs through the app's own `db.py` Postgres path
      (`DATABASE_URL` → `get_connection`). Full suite green (750 passing).

  **Bonus bug found + fixed along the way:** the real-Postgres test surfaced a
  latent bug in `delete_user_data` — it deleted brews and the user row but not
  the user's coffee bags or sessions. On SQLite (no enforced foreign keys) this
  silently left orphans; on the live Supabase backend it would raise a foreign-key
  error for any user who deleted their data while owning a coffee bag. Fixed to
  delete all child rows in FK-safe order, and the `delete_user_data` unit test was
  strengthened to cover a bag + session so it actually guards "removes everything".

**Goal C is done when:** there's a passing test proving data survives a
restart, and you can download your full brew history any time.

---

## What is explicitly NOT in Phase 1

To keep this focused and trackable, these are deliberately left for later:

- The new look-and-feel / UI redesign → **Phase 2**
- Moving off Streamlit to a new host → **Phase 2**
  - **Decision (2026-06-18):** the Phase-2 UI direction is a proper React/Next
    front-end (hosted on Vercel) with the Python ML split out into a separate
    API on a Python-friendly host. NOT a Streamlit re-host — Vercel does not run
    Streamlit. User confirmed: finish Phase 1 first, then do this rebuild
    deliberately as the Phase-2 centerpiece. Optional interim: light Streamlit
    theming as a stopgap, not the destination.
- Real login (social sign-in, password reset, email verification) → **Phase 2**
  (ties into the UI redesign; the current basic login keeps working until then)
- Recipe-sharing / community / multiple users → **Phase 3**
- Anything about charging money / commercialisation → after Phase 3, once there
  are real users to learn from
- New brew methods (AeroPress, espresso, etc.) → later, your call

---

## What's actually left in Phase 1 (post-reconciliation, 2026-06-15; updated 2026-06-24)

**Nothing blocking remains — Phase 1 is functionally complete.** Goal A (stop
resetting) and B1 (logging flow) are done, the learning engine runs
automatically, and as of 2026-06-24 the restart-survival proof (C2 / A4) is
landed and green. The only optional, deliberately-deferred item is C1 (one-click
export). Phase 2 (the React/Vercel rebuild) can begin.

_C2 / A4 (recorded restart-survival proof) was done 2026-06-24 — an automated
test writes to a real disposable PostgreSQL, simulates a restart, and proves
every record survives; it also surfaced and fixed a `delete_user_data`
foreign-key bug that would have hit real users on Supabase._

_B2 (explicit retrain button) was resolved 2026-06-16: skipped — the model
already retrains on every logged brew, so a button adds no behavior._

_B3 (honest "learned from N brews" wording) was done 2026-06-18 — the sidebar
now shows the brew count beneath the phase, guarded by a regression test._

_C1 (one-click export) was deferred 2026-06-18: KIV for a future phase —
nice-to-have safety feature, not blocking Phase 1._

---

## Approach note (for whoever builds this)

This app is plain Python + scikit-learn + Streamlit with a clean, single-file
database layer (`src/app/db.py`). Phase 1 extends that layer to support
PostgreSQL alongside SQLite — it does **not** rebuild the app or adopt a
heavier framework. Keeping the change contained to `db.py` is deliberate: it's
the smallest change that fixes the resetting and it carries straight over to
the Phase 2 host.

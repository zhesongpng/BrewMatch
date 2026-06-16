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

- [ ] **A4. Prove it survives a restart.** _(only open Goal-A item; same work as C2)_
      In practice the live app is already persisting to Supabase, but this has
      not been **explicitly proven and recorded**: create a test account,
      restart the live app, log back in, confirm the account and history are
      still there. Recording an automated version of this is C2.

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

- [~] **B2. Add a "retrain on my brews" action.** _(engine exists; explicit button is a design call)_
  The learning itself already works: `PersonalizationEngine.record_brew`
  updates your personal model on every logged brew, blends with the general
  model early, and shifts toward your own data as history grows — **fully
  automatic, no button needed**. What is NOT yet decided: whether to add an
  explicit "retrain now" button on top of the automatic learning. Open
  question for you (see bottom of file).

- [~] **B3. Show that it's learning.** _(phase indicator exists; brew-count wording is the gap)_
  The sidebar already shows your personalization **phase**, derived from how
  many brews you've logged (`get_phase_info` returns phase + brew count +
  description). The remaining polish is the honest, explicit wording —
  e.g. "learned from N brews" — rather than only the phase name.

**Goal B is done when:** after you log a handful of real brews, the
recommendations visibly reflect your logged preferences (already automatic) and
the app honestly shows how much it has learned.

**Honest expectation:** this compounds. You'll likely need ~15–30 real logged
brews before your personal model clearly beats the generic one. It starts
helping immediately but gets better the more you use it.

---

## Goal C — Keep it safe and proven

The point of this goal: nothing breaks, and your data is always yours.

- [ ] **C1. Your data is exportable.** _(not started — no export path in the app yet)_
      A one-click export so your brew log is always downloadable and yours,
      independent of any host.

- [~] **C2. Automated checks for the permanent database.** _(partial)_
  Existing regression tests already cover in-memory survival across
  connection cycles (`tests/regression/test_demo_mode_persistence.py`) and
  that the personalization phase persists on login
  (`tests/regression/test_phase_persists_on_login.py`), and the full suite
  stays green. The **gap** is a test that writes to a real PostgreSQL
  database, simulates a restart, and proves the data is still there — the
  automated form of A4.

**Goal C is done when:** there's a passing test proving data survives a
restart, and you can download your full brew history any time.

---

## What is explicitly NOT in Phase 1

To keep this focused and trackable, these are deliberately left for later:

- The new look-and-feel / UI redesign → **Phase 2**
- Moving off Streamlit to a new host → **Phase 2**
- Real login (social sign-in, password reset, email verification) → **Phase 2**
  (ties into the UI redesign; the current basic login keeps working until then)
- Recipe-sharing / community / multiple users → **Phase 3**
- Anything about charging money / commercialisation → after Phase 3, once there
  are real users to learn from
- New brew methods (AeroPress, espresso, etc.) → later, your call

---

## What's actually left in Phase 1 (post-reconciliation, 2026-06-15)

Goal A (stop resetting) and B1 (logging flow) are done; the learning engine
already runs automatically. The genuinely outstanding work is small:

1. **C1 — one-click brew-log export** (not started).
2. **C2 / A4 — a recorded restart-survival proof** against the real PostgreSQL
   database (the two are the same underlying test).
3. **B3 polish — honest "learned from N brews" wording** in the sidebar (the
   phase indicator already exists; this is a wording change).
4. **B2 decision — does the automatic learning need an explicit "retrain"
   button?** (see open question below).

## Open question for you

- **Explicit retrain button (B2):** the app already retrains on every brew you
  log, automatically. Do you also want a visible "retrain now" button? My
  recommendation: **skip it for now.** It adds a control that does nothing the
  automatic learning isn't already doing, and an unused button invites the
  question "did I need to press this?" The honest "learned from N brews"
  indicator (B3) gives you the visible proof-of-learning without a redundant
  button. Trade-off: some users like an explicit "do it now" action for
  reassurance — if that's you, it's a small add. Want the button, or skip it?

---

## Approach note (for whoever builds this)

This app is plain Python + scikit-learn + Streamlit with a clean, single-file
database layer (`src/app/db.py`). Phase 1 extends that layer to support
PostgreSQL alongside SQLite — it does **not** rebuild the app or adopt a
heavier framework. Keeping the change contained to `db.py` is deliberate: it's
the smallest change that fixes the resetting and it carries straight over to
the Phase 2 host.

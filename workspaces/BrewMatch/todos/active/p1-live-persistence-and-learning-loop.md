# Phase 1 — Permanent Storage on the Live App + Learning From Your Brews

Created: 2026-06-10
Goal in one sentence: **the live online app stops forgetting your data, and
starts getting smarter from the brews you log.**

How to read this list: each `[ ]` is one trackable step. Steps are grouped into
three goals. Goal A stops the resetting (the urgent pain). Goal B is the payoff
you chose — the app learning from your real brews. Goal C keeps everything safe
and proven.

---

## Decisions needed from you (small, one-time)

- [ ] **Pick the permanent-database provider.**
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

- [ ] **A2. Create the free permanent database.**
      You sign up (Supabase, per the decision above) and create one project; I
      guide you and capture the secure connection address. We use only its
      database in Phase 1 — its login and community features come in later
      phases, but choosing Supabase now means they're ready when we are.

- [ ] **A3. Connect the live app to it.**
      Add the connection address to your Streamlit app's secret settings so the
      live app reads/writes the permanent database instead of its temporary
      memory.

- [ ] **A4. Prove it survives a restart.**
      Create a test account, restart the live app, log back in, confirm the
      account and any history are still there. This is the moment the pain is
      gone.

**Goal A is done when:** you can log into the live app, close it, come back the
next day, and everything is still there.

---

## Goal B — Learn from your real brews (the payoff you chose)

The point of this goal: recommendations stop being generic and start matching
your palate as you log real cups.

- [ ] **B1. Make logging + rating a brew quick and consistent.**
      Tighten the "here's what I brewed, here's how it tasted" flow so it's
      fast enough that you'll actually do it every cup. Clean, consistent
      entries are what the model learns from.

- [ ] **B2. Add a "retrain on my brews" action.**
      A simple button/command that rebuilds your _personal_ taste model from
      your real logged brews. Early on it blends with the general model (so
      it's useful before you've logged much); as your history grows, your own
      data takes over.

- [ ] **B3. Show that it's learning.**
      A small, honest indicator — e.g. "your personal model has learned from
      N brews" — so you can see the payoff building over time.

**Goal B is done when:** after you log a handful of real brews and hit retrain,
the recommendations visibly reflect your logged preferences.

**Honest expectation:** this compounds. You'll likely need ~15–30 real logged
brews before your personal model clearly beats the generic one. It starts
helping immediately but gets better the more you use it.

---

## Goal C — Keep it safe and proven

The point of this goal: nothing breaks, and your data is always yours.

- [ ] **C1. Your data is exportable.**
      A one-click export so your brew log is always downloadable and yours,
      independent of any host.

- [ ] **C2. Automated checks for the permanent database.**
      Tests that confirm data really survives a restart, plus keeping all 646
      existing tests green, so a future change can't silently bring the
      resetting back.

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

## Approach note (for whoever builds this)

This app is plain Python + scikit-learn + Streamlit with a clean, single-file
database layer (`src/app/db.py`). Phase 1 extends that layer to support
PostgreSQL alongside SQLite — it does **not** rebuild the app or adopt a
heavier framework. Keeping the change contained to `db.py` is deliberate: it's
the smallest change that fixes the resetting and it carries straight over to
the Phase 2 host.

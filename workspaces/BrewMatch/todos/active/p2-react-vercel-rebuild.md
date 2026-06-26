# Phase 2 — Rebuild the App on a Modern Front-End (React + Vercel)

Created: 2026-06-24
Status: **DRAFT FOR YOUR REVIEW — not started.** Nothing here is built yet.
This is the plan to read, adjust, and approve before we begin.

Goal in one sentence: **give BrewMatch a polished, phone-friendly look and feel
without throwing away the Python "brain" you've already built.**

---

## What actually changes (and what doesn't)

Your app has three parts. Phase 2 changes two of them and keeps the most
valuable one untouched:

| Part           | What it does                         | Now             | After Phase 2                              |
| -------------- | ------------------------------------ | --------------- | ------------------------------------------ |
| **The face**   | the screens people see and tap       | Streamlit       | **React** (modern, smooth, phone-first)    |
| **The home**   | where the app lives online           | Streamlit Cloud | **Vercel** (free tier, fast)               |
| **The brain**  | recommendations, diagnosis, learning | Python          | **stays Python** (moved behind the scenes) |
| **The memory** | accounts + brew history              | Supabase        | **stays Supabase** (no change)             |

The headline reassurance: **all your Python recommendation and learning work is
kept.** In Phase 2 it stops being tangled up with the screens and becomes a small
behind-the-scenes service the new front-end talks to. We're changing the face and
the address, not re-doing the intelligence.

Why bother at all: Streamlit reloads the whole page on every tap and always looks
"Streamlit-ish." For a brewing companion someone holds mid-pour, a smooth,
phone-first feel is the whole point — and that's exactly where React wins.

---

## Decisions needed from you (small, one-time — with my recommendation)

These shape the build. My recommendation is given for each; you can override any.

- [x] **D1. Where the Python "brain" lives online.** _(DECIDED + LIVE 2026-06-25 → Render, free tier, lite mode)_
      Correction (2026-06-24): Vercel **can** run Python (size limit raised to 500 MB
      in Feb 2026; "Fluid Compute" reduces cold-start lag). So the question was never
      "can Vercel run Python" — it was whether BrewMatch's _heavy_ ML libraries fit
      under 500 MB. **Measured: they don't.** The must-have stack is ~700 MB —
      PyTorch alone is 373 MB (needed by the text-embedding model), plus scipy 81,
      onnxruntime 64, transformers 60, chromadb ~49, scikit-learn 36, numpy+pandas
      ~73. No realistic trim keeps the current embedding-based recommendations and
      fits under 500 MB.
      **Verdict / recommendation: host the brain on a separate always-on Python host
      (Render).** Front-end stays on Vercel. _Trade-off:_ one extra free account +
      a bit more wiring than "everything on Vercel" — but the all-on-Vercel option
      simply isn't available at this size.
      _Alternative (not recommended, recorded for completeness):_ swap the local
      embedding model for an embeddings **API** (OpenAI — already a dependency),
      which deletes PyTorch + transformers (~430 MB) and would fit on Vercel.
      Upside: one platform. Downside: a real change to how recommendations work, a
      small per-use cost, and an outside dependency for a core feature. Only worth it
      if "one platform / no local ML" is independently desirable.

- [x] **D2. Real login, or keep the current basic login?** _(DECIDED 2026-06-25 →
      turn on real Supabase login. Build it step by step, AFTER the front-end is
      connected to the brain — i.e. Goal C comes after B2/B3.)_
      Supabase (already your database) comes with a proper, production-grade login
      system — "sign in with Google," password reset, email verification. My
      recommendation: **turn on real login now**, since the foundation is already
      there and Phase 2 is the natural moment. _Trade-off:_ adds a bit of setup, but
      it's the difference between a toy login and one real users would trust — and it
      sets up the future community/sharing features.

- [ ] **D3. How much the look-and-feel changes.**
      My recommendation: **same features, much nicer skin** — keep what the app
      does, rebuild how it looks (clean, mobile-first, calmer). _Trade-off:_ resisting
      the urge to add new features here keeps Phase 2 finishable; new ideas go on a
      Phase 3 list. We can do a quick visual mockup first so you approve the look
      before I build it.

---

## Goal A — Stand up the Python "brain" as its own service

The point: take the recommendation/diagnosis/learning code that's currently
mixed into the Streamlit app and run it as a small web service the new front-end
can call over the internet.

- [x] **A1. Wrap the existing Python functions in a small web service.**
      No rewrite of the logic — just put a thin "front door" on the functions you
      already have (get recommendations, run diagnosis, save a brew, learn from
      brews, fetch history) so other programs can call them.
      _Done: FastAPI brain at `api/main.py`, 6 endpoints, 761 tests passing._
- [x] **A2. Point it at the same Supabase database.** Same data, same accounts —
      the brain reads and writes exactly where the app does today.
      _Done: reads `DATABASE_URL` (Supabase) on the host._
- [x] **A3. Put it online (D1's host) and confirm it answers.** A recorded check
      that calling it returns real recommendations from the real database.
      _Done 2026-06-25: live at https://brewmatch-iki5.onrender.com (Render, free
      tier, lite mode). `/health` all green; live `/recommend` returned ranked
      V60 recipes and `/diagnose` returned ML-mode fixes against real data._

**Goal A is DONE ✅** — the brain runs on its own, online, and returns real
answers from your real data, proven without opening the app (live API calls
2026-06-25).

---

## Goal B — Build the new React front-end and host it on Vercel

The point: the screens people actually use, rebuilt to feel like a real product.

- [~] **B1. Set up the React (Next.js) project and put it on Vercel.** Get a live
  web address showing a real (if empty) BrewMatch as the foundation to build on.
  _Built 2026-06-25: Next.js (App Router) + TypeScript + Tailwind v4 app at
  `apps/web/`. Coffee-palette design system ported from the approved mockup;
  mobile-first shell with a working bottom tab bar (Diagnose / Recipes /
  Coffees / History). Diagnose home is built out; the other three are honest
  "coming next" shells. `npm run build` is clean (lint + types pass; all 4
  routes prerender). Screenshots verified against the mockup. REMAINING: the
  Vercel deploy itself needs your Vercel login — see `apps/web/README.md`
  § "Deploying to Vercel" (import repo, set Root Directory = `apps/web`)._
- [x] **B2. Connect the front-end to the brain (Goal A).** When someone taps
      something, the screen asks the Python brain and shows the answer — smoothly,
      no full-page reload.
      _Done 2026-06-26: the Diagnose screen's four taste flags are tappable and
      POST to the live brain's `/diagnose`; the cause + concrete fixes render
      inline with loading/error/retry states. New `apps/web/lib/api.ts` client
      (brain URL from `NEXT_PUBLIC_BREWMATCH_API_URL`). Brain CORS locked from
      `*` to the Vercel site + localhost (env-overridable via
      `BREWMATCH_ALLOWED_ORIGINS`). Red-teamed (L5): caught + fixed a
      deploy-breaking `.gitignore` `lib/` rule that hid the client from git; see
      `04-validate/b2-diagnose-wire.md`. API-key-on-writes deferred to B3 (no
      write endpoints wired yet)._
- [ ] **B3. Build the core screens** with the agreed look (D3): home/diagnosis,
      recommendation/recipe view, log-a-brew, your coffees/bags, history + "what
      it's learned."

**Goal B is done when:** the new app is live at a real web address, looks like a
real product, and talks to your brain.

---

## Goal C — Real login (if D2 = yes)

The point: people sign in securely, and it's ready for future sharing/community.

- [ ] **C1. Turn on Supabase's built-in login** (email + "sign in with Google").
- [ ] **C2. Wire the new screens to it** so each person sees only their own
      coffees, brews, and learning.

**Goal C is done when:** a new person can sign up, log in, and their data is
private to them — with password reset and the rest handled for you.

---

## Goal D — Move every existing feature across (nothing lost)

The point: a checklist so the new app does **everything** the current one does
before we retire the old one.

- [ ] **D-parity. Feature-for-feature check:** diagnosis flow, recommendations,
      recipe card (running water total, clock-format times), log + rate a brew,
      editable dose that rescales the recipe, your coffees/bags + "running low,"
      personalization phase + "learned from N brews," brew history, trust badge on
      sources. Each one re-checked working in the new app.

**Goal D is done when:** every feature you have today works in the new app.

---

## Goal E — Launch safely

The point: switch over without breaking anything or losing data.

- [ ] **E1. Run old and new side by side briefly** (same Supabase data) so you can
      compare before committing.
- [ ] **E2. Point people to the new app; keep the old one as a fallback** for a
      short window, then retire it.

**Goal E is done when:** the new app is the real BrewMatch, your data carried
over untouched, and the old Streamlit app can be turned off.

---

## What is explicitly NOT in Phase 2

- One-click data export (Phase 1's parked C1) → still later, your call
- Recipe-sharing / community / multiple-people-see-each-other → **Phase 3**
- New brew methods (AeroPress, espresso, etc.) → later, your call
- Charging money / commercialisation → after Phase 3, once there are real users
- Any change to the recommendation/learning logic itself → out of scope; Phase 2
  is a re-skin + re-home, not a brain change. (If we want smarter recommendations,
  that's its own separate piece of work.)

---

## Approach note (plain version)

Phase 2 is deliberately a **"new face, same brain"** move: keep all the Python
intelligence, wrap it as a small service, and build a modern phone-first front-end
that calls it. The risk we're managing is doing too much at once — so the rule for
this phase is **feature parity first, new ideas later.** We finish by proving the
new app does everything the old one did, then switch over with your data intact.

**Rough sequencing (for expectation-setting, not a commitment):** Goal A (stand up
the brain) and an empty Goal B (live React shell) come first and are quick; the
bulk of the work is Goal B's screens + Goal D's parity; login (C) slots in
alongside; launch (E) is last. We'd tackle it in a few focused build passes, each
ending with something you can see and click.

---

## Your review — three questions before we proceed

1. Does this cover what you pictured for the rebuild?
2. Is anything here you **don't** want (or that should wait)?
3. Anything missing you expected to see?

Once you've answered D1–D3 and you're happy with the scope, say the word and I'll
turn this into the detailed build steps and start with Goal A.

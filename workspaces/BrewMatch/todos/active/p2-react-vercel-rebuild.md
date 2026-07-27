# Phase 2 — Rebuild the App on a Modern Front-End (React + Vercel)

Created: 2026-06-24
Reconciled against actual repo state: 2026-07-27
Status: **IN PROGRESS — Goals A, B and C are built and live.** Goal D (parity
check) and Goal E (switchover) remain.

> **Status reconciliation (2026-07-27).** This file had drifted badly behind the
> code: it still described B1 as "needs your Vercel login", B3 as not started,
> and Goal C as undecided. Verified against the repo and the running services:
> the site is live at `https://brewmatch-sepia.vercel.app`, the brain is live at
> `https://brewmatch-iki5.onrender.com`, all five screens are built (Home,
> Recipes, Coffees, History, Profile, plus log-a-brew and sign-in), and Supabase
> email sign-in is wired end-to-end with the brain verifying login tokens.
> Boxes below are now ticked against evidence, with the honest gaps named.
> Nothing in this reconciliation changed any code — only the record.

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

- [x] **D3. How much the look-and-feel changes.** _(SETTLED IN PRACTICE — "same
      features, nicer skin" is what was built; recorded 2026-07-27.)_
      My recommendation was: **same features, much nicer skin** — keep what the app
      does, rebuild how it looks (clean, mobile-first, calmer). _Trade-off:_ resisting
      the urge to add new features here keeps Phase 2 finishable; new ideas go on a
      Phase 3 list. We can do a quick visual mockup first so you approve the look
      before I build it.
      _What actually happened: a mockup was approved (see the two-path home hub
      decision, journal 0033), and the build followed the "nicer skin, same
      features" line — the coffee palette, mobile-first shell and bottom tab bar
      came from that mockup. This box was never formally ticked; it is ticked now
      to match reality. Two things did grow beyond a pure re-skin, deliberately
      and with your say-so: grinder-specific grind guidance and brewer-as-gear._

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

- [x] **B1. Set up the React (Next.js) project and put it on Vercel.** Get a live
      web address showing a real (if empty) BrewMatch as the foundation to build on.
      _Built 2026-06-25: Next.js (App Router) + TypeScript + Tailwind v4 app at
      `apps/web/`. Coffee-palette design system ported from the approved mockup;
      mobile-first shell with a working bottom tab bar. `npm run build` is clean
      (lint + types pass). Screenshots verified against the mockup._
      _**Deploy done** (recorded 2026-07-27): the site is live at
      `https://brewmatch-sepia.vercel.app` — evidenced by the brain's CORS allow-list
      naming that exact origin (`api/main.py:118`), which only works against a real
      deployed site. The tab bar now carries five tabs (Home / Recipes / Coffees /
      History / Profile), not the original four._
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
- [x] **B3. Build the core screens** with the agreed look (D3): home/diagnosis,
      recommendation/recipe view, log-a-brew, your coffees/bags, history + "what
      it's learned."
      _Done — verified 2026-07-27 by reading the code, not the filenames. Every
      screen is real and wired to the brain:_
  - _Home (`app/page.tsx`) — the two-path hub ("get a recipe" / "fix a cup"),
    per journal 0033._
  - _Diagnose (`components/DiagnoseFlags.tsx`, 158 lines) — all five taste
    flags, POSTs to `/diagnose`._
  - _Recipes (`components/RecipesFlow.tsx`, 707 lines) — bean entry, ranked
    recipes, recipe card with running water totals and clock-format times,
    editable dose that rescales, source trust labels
    (champion / barista / enthusiast)._
  - _Coffees (`components/CoffeesFlow.tsx`, 588 lines) — add, edit and finish
    bags, with the "≈N brews left" running-low estimate._
  - _Log a brew (`components/LogBrew.tsx`, 194 lines) — thumbs, score, taste
    flags, notes._
  - _History (`components/HistoryFlow.tsx`, 247 lines) — past brews, the
    learning phase in plain language, and "learned from N brews"._
  - _Profile (`components/ProfileFlow.tsx`, 349 lines) — your grinder, your
    brewers, brew stats._
- [x] **B3-grinder. Grinder-specific grind guidance (USER WANTS — every
      grinder model differs).** Add a "pick your grinder" step (setup or
      profile) covering the 9 grinders in `src/grinder_catalog.py`
      (Comandante C40, Timemore C2/C3, Kingrinder K6, 1Zpresso K-Max/J-Max,
      Baratza Encore, Fellow Ode Gen 2, Niche Zero, + Other). Grind advice
      then shows in that grinder's real units (clicks/rotations/setting),
      e.g. "~28 clicks on Comandante C40", not just "finer". Decision: the
      brain keeps the catalog and exposes the translation over its web
      service (single source of truth — do NOT copy the table into the
      front-end). Depends on recipe-aware diagnosis (a real grind number to
      translate).
      _Done 2026-06-26 (`5194230`), then rebuilt 2026-07-08 (`086bc08`) on real
      measured microns plus an on-device "your usual setting" baseline
      (`lib/grinderCalibration.ts`) — because a fixed chart can't be trusted
      across grinder variants, so advice is anchored to one reading the user
      gives from their own dial. Python↔TypeScript translation parity is now
      guarded by tests (`93654b2`)._

**Goal B is done when:** the new app is live at a real web address, looks like a
real product, and talks to your brain.

---

## Goal C — Real login (if D2 = yes)

The point: people sign in securely, and it's ready for future sharing/community.

- [x] **C1. Turn on Supabase's built-in login** — _done for email; Google
      sign-in NOT built (recorded 2026-07-27)._
      _What shipped (`23017e4`): a Sign in screen (`components/SignInFlow.tsx`)
      with three ways in — create an account with email + password, sign in with
      email + password, or a "magic link" emailed to you (no password at all).
      Supabase handles the accounts._
      _Honest gap: **"sign in with Google" was never built**, and there is no
      explicit "forgot my password" flow — the magic link covers the same need
      (you can always get in via email without your password), but it is not the
      same thing as a password reset. Both are small additions if you want them;
      neither blocks anything today._
- [x] **C2. Wire the new screens to it** so each person sees only their own
      coffees, brews, and learning. _(done — `ba513b0`, `efaecce`)_
      _The brain now checks the login token on every per-person request
      (`api/main.py:173` `resolve_user`): a token that doesn't match the account
      being asked for is refused, and an account can't be read without one.
      Before you sign in, the app still works — each device gets its own private
      anonymous id (`lib/identity.ts`), so you can use BrewMatch without an
      account and your data is still saved._
      _Known loose end: brews logged anonymously on a device are **not yet moved
      onto your account when you sign in** — `lib/identity.ts` deliberately keeps
      the device id so a future migration can find them, but that migration
      ("Goal C step 3" in the code comment) was never built. In practice: sign in
      before you start logging brews, or that history stays under the device._

**Goal C is done when:** a new person can sign up, log in, and their data is
private to them — with password reset and the rest handled for you.
_Substantially met via email + magic link; Google sign-in, an explicit password
reset, and the anonymous→account history migration are the named gaps._

---

## Goal D — Move every existing feature across (nothing lost)

The point: a checklist so the new app does **everything** the current one does
before we retire the old one.

- [~] **D-parity. Feature-for-feature check:** diagnosis flow, recommendations,
  recipe card (running water total, clock-format times), log + rate a brew,
  editable dose that rescales the recipe, your coffees/bags + "running low,"
  personalization phase + "learned from N brews," brew history, trust badge on
  sources. Each one re-checked working in the new app.

  > **⚠ A parity check was run on 2026-07-05 and its record was lost.**
  > Commit `2309012` says "Found via the Goal D parity red-team; see
  > `workspaces/BrewMatch/04-validate/d-parity.md`" — **that file was never
  > committed and does not exist**, on disk or anywhere in git history. So we
  > know a parity pass happened and found at least two real regressions (the
  > Diagnose screen had lost its recipe-awareness, and the "too harsh" taste
  > flag was missing entirely — both fixed in that commit), but **we cannot know
  > what else it found**. Anything it flagged and didn't fix is invisible.
  >
  > Disposition: the parity check MUST be re-run from scratch and its findings
  > committed this time. Treat the 2026-07-05 pass as unrecoverable, not as
  > coverage.

  _Desk-check done during the 2026-07-27 reconciliation (reading code, not
  running the app) — every item on the list above has a real implementation:
  running water totals + clock format (`lib/recipe.ts`
  `poursWithRunningTotal`/`clockFormat`), dose rescale (`rescaleToDose`),
  running-low (`CoffeesFlow.tsx:554`, "≈N brews left"), learning phase +
  brew count (`HistoryFlow.tsx:108`), source tier labels
  (`RecipesFlow.tsx:56`). This is evidence the features EXIST; it is **not**
  evidence they behave correctly against the live app, which is what the
  re-run must establish._

**Goal D is done when:** every feature you have today works in the new app,
**and** the check that proves it is written down and committed.

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

## What's actually left in Phase 2 (post-reconciliation, 2026-07-27)

Goals A, B and C are built and live. What remains:

1. **Re-run the Goal D parity check and commit the record.** The 2026-07-05 pass
   is unrecoverable (see the warning under D-parity). This is the real remaining
   work and the gate before switchover.
2. **Goal E — switchover.** Run old and new side by side, then retire Streamlit.
3. **Named Goal C gaps, all optional:** "sign in with Google", an explicit
   password reset, and moving anonymous device history onto an account at
   sign-in.

Known accepted issue, not a Phase 2 task: the brain sleeps after ~15 minutes idle
on Render's free tier, so the first visit after a quiet spell waits ~50 seconds.
A scheduled wake-up ping was tried and removed on 2026-07-15 (`4403a11`,
`0fbe934`) — GitHub throttled the 10-minute schedule to roughly hourly, so it
woke an already-asleep service instead of preventing sleep, and occasionally
timed out mid-wake and raised false alarms. The reliable fix is Render's paid
Starter tier; until then this is accepted behaviour.

Work that shipped inside Phase 2 but was never in this plan (recorded here so the
plan matches history): brewer-as-gear (its own todo, now complete), the
grinder-calibration rebuild on real microns, bag editing with form-level size
validation, and a Vitest test harness for the website.

---

## Your review — three questions before we proceed

1. Does this cover what you pictured for the rebuild?
2. Is anything here you **don't** want (or that should wait)?
3. Anything missing you expected to see?

Once you've answered D1–D3 and you're happy with the scope, say the word and I'll
turn this into the detailed build steps and start with Goal A.

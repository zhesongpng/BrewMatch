# BrewMatch — Master Todo List

Last updated: 2026-07-27 (reconciled against actual repo state)

---

## Where the project is now

**The foundational build is complete.** Milestones 1–5 (data, ML
pipeline, web app, evaluation, polish) are all complete. Their finalized
records live in `todos/completed/`. The app is built, tested, and deployed.

_Test count: **823 passing, 0 failed, 0 warnings** — verified 2026-07-27 by
running `.venv/bin/python -m pytest -q`. Earlier claims in this file (646, then 761) were both stale._

**Fresh-checkout prerequisite:** the suite needs the synthetic dataset, which is
generated and gitignored (`data/synthetic/*.csv`). On a clean clone, 10 tests in
`tests/unit/test_evaluate_pipeline.py` fail with a bare `FileNotFoundError` until
you run `python -m src.data_generator.generator` (documented at `README.md:62`;
seeded with 42, so it is reproducible). Worth knowing before concluding the suite
is broken._

We are now in a **new chapter with a bigger goal: grow BrewMatch into a real
product** — reliable enough for daily use, nice enough to
show people, and eventually a small community of like-minded coffee people
sharing recipes, with the option to commercialise later.

That vision is sequenced so each phase delivers something usable on its own and
nothing has to be rebuilt later:

| Phase       | Goal                                                            | Status          |
| ----------- | --------------------------------------------------------------- | --------------- |
| **Phase 1** | Stop the live app resetting + let it learn from your real brews | ✅ Done¹        |
| **Phase 2** | A nicer, redesigned interface + a real login, on a new host     | 🔜 Nearly done² |
| **Phase 3** | Community: share recipes with a group of users                  | 💭 Future       |
| **Later**   | Commercialisation, once there are real users to learn from      | 💭 Future       |

¹ **Phase 1 (complete).** The resetting is fixed (Supabase connected, the live
app persists to it), the brew-logging flow shipped, the learning engine runs
automatically on every logged brew, and an automated test proves data survives a
restart. One item deliberately parked: one-click data export (C1). Detail in
`active/p1-live-persistence-and-learning-loop.md`.

² **Phase 2 status (reconciled 2026-07-27).** Much further along than this file
previously claimed. The website is live on Vercel
(`https://brewmatch-sepia.vercel.app`), the Python brain is live on Render
(`https://brewmatch-iki5.onrender.com`), all screens are built, and Supabase
email sign-in works end-to-end with the brain verifying login tokens. **Left to
do: re-run the feature-parity check (the 2026-07-05 pass exists only as a
reference in a commit message — its record was never committed and is
unrecoverable), then switch over and retire the Streamlit app.** Optional
follow-ons: "sign in with Google", an explicit password reset, and moving
anonymous device history onto an account at sign-in. Full detail in
`active/p2-react-vercel-rebuild.md`.

The order matters: a reliable foundation (Phase 1) before a nice face and real
accounts (Phase 2) before inviting other people in (Phase 3) before charging
anyone (Later). Building the foundation on **Supabase** (see Phase 1 decision)
means the login and community pieces are ready when we reach them — no redo.

---

## Phase 1 — at a glance

**The problem:** the live online app forgets everything when it restarts —
accounts, brew history, the lot. This happens often on free Streamlit hosting,
which is why your logins keep resetting.

**The cause:** the app currently keeps your data in its own temporary memory
(like a whiteboard inside the app). Every restart wipes the whiteboard.

**The fix:** give the app a _permanent database_ — a separate filing cabinet
that lives on the internet and survives restarts — and point the live app at
it. Then build the part you most wanted: the app learning from the brews you
actually log and rate.

**When Phase 1 is done, two things are true:**

1. You stay logged in and your brew history never disappears.
2. The more real brews you log and rate, the more the recommendations bend
   toward _your_ taste.

➡️ **Step-by-step task list:**
`active/p1-live-persistence-and-learning-loop.md`

---

## Phase 2 — in progress (nearly done)

Redesigned look-and-feel with full design control, a **real login** using
Supabase's built-in accounts, and a move off Streamlit. All of Phase 1's work
(database + learning) carried over unchanged, as planned.

**Built and live:** the website is a React (Next.js) app on Vercel; the Python
brain runs as its own small service on Render; the two talk over the internet.
Every screen is built — home, recipes, coffees, log-a-brew, history, profile —
and email sign-in works, with the brain checking your login before it hands over
any account data.

**Still to do:** re-run the feature-parity check (prove the new app does
everything the old Streamlit one did) and commit the result, then switch over and
retire the old app. Optional extras: "sign in with Google", an explicit password
reset, and carrying anonymous device history onto an account when you sign in.

➡️ **Step-by-step task list:** `active/p2-react-vercel-rebuild.md`

A second Phase 2 workstream — **brewer-as-gear** (your brewers are equipment you
own and pick, not a property of the beans) — is complete; its record moved to
`completed/p2-brewer-as-gear.md`. One deferred question from it: should the
grinder also become multi-owned, for consistency with brewers? Not blocking.

## Phase 3 — future (community)

Open it up so a group of like-minded people can join, log their own brews, and
share recipes with each other. This is where BrewMatch stops being a solo tool
and becomes a small community. Built on the same Supabase foundation, so the
accounts and permissions are already in place. We plan this in detail after
Phase 2.

## Later — commercialisation (deliberately last)

The recommended order is: prove it's reliable (Phase 1) → make it nice with real
accounts (Phase 2) → get a handful of real users sharing recipes (Phase 3) →
_then_ explore charging. Trying to monetise before there are engaged users is
the most common way small products stall. The genuine asset to build toward is
the brew data: a community logging real cups creates something generic coffee
apps don't have. No tasks here yet — this is a marker, not active work.

---

## Key product decisions already on record

(Kept for context — these are settled, not open questions.)

- **Scope:** pour-over only — V60, Kalita Wave, Origami.
- **Diagnosis-first:** the app is a troubleshooting tool first, personalization
  second.
- **Five taste flags:** too sour, too bitter, too weak, too harsh, astringent.
- **Optimizer:** tunes 4 things (grind, temperature, dose, ratio); the pour
  schedule comes fixed from the retrieved recipe.

---

## Archived: foundational build (Milestones 1–5)

All complete. Finalized records are in `todos/completed/`. Nothing in those
milestones is outstanding — they are kept only for history.

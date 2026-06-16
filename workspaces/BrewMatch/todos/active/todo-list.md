# BrewMatch — Master Todo List

Last updated: 2026-06-15 (reconciled against actual repo state)

---

## Where the project is now

**The foundational build is complete.** Milestones 1–5 (data, ML
pipeline, web app, evaluation, polish) are all complete. Their finalized
records live in `todos/completed/`. The app is built, tested (646 tests
passing), and deployed.

We are now in a **new chapter with a bigger goal: grow BrewMatch into a real
product** — reliable enough for daily use, nice enough to
show people, and eventually a small community of like-minded coffee people
sharing recipes, with the option to commercialise later.

That vision is sequenced so each phase delivers something usable on its own and
nothing has to be rebuilt later:

| Phase       | Goal                                                            | Status          |
| ----------- | --------------------------------------------------------------- | --------------- |
| **Phase 1** | Stop the live app resetting + let it learn from your real brews | 🔜 Mostly done¹ |
| **Phase 2** | A nicer, redesigned interface + a real login, on a new host     | ⏳ Planned      |
| **Phase 3** | Community: share recipes with a group of users                  | 💭 Future       |
| **Later**   | Commercialisation, once there are real users to learn from      | 💭 Future       |

¹ **Phase 1 status (reconciled 2026-06-15):** the resetting is fixed (Supabase
chosen, created, connected — the live app persists to it), the brew-logging
flow shipped, and the learning engine runs automatically on every logged brew.
Genuinely outstanding: a one-click export (C1), a recorded restart-survival
proof (C2/A4), an honest "learned from N brews" indicator (B3 polish), and a
small decision on whether to add an explicit "retrain" button (B2). Full detail
and an open question in `active/p1-live-persistence-and-learning-loop.md`.

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

## Phase 2 — planned (not started)

Redesign the look-and-feel with full design control, add a **real login**
(social sign-in, password reset, email verification — using Supabase's built-in
accounts), and move onto a host that isn't Streamlit. We lock in the exact
tools when we get here; all of Phase 1's work (database + learning) carries over
unchanged. No detailed tasks yet — we plan this once Phase 1 lands.

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

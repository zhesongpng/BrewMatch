---
type: DECISION
date: 2026-07-27
created_at: 2026-07-27T00:00:00Z
author: co-authored
project: BrewMatch
topic: Plan-of-record reconciled against the repo after three weeks of undocumented shipping
phase: todos
tags: [phase-2, reconciliation, process, drift, session-notes]
---

# DECISION — Plan-of-record reconciled against the repo

Date: 2026-07-27
Phase: /todos (reconciliation pass)
Status: DONE — no code changed; records now match the code

## Why this was needed

The user asked what was outstanding. There are **no `.session-notes` anywhere in
this repo** — `/wrapup` has never been run — so the only way to answer was to
read the journal, the todos, and the git history and compare them against the
code. They disagreed substantially.

The written plan claimed Phase 2 was barely started: B1 "needs your Vercel
login", B3 "not started", Goal C undecided. The code said otherwise — the site
is live on Vercel, all screens are built, and Supabase email sign-in works
end-to-end with the brain verifying tokens.

Three weeks of work (2026-07-05 → 2026-07-15) shipped with no journal entries
and no todo updates: recipe-aware diagnosis restored plus a fifth taste flag,
grinder calibration rebuilt on real microns, bag editing, a Vitest harness, and
the deployment fixes.

## What was reconciled

- **`todos/active/p2-react-vercel-rebuild.md`** — B1, B3, B3-grinder, D3 and
  Goal C ticked against evidence (commit SHAs and file:line, not memory); the
  three real Goal C gaps named; a "what's actually left" section added.
- **`todos/active/todo-list.md`** — Phase 1 marked done, Phase 2 marked nearly
  done with the remaining work stated plainly.
- **`todos/active/p2-brewer-as-gear.md`** → `todos/completed/` (both tasks
  shipped and were red-teamed).
- **`apps/web/README.md`** — described Recipes / Coffees / History as empty
  shells; they are 588–707 line screens. Rewritten, plus the live URL, the test
  command, and the cold-start caveat.
- **`specs/`** — `user-interface.md` described Streamlit as *the* UI. Marked
  legacy, and a new `specs/web-frontend.md` written as the authority for the
  React app.
- **Journal** — [[0037-GAP-goal-d-parity-redteam-record-lost]],
  [[0038-DECISION-grind-advice-anchored-to-user-baseline]],
  [[0039-DECISION-render-cold-start-accepted-keepalive-removed]], and this
  entry.

Journal numbering note: `0035` is genuinely absent — the sequence skips from
0034 to 0036. Not reused; entries are immutable and renumbering would break
existing references.

## What the reconciliation surfaced

The most valuable finding was not any single stale checkbox but
[[0037-GAP-goal-d-parity-redteam-record-lost]]: a Goal D parity red-team ran on
2026-07-05, found at least two real regressions, and left no committed record.
Coverage that cannot be read is not coverage. Goal D must be re-run.

Ticking boxes to match reality is the cheap half of this. The expensive half is
that between 2026-07-05 and today, anyone reading the plan would have concluded
the React app barely existed.

## Root cause and the cheap fix

Documentation updates were bundled into feature commits, so any session that ran
out of room shipped the code and dropped the record. `/wrapup` — which exists
precisely to write `.session-notes` — was never run, so nothing caught it at
session end.

The fix is not more discipline mid-session; it is running `/wrapup` before
ending one. A session that ends with notes leaves the next session a starting
point instead of a three-week archaeology exercise.

## For Discussion

1. Counterfactual: had `/wrapup` run on 2026-07-05, would `d-parity.md` have
   survived? (Probably yes — session notes would have carried the round's
   findings even if the file itself was never staged.)
2. Feature commits carried thorough messages — `0fbe934`'s body explains the
   keep-alive failure better than most journal entries. Is the journal
   duplicating what git already holds, or is the difference that journal entries
   are discoverable by topic while commit bodies are only findable if you know
   to grep for them?
3. This reconciliation trusted code-reading for its evidence ("the feature
   exists at this file:line"). Goal D needs behavioural proof against the live
   app. Where else in this project has "the code exists" been quietly accepted
   as "the feature works"?

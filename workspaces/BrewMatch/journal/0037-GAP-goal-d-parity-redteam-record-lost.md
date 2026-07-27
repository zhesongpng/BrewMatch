---
type: GAP
date: 2026-07-27
created_at: 2026-07-27T00:00:00Z
author: agent
project: BrewMatch
topic: The Goal D parity red-team ran on 2026-07-05 but its findings record was never committed
phase: redteam
tags: [phase-2, goal-d, parity, red-team, process-gap, lost-artifact]
---

# GAP — Goal D parity red-team record lost

Date: 2026-07-27 (recording a gap created 2026-07-05)
Phase: /redteam (Phase 2, Goal D — feature parity)
Severity: MEDIUM (no broken code; lost coverage and a false sense of it)
Status: OPEN — the parity check must be re-run

## What

Commit `2309012` (2026-07-05, "feat(web): restore recipe-aware diagnosis + add
5th taste flag") ends with:

> Found via the Goal D parity red-team; see
> `workspaces/BrewMatch/04-validate/d-parity.md`.

**That file does not exist.** It is not on disk, not in `04-validate/`, and not
anywhere in git history:

```
$ git log --all -- "workspaces/BrewMatch/04-validate/d-parity.md"   # empty
$ ls workspaces/BrewMatch/04-validate/d-parity.md                   # No such file
```

Every other red-team round in this project produced a committed record in
`04-validate/` (b1.1 through b1.7, b2, grinder-calibration, milestones 1–5). This
one did not. The most likely explanation is that the file was written in the
working tree and never staged — the commit that cites it touched only `apps/web`
files.

## Why it matters

The round found at least two real regressions, both fixed in that same commit:

1. The React Diagnose screen had regressed to diagnosing a single, context-free
   taste flag, so the brain's ML engine never fired — users got generic
   rule-based advice where the Streamlit app gave personalized fixes.
2. The "too harsh" flag was missing entirely from the Diagnose screen, so a
   whole taste problem could be logged but never diagnosed.

Both are exactly the class of failure a parity check exists to catch, which
means the round was working. **What we cannot know is what else it found.**
Anything flagged but not fixed in `2309012` — a lower-severity finding, a
deferred item, a note about an unported feature — is unrecoverable.

The dangerous outcome is not the lost text; it is the plan recording Goal D as
partly covered on the strength of a round nobody can read.

## Disposition

Treat the 2026-07-05 round as **not having happened** for coverage purposes. The
parity check is re-run from scratch, and its record is committed in the same
commit as any fix it produces. Recorded in
`todos/active/p2-react-vercel-rebuild.md` under Goal D with the same warning.

A desk-check during the 2026-07-27 reconciliation confirmed every item on the
parity list has a real implementation in the React app (running water totals,
clock format, dose rescale, running-low estimate, learning phase + brew count,
source trust labels). That establishes the features **exist**; it says nothing
about whether they **behave** correctly against the live app.

## Follow-up

- Re-run Goal D parity; commit `04-validate/d-parity.md` this time.
- Process fix worth considering: a red-team round is not complete until its
  record file is committed — the commit that cites a validation artifact should
  contain it.

## For Discussion

1. Counterfactual: if the round had found a HIGH it chose to defer rather than
   fix, would anything in the current repo surface it? (Best available answer:
   no — no todo, journal entry, or code comment references the round beyond the
   commit message. A deferred finding would be invisible.)
2. Six other red-team rounds in `04-validate/` were committed with their fixes.
   What was different about this one — a longer round that outran the commit, or
   simply that the fix felt self-contained enough to ship alone?
3. Should validation records live alongside code changes in one commit, or is
   the real defect that `/redteam` has no completion gate that checks its own
   output landed?

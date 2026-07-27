---
type: DECISION
date: 2026-07-27
created_at: 2026-07-27T00:00:00Z
author: human
project: BrewMatch
topic: Sunset the Streamlit app — dependencies trimmed now, code deleted after the Goal D parity check
phase: deploy
tags: [phase-2, goal-e, streamlit, sunset, render, dependencies]
---

# DECISION — Sunset the Streamlit app

Date: 2026-07-27
Phase: /deploy (Phase 2, Goal E)
Decided by: the user ("i am the only one using the app. lets just sunset it.
trim it. i will delete it accordingly")
Status: STEP 1 DONE (dependencies trimmed, PR #3 merged). Step 2 pending Goal D.

## The decision

Retire the Streamlit app. It is no longer the product — the React app on Vercel
is. The user is its only user, so there is no audience to migrate and no reason
to keep a fallback alive.

Executed in two deliberate steps rather than one:

1. **Now — drop it from the brain's install.** Render builds with
   `pip install -r requirements.txt`, then runs only `uvicorn api.main:app`, so
   every rebuild was installing an entire web framework the brain never imports,
   on a 512 MB instance.
2. **After the Goal D parity check — delete the app itself** (`app.py`,
   `src/app/app.py`, `src/app/pages/`, `.streamlit/`, the two regression tests
   that exercise it, and the Streamlit entries in `pyproject.toml`).

## Why that order

The parity check asks "does the new app do everything the old one did", and the
old app's source is the reference for answering it. Deleting the yardstick before
measuring is precisely how the previous parity round's findings were lost — see
[[0037-GAP-goal-d-parity-redteam-record-lost]]. Step 2 waits.

## What Step 1 actually removed

Streamlit-only: `streamlit`, `streamlit-cookies-manager`, `altair` (charts on the
old evaluation/history pages), `bcrypt` (the old password login; accounts are
Supabase now).

Dead weight found while verifying: `shap`, `numba`, `llvmlite`. A repo-wide grep
for their imports returns zero hits — `shap` was never used, and `numba`+
`llvmlite` were pinned only as its transitive dependencies. They are also the
packages that compile from source when no manylinux wheel matches, which
`requirements.txt` itself named as the leading suspect for an earlier failed
rebuild. Removing them removes that build-risk class outright.

`lightgbm` was checked and **kept** — it is genuinely reachable via
`src/taste_predictor/model.py`. A trim done by intuition rather than import trace
would have removed it and broken model loading.

`pyproject.toml` was deliberately left intact: local dev and the test suite still
need Streamlit until Step 2.

## Alternatives considered

- **Delete everything at once.** Rejected — destroys the parity reference.
- **Keep Streamlit as a live fallback.** Rejected — the user is the sole user,
  and the deployment is not publicly reachable anyway, so it was not functioning
  as a fallback for anyone.
- **Leave the dependencies in place "just in case".** Rejected — cost is paid on
  every rebuild, and the removal is trivially revertible.

## Consequences

- The Streamlit Cloud deployment will fail its next rebuild, since it installs
  the same `requirements.txt`. Intended; the user is deleting the app there.
- Its deployment status was never determinable from the repo — no URL was ever
  recorded, and a live probe could not distinguish "private app" from "no app"
  because Streamlit Cloud gates every subdomain behind the same login redirect.
- Step 2 remains blocked on Goal D, by design.

## For Discussion

1. Step 2's checklist is written down here and in the Goal E todo, but nothing
   enforces it. What stops the Streamlit code from lingering for months after
   Goal D closes — is the todo sufficient, or should it become a dated issue?
2. `shap` sat in the deploy set unused for long enough to be blamed for build
   failures. Would a periodic "unused dependency" sweep have caught it, or was
   the import trace only prompted because the sunset forced the question?
3. Counterfactual: had `lightgbm` been removed alongside the other ML-sounding
   packages, the brain would have failed to load models at startup. Does that
   argue Step 1 should have waited for a runnable local test environment, given
   it shipped on static analysis?

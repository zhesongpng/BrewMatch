---
type: DISCOVERY
date: 2026-05-17
project: BrewMatch
topic: Milestone 5 walkthrough uncovered a class of cloud-only bugs invisible to local file-mode testing
phase: deploy
tags:
  [
    streamlit-cloud,
    in-memory-sqlite,
    sentence-transformers,
    meta-tensor,
    graceful-degradation,
    ux-consistency,
    regression-tests,
  ]
---

## Finding

The Milestone 5 demo walkthrough exercised the app in demo / in-memory mode
(what Streamlit Cloud actually runs) rather than the local file-based SQLite
mode used during development. This surfaced a whole class of bugs that local
testing structurally could not catch — the deployed app was effectively
non-functional on Streamlit Cloud while every local test passed. Five distinct
issues were found and fixed across three commits (`83e5072`, `8917099`,
`d2b020a`), each guarded by a regression test in
`tests/regression/test_demo_mode_persistence.py`.

## Main Changes

1. **In-memory DB wiped between every operation** (`83e5072`).
   Shared-cache in-memory SQLite is destroyed when its last connection
   closes. The app opens/closes connections serially with no overlap, so the
   database was erased between operations — the demo account was never
   created and registrations never persisted. Fixed by holding one
   process-lifetime keep-alive connection per in-memory URI in
   `src/app/db.py`.

2. **Demo account had no drippers** (`83e5072`).
   The demo seed never set Alex's equipment, so the showcase profile showed
   no drippers despite 15 brews spanning V60 / Kalita Wave / Origami. Fixed
   by seeding `ALEX_DRIPPERS` in both seed paths in `scripts/seed_demo.py`.

3. **Evaluation dashboard read a CWD-relative path** (`83e5072`).
   `models/` was resolved relative to the working directory; Streamlit Cloud
   runs the app from a temp dir, so every metric showed "Not yet evaluated".
   Fixed to resolve from the repo root, matching `model.py::MODELS_DIR`.

4. **Recipe retrieval hard-failed when the embedding model could not load**
   (`8917099`). Cloud logs confirmed `sentence-transformers` fails with
   "Cannot copy out of meta tensor; no data!". The fix has three parts:
   `low_cpu_mem_usage=False` to stop the accelerate meta-device lazy init
   (root-cause attempt); BM25 sparse index built first so a model failure
   cannot skip it; `retrieve()` computes the query embedding best-effort and
   degrades to BM25-only keyword ranking instead of raising. Net effect:
   recipe search works on cloud (keyword-ranked) even when the semantic
   model cannot load.

5. **Grind display inconsistent between recipe card and optimizer**
   (`d2b020a`). The recipe card showed grinder-specific clicks; the
   optimization comparison showed only the bare 1-10 scale, so one grind
   value read as two different things on one screen. Extracted a shared
   `_format_grind` helper (rounds the optimizer's continuous values to whole
   steps, shows clicks when a grinder is set, falls back to the 1-10 scale
   otherwise) used by the recipe card, the Original/Optimized columns, and
   the Changes list.

One reported symptom — the `auth.py:111` cookie-manager `AttributeError`
traceback in the cloud logs — was investigated and is **not a bug**: the
code already guards it with `if cm is not None` plus `try/except`; the
traceback is `exc_info` from a handled warning, login still succeeds, and
session-not-persisting is the already-documented ephemeral-cloud limitation.

## Root Insight

Local development used file-based SQLite and a working `sentence-transformers`
install, so the test suite (652 passing at session start) validated a code
path that production never runs. The cloud environment differs on three
axes simultaneously — read-only filesystem (forces in-memory DB), temp
working directory (breaks relative paths), constrained model loading (meta
tensor error). None of these are exercised by `pytest` against the local
checkout. "All tests pass" was true and irrelevant to whether the deployed
app worked.

## Alternatives Considered

- **Grind display (issue 5): remove the 1-10 scale entirely** (the user's
  initial proposal). Rejected: `get_grinder_display` returns nothing for
  "Other"/no-grinder users, so removing the scale would leave their grind
  field blank. Keeping the scale as a fallback is strictly safer; the real
  defect was inconsistency, not the scale's existence.
- **Recipe retrieval (issue 4): only fix the meta-tensor model load.**
  Rejected as the sole fix — it cannot be verified locally and depends on
  cloud library versions. Graceful BM25 degradation is the guarantee;
  the model-load fix is the best-effort enhancement on top.

## Consequences

- The deployed app is functional on Streamlit Cloud after rebuild: demo
  login works, recipes retrieve (keyword-ranked if the model fails), the
  evaluation dashboard displays, and grind reads consistently in clicks.
- Test count rose 652 → 661; all new coverage is cloud-mode behavior that
  the prior suite could not express from a local checkout.
- `REPORT.md` Section 6 now documents the cloud in-memory hardening.

## Follow-up Actions

- Backup demo screenshots still owed — requires a browser; capture manually
  from the live app post-rebuild (noted in `m5-polish.md`).
- Confirm on the live app whether `low_cpu_mem_usage=False` makes semantic
  search actually load on cloud, or whether it stays in BM25-only mode (the
  `Dense index unavailable ... falling back to BM25-only` WARN in the logs
  is the signal).
- Persistent-database migration remains deferred (user: "nvm later"); it is
  the only remaining structural cloud limitation.

## For Discussion

1. Counterfactual: if the Milestone 5 step had again tested only local
   file-based mode (as every prior session did), how many more sessions
   would have shipped "all 652 tests pass" while the deployed app stayed
   broken — and what would have caught it short of a user opening the live
   URL?
2. The suite grew to 661 passing yet none of the five bugs were caught by
   the 652 that existed before. What is the minimum standing harness that
   exercises in-memory mode + foreign CWD + simulated model failure on
   every run, so cloud-mode regressions fail in CI rather than in
   production?
3. Issue 4 ships a degraded mode (keyword-only) that is invisible to users
   except via a log line. Is silent degradation the right default for a
   course demo where the evaluator may never read logs, or should the UI
   surface "ranking by keywords (semantic model unavailable)" when the
   dense index is absent?

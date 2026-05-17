---
type: DISCOVERY
date: 2026-05-17
project: BrewMatch
topic: Every below-target evaluation metric traces to one root cause — synthetic training data zeroed the per-user features
phase: redteam
tags:
  [
    evaluation,
    synthetic-data,
    honest-reporting,
    personalization,
    r-squared,
    report,
  ]
source_commit: 1ca51d8271ee8fcb55daac65c6b0417e5a6d90ab
---

## Finding

While verifying Milestone 4, the evaluation scorecard showed several metrics
below their targets (R² 0.08 vs >0.5, optimization improvement 0.24 vs >0.5,
personalization phase-RMSE improvement 0% vs >10%, bean-extraction accuracy
88% vs >90%). Investigated as if they were separate defects; they are not.
**All of them share a single root cause: the taste predictor was trained on
~2,000 synthetic ratings in which every per-user history feature was zero.**
A gradient-boosting model never splits on a feature with no training-time
variance, so at inference it ignores the user-history and personalization
columns entirely. That one fact explains the whole cluster of misses.

The most important sub-finding: the personalization 0% is **not** a broken
personalization engine. The engine's feature-space convergence climbs from
0.00 to 0.99 across brews — it correctly learns each user's preferences. The
flat phase-RMSE reflects the _predictor_ not consuming those learned features
(it was trained without them), not a logic failure. Mechanism correct; model
cannot yet exploit it.

`RMSE = 1.31` (within the <1.5 target) is the trustworthy headline accuracy
number; `R²` is structurally suppressed because synthetic ratings have
compressed variance, so there is little real signal to "explain."

## Decision Taken

Report the misses honestly rather than chase the numbers. `REPORT.md`
Section 7.1 now carries the full scorecard transparently and attributes the
gaps to the single synthetic-data root cause (committed in `1ca51d8`).

## Alternatives Considered

- **Tune/retrain to hit the targets.** Rejected: improving R² on synthetic
  data means overfitting fabricated patterns — worse than an honest miss for
  an academic ML submission, and pedagogically backwards.
- **Quietly omit the weak metrics from the report.** Rejected: an MBA ML
  course rewards understanding _why_ numbers land where they do; selective
  reporting is the opposite of the analysis the assignment asks for.
- **Treat each miss as its own defect with its own fix.** Rejected once the
  shared root cause was found — five "bugs" collapse to one explained
  limitation.

## Consequences

- The report frames the limitation as a demonstration of ML understanding
  (variance, feature learning, synthetic-vs-real generalization) rather than
  a failure to hide.
- Closing the gaps requires real-world brew data, not new algorithms — once
  per-user features gain variance, the predictor can learn to use them and
  the personalization engine's already-correct signal becomes visible in
  accuracy. This is the same limitation already deferred elsewhere.

## Follow-up Actions

- None blocking. If real user ratings are ever collected, re-run the
  evaluation and the personalization improvement should appear without any
  code change to the engine.

## For Discussion

1. Counterfactual: had the five misses been "fixed" individually by tuning
   until each target was hit on synthetic data, what would the model have
   actually learned — and how would that have surfaced the moment a single
   real user logged a real rating?
2. The scorecard reports `RMSE 1.31` (pass) and `R² 0.08` (fail) for the
   same model on the same data. Which number should a course evaluator
   weight, and does the report make the case for that clearly enough on its
   own without this journal entry?
3. Personalization shows 0% phase-RMSE improvement yet 0.00→0.99 feature
   convergence. If a reader only saw the 0%, they would conclude the
   feature is broken. Is "mechanism correct, model can't consume it" a
   distinction the report communicates, or one that still depends on a
   reader opening the source?

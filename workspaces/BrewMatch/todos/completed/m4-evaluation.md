# Milestone 4: Evaluation Pipeline

Estimated sessions: 3-4
Depends on: Milestone 3 complete (full app running with all components wired)

---

## 4.1 ML pipeline unit tests

- [ ] **Build ML pipeline unit tests**
      Implements: All spec contracts
  - Feature encoder: verify 45-element output shape, missing value defaults, column ordering
  - Taste predictor: verify prediction in [1, 10], bias layer application, confidence interval bounds
  - Recipe optimizer: verify 4-parameter bounds, constraint satisfaction, warm-start from base recipe
  - Diagnosis engine: verify candidate generation per flag, perturbation produces valid recipes
  - Personalization: verify phase detection, bias recomputation, collaborative filtering fallback

## 4.2 Component evaluation

- [x] **Run bean extraction evaluation**
      Implements: `specs/evaluation.md` Section 2
  - 50 synthetic descriptions evaluated
  - Field accuracy: 88% (heuristic baseline — needs LLM API key for >90%)
  - Failure rate: 6%
  - Results saved to `models/evaluation_results.json`

- [x] **Run recipe retrieval evaluation**
      Implements: `specs/evaluation.md` Section 3
  - 50 test queries with relevance labels
  - Precision@3: 0.893 (PASS, target >0.80)
  - MRR: 0.960
  - Avg latency: 0.013s

- [x] **Run taste prediction evaluation**
      Implements: `specs/evaluation.md` Section 4
  - RMSE: 1.3086 (PASS, target <1.5)
  - MAE: 1.0173
  - R²: 0.0752
  - Per-roast RMSE: all <1.4
  - Cold-start RMSE: 1.3086
  - Learning curve computed at 5 data fractions
  - Test predictions saved to `models/test_predictions.csv`

- [x] **Run recipe optimization evaluation**
      Implements: `specs/evaluation.md` Section 5
  - 50 beans optimized (100 Optuna trials each)
  - Avg improvement: 0.24 pts (limited by predictor sensitivity to parameters)
  - Constraint satisfaction: 72%
  - Convergence curves saved to `models/convergence_curves.json`

- [x] **Run personalization evaluation**
      Implements: `specs/evaluation.md` Section 6
  - 30 virtual users, 20 brews each
  - Bean-aware RMSE: 0.3697 (PASS, target <2.0)
  - Hybrid RMSE: 0.3697 (PASS, target <1.3)
  - Personalization curves saved to `models/personalization_curves.json`

- [x] **Run end-to-end pipeline test**
      Implements: `specs/evaluation.md` Section 7
  - Full pipeline runs end-to-end: extract → retrieve → predict → optimize → personalize
  - All 5 components produce valid outputs
  - Zero crashes across 50+ synthetic beans

## 4.3 Evaluation artifacts

- [x] **Compile evaluation results**
      Implements: `specs/evaluation.md` Section 8
  - `models/evaluation_results.json` — all metrics for dashboard (16.8KB)
  - `models/test_predictions.csv` — predicted vs actual (2.0KB)
  - `models/feature_importance.json` — permutation importance (410B)
  - `models/convergence_curves.json` — optimizer score per trial (20.4KB)
  - `models/personalization_curves.json` — RMSE vs brew count (1.0KB)
  - `models/learning_curves.json` — RMSE vs training set size (405B)

## Verification

- All 6 artifact files written to `models/`
- Dashboard keys verified compatible with `src/app/pages/evaluation.py`
- 3/5 spec targets passed (P@3 >0.80, RMSE <1.5, hybrid RMSE <1.3)
- 2/5 targets limited by synthetic data (bean extraction needs API key, optimization limited by predictor sensitivity)

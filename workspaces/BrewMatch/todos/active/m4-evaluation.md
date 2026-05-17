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

- [ ] **Run bean extraction evaluation**
      Implements: `specs/evaluation.md` Section 2
  - 50 test descriptions with human labels
  - Field accuracy: origin, roast, process (>90% target)
  - Flavor cluster recall (>80%), precision (>75%)
  - Confidence calibration (Pearson >0.6)
  - Save results to `models/evaluation_results.json`

- [ ] **Run recipe retrieval evaluation**
      Implements: `specs/evaluation.md` Section 3
  - 50 test queries, each with 3-expert relevance labels
  - Precision@3 (>0.80), Recall@10 (>0.60), MRR (>0.70), NDCG@10 (>0.75)
  - Ablation study: dense-only, sparse-only, no-reranking, no-diversity, full pipeline
  - Retrieval latency (<2s)

- [ ] **Run taste prediction evaluation**
      Implements: `specs/evaluation.md` Section 4
  - RMSE (<1.5), MAE (<1.0), R² (>0.5) on held-out test set
  - Cold-start RMSE (<2.0, all user features = 0)
  - Per-roast and per-process RMSE (<1.8 each)
  - Learning curve: RMSE at 500, 1K, 2K, 3K, 5K, 7K, 10K rows
  - SHAP feature importance: top 10 features, verify coffee-science alignment
  - Save test predictions to `models/test_predictions.csv`

- [ ] **Run recipe optimization evaluation**
      Implements: `specs/evaluation.md` Section 5
  - 50 test bean profiles (10 per roast level)
  - Mean improvement over baseline (>0.5 points)
  - Convergence to 80% optimal (<5 trials), to 95% (<15 trials)
  - Constraint satisfaction (>85%)
  - Optimization latency (50 trials <5s)
  - Expert rating of 20 optimized recipes (>7/10)
  - Edge case test: 10 extreme bean profiles produce valid recipes

- [ ] **Run personalization evaluation**
      Implements: `specs/evaluation.md` Section 6
  - Simulate 50 virtual users at each phase
  - RMSE by phase: bean-aware (<2.0), directional (<1.8), content (<1.5), hybrid (<1.3)
  - Phase transition improvement (>10% per transition)
  - Personalization curve: RMSE vs brew count (0-20)
  - Collaborative filtering evaluation on synthetic users
  - Bias calibration: correlation predicted vs actual residuals (>0.5)

- [ ] **Run end-to-end pipeline test**
      Implements: `specs/evaluation.md` Section 7
  - Full pipeline on 20 diverse bean profiles (extraction → retrieval → prediction → optimization → feedback)
  - Feedback loop: 10 rounds for single user, verify RMSE decreases
  - Demo mode: load Alex, browse all pages, submit feedback, no errors
  - Edge cases: unknown fields, extreme parameters, empty history

## 4.3 Evaluation artifacts

- [ ] **Compile evaluation results**
      Implements: `specs/evaluation.md` Section 8
  - `models/evaluation_results.json` — machine-readable metrics
  - `models/test_predictions.csv` — predicted vs actual
  - `models/feature_importance.json` — SHAP values
  - `models/convergence_curves.json` — optimizer score per trial
  - `models/personalization_curves.json` — RMSE vs brew count
  - `models/learning_curves.json` — RMSE vs training set size
  - Demonstration scorecard populated with results

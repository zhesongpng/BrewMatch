# Evaluation Metrics Specification

## 1. Overview

This document defines evaluation metrics, targets, measurement methods, and success criteria for all five ML components in the BrewMatch pipeline. Each component has specific metrics aligned with its role in the system. The evaluation dashboard (`specs/user-interface.md` Section 4.9) displays these metrics.

---

## 2. Component 1: Bean Profile Extraction (NLP)

### 2.1 Metrics

| Metric                                  | Definition                                                       | Target | Measurement Method                                                |
| --------------------------------------- | ---------------------------------------------------------------- | ------ | ----------------------------------------------------------------- |
| Field accuracy (origin, roast, process) | Percentage of correctly extracted fields vs human labels         | > 90%  | Compare LLM extraction against 50 human-labeled bean descriptions |
| Flavor cluster recall                   | Fraction of human-assigned clusters that appear in extraction    | > 80%  | Compare against 3-expert consensus labels                         |
| Flavor cluster precision                | Fraction of extracted clusters that match human labels           | > 75%  | Compare against same labels                                       |
| Confidence calibration                  | Pearson correlation between confidence score and actual accuracy | > 0.6  | Bin by confidence tier; check HIGH > MEDIUM > LOW accuracy        |
| Extraction failure rate                 | Percentage of inputs that fall back to manual entry              | < 10%  | Count fallbacks vs successful extractions on test set             |

### 2.2 Test Set

50 bean descriptions from diverse roasters, each labeled by at least 2 human annotators. Fields: origin_country, process, roast_level, flavor_clusters.

### 2.3 Measurement Protocol

1. Run extraction pipeline on all 50 test descriptions.
2. Compare each extracted field against human labels.
3. Field is "correct" if it matches the consensus label exactly (for enums) or overlaps >= 80% (for flavor_clusters).
4. Compute per-field accuracy, then average across fields.

### 2.4 Success Criteria

All targets must be met. If field accuracy < 90%, investigate prompt engineering or add few-shot examples to the extraction prompt.

---

## 3. Component 2: Recipe Retrieval (RAG)

### 3.1 Metrics

| Metric                     | Definition                                                | Target      | Measurement Method                          |
| -------------------------- | --------------------------------------------------------- | ----------- | ------------------------------------------- |
| Precision@3                | Fraction of top-3 results that are relevant               | > 0.80      | Expert judgment on 50 test queries          |
| Recall@10                  | Fraction of all relevant recipes appearing in top 10      | > 0.60      | Expert judgment on same queries             |
| MRR (Mean Reciprocal Rank) | Average of 1/rank of first relevant result                | > 0.70      | Computed from same expert labels            |
| NDCG@10                    | Normalized Discounted Cumulative Gain at position 10      | > 0.75      | Graded relevance from expert labels         |
| Retrieval latency          | Time to return top-3 results                              | < 2 seconds | Timed measurement on test queries           |
| Diversity                  | Average pairwise parameter distance between top-3 results | > 0.3       | Euclidean distance on normalized parameters |

### 3.2 Test Set

50 test queries, each consisting of a bean profile. For each query, 3 coffee experts independently label the top 10 retrieved recipes as "relevant" (1) or "not relevant" (0). A recipe is "relevant" if majority of experts (2 of 3) agree.

### 3.3 Graded Relevance (for NDCG)

| Grade                  | Criteria                                         |
| ---------------------- | ------------------------------------------------ |
| 2 (Highly relevant)    | All 3 experts agree it is a good starting recipe |
| 1 (Partially relevant) | 2 of 3 experts agree                             |
| 0 (Not relevant)       | Fewer than 2 experts agree                       |

### 3.4 Ablation Study

| Variant       | Description                           | Purpose                           |
| ------------- | ------------------------------------- | --------------------------------- |
| Dense only    | ChromaDB cosine similarity, no BM25   | Measure BM25 contribution         |
| Sparse only   | BM25, no dense retrieval              | Measure embedding contribution    |
| No reranking  | RRF results without stage-3 reranking | Measure reranking contribution    |
| No diversity  | Top-3 by relevance score only         | Measure diversity selection value |
| Full pipeline | All stages active                     | Baseline for comparison           |

Each variant is measured on the same 50 test queries. Report delta from full pipeline for each metric.

### 3.5 Success Criteria

Precision@3 > 0.80 on the full pipeline. Each ablation variant should show degradation, confirming that every pipeline stage contributes value.

---

## 4. Component 3: Taste Prediction (Supervised Learning)

### 4.1 Metrics

| Metric           | Definition                                   | Target               | Measurement Method              |
| ---------------- | -------------------------------------------- | -------------------- | ------------------------------- |
| RMSE (test set)  | Root Mean Squared Error on held-out test set | < 1.5                | Standard regression metric      |
| MAE (test set)   | Mean Absolute Error on test set              | < 1.0                | Less sensitive to outliers      |
| R-squared        | Coefficient of determination on test set     | > 0.50               | Explains variance               |
| Cold-start RMSE  | RMSE when user features are zero             | < 2.0                | Simulate cold start on test set |
| Per-roast RMSE   | RMSE broken down by roast level              | < 1.8 for each level | Fairness check                  |
| Per-process RMSE | RMSE broken down by process type             | < 1.8 for each type  | Fairness check                  |

### 4.2 Test Set

15% holdout from synthetic data (750-1500 rows, depending on total generated). Stratified by roast level to ensure each level is represented.

### 4.3 Measurement Protocol

1. Train model on 70% of synthetic data.
2. Validate on 15% (early stopping, hyperparameter tuning).
3. Evaluate on held-out 15% (final metrics, reported once).
4. For cold-start evaluation: set all user features to 0, re-predict, compute RMSE.
5. For per-roast and per-process: filter test set by each category, compute RMSE.

### 4.4 Learning Curve

Plot RMSE vs training set size at: 500, 1000, 2000, 3000, 5000, 7000, 10000 rows. Report the training set size at which RMSE plateaus (stops improving by > 0.05).

### 4.5 Feature Importance

Report SHAP values for the top 10 features. Expected top features based on coffee science:

1. `roast_ordinal`
2. `water_temp_c`
3. `grind_setting`
4. `roast_x_temp` (interaction)
5. `ratio`
6. `total_time_s`

If the top features do not include at least 3 of these, investigate whether the response surface in synthetic data generation is correctly encoding coffee science.

### 4.6 Success Criteria

RMSE < 1.5 on test set. Cold-start RMSE < 2.0. No roast level has RMSE > 1.8. Learning curve shows clear improvement with more data.

---

## 5. Component 4: Recipe Optimization

### 5.1 Metrics

| Metric                            | Definition                                                      | Target         | Measurement Method                              |
| --------------------------------- | --------------------------------------------------------------- | -------------- | ----------------------------------------------- |
| Improvement over baseline         | Mean delta (optimized - baseline predicted score)               | > 0.5 points   | Run optimization on 50 test bean profiles       |
| Convergence speed (trials to 80%) | Number of trials to reach 80% of best-found score               | < 5            | Track best score per trial                      |
| Convergence speed (trials to 95%) | Number of trials to reach 95% of best-found score               | < 20           | Same tracking                                   |
| Constraint satisfaction           | Percentage of optimized recipes satisfying all soft constraints | > 85%          | Check soft constraints on all optimized recipes |
| Optimization latency (50 trials)  | Time to complete 50 optimization trials                         | < 5 seconds    | Timed measurement                               |
| Parameter reasonableness          | Expert rating of optimized recipes                              | > 7/10 average | 3 experts rate 20 optimized recipes             |

### 5.2 Test Set

50 bean profiles (diverse: 10 per roast level, mixed origins and processes). For each, run optimization with a cold-start user profile.

### 5.3 Measurement Protocol

1. For each test bean profile, retrieve the baseline recipe (top-1 from retrieval).
2. Predict baseline score using the taste predictor.
3. Run optimization (100 trials).
4. Predict optimized score.
5. Compute improvement = optimized - baseline.
6. Track best score per trial for convergence analysis.

### 5.4 Baseline Comparison

| Method                | Description                         | Expected Improvement                                          |
| --------------------- | ----------------------------------- | ------------------------------------------------------------- |
| Random initialization | No warm start from retrieved recipe | Lower convergence speed                                       |
| Grid search           | Exhaustive grid over 7 parameters   | Impractical (26.7M combinations), used as theoretical optimum |
| TPE (proposed)        | Warm-started from best retrieval    | Target: > 0.5 point improvement                               |

### 5.5 Success Criteria

Mean improvement > 0.5 points. Convergence to 80% optimal in < 5 trials. Constraint satisfaction > 85%. No optimized recipe has a predicted score below the baseline.

---

## 6. Component 5: Personalization (Bean-Aware to Full Hybrid)

### 6.1 Metrics

| Metric                    | Definition                                         | Target                     | Measurement Method             |
| ------------------------- | -------------------------------------------------- | -------------------------- | ------------------------------ |
| Bean-aware RMSE (0 brews) | RMSE for users with 0 brews                        | < 2.0                      | Global model only              |
| Directional RMSE          | RMSE for users with 1-4 brews                      | < 1.8                      | Global + linear bias           |
| Content-based RMSE        | RMSE for users with 5-9 brews                      | < 1.5                      | LightGBM with user features    |
| Full hybrid RMSE          | RMSE for users with 10+ brews                      | < 1.3                      | Full model + collaborative     |
| Improvement per phase     | RMSE reduction from previous phase                 | > 10% per phase transition | Compare adjacent phases        |
| Bias calibration          | Correlation between predicted and actual residuals | > 0.5                      | Plot predicted vs actual error |

### 6.2 Test Set

Simulate 50 virtual users at each personalization phase using the synthetic data generator. For each user:

1. Train global model on all data excluding this user.
2. Simulate sequential brew feedback (1 brew at a time).
3. After each brew, update personalization state and re-predict next brew.
4. Track RMSE as a function of number of brews.

### 6.3 Measurement Protocol

1. Generate 200 virtual users with varied taste profiles.
2. For each user, generate 20 brews sequentially.
3. After each brew k (k = 1 to 20), compute:
   - Personalization phase
   - RMSE on the next brew (leave-one-out)
4. Average RMSE across all users at each phase.

### 6.4 Personalization Curve

Plot RMSE vs number of brews (0, 1, 2, ..., 20). Expected shape:

```
RMSE
  ^
2.0|*
   | *
   |  *
1.5|   * * *
   |        * * * *
1.3|             * * * * * *
   +-------------------------> Number of brews
   0  1  2  5  10     20
```

The curve should show clear phase transitions at brew 1 (bean-aware -> directional), brew 5 (directional -> content), and brew 10 (content -> hybrid).

### 6.5 Collaborative Filtering Evaluation (Simulated)

Since the demo is single-user, collaborative filtering is evaluated on the synthetic user population:

1. Hold out 20% of each user's brews as test.
2. Find top-5 similar users based on the remaining 80%.
3. Predict test brews using collaborative signals from similar users.
4. Report collaborative RMSE vs content-only RMSE.

### 6.6 Success Criteria

- Personalized predictions should show improvement over global predictions as brew count increases. Target: personalized RMSE < global RMSE for users with 10+ brews.
- Phase transitions produce > 10% RMSE reduction.
- Full hybrid RMSE < 1.3.
- Personalization curve shows clear improvement pattern.

---

## 7. Overall System Evaluation

### 7.1 End-to-End Pipeline Test

| Test                    | Description                                                                     | Pass Criterion                                      |
| ----------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------- |
| Full pipeline execution | Bean input -> extraction -> retrieval -> prediction -> optimization -> feedback | Completes without error on 20 diverse bean profiles |
| Feedback loop           | Submit 10 rounds of feedback for a single user; verify predictions improve      | RMSE decreases over 10 rounds                       |
| Demo mode               | Load Alex's profile; browse all pages; submit feedback                          | No errors; all metrics display correctly            |
| Edge case coverage      | Test with "unknown" bean fields, extreme parameters, empty history              | Graceful degradation, no crashes                    |

### 7.2 Demonstration Scorecard

For the course submission, the evaluation dashboard presents:

| Component        | Metric         | Result | Target    | Status |
| ---------------- | -------------- | ------ | --------- | ------ |
| Bean Extraction  | Field accuracy | --     | > 90%     | --     |
| Recipe Retrieval | Precision@3    | --     | > 0.80    | --     |
| Taste Prediction | RMSE           | --     | < 1.5     | --     |
| Optimization     | Improvement    | --     | > 0.5 pts | --     |
| Personalization  | Phase 4 RMSE   | --     | < 1.3     | --     |

All metrics are computed and populated at evaluation time.

---

## 8. Evaluation Artifacts

| Artifact               | Path                                 | Format | Purpose                                |
| ---------------------- | ------------------------------------ | ------ | -------------------------------------- |
| Evaluation results     | `models/evaluation_results.json`     | JSON   | Machine-readable metrics for dashboard |
| Test predictions       | `models/test_predictions.csv`        | CSV    | Predicted vs actual for all test rows  |
| Feature importance     | `models/feature_importance.json`     | JSON   | SHAP values for top features           |
| Convergence curves     | `models/convergence_curves.json`     | JSON   | Score per trial for optimization       |
| Personalization curves | `models/personalization_curves.json` | JSON   | RMSE vs brew count                     |
| Learning curves        | `models/learning_curves.json`        | JSON   | RMSE vs training set size              |

---

## 9. Evaluation Execution Protocol

1. Generate synthetic data (`data/synthetic/`).
2. Train taste prediction model -> `models/taste_predictor.joblib`.
3. Compute bean extraction metrics on test descriptions.
4. Compute retrieval metrics on test queries.
5. Compute prediction metrics on test set.
6. Compute optimization metrics on test bean profiles.
7. Compute personalization metrics on virtual users.
8. Save all results to `models/evaluation_results.json`.
9. Dashboard reads this file and displays metrics.

---

## 10. Dependencies

| Dependency                     | Purpose                                           |
| ------------------------------ | ------------------------------------------------- |
| `specs/bean-extraction.md`     | Bean extraction evaluation method                 |
| `specs/recipe-retrieval.md`    | Retrieval metrics and test set definition         |
| `specs/taste-prediction.md`    | Prediction metrics and test protocol              |
| `specs/recipe-optimization.md` | Optimization metrics and convergence definition   |
| `specs/personalization.md`     | Personalization phase metrics and user simulation |
| `specs/synthetic-data.md`      | Test data generation                              |
| `specs/user-interface.md`      | Evaluation dashboard layout                       |

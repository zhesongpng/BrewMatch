# Milestone 2: ML Pipeline Components

Estimated sessions: 4-5
Depends on: Milestone 1 complete

---

## 2.1 Bean profile extraction

- [ ] **Build bean profile extraction pipeline**
      Implements: `specs/bean-extraction.md` Sections 2-4
  - LLM structured extraction with JSON mode (prompt template from spec Section 3.1)
  - Validation layer: type checking, enum validation, range validation per Section 3.2
  - Confidence scoring: weighted sum of extracted fields per Section 3.3
  - Confidence tiers: HIGH (0.7-1.0), MEDIUM (0.4-0.69), LOW (0.0-0.39)
  - Flavor note normalization to 15-cluster taxonomy
  - Manual entry fallback (returns BeanProfile with confidence=null)
  - Output: `ExtractionResult` dataclass
  - Timeout budget: 8s LLM call, 5s retry, 13s max, progress indicator at 3s

- [ ] **Wire bean extraction to LLM provider**
  - Configure LLM model from `.env` (`LLM_MODEL`, `LLM_API_KEY`)
  - Implement retry-once logic with timeout
  - Test against 10 real roaster descriptions
  - Fallback to manual entry on timeout/invalid JSON

## 2.2 Taste prediction model

- [ ] **Build feature encoder (`encode_features`)**
      Implements: `specs/taste-prediction.md` Section 4.0
  - 45-element feature array in exact column order: 23 bean + 7 recipe + 9 user + 6 interaction
  - Bean features: origin label encoding, process one-hots, roast ordinal, cluster multi-hots, altitude mean
  - Recipe features: dose, ratio, grind, temp, bloom, total_time, pour_count
  - User features: avg_rating, rating_count, roast_pref, temp_pref, grind_pref, ratio_pref, 3 bias dimensions
  - Interaction features: roast_x_temp, grind_x_time, grind_x_temp, ratio_x_dose, roast_x_grind, cluster_count
  - Missing value defaults per Section 3.6
  - Origin label encoding mapping: top-20 countries → int, "other" for rest. Stored as part of `feature_encoder.joblib`
  - Serialize to `models/feature_encoder.joblib`

- [ ] **Train LightGBM taste prediction model**
      Implements: `specs/taste-prediction.md` Sections 4-5
  - Load synthetic data from `data/synthetic/ratings.csv`
  - Extract features using encoder
  - Train/val/test split: 70/15/15, stratified by roast level
  - LightGBM config: regression, RMSE metric, num_leaves=31, max_depth=6, lr=0.05, n_estimators=500 with early stopping (patience=50)
  - Per-user bias layer: 0 brews→0.0, 1-4→0.3\*mean_residual, 5+→full with exponential decay
  - Post-processing: clip [1, 10], round to 1 decimal, confidence interval from validation variance
  - Serialize model to `models/taste_predictor.joblib`
  - Save training metadata to `models/training_metadata.json`
  - Evaluate: target RMSE < 1.5, MAE < 1.0, R² > 0.5

## 2.3 Recipe retrieval (RAG)

- [ ] **Build recipe indexing pipeline**
      Implements: `specs/recipe-retrieval.md` Sections 2-4
  - Embedding model: `all-MiniLM-L6-v2` (384 dims, L2-normalized)
  - Composite text construction from recipe metadata + parameters + instructions
  - ChromaDB setup: `data/chroma/`, collection `brewmatch_recipes`, cosine similarity
  - BM25 tokenization: lowercase, remove stopwords, stem
  - Curation filter: method check, parameter validation, source normalization
  - Ingestion script: `scripts/index_recipes.py`
  - Index all 50-80 recipes
  - Query result caching: cache embedding queries for same bean profile (avoid re-embedding on navigation)

- [ ] **Build hybrid retrieval + reranking pipeline**
      Implements: `specs/recipe-retrieval.md` Sections 5-6
  - Stage 1: Dense retrieval (ChromaDB top-20) + sparse retrieval (BM25 top-20) + RRF fusion (dense=0.6, sparse=0.4, k=60)
  - Stage 2: Hard filtering (method match, roast compatibility, parameter range)
  - Stage 3: Reranking with 5 signals (semantic 0.35, cluster overlap 0.25, process match 0.15, origin match 0.10, constraint fit 0.15)
  - Stage 4: Diversity selection (alpha=0.7, min param distance constraint)
  - Fallback tiers: broad matches (same method), general recommendations (all methods), single result
  - Output: `RetrievalResult` with 1-3 `RankedRecipe` objects, match_reasons per recipe
  - Query embedding construction from bean profile

## 2.4 Recipe optimizer

- [ ] **Build Optuna recipe optimizer**
      Implements: `specs/recipe-optimization.md` Sections 2-5
  - 4 decision variables: grind_setting (1-10), water_temp_c (85-100, step 0.5), dose_g (12-22, step 0.5), ratio (14-18, step 0.25)
  - Fixed from retrieved recipe: bloom_time_s, total_time_s, pour_count
  - Hard constraints: water_total_g in [180, 400], all params in valid ranges
  - Soft constraints with penalties: light roast temp >= 92C, dark roast temp <= 94C
  - Objective: maximize predicted taste score minus penalty
  - Optuna config: TPESampler, seed=42, n_trials=50, n_startup_trials=10
  - Warm start: initialize from best-matching recipe (trial 0 = base recipe, trials 1-9 = +/-20% perturbation)
  - Early stopping: stop if no improvement > 0.05 over 15 consecutive trials
  - Output: `OptimizationResult` with optimized params, predicted score, baseline score, improvement, parameter changes
  - Fallback: return baseline recipe if optimization fails
  - Performance target: 50 trials < 5 seconds

## 2.5 Personalization engine

- [ ] **Build personalization module (4 phases)**
      Implements: `specs/personalization.md` Sections 2-7
  - Phase detection: `get_personalization_phase(total_brews)`
  - Bean-aware phase: construct pseudo-bean from quiz, retrieve recipes
  - Directional phase (1-4 brews): flag processing → bias delta, linear user bias with 0.3 damping, parameter adjustment hints
  - Content-based phase (5-9 brews): full user features, exponential-decay bias, learned preference extraction (temp range, ratio range, bias dimensions)
  - Full hybrid phase (10+ brews): collaborative filtering with cosine similarity on 15-dim cluster vectors, score blending (collab weight 0-0.3)
  - Feedback validation: thumbs_up required, score optional 1-10, flags from 5-flag set
  - Bias recomputation after every feedback submission
  - User bias store persistence: save/load `models/user_biases.json` on app startup and after each feedback
  - Output: `PersonalizationState` with phase, bias, preferences, similar_users_count, confidence, next_milestone
  - Confidence model per phase

- [ ] **Wire collaborative filtering to synthetic user population**
      Implements: `specs/personalization.md` Section 6, `specs/synthetic-data.md` Section 11
  - Load 200 synthetic users from `data/synthetic/users.json` into SQLite
  - `find_similar_users()` queries SQLite, computes cosine similarity
  - Cap collaborative weight at 0.3
  - Fallback to content-based only when no similar users found

## 2.6 Diagnosis engine

- [ ] **Build diagnosis engine (Perturb-and-Score)**
      Implements: `specs/coffee-science.md` Section 7.2
  - Candidate generation: for each reported flag, look up primary + secondary adjustments
  - Perturbation: create recipe copy with single parameter change, predict score
  - Ranking: sort candidates by delta (predicted_score(candidate) - predicted_score(current))
  - Roast-aware weighting: multiply candidates by roast-specific bonus
  - Zero-brew branch: rule-based diagnosis using bean profile + flags (no history)
  - 3+ brew branch: pattern-based diagnosis from brew history
  - Top 2-3 candidates with predicted improvements displayed
  - Canonical perturbation delta table: temperature ±2C, grind ±1, ratio ±0.5, dose ±0.5g (per RT2-17)

## Internal dependencies

```
bean extraction ──┐
                  ├──► feature encoder ──► taste predictor ──┬──► optimizer
recipe retrieval ──┘                                          ├──► personalization
                                                              └──► diagnosis engine
```

- Bean extraction and feature encoder can run in parallel
- Taste predictor must complete before optimizer, personalization, and diagnosis engine
- Retriever can run in parallel with predictor

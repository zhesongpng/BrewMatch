# Milestone 2 Red Team Findings — ML Pipeline Implementation Audit

Date: 2026-05-10
Scope: All 7 Milestone 2 components — taste predictor, feature encoder, recipe retriever, recipe optimizer, diagnosis engine, personalization engine, bean extractor
Auditors: Security reviewer, Code reviewer, Test coverage auditor, ML correctness auditor

---

## Summary

| Severity | Count | Description                                                            |
| -------- | ----- | ---------------------------------------------------------------------- |
| CRITICAL | 8     | Runtime crashes, unsafe deserialization, spec drift breaking contracts |
| HIGH     | 12    | Data quality issues, missing error paths, private API coupling         |
| MEDIUM   | 18    | Test gaps, edge-case handling, minor spec inconsistencies              |
| LOW      | 12    | Code quality, documentation, minor improvements                        |

**Overall assessment**: 8 CRITICAL findings must be fixed before Milestone 2 can be considered production-ready. The most impactful issues are: (1) `joblib.load` unsafe deserialization allowing arbitrary code execution, (2) `user_roast_pref_encoded` key mismatch causing runtime crash when personalization is wired to predictor, (3) recipe retriever returning bare `Recipe` objects instead of spec-mandated `RetrievalResult` with `RankedRecipe`. Three components (retriever, optimizer, personalization) have spec-drift issues where implementation diverges from the spec contract.

---

## CRITICAL Findings (fix first)

### M2-C01: `joblib.load` Unsafe Deserialization in TastePredictor — FIXED

**File**: `src/taste_predictor/model.py`
**Found by**: Security reviewer
**Impact**: Arbitrary code execution if a crafted `.pkl` file replaces the model artifact

`TastePredictor.load()` calls `joblib.load(path)` directly on the persisted model file. `joblib.load` uses Python's pickle protocol, which can execute arbitrary code during deserialization. Any attacker who can replace `models/taste_predictor.pkl` (or any path passed to `load()`) achieves remote code execution.

**Fix**: Add a hash verification step. At training time, compute and store a SHA-256 of the model file alongside it. At load time, verify the hash before calling `joblib.load`. Alternatively, use a safer serialization format (e.g., save model coefficients as numpy arrays + JSON config).

---

### M2-C02: `user_roast_pref_encoded` Key Mismatch Between Personalization and Encoder — FIXED

**File**: `src/personalization/engine.py` vs `src/taste_predictor/encoder.py`
**Found by**: ML correctness auditor, Code reviewer
**Impact**: Runtime `KeyError` when personalization engine feeds user features to the predictor

`PersonalizationEngine.get_user_features()` returns a dict with key `"user_roast_pref_encoded"` but `FeatureEncoder.encode()` expects `"user_roast_pref"`. When these two components are wired together end-to-end (which is the intended architecture), every prediction call crashes with a `KeyError`.

**Fix**: Align the key name. The encoder should be the authority — change `get_user_features()` to return `"user_roast_pref"` instead of `"user_roast_pref_encoded"`.

---

### M2-C03: Recipe Retriever Returns Bare `Recipe` Objects Instead of `RetrievalResult` — FIXED

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Code reviewer
**Impact**: Breaks the spec contract; downstream consumers expecting `RetrievalResult` with `RankedRecipe` get wrong type

Spec (`specs/recipe-retrieval.md` Section 4) mandates that the retriever returns a `RetrievalResult` containing a list of `RankedRecipe` objects (with score, rank, and relevance metadata). The implementation returns `list[Recipe]` — stripping all ranking metadata. Any consumer that relies on score-based filtering, relevance display, or rank-based UI ordering silently breaks.

**Fix**: Define `RankedRecipe` and `RetrievalResult` dataclasses. Update `retrieve()` to return `RetrievalResult` with scored, ranked recipes.

---

### M2-C04: Recipe Retriever Uses Wrong Reranking Signals (Spec Drift) — FIXED

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Code reviewer
**Impact**: Ranking quality diverges from spec; retrieval produces suboptimal recommendations

Spec (`specs/recipe-retrieval.md` Section 3.3) defines 5 reranking signals: bean_match, method_match, difficulty_match, flavor_affinity, popularity. The implementation uses different signals (embedding_similarity, method_exact_match, etc.). The spec's signals are domain-informed and were designed for coffee brewing; the implementation's signals are generic IR metrics that don't capture coffee-specific relevance.

**Fix**: Reimplement the 5-signal reranking per spec Section 3.3.

---

### M2-C05: Recipe Retriever Uses Wrong Diversity Algorithm (Spec Drift) — FIXED

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Code reviewer
**Impact**: Results cluster around one method/bean profile instead of providing diverse recommendations

Spec calls for MMR-style diversity using parameter distance (ensuring diverse grind settings, temperatures, ratios). The implementation uses a per-method cap (max N recipes per brew method). This produces diversity by method but not by parameter space — all V60 recipes could have nearly identical grind/temp/dose.

**Fix**: Implement parameter-distance-based diversity selection per spec Section 3.4.

---

### M2-C06: Recipe Optimizer Accesses Private `_encoder` Attribute of Predictor — FIXED

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Code reviewer
**Impact**: Breaks if TastePredictor internal structure changes; coupling to implementation detail

The optimizer calls `self._predictor._encoder.encode(...)` to produce feature vectors for the objective function. The underscore prefix marks `_encoder` as a private implementation detail. Refactoring TastePredictor (e.g., renaming or removing `_encoder`) silently breaks the optimizer with an `AttributeError`.

**Fix**: Add a public `encode_features(bean_profile, recipe, user_features)` method to `TastePredictor` that delegates to the encoder. The optimizer calls the public API.

---

### M2-C07: LightGBM Import Guard Catches Only `OSError`, Misses `ImportError` — FIXED

**File**: `src/taste_predictor/model.py`
**Found by**: Code reviewer, ML correctness auditor
**Impact**: Crash on systems where LightGBM is not installed (raises `ImportError`, not `OSError`)

The try/except fallback from LightGBM to sklearn catches `except OSError` but LightGBM raises `ImportError` when the package is not installed. On a fresh environment without `lightgbm`, the import fails with an unhandled `ImportError` instead of gracefully falling back.

**Fix**: Change `except OSError` to `except (ImportError, OSError)`.

---

### M2-C08: User Features Never Populated During Training (Indices 30-38 Always Zero) — ACKNOWLEDGED

**File**: `scripts/train_model.py`, `src/taste_predictor/encoder.py`
**Found by**: ML correctness auditor
**Impact**: Model learns to ignore user features; personalization layer has no training signal

The 45-element feature vector has user features at indices 30-38 (9 features including roast preference, brew count, avg score, etc.). The training script generates features from raw CSV which has no user columns — these 9 indices are always encoded as zeros across all 2,895 training rows. The trained model has zero gradient signal for user features, making the personalization bias layer a dead path.

**Fix**: Either (a) generate synthetic user features in the training data (per `specs/synthetic-data.md` Section 11 — 200 synthetic users with assigned brews) or (b) acknowledge this is a synthetic-data limitation and document that real user data will be needed to train personalization features.

---

## HIGH Findings (fix next)

### M2-H01: Directional Biases Accumulate Without Clamping in Personalization Engine — FIXED

**File**: `src/personalization/engine.py`
**Found by**: Security reviewer, Code reviewer, ML correctness auditor (3-way duplicate)
**Impact**: Bias values can exceed [-1, 1] range, causing numerical instability in downstream predictions

The personalization engine accumulates directional biases (acidity_bias, body_bias, etc.) additively with each brew feedback. Multiple brews with the same flag (e.g., 5 consecutive "too_sour" reports) push biases far outside the intended [-1, 1] range. No clamping is applied.

**Fix**: Clamp all bias values to [-1, 1] after each update. The spec's damping factors are designed for this range.

---

### M2-H02: Altitude Encoding Train-Serving Skew — FIXED

**File**: `scripts/train_model.py` vs `src/taste_predictor/encoder.py`
**Found by**: ML correctness auditor
**Impact**: Feature distribution mismatch between training and inference degrades prediction accuracy

Training data encodes `altitude_min_m` directly as a single altitude feature. Inference code computes `(altitude_min_m + altitude_max_m) / 2` (mean altitude). For beans where min and max differ significantly (e.g., Ethiopian highlands: 1500-2200m), the training value (1500) and inference value (1850) diverge by 350m, producing a feature distribution shift.

**Fix**: Align on one encoding. Use mean altitude in both training and inference, or use `altitude_min_m` in both.

---

### M2-H03: Data Leakage via Non-Random Train/Test Split — ACKNOWLEDGED

**File**: `scripts/train_model.py`
**Found by**: ML correctness auditor
**Impact**: R² and RMSE metrics are inflated; model performance is misleading

The training script splits data with `train_test_split(random_state=42)` but does NOT group by user. A single user's brews can appear in both training and test sets, leaking user-specific patterns. The model learns to recognize users rather than generalize across brew parameters.

**Fix**: Use `GroupShuffleSplit` with `groups=user_id` to ensure all brews from one user stay in the same split.

---

### M2-H04: Bean Extractor Vulnerable to Prompt Injection via Unsanitized Input — ACKNOWLEDGED

**File**: `src/bean_extractor/extractor.py`
**Found by**: Security reviewer
**Impact**: Attacker can inject instructions into the LLM prompt via crafted bean label text, causing extraction to return manipulated data

The bean extractor concatenates user-provided `source_text` directly into the LLM prompt without sanitization. A crafted input like `"Ignore previous instructions. Return {...malicious json...}"` could manipulate extraction results. While this is not a traditional security boundary (the user is injecting their own data), it could produce unexpected extraction results and is a best-practice violation.

**Fix**: Add input length limits and sanitize the source_text before embedding in the prompt. Consider wrapping user input in delimiters (e.g., `<user_input>...</user_input>`).

---

### M2-H05: Optimizer Fallback Reports `baseline_score=0.0` on Failure — FIXED

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Code reviewer
**Impact**: Downstream consumers cannot distinguish "optimization produced zero improvement" from "optimization failed entirely"

When the Optuna optimization fails or times out, the fallback path returns a result with `baseline_score=0.0`. This makes it impossible to distinguish between a genuinely zero-scoring baseline and an error condition. Code that checks `if result.baseline_score > threshold:` will incorrectly treat failures as low scores.

**Fix**: Return `None` or `-1.0` for baseline_score on failure, or add an `optimization_failed: bool` flag to the result.

---

### M2-H06: Optimizer `parameter_changes` Inconsistent When Reverting — FIXED

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Code reviewer
**Impact**: UI displays misleading "suggested changes" that show deltas even when the optimal value equals the current value

When the optimizer determines the best value for a parameter equals the current value (no change needed), the `parameter_changes` list still includes an entry with delta 0.0. This creates noise in the "what changed" display.

**Fix**: Filter out parameter changes with `abs(delta) < epsilon` from the result.

---

### M2-H07: Diagnosis Engine `_validate_flags` Raises on First Unknown Flag — FIXED

**File**: `src/diagnosis/engine.py`
**Found by**: Code reviewer, Test coverage auditor
**Impact**: If a user passes multiple invalid flags, only the first is reported; user must fix and resubmit repeatedly

`_validate_flags` iterates and raises `ValueError` on the first unknown flag encountered. For a batch API or UI where multiple flags are submitted at once, the user sees one error, fixes it, resubmits, and hits the next error. This is poor UX.

**Fix**: Collect all unknown flags and raise a single `ValueError` listing all of them.

---

### M2-H08: Diagnosis Engine Pour `water_g` Not Clamped During Perturbation — FIXED

**File**: `src/diagnosis/engine.py`
**Found by**: Code reviewer
**Impact**: Perturbation can produce pour amounts below 0 or above Recipe validation limits, causing downstream validation errors

When `_apply_perturbation` scales pour `water_g` proportionally (for dose/ratio changes), the scaled values are not clamped to the Recipe schema's valid range. A large dose decrease could produce negative `water_g` values.

**Fix**: Clamp each pour's `water_g` to `[0, recipe.water_total_g]` after scaling.

---

### M2-H09: `_best_iteration` Not Persisted in Model Metadata

**File**: `src/taste_predictor/model.py`
**Found by**: ML correctness auditor
**Impact**: Model loads without early-stopping information, potentially using all estimators instead of the optimal iteration count

When LightGBM/sklearn GBM uses early stopping, `_best_iteration` records the optimal number of boosting rounds. This value is not saved in the model metadata file. On load, the model uses all estimators rather than stopping at the best iteration, potentially overfitting.

**Fix**: Include `_best_iteration` in the metadata dict saved alongside the model.

---

### M2-H10: Recipe Retriever ChromaDB Dense Retrieval Has No Similarity Threshold

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Code reviewer
**Impact**: Retrieval returns results with very low relevance, diluting recommendation quality

The dense retrieval step queries ChromaDB with `n_results=k` but no minimum similarity threshold. A query for an unusual bean profile could return recipes with near-zero embedding similarity. These low-relevance results would still be ranked and presented to the user.

**Fix**: Add a minimum similarity threshold (e.g., cosine distance < 1.5) and fall back to constraint relaxation when too few results pass the threshold.

---

### M2-H11: No Input Length Limit on Bean Extractor `source_text`

**File**: `src/bean_extractor/extractor.py`
**Found by**: Security reviewer
**Impact**: Extremely long input text could exceed LLM context window or cause excessive token costs

The bean extractor accepts `source_text` of any length and sends it to the LLM. There is no validation of input length. A user pasting an entire coffee bag's text (or accidentally pasting a large document) could trigger a costly LLM call or context overflow.

**Fix**: Add a maximum input length (e.g., 2000 characters) and raise `ValueError` if exceeded.

---

### M2-H12: Predict Batch Has No Untrained Model Guard — FIXED

**File**: `src/taste_predictor/model.py`
**Found by**: Test coverage auditor
**Impact**: Calling `predict_batch` on an untrained model produces unclear errors or garbage predictions

`predict_batch` does not check whether the model has been trained/loaded before attempting predictions. An untrained model would raise an `AttributeError` or produce meaningless predictions depending on the sklearn internal state.

**Fix**: Add a `_is_trained` flag check at the start of `predict` and `predict_batch`, raising `RuntimeError("Model not trained")` if false.

---

## MEDIUM Findings

### M2-M01: Untested Retry Logic in Bean Extractor — FIXED

**File**: `src/bean_extractor/extractor.py`
**Found by**: Test coverage auditor

The extractor has retry logic (retry once on LLM failure) but no test exercises the retry path. A regression in retry handling would go undetected.

---

### M2-M02: Untested ValueError on Missing API Key in Bean Extractor — FIXED

**File**: `src/bean_extractor/extractor.py`
**Found by**: Test coverage auditor

The extractor validates the API key at initialization, raising `ValueError` if missing. This error path has no direct test.

---

### M2-M03: Diagnosis Engine Flag Validation Not Directly Tested — FIXED

**File**: `src/diagnosis/engine.py`
**Found by**: Test coverage auditor

While `diagnose()` is tested with invalid flags, `_validate_flags()` has no isolated unit tests covering edge cases (empty list, all invalid, mixed valid/invalid).

---

### M2-M04: Encoder Missing-Field Defaults Not Tested — FIXED

**File**: `src/taste_predictor/encoder.py`
**Found by**: Test coverage auditor

The encoder has default values for missing fields but no test verifies these defaults are actually applied when fields are absent.

---

### M2-M05: Optimizer Objective Function Not Tested in Isolation — FIXED

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Test coverage auditor

The Optuna objective function is only tested through the full `optimize()` call. Edge cases in the objective (boundary values, identical parameters) are not exercised.

---

### M2-M06: Personalization Phase Transitions Not Tested — FIXED

**File**: `src/personalization/engine.py`
**Found by**: Test coverage auditor

The 4-phase personalization system transitions between phases based on brew count, but no test verifies the correct phase is selected at each boundary (0, 1, 5, 10 brews).

---

### M2-M07: Personalization Content-Based Filtering Not Tested with Real Clusters — FIXED

**File**: `src/personalization/engine.py`
**Found by**: Test coverage auditor

The content-based filtering phase (Phase 3, 5-9 brews) uses cluster similarity but tests use minimal fixtures that don't exercise real cluster-based scoring.

---

### M2-M08: Retriever Sparse Retrieval (TF-IDF) Not Tested — FIXED

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Test coverage auditor

The hybrid retrieval uses both dense (ChromaDB) and sparse (TF-IDF) signals, but tests only exercise the dense path. Sparse retrieval scoring and fusion are untested.

---

### M2-M09: Retriever Constraint Relaxation Stages Not Tested — FIXED

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Test coverage auditor

The spec defines 4 relaxation stages when initial retrieval returns too few results. Tests don't exercise the relaxation cascade.

---

### M2-M10: Optimizer Parameter Bounds Not Tested at Edge Values — FIXED

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Test coverage auditor

No test verifies the optimizer respects parameter bounds when starting near edges (e.g., grind_setting=1.0, water_temp_c=100.0).

---

### M2-M11: TastePredictor Save/Load Round-Trip Not Tested with Bias Layer — FIXED

**File**: `src/taste_predictor/model.py`
**Found by**: Test coverage auditor

Model save/load is tested for the base model but not with an active per-user bias layer. Bias state could be lost during persistence.

---

### M2-M12: Diagnosis Suggestion Confidence Scores Not Validated — FIXED

**File**: `src/diagnosis/engine.py`
**Found by**: Code reviewer

The `_compute_confidence` function uses a sigmoid-like formula but no test verifies the output range is strictly [0, 1] or that the claimed breakpoints (delta=0.5 → 0.62, delta=1.0 → 0.80) are accurate.

---

### M2-M13: No Logging in ML Pipeline Components — FIXED

**File**: All ML components
**Found by**: Code reviewer

None of the 7 ML components emit structured logs. Operations like model training, prediction, optimization, and retrieval have zero observability. Production debugging would require code changes.

---

### M2-M14: Personalization Engine Doesn't Handle Negative Brew Counts — FIXED

**File**: `src/personalization/engine.py`
**Found by**: Code reviewer

The `get_phase()` method accepts any integer but the spec defines phases starting from 0. Negative brew counts are nonsensical but not validated.

---

### M2-M15: Diagnosis Explanation Templates Don't Vary by Magnitude — FIXED

**File**: `src/diagnosis/engine.py`
**Found by**: Code reviewer

All explanations are static strings regardless of the magnitude of the suggested change. "Increase temperature by 0.5C" and "Increase temperature by 3C" produce the same explanation text.

---

### M2-M16: Retriever Embedding Cache Not Implemented — FIXED

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Code reviewer

The spec mentions embedding caching for repeated queries, but the implementation recomputes embeddings on every call. For a demo with repeated queries, this adds unnecessary latency.

---

### M2-M17: Optimizer Study Object Not Persisted — FIXED

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: ML correctness auditor

The Optuna study is created fresh on each call. Historical optimization runs are not stored, preventing the optimizer from learning from past optimizations for the same user/bean.

---

### M2-M18: Bean Extractor LLM Response Parsing Fragile — FIXED

**File**: `src/bean_extractor/extractor.py`
**Found by**: Code reviewer

The extractor parses LLM JSON output with basic string manipulation. LLM output variations (markdown code fences, extra whitespace, trailing commas) could cause parse failures.

---

## LOW Findings

### M2-L01: Model Training Script Doesn't Log Feature Importance

**File**: `scripts/train_model.py`
**Found by**: ML correctness auditor

The trained model's feature importances are not logged or saved. Without this, it's impossible to audit which features drive predictions.

---

### M2-L02: Encoder Doesn't Validate Bean Origin Against Known Origins

**File**: `src/taste_predictor/encoder.py`
**Found by**: Code reviewer

The encoder accepts any string for bean origin and encodes it. Unknown origins get a default encoding, but no warning is emitted.

---

### M2-L03: Optimizer Doesn't Respect Pour Schedule Immutability

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Code reviewer

The spec says pour schedule should be fixed from the retrieved recipe, but the optimizer doesn't explicitly validate that optimized recipes maintain the same pour structure.

---

### M2-L04: Personalization Engine Uses String Constants for Phase Names

**File**: `src/personalization/engine.py`
**Found by**: Code reviewer

Phase names are string literals ("bean_aware", "directional", etc.) rather than an enum. Typos would silently produce wrong phase selection.

---

### M2-L05: Diagnosis Engine Doesn't Handle Simultaneous Opposing Flags

**File**: `src/diagnosis/engine.py`
**Found by**: Code reviewer

A user reporting both "too_sour" (under-extraction) and "too_bitter" (over-extraction) simultaneously is contradictory. The engine processes both without flagging the conflict.

---

### M2-L06: Retriever Doesn't Log Retrieval Latency

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Test coverage auditor

No timing information is captured for the multi-stage retrieval pipeline, making performance optimization impossible without code changes.

---

### M2-L07: Model Metadata Doesn't Include Training Data Hash

**File**: `src/taste_predictor/model.py`
**Found by**: ML correctness auditor

The saved model metadata doesn't record a hash of the training data, making it impossible to verify which data produced which model.

---

### M2-L08: No Type Hints on Several Internal Methods

**File**: Multiple files
**Found by**: Code reviewer

Several internal methods (e.g., `_compute_confidence`, `_find_best_perturbation`) lack return type hints, reducing IDE support and type safety.

---

### M2-L09: Bean Extractor Doesn't Handle Multi-Language Labels

**File**: `src/bean_extractor/extractor.py`
**Found by**: Code reviewer

Coffee bags from international roasters may have labels in non-English languages. The extractor's prompt is English-only and may produce poor results for non-English text.

---

### M2-L10: Optimizer Default Trial Count Not Configurable

**File**: `src/recipe_optimizer/optimizer.py`
**Found by**: Test coverage auditor

The number of Optuna trials is hardcoded (100). For quick demos, users may want fewer trials; for production, more. No configuration knob exists.

---

### M2-L11: Retriever Index Building Not Tested for Idempotency

**File**: `src/recipe_retriever/retriever.py`
**Found by**: Test coverage auditor

Building the ChromaDB index twice (e.g., on app restart) could produce duplicate embeddings. No test verifies idempotent index construction.

---

### M2-L12: No Integration Test Across Full Pipeline (Extract → Retrieve → Predict → Optimize) — FIXED

**File**: `tests/`
**Found by**: Test coverage auditor

Each component has unit tests, but no test exercises the end-to-end pipeline from bean extraction through recipe optimization. Handoff issues (like M2-C02) are invisible to unit tests.

---

## Cross-Component Issues (Multi-Reviewer Findings)

These findings were independently identified by multiple reviewers, confirming severity:

| Issue                              | Security | Code | Test | ML  | Deduplicated as |
| ---------------------------------- | -------- | ---- | ---- | --- | --------------- |
| Bias clamping overflow             | YES      | YES  | —    | YES | M2-H01          |
| `user_roast_pref` key mismatch     | —        | YES  | —    | YES | M2-C02          |
| LightGBM import guard              | —        | YES  | —    | YES | M2-C07          |
| Flag validation UX                 | —        | YES  | YES  | —   | M2-H07          |
| User features zero during training | —        | —    | —    | YES | M2-C08          |
| No pipeline integration test       | —        | —    | YES  | —   | M2-L12          |

---

## Recommended Fix Order

### Phase 1: Security + Runtime Crash Fixes (do immediately)

1. ~~**M2-C01** — `joblib.load` unsafe deserialization → add hash verification~~ FIXED
2. ~~**M2-C02** — `user_roast_pref` key mismatch → align key names~~ FIXED
3. ~~**M2-C07** — LightGBM import guard → catch `(ImportError, OSError)`~~ FIXED

### Phase 2: Spec Drift Fixes (do next)

4. ~~**M2-C03** — Retriever returns `list[Recipe]` → return `RetrievalResult`~~ FIXED
5. ~~**M2-C04** — Retriever wrong reranking signals → implement spec signals~~ FIXED
6. ~~**M2-C05** — Retriever wrong diversity algorithm → parameter-distance diversity~~ FIXED
7. ~~**M2-C06** — Optimizer accesses private `_encoder` → add public API~~ FIXED

### Phase 3: Data Quality + Correctness (do before evaluation)

8. **M2-C08** — User features always zero in training → ACKNOWLEDGED (synthetic data limitation)
9. ~~**M2-H01** — Bias clamping → add [-1, 1] clamp~~ FIXED
10. ~~**M2-H02** — Altitude train-serving skew → align encoding~~ FIXED
11. **M2-H03** — Data leakage in train/test split → ACKNOWLEDGED (synthetic data, no real users to group by)

### Phase 4: Error Handling + Edge Cases

12. **M2-H04** — Prompt injection in extractor → ACKNOWLEDGED (low-risk, user inputs own data)
13. ~~**M2-H05** — Optimizer fallback score → use None on failure~~ FIXED
14. ~~**M2-H06** — Optimizer parameter_changes → filter zero-delta entries~~ FIXED
15. ~~**M2-H07** — Flag validation → collect all invalid flags~~ FIXED
16. ~~**M2-H08** — Pour water_g clamping → add bounds check~~ FIXED
17. ~~**M2-H12** — Untrained model guard → add `_is_trained` check~~ FIXED

### Phase 5: Test Gaps (fill during fix cycles)

- ~~M2-M01 through M2-M18 — add missing test coverage~~ FIXED
- ~~M2-L12 — end-to-end pipeline integration test (catches handoff issues like M2-C02)~~ FIXED

---

## Resolved Findings

Findings that have been fixed or formally acknowledged during the Milestone 2 red team remediation cycle.

### Fixed (code changes applied, tests passing)

| ID     | Summary                                                    | Resolution                                                                                                              |
| ------ | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| M2-C01 | `joblib.load` unsafe deserialization                       | SHA-256 hash verification on model load                                                                                 |
| M2-C02 | `user_roast_pref` key mismatch                             | Key name aligned to `user_roast_pref`                                                                                   |
| M2-C03 | Retriever returns bare `list[Recipe]`                      | `RetrievalResult` + `RankedRecipe` dataclasses implemented                                                              |
| M2-C04 | Retriever wrong reranking signals                          | 5 spec-aligned signals (semantic_similarity, bean_profile_match, process_match, origin_match, parameter_constraint_fit) |
| M2-C05 | Retriever wrong diversity algorithm                        | MMR-style parameter-distance diversity with DIVERSITY_ALPHA=0.7                                                         |
| M2-C06 | Optimizer accesses private `_encoder`                      | Public `encode_features` method added to TastePredictor                                                                 |
| M2-C07 | LightGBM import guard misses `ImportError`                 | Catches `(ImportError, OSError)`                                                                                        |
| M2-H01 | Directional biases accumulate without clamping             | Biases clamped to [-1, 1] in `_process_directional_flags`                                                               |
| M2-H02 | Altitude encoding train-serving skew                       | Encoder uses `altitude_min_m` directly, matching training data                                                          |
| M2-H05 | Optimizer fallback reports `baseline_score=0.0`            | Fallback returns `baseline_score=None` and empty `parameter_changes`                                                    |
| M2-H06 | Optimizer `parameter_changes` includes zero-delta entries  | Zero-delta entries filtered; only actual changes reported                                                               |
| M2-H07 | Flag validation raises on first unknown flag               | Collects all unknown flags before raising single `ValueError`                                                           |
| M2-H08 | Pour `water_g` not clamped during perturbation             | Pour volumes clamped to [10.0, 200.0] after scaling                                                                     |
| M2-H12 | Predict batch has no untrained model guard                 | `is_trained` guard already in place; both `predict` and `predict_batch` raise `RuntimeError` if untrained               |
| M2-M01 | Untested retry logic in bean extractor                     | Added retry-path tests with mocked LLM failures                                                                         |
| M2-M02 | Untested ValueError on missing API key                     | Added direct test for `ValueError` on missing key                                                                       |
| M2-M03 | Diagnosis flag validation not directly tested              | Added isolated unit tests for `_validate_flags` edge cases                                                              |
| M2-M04 | Encoder missing-field defaults not tested                  | Added tests verifying defaults applied when fields absent                                                               |
| M2-M05 | Optimizer objective function not tested in isolation       | Added `TestObjectiveFunctionIsolation` — 4 tests for finite output, hard/soft constraints                               |
| M2-M06 | Personalization phase transitions not tested               | Added 17 parametrized boundary tests covering all phase transitions                                                     |
| M2-M07 | Personalization content-based filtering not tested         | Added `TestContentBasedFilteringWithClusters` — 4 tests for cluster-based scoring                                       |
| M2-M08 | Retriever sparse retrieval (TF-IDF) not tested             | Added `TestSparseRetrieval` — 7 tests for BM25 scoring, hybrid fusion, empty queries                                    |
| M2-M09 | Retriever constraint relaxation stages not tested          | Added `TestConstraintRelaxation` — 6 tests for roast/method relaxation, fallback behavior                               |
| M2-M10 | Optimizer parameter bounds not tested at edge values       | Added `TestParameterBoundsAtEdges` — 6 tests at grind/temp/dose boundaries                                              |
| M2-M11 | TastePredictor save/load not tested with bias layer        | Added round-trip tests with active per-user bias                                                                        |
| M2-M12 | Diagnosis confidence scores not validated                  | Added tests verifying output range [0, 1] and breakpoint accuracy                                                       |
| M2-M13 | No logging in ML pipeline components                       | Added `import logging` + INFO log lines to all 7 ML components                                                          |
| M2-M14 | Personalization engine doesn't handle negative brew counts | `get_phase_for_count()` clamps negative to 0 with `logger.warning()`                                                    |
| M2-M15 | Diagnosis explanations don't vary by magnitude             | `_generate_explanation` appends "gradually"/"small adjustment" context by delta magnitude                               |
| M2-M16 | Retriever embedding cache not implemented                  | `_get_query_embedding()` with hash-keyed LRU cache (maxsize=128)                                                        |
| M2-M17 | Optimizer study object not persisted                       | `study_path` parameter; loads/saves via `joblib.dump/load`                                                              |
| M2-M18 | Bean extractor LLM response parsing fragile                | `_parse_llm_json()` strips markdown fences, whitespace, trailing commas; clear `ValueError` on failure                  |
| M2-L12 | No integration test across full pipeline                   | 4 `@pytest.mark.regression` tests exercising bean→retrieve→predict→optimize→diagnose end-to-end                         |

### Acknowledged (deferred with documented rationale)

| ID     | Summary                                      | Rationale                                                                                                 |
| ------ | -------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| M2-C08 | User features always zero during training    | Synthetic data limitation. Training docstring updated. Personalization phases 2-4 require real user data. |
| M2-H03 | Data leakage via non-random train/test split | No real user data to group by. Revisit when real user data is available.                                  |
| M2-H04 | Bean extractor prompt injection              | Low-risk — user inputs own bean data. Revisit if extractor is exposed to third-party input.               |

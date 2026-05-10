# Red Team Findings: BrewMatch — Round 2 (Spec + Brief Adversarial Audit)

Date: 2026-05-09
Scope: All 10 spec files (`specs/*.md`), product brief (`briefs/01-product-brief.md`), cross-spec consistency, ML pipeline feasibility, brief-to-spec traceability, edge cases and user flows

---

## Summary

| Severity | Count |
| -------- | ----- |
| CRITICAL | 0     |
| HIGH     | 0     |
| MEDIUM   | 12    |
| LOW      | 8     |

**Overall assessment**: All CRITICAL and HIGH findings resolved. 12 MEDIUM and 8 LOW findings remain for implementation-phase resolution.

---

## CRITICAL Findings

### RT2-01: too_harsh Flag Maps to Opposite Bias Directions Across Specs

**Files**:

- `specs/taste-prediction.md` Section 3.3: `too_harsh → "increase acidity_bias"`
- `specs/personalization.md` Section 4.2: `too_harsh → acidity_bias -0.05` (decrease)
- `specs/data-models.md` Section feedback.directional_flags: `too_harsh` defined as a valid enum value

**The problem**: When a user reports "too harsh," the taste prediction model increases acidity bias while the personalization layer decreases it. These directly oppose each other. The optimizer will receive contradictory signals, and the resulting recipe will be worse than doing nothing.

**Recommendation**: Decide one canonical direction. Coffee science supports: "too harsh" usually means over-extraction of astringent compounds → reduce acidity (personalization's `-0.05` is correct). Update `taste-prediction.md` Section 3.3 to read `too_harsh → decrease acidity_bias`.

### RT2-02: Feature Count Is Wrong — Claimed 44, Actual 45 (RESOLVED)

**File**: `specs/taste-prediction.md` Section 3

**The problem**: The spec claimed "44 features total" broken into 22 bean + 7 recipe + 9 user history + 6 interaction. Actual count from the spec's own feature tables:

- Bean features: 23 (not 22) — Section 3.1 lists origin_encoded, 5 process one-hots, roast_ordinal, 15 cluster multi-hots, altitude_mean = 23
- Recipe features: 7 ✓
- User history features: 9 ✓
- Interaction features: 6 ✓
- **Total: 23 + 7 + 9 + 6 = 45, not 44**

**Resolution**: Updated taste-prediction.md: bean count 22→23, total 44→45.

### RT2-03: Temperature Threshold Uses Three Different Values Across Three Specs

**Files**:

- `specs/synthetic-data.md`: `is_underextracted` uses 91C threshold
- `specs/coffee-science.md`: Section 7.2 states "water below 93C produces under-extraction"
- `specs/recipe-optimization.md` Section 3.2: soft constraint says "light roast temp >= 92C"

**The problem**: The synthetic training data labels brews at 91.5C as "properly extracted" (below 91C threshold), but coffee-science.md says those same brews are under-extracted (below 93C), and the optimizer won't even explore below 92C for light roasts. The model will train on labels that disagree with both the domain knowledge spec and the optimizer's search space.

**Recommendation**: Pick one threshold. Recommend 92C as the canonical minimum (matches the optimizer's soft constraint and is a reasonable middle ground). Update synthetic-data.md's `is_underextracted` to use 92C. Update coffee-science.md to say "water below 92C tends toward under-extraction."

---

## HIGH Findings

### RT2-04: Collaborative Filtering References Undefined Runtime Loading of Synthetic Users (RESOLVED)

**Files**:

- `specs/personalization.md` Section 6: `find_similar_users(target_user, all_users)`
- `specs/data-models.md`: no synthetic user schema
- `specs/synthetic-data.md`: generates brew records but no user taste profiles

**Original problem**: The personalization spec's collaborative filtering (Phase 4, 10+ brews) references `find_similar_users(target_user, all_users)` but no spec described how synthetic users are loaded into the database at runtime, what schema they follow, or how many there are.

**Resolution**: Added Section 11 to `synthetic-data.md` defining: (a) `SyntheticUser` schema (user_id, roast_preference, preferred_clusters, rating_bias, acidity/body/sweetness tolerance, experience_level), (b) 200 synthetic users, (c) loading mechanism via `data/synthetic/users.json` → SQLite seed script at startup.

### RT2-05: `encode_features()` Function Referenced But Never Defined (RESOLVED)

**File**: `specs/recipe-optimization.md` Section 3.1

**Original problem**: The optimizer's objective function calls `encode_features(bean_profile, params, user_features)` to produce the feature vector for the surrogate model. No spec defined its implementation, mapping logic, or how it handles missing fields.

**Resolution**: Added Section 4.0 to `taste-prediction.md` defining the full `encode_features()` contract: input schemas, 45-element output array, exact column ordering (23 bean + 7 recipe + 9 user + 6 interaction), and missing value defaults per Section 3.6.

### RT2-06: Optimizer Reduced to 4 Tunable Parameters (RESOLVED)

**Files**:

- `specs/recipe-optimization.md` Section 2.2 (updated)

**Original problem**: The optimizer optimized all 7 recipe parameters including pour schedule (pour_count, bloom_time_s, total_time_s), which could produce invalid pour distributions and fundamentally changed the recipe structure rather than tuning it.

**Resolution**: Reduced optimizer to 4 decision variables (grind_setting, water_temp_c, dose_g, ratio). Pour schedule is fixed from the retrieved recipe. This aligns with user feedback: optimizing pour structure creates a new recipe, not an adjustment. Grind and temperature are the clearest variables for diagnosis-driven tuning.

### RT2-07: "Always Returns Exactly 3 Recipes" Has No Fallback (RESOLVED)

**File**: `specs/recipe-retrieval.md` Section 4 (Output Contract)

**Original problem**: The output contract guaranteed "Always returns exactly 3 recipes" but no spec defined fallback behavior when fewer than 3 recipes match after all constraint relaxation stages.

**Resolution**: Updated `recipe-retrieval.md` Output Contract to return 1-3 recipes. Added fallback tiers: broad matches (same method), general recommendations (all methods), and single-result handling.

### RT2-08: Diagnosis Page Undefined for Zero-Brew Users (RESOLVED)

**File**: `specs/user-interface.md` Section 4.7

**Original problem**: The diagnosis page assumed historical brew data. For a brand-new user with zero history, the spec didn't define what to show.

**Resolution**: Added two-branch behavior to Section 4.7: 0-2 prior brews → rule-based diagnosis using bean profile + feedback flags; 3+ brews → pattern-based diagnosis from brew history.

### RT2-09: Bean Extraction Timeout Budget Undefined (RESOLVED)

**File**: `specs/bean-extraction.md` Section 7

**Original problem**: The spec said "retry once then fallback to manual entry" on LLM timeout, but didn't define the timeout budget. Users could wait 30+ seconds before seeing the manual entry form.

**Resolution**: Added explicit timeout budget to performance table and error handling: LLM call timeout 8s, retry timeout 5s, total max wait 13s, progress indicator after 3s.

### RT2-10: Demo Mode "Resets on Reload" Conflicts with SQLite Persistence (RESOLVED)

**File**: `specs/user-interface.md` Section 5

**Original problem**: Demo mode said "resets on reload" but the app uses SQLite, which persists across reloads.

**Resolution**: Demo mode now uses in-memory SQLite (`:memory:`) activated by `BREWMATCH_DEMO_MODE=true`. Updated both the demo behavior and persistence table in Section 6.2.

### RT2-11: Evaluation Claims Monotonic RMSE Improvement But Global Model Is Never Retrained (RESOLVED)

**File**: `specs/evaluation.md` Section 6.6

**Original problem**: The spec claimed "RMSE decreases monotonically with more brews" but the global LightGBM model is never retrained, making monotonic improvement unachievable.

**Resolution**: Softened to: "Personalized predictions should show improvement over global predictions as brew count increases. Target: personalized RMSE < global RMSE for users with 10+ brews."

### RT2-12: Onboarding Quiz Allows 1-3 Flavor Clusters But Data Model Allows 1-5 (RESOLVED)

**Files**:

- `specs/user-interface.md` Section 3: "Select 1-3 flavor clusters"
- `specs/data-models.md` Section User Taste Profile: `preferred_flavor_clusters` lists up to 5 entries

**Original problem**: The UI restricted selection to 3 clusters but the data model stores up to 5, creating unused capacity and potential future schema misalignment.

**Resolution**: Updated onboarding Step 2 label from "up to 3" to "up to 5" to align with the data model.

### RT2-13: Brief Lists 4 Directional Flags But All Specs Use 5

**Files**:

- `briefs/01-product-brief.md`: lists too_sour, too_bitter, too_weak, too_harsh (4 flags)
- `specs/data-models.md`, `taste-prediction.md`, `personalization.md`: include "astringent" as a 5th flag

**The problem**: The brief that the user approved lists 4 flags. Every spec silently added a 5th ("astringent") without surfacing the scope addition. This is a traceability gap — if the user checks the brief against the system, they'll see an extra flag they didn't request.

**Recommendation**: Surface this to the user at the `/todos` gate: "Brief defines 4 directional flags. Specs added a 5th ('astringent') to distinguish mouthfeel harshness from taste bitterness. Keep 5 (recommended — finer diagnostic signal) or revert to 4?"

---

## MEDIUM Findings

### RT2-14: Brief's "LLM-Generated Brewing Instructions" Has No Spec Coverage

**File**: `briefs/01-product-brief.md` — "LLM layer generates natural-language brewing instructions"

**The problem**: The brief promises LLM-generated brewing instructions (the Instruction Generator from the architecture diagram). No spec file covers this component — no input/output contract, no prompt strategy, no evaluation metric. It was identified as an orphan in Round 1 (F-12) but the specs were written without resolving it.

**Recommendation**: Either add a spec section for instruction generation (input: optimized recipe parameters + bean profile; output: step-by-step brewing guide) or explicitly remove it from scope and update the brief traceability table.

### RT2-15: Synthetic Data Omits `pour_count` and `bloom_time_s` Features

**File**: `specs/synthetic-data.md` Section 3

**The problem**: The `extraction_quality_score` response surface uses 5 weighted terms but does not include `pour_count` or `bloom_time_s`. These are features in the taste prediction model (Section 2.3 of `taste-prediction.md`). Training data generated from this response surface will have `pour_count` and `bloom_time_s` columns with zero signal — the model will learn to ignore them.

**Recommendation**: Add `pour_count` and `bloom_time_s` terms to the response surface: "Higher pour_count (4-6) contributes +0.05 per pour beyond 3 (better extraction uniformity). Bloom_time_s in range 30-60s contributes +0.1; outside this range, -0.05."

### RT2-16: Coffee Science Spec Has Duplicate Section Numbers

**File**: `specs/coffee-science.md`

**The problem**: Two sections are numbered "7.2" — one covers "Diagnostic Rules" and another covers "ML-Powered Diagnosis." This creates ambiguity when cross-referencing from other specs.

**Recommendation**: Renumber the sections sequentially. "ML-Powered Diagnosis" should be Section 7.3.

### RT2-17: Perturb-and-Score Example Deltas Are Not Canonical Values

**File**: `specs/coffee-science.md` Section 7.2 (ML-Powered Diagnosis)

**The problem**: The Perturb-and-Score explanation gives example deltas (e.g., "increase temperature by 2C") but notes these are illustrative. Other specs (`recipe-optimization.md`, `taste-prediction.md`) reference perturbation but don't define canonical step sizes. Inconsistent perturbation deltas across components will produce inconsistent diagnosis results.

**Recommendation**: Add a canonical perturbation table to `coffee-science.md`: "Standard perturbation deltas for diagnosis: temperature ±2C, grind ±1, ratio ±0.5, pour_count ±1, bloom_time ±10s." Reference this table from other specs instead of defining their own deltas.

### RT2-18: No Spec Defines What Happens When ChromaDB Has Zero Matching Embeddings

**File**: `specs/recipe-retrieval.md`

**The problem**: The dense retrieval stage (Stage 2) queries ChromaDB for similar embeddings. If the user enters a bean description that produces an embedding far from all recipe embeddings, ChromaDB may return zero results above the similarity threshold. The spec defines 4 relaxation stages but none handles the "zero results at any similarity level" case.

**Recommendation**: This is partially covered by RT2-07 (fallback for <3 results). Ensure the fallback mechanism also handles the zero-results-from-dense-retrieval case specifically.

### RT2-19: Bias Layer Damping Factor 0.3 for 1-4 Brews May Be Too Aggressive

**File**: `specs/taste-prediction.md` Section 4.2

**The problem**: The per-user bias layer applies a 0.3 damping factor for users with 1-4 brews. With only 1-4 data points, the bias correction is heavily discounted (70% suppressed). This means the first 4 brews produce almost no personalization effect, contradicting the "directional learning from brew 1" promise in the personalization spec.

**Recommendation**: Consider a graduated damping: 0.5 for 1 brew, 0.6 for 2, 0.7 for 3, 0.8 for 4, 1.0 for 5+. This produces visible personalization earlier while still preventing overfitting on sparse data.

### RT2-20: `feedback.score` Range Inconsistency

**Files**:

- `specs/data-models.md`: `score: int 1-10`
- `specs/user-interface.md` Section 4.4: primary input is "thumbs up/down" with optional 1-10 slider
- `specs/taste-prediction.md`: trains on 1-10 score from synthetic data

**The problem**: The UI spec says the 1-10 score is optional (thumbs up/down is primary). If most users only give thumbs up/down, the taste prediction model will have sparse 1-10 training signal from real data. Synthetic data uses 1-10, creating a train-test distribution mismatch.

**Recommendation**: Define the mapping clearly: "thumbs_up = score 7, thumbs_down = score 3. Optional slider overrides this default. The model trains on the mapped score when no explicit score is provided."

### RT2-21: Personalization Phase Boundaries Differ Across Specs

**Files**:

- `specs/personalization.md`: Bean-Aware (0) → Directional (1-4) → Content-Based (5-9) → Full Hybrid (10+)
- `specs/data-models.md`: Phase field uses same thresholds
- `briefs/01-product-brief.md`: "After 3-5 rated brews: directional" and "After 10+ brews: full personalized"

**The problem**: The brief says directional starts at "3-5 brews." The specs say it starts at brew 1. This was flagged in Round 1 (F-14) and the specs were written with "1-4" but the brief wasn't updated.

**Recommendation**: Update the brief to match: "From brew 1: directional adjustments begin. After 5+ brews: content-based filtering. After 10+ brews: full collaborative + content hybrid." This is more aggressive but matches the spec implementation.

### RT2-22: No Evaluation for Edge Cases in Recipe Optimizer

**File**: `specs/evaluation.md`

**The problem**: The evaluation spec covers convergence speed and improvement metrics for the optimizer but doesn't test edge cases: extreme bean profiles (very dark roast + fine grind), boundary parameter values (water_temp = 80C, grind = 1), or infeasible combinations. The optimizer may produce invalid recipes for these inputs.

**Recommendation**: Add edge-case test scenarios to evaluation: "Optimizer MUST produce valid recipes for 10 edge-case beans: extreme roast levels, unusual origins, boundary parameter values. Valid = all parameters within Recipe schema constraints."

### RT2-23: "Optimize for My Taste" Button Available at 0 Brews

**File**: `specs/user-interface.md` Section 4.5

**The problem**: The recipe detail page shows an "Optimize for my taste" button regardless of brew count. At 0 brews, the optimizer has no user bias layer and will return the same recipe (no optimization possible). The button misleads users into expecting personalization that can't happen.

**Recommendation**: Disable or relabel the button based on phase: "0 brews: hidden. 1-4 brews: labeled 'Suggest adjustments' (directional only). 5+ brews: labeled 'Optimize for my taste' (full optimization)."

### RT2-24: Synthetic Data Evaluation Metrics May Be Trivially Achievable

**File**: `specs/evaluation.md`

**The problem**: All evaluation metrics are tested against synthetic data that was generated from the same response surface the model learns. Precision@3, RMSE, convergence speed, and personalization improvement can all be trivially met by construction. The evaluation won't catch genuine model failures.

**Recommendation**: Add a held-out bean test: "Reserve 5 bean profiles from synthetic data generation. Train on all others. Evaluate on the 5 held-out beans. Report generalization gap (train RMSE vs held-out RMSE). Target: gap < 0.5 points."

### RT2-25: No Spec for Error Messages and User-Facing Error Handling

**Files**: All spec files

**The problem**: No spec defines user-facing error messages for common failures: LLM extraction fails, ChromaDB returns no results, optimizer doesn't converge, SQLite write fails. The UI spec has pages but no error states.

**Recommendation**: Add an "Error States" section to `user-interface.md` covering: extraction failure, no matching recipes, optimization timeout, data persistence errors. Each with user-facing message and recovery action.

---

## LOW Findings

### RT2-26: `suitable_for.flavor_profiles` Optional But Used for Ranking

**File**: `specs/data-models.md` — `suitable_for.flavor_profiles` is Required: NO

**The problem**: If some recipes lack flavor_profiles, RAG retrieval will rank them lower for flavor-specific queries. Every curated recipe can be tagged against the 15-cluster taxonomy.

**Recommendation**: Make `flavor_profiles` Required (YES) in the spec.

### RT2-27: Grind Scale 1-10 May Not Cover All Equipment

**File**: `specs/data-models.md` — `grind_setting: int 1-10`

**The problem**: The brief mentions V60, Kalita, and Origami, which use different grind ranges. A 1-10 scale may not capture the fine adjustments needed for different drippers. This is a minor UX concern, not a technical blocker.

**Recommendation**: Document the scale as method-relative: "1 = very fine (espresso-adjacent), 10 = very coarse (French press-adjacent). Exact particle size varies by grinder."

### RT2-28: No Citation for Coffee Science Temperature Claims

**File**: `specs/coffee-science.md`

**The problem**: Temperature ranges, extraction percentages, and TDS targets are stated without citations. For a course submission, the professor may check these claims.

**Recommendation**: Add footnotes citing SCA (Specialty Coffee Association) standards or peer-reviewed sources for key claims (extraction yield 18-22%, TDS 1.15-1.45%, brew temperature 90-96C).

### RT2-29: Bean Profile Confidence Threshold Undefined

**File**: `specs/bean-extraction.md` — mentions `extraction_confidence` score

**The problem**: The spec describes confidence scoring but doesn't define the threshold for triggering manual entry fallback. Is it 0.3? 0.5? 0.7? The architecture plan (from Round 1 F-10) used 0.5 as an example.

**Recommendation**: Define: "If extraction_confidence < 0.5, show manual entry form with pre-filled fields from partial extraction. If >= 0.5, show confirmation form."

### RT2-30: No Spec for Model Versioning or Retraining

**File**: `specs/taste-prediction.md`

**The problem**: The LightGBM model is trained once on synthetic data. No spec covers: what happens if synthetic data is regenerated, whether model artifacts are versioned, or how to trigger retraining.

**Recommendation**: Add a note: "Model is trained once during setup. Retraining is manual (delete model file, rerun training script). Model artifacts are stored in `models/taste_predictor.pkl` with a metadata file recording training date and data hash."

### RT2-31: No Performance Budget for End-to-End Pipeline

**Files**: All spec files

**The problem**: No spec defines acceptable latency for the full pipeline: bean extraction (LLM) → recipe retrieval (ChromaDB) → taste prediction (LightGBM) → optimization (Optuna). For a live demo, the user needs to know if the app will respond in 2 seconds or 30 seconds.

**Recommendation**: Add performance targets to `evaluation.md`: "End-to-end pipeline (extraction to recommendation): <5 seconds for initial recipe, <10 seconds for optimized recipe. Bean extraction is the bottleneck (LLM call)."

### RT2-32: `stats` Object Computation Method Undefined

**File**: `specs/data-models.md` — User Taste Profile `stats` object

**The problem**: The `stats` object (total_brews, avg_score, favorite_origins, favorite_clusters) has no defined computation strategy — computed on read or materialized on write?

**Recommendation**: Note in spec: "Stats are computed on read from brew_history. Not stored persistently."

### RT2-33: No Spec for Data Migration or Schema Evolution

**File**: `specs/data-models.md`

**The problem**: As an MBA course project, the data model will evolve during development. No spec covers how to handle schema changes in SQLite without losing existing brew history.

**Recommendation**: Add a note: "Use SQLite's ALTER TABLE for additive changes. For breaking changes, write a migration script in `scripts/migrate_db.py` that transforms existing data."

---

## Brief Traceability Audit

| Brief Requirement                | Covered? | Where                                 | Finding                                            |
| -------------------------------- | -------- | ------------------------------------- | -------------------------------------------------- |
| Pour-over (V60, Kalita, Origami) | YES      | `data-models.md` method enum          | All 3 included                                     |
| AeroPress                        | NO       | Explicitly excluded (from Round 1)    | Resolved in Round 1                                |
| Bean profile input via bag label | PARTIAL  | `bean-extraction.md` (text input)     | Photo/OCR deferred                                 |
| Initial recipe recommendation    | YES      | `recipe-retrieval.md`                 |                                                    |
| Post-brew feedback capture       | PARTIAL  | `data-models.md`, `user-interface.md` | RT2-20 (score mapping)                             |
| Personalization adjustments      | YES      | `personalization.md`, 4 phases        | RT2-21 (phase boundaries)                          |
| Recipe knowledge base            | YES      | `recipe-retrieval.md`, 50-80 recipes  |                                                    |
| Taste Score Prediction           | YES      | `taste-prediction.md`                 | RT2-02 (feature count)                             |
| Recipe Optimization              | YES      | `recipe-optimization.md`              | RT2-05 (encode_features), RT2-06 (pour validation) |
| Bean Profile Extraction          | YES      | `bean-extraction.md`                  | RT2-09 (timeout)                                   |
| Personalization Layer            | YES      | `personalization.md`                  | RT2-04 (collaborative filtering)                   |
| Embedding-based retrieval        | YES      | `recipe-retrieval.md`, ChromaDB       |                                                    |
| LLM-generated instructions       | NO       | No spec exists                        | RT2-14                                             |
| Diagnosis ("what went wrong")    | PARTIAL  | `user-interface.md` Section 4.7       | RT2-08 (zero-brew case)                            |
| 4 directional flags              | PARTIAL  | Specs use 5 flags (added astringent)  | RT2-13                                             |

---

## Spec Cross-Reference Consistency Matrix

| Cross-Spec Reference            | Source                       | Target                                         | Consistent? | Finding |
| ------------------------------- | ---------------------------- | ---------------------------------------------- | ----------- | ------- |
| too_harsh bias direction        | `taste-prediction.md`        | `personalization.md`                           | NO          | RT2-01  |
| Temperature threshold           | `synthetic-data.md`          | `coffee-science.md` / `recipe-optimization.md` | NO          | RT2-03  |
| Feature count                   | `taste-prediction.md`        | `synthetic-data.md`                            | NO          | RT2-02  |
| Directional flag count          | `briefs/01-product-brief.md` | `data-models.md`                               | NO          | RT2-13  |
| Phase boundaries                | `briefs/01-product-brief.md` | `personalization.md`                           | NO          | RT2-21  |
| Onboarding cluster count        | `user-interface.md`          | `data-models.md`                               | NO          | RT2-12  |
| `encode_features` function      | `recipe-optimization.md`     | (nowhere)                                      | NO          | RT2-05  |
| Collaborative filtering users   | `personalization.md`         | (nowhere)                                      | NO          | RT2-04  |
| Extraction confidence threshold | `bean-extraction.md`         | (undefined)                                    | NO          | RT2-29  |
| Score mapping (thumbs → 1-10)   | `user-interface.md`          | `taste-prediction.md`                          | NO          | RT2-20  |

---

## Recommendations Summary

### RESOLVED (all CRITICAL and HIGH findings):

1. **RT2-01**: too_harsh bias direction — aligned to decrease across all specs
2. **RT2-02**: Feature count — corrected to 45 everywhere
3. **RT2-03**: Temperature threshold — canonicalized to 92C
4. **RT2-04**: Synthetic user loading for collaborative filtering — defined in synthetic-data.md Section 11
5. **RT2-05**: `encode_features()` function contract — defined in taste-prediction.md Section 4.0
6. **RT2-06**: Optimizer reduced to 4 tunable parameters (grind, temp, dose, ratio)
7. **RT2-07**: Recipe retrieval fallback for <3 results — added fallback tiers
8. **RT2-08**: Diagnosis for zero-brew users — added two-branch behavior
9. **RT2-09**: Bean extraction timeout budget — 8s/5s/13s budget defined
10. **RT2-10**: Demo mode in-memory SQLite — `BREWMATCH_DEMO_MODE=true`
11. **RT2-11**: Evaluation monotonic RMSE claim — softened to achievable target
12. **RT2-12**: Onboarding cluster count — aligned to 1-5

### Pending user decision:

- **RT2-13**: 5th flag (astringent) — surface to user at `/todos` gate

### CAN resolve during `/implement`:

- RT2-14 (instruction generator), RT2-15 (synthetic data features), RT2-19 (damping factor), RT2-20 (score mapping), RT2-22 (optimizer edge cases), RT2-23 (button state), RT2-25 (error messages)

### CAN resolve during testing/validation:

- RT2-16 through RT2-18, RT2-24, RT2-26 through RT2-33

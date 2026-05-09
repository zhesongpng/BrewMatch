# Taste Prediction Specification (Supervised Learning)

## 1. Overview

The taste prediction model estimates how much a user will enjoy a specific brew, given the bean profile, recipe parameters, and (where available) the user's brewing history. In the diagnosis-first architecture, this model serves two purposes: (1) ranking retrieved recipes by predicted taste score, and (2) powering the diagnosis engine by answering "which parameter change would most improve the predicted score for this user's reported issue?"

This is the supervised learning component of the ML pipeline, using LightGBM gradient-boosted regression to predict a rating score.

---

## 2. Prediction Target

| Attribute       | Value                                                                            |
| --------------- | -------------------------------------------------------------------------------- |
| Target variable | `rating` (1-10 integer, treated as continuous for regression)                    |
| Scale           | 1 = "undrinkable", 5 = "acceptable", 7 = "good", 9 = "excellent", 10 = "perfect" |
| Output          | Predicted rating as float in [1.0, 10.0], clipped post-prediction                |

---

## 3. Feature Engineering

### 3.1 Bean Profile Features

| Feature               | Type   | Source                                  | Encoding                                          |
| --------------------- | ------ | --------------------------------------- | ------------------------------------------------- |
| `origin_encoded`      | int    | `BeanProfile.origin_country`            | Label encoding (top-20 countries, rest = "other") |
| `process_washed`      | binary | `BeanProfile.process`                   | One-hot                                           |
| `process_natural`     | binary | `BeanProfile.process`                   | One-hot                                           |
| `process_honey`       | binary | `BeanProfile.process`                   | One-hot                                           |
| `process_anaerobic`   | binary | `BeanProfile.process`                   | One-hot                                           |
| `process_other`       | binary | `BeanProfile.process`                   | One-hot (wet-hulled + unknown)                    |
| `roast_ordinal`       | int    | `BeanProfile.roast_level`               | Ordinal: light=1, medium-light=2, ..., dark=5     |
| `cluster_floral`      | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_berry`       | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_citrus`      | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_stone_fruit` | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_tropical`    | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_sweet`       | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_chocolate`   | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_nutty`       | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_spice`       | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_roasted`     | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_vegetal`     | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_tea_like`    | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_fermented`   | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_syrupy`      | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `cluster_balanced`    | binary | `BeanProfile.flavor_clusters`           | Multi-hot                                         |
| `altitude_mean`       | float  | `(altitude_min_m + altitude_max_m) / 2` | Mean of range, 0 if missing                       |

**Total bean features**: 22

### 3.2 Recipe Parameter Features

| Feature         | Type  | Source                 | Range        |
| --------------- | ----- | ---------------------- | ------------ |
| `dose_g`        | float | `Recipe.dose_g`        | 12.0 - 22.0  |
| `ratio`         | float | `Recipe.ratio`         | 14.0 - 18.0  |
| `grind_setting` | int   | `Recipe.grind_setting` | 1 - 10       |
| `water_temp_c`  | float | `Recipe.water_temp_c`  | 85.0 - 100.0 |
| `bloom_time_s`  | int   | `Recipe.bloom_time_s`  | 15 - 90      |
| `total_time_s`  | int   | `Recipe.total_time_s`  | 120 - 360    |
| `pour_count`    | int   | `len(Recipe.pours)`    | 1 - 6        |

**Total recipe features**: 7

### 3.3 User History Features (available after 1+ brews)

| Feature                   | Type  | Computation                                                          |
| ------------------------- | ----- | -------------------------------------------------------------------- |
| `user_avg_rating`         | float | Mean of all prior ratings by this user                               |
| `user_rating_count`       | int   | Number of prior ratings                                              |
| `user_roast_pref_encoded` | int   | Most common roast level among highly-rated brews (> user_avg_rating) |
| `user_temp_pref`          | float | Mean water_temp_c of highly-rated brews                              |
| `user_grind_pref`         | float | Mean grind_setting of highly-rated brews                             |
| `user_ratio_pref`         | float | Mean ratio of highly-rated brews                                     |
| `user_acidity_bias`       | float | Learned preference (-1.0 to 1.0, from directional flags)             |
| `user_body_bias`          | float | Learned preference (-1.0 to 1.0)                                     |
| `user_sweetness_bias`     | float | Learned preference (-1.0 to 1.0)                                     |

**"Highly-rated"**: brews where the user gave a rating >= their own average rating.

**Directional flag mapping:**

| Flag         | Bias Effect                                                              |
| ------------ | ------------------------------------------------------------------------ |
| "too_sour"   | Decrease `acidity_bias` (prefers less acidic)                            |
| "too_bitter" | Decrease `body_bias` (prefers less body/harshness)                       |
| "too_weak"   | Increase `body_bias` (prefers more body/strength)                        |
| "too_harsh"  | Decrease `body_bias`, increase `acidity_bias` (harsh = overextracted)    |
| "astringent" | Decrease `sweetness_bias` (astringent = underdeveloped or overextracted) |

**Total user features**: 9 (all zero/null for cold-start users)

### 3.4 Interaction Features

| Feature         | Type  | Computation                     | Rationale                                                                              |
| --------------- | ----- | ------------------------------- | -------------------------------------------------------------------------------------- |
| `roast_x_temp`  | float | `roast_ordinal * water_temp_c`  | Light roasts need higher temp; dark roasts need lower temp. Interaction captures this. |
| `grind_x_time`  | float | `grind_setting * total_time_s`  | Fine grind + long time = overextraction. Captures grind-time tradeoff.                 |
| `grind_x_temp`  | float | `grind_setting * water_temp_c`  | Fine grind + high temp = fast extraction. Coarse grind + low temp = slow extraction.   |
| `ratio_x_dose`  | float | `ratio * dose_g`                | Total water amount = ratio \* dose. Directly affects extraction yield.                 |
| `roast_x_grind` | float | `roast_ordinal * grind_setting` | Dark roasts extract more easily (coarser grind compensates).                           |
| `cluster_count` | int   | `sum(flavor_cluster binaries)`  | More complex flavor profiles may need adjusted parameters.                             |

**Total interaction features**: 6

### 3.5 Feature Summary

| Category          | Count  | Notes                                             |
| ----------------- | ------ | ------------------------------------------------- |
| Bean profile      | 22     | One-hot encoded clusters + ordinal roast          |
| Recipe parameters | 7      | Raw numeric values                                |
| User history      | 9      | Zero for cold-start users                         |
| Interactions      | 6      | Domain-informed cross-terms                       |
| **Total**         | **44** | All numeric, no missing values (defaults applied) |

### 3.6 Missing Value Handling

| Scenario                  | Handling                                   |
| ------------------------- | ------------------------------------------ |
| Cold-start user (0 brews) | All user history features set to 0.0       |
| "unknown" roast level     | `roast_ordinal` = 3 (medium, the midpoint) |
| "unknown" process         | All process one-hots = 0                   |
| Empty flavor clusters     | Default to `cluster_balanced = 1`          |
| Missing altitude          | `altitude_mean` = 0.0                      |
| Missing variety           | Not used as a feature in v1                |

---

## 4. Model Architecture

### 4.1 Global Model (LightGBM)

| Hyperparameter      | Value                     | Rationale                             |
| ------------------- | ------------------------- | ------------------------------------- |
| `objective`         | `regression`              | Predict continuous rating             |
| `metric`            | `rmse`                    | Primary evaluation metric             |
| `num_leaves`        | 31                        | Moderate complexity for small dataset |
| `max_depth`         | 6                         | Prevent overfitting                   |
| `learning_rate`     | 0.05                      | Slow learning for stability           |
| `n_estimators`      | 500 (with early stopping) | Sufficient rounds with early stopping |
| `min_child_samples` | 20                        | Regularization for small dataset      |
| `subsample`         | 0.8                       | Row sampling for robustness           |
| `colsample_bytree`  | 0.8                       | Feature sampling for robustness       |
| `reg_alpha`         | 0.1                       | L1 regularization                     |
| `reg_lambda`        | 1.0                       | L2 regularization                     |
| `random_state`      | 42                        | Reproducibility                       |

### 4.2 Per-User Bias Layer

After the global model predicts a base rating, a per-user linear bias adjusts the prediction:

```
predicted_rating = clip(global_model.predict(features) + user_bias, 1.0, 10.0)
```

**User bias estimation:**

| Phase                | User Bias        | Computation                                                                |
| -------------------- | ---------------- | -------------------------------------------------------------------------- |
| Bean-aware (0 brews) | 0.0              | No adjustment                                                              |
| 1-4 brews            | Weighted average | `0.3 * mean_residual`, where residual = actual - predicted for prior brews |
| 5+ brews             | Full linear bias | `mean(user_residuals)` with exponential decay (recent brews weighted more) |

The 0.3 weight for early brews prevents overreaction to noisy early ratings.

### 4.3 Post-Processing

1. **Clip** predicted rating to [1.0, 10.0].
2. **Round** to 1 decimal place for display.
3. **Confidence interval**: estimated from prediction variance on validation set, displayed as +/- range.

---

## 5. Training

### 5.1 Training Data

Primary training data is synthetic, generated per `specs/synthetic-data.md`.

| Data Source            | Volume                    | Purpose                  |
| ---------------------- | ------------------------- | ------------------------ |
| Synthetic ratings      | 5,000 - 10,000 rows       | Primary training data    |
| Expert-labeled recipes | 50 - 80 rows              | Validation / calibration |
| Real user feedback     | 0 at launch, accumulating | Fine-tuning after launch |

**Training row schema:**

```
(bean_profile_features, recipe_features, user_history_features, interaction_features) -> rating
```

Each row represents one brew event: a specific user, bean, and recipe combination with a rating.

### 5.2 Train/Validation/Test Split

| Split      | Ratio | Strategy                                          |
| ---------- | ----- | ------------------------------------------------- |
| Train      | 70%   | Random stratified by roast level                  |
| Validation | 15%   | Used for early stopping and hyperparameter tuning |
| Test       | 15%   | Held out for final evaluation only                |

**Stratification**: Ensure each split has proportional representation across roast levels and process types to prevent roast-level-specific performance gaps.

### 5.3 Training Protocol

1. Generate synthetic training data per `specs/synthetic-data.md`.
2. Extract features for all rows.
3. Split into train/val/test.
4. Train LightGBM with early stopping on validation set (patience = 50 rounds).
5. Evaluate on test set.
6. Calibrate user bias on training set residuals.
7. Serialize model to `models/taste_predictor.joblib`.

---

## 6. Performance Target

| Metric                            | Target               | Measurement                            |
| --------------------------------- | -------------------- | -------------------------------------- |
| RMSE (test set)                   | < 1.5                | On the 1-10 rating scale               |
| MAE (test set)                    | < 1.0                | Less sensitive to outliers             |
| R-squared (test set)              | > 0.5                | Explains at least 50% of variance      |
| Bean-aware RMSE (no user history) | < 2.0                | Without user history features          |
| Per-user bias improvement         | RMSE reduction > 10% | After 5+ ratings vs global model alone |

**RMSE < 1.5** means predictions are typically within 1.5 points of the actual rating on a 1-10 scale. For a 7-point scale (4-10 practical range), this is approximately 20% relative error.

---

## 7. Output Contract

```python
@dataclass
class PredictionResult:
    predicted_rating: float           # Predicted rating [1.0, 10.0]
    confidence_interval: tuple[float, float]  # (lower, upper) bound
    user_bias: float                  # Per-user adjustment applied
    base_prediction: float            # Before user bias
    feature_importance: dict[str, float]  # Top 10 features by SHAP value
```

### Guarantees

1. `predicted_rating` is always in [1.0, 10.0].
2. `confidence_interval` bounds are in [1.0, 10.0].
3. `confidence_interval` width is at most 3.0 (for bean-aware users with no history) and narrows with more data.
4. `feature_importance` contains exactly 10 entries (or fewer if fewer features exist).

---

## 8. Edge Cases

| Case                                         | Handling                                                                 |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| All features zero (empty bean profile)       | Return global mean rating from training data (typically ~6.0)            |
| Extreme parameter values (grind=1, temp=100) | LightGBM handles extrapolation; clip prediction to [1, 10]               |
| New origin not in training data              | `origin_encoded` maps to "other" category                                |
| User with 100+ brews                         | Use full user bias with exponential decay; recent 20 brews weighted most |
| Very high or very low ratings (1 or 10)      | Model may predict toward mean; acceptable for regression task            |

---

## 9. Model Persistence

| Artifact                         | Path                            | Format                                           |
| -------------------------------- | ------------------------------- | ------------------------------------------------ |
| Trained LightGBM model           | `models/taste_predictor.joblib` | joblib                                           |
| Feature encoder (label mappings) | `models/feature_encoder.joblib` | joblib                                           |
| User bias store                  | `models/user_biases.json`       | JSON                                             |
| Training metadata                | `models/training_metadata.json` | JSON (train/val/test sizes, RMSE, feature count) |

---

## 10. Dependencies

| Dependency                 | Purpose                                             |
| -------------------------- | --------------------------------------------------- |
| `specs/data-models.md`     | BeanProfile, Recipe schemas                         |
| `specs/coffee-science.md`  | Interaction feature design rationale                |
| `specs/synthetic-data.md`  | Training data generation                            |
| `specs/personalization.md` | Bean-aware phases and user bias strategy            |
| `lightgbm`                 | Gradient boosted regression                         |
| `scikit-learn`             | Train/test split, metrics, preprocessing            |
| `shap`                     | Feature importance (optional, for explanation view) |

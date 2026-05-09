# Recipe Optimization Specification

## 1. Overview

The recipe optimization component finds the best parameter adjustment for a diagnosed brew issue. In the diagnosis-first architecture, the optimizer starts from the recipe the user actually brewed and finds the minimum change that fixes the reported problem (e.g., "too sour" → find the smallest parameter change that maximizes predicted taste score). This is the optimization component of the ML pipeline, using Bayesian optimization (Optuna TPE sampler) over a constrained parameter space.

---

## 2. Optimization Problem Formulation

### 2.1 Objective

Maximize the predicted taste score from the taste prediction model (`specs/taste-prediction.md`).

```
maximize  f(bean_features, recipe_params, user_features)
subject to:
    - recipe_params in valid_ranges
    - domain constraints (roast-temperature, grind-time relationships)
    - parameter consistency constraints
```

Where `f` is the trained LightGBM taste predictor.

### 2.2 Decision Variables (7 Parameters)

| Parameter       | Type  | Range        | Step | Notes                   |
| --------------- | ----- | ------------ | ---- | ----------------------- |
| `dose_g`        | float | 12.0 - 22.0  | 0.5  | Coffee weight in grams  |
| `ratio`         | float | 14.0 - 18.0  | 0.25 | Water:coffee ratio      |
| `grind_setting` | int   | 1 - 10       | 1    | Relative grind fineness |
| `water_temp_c`  | float | 85.0 - 100.0 | 0.5  | Water temperature       |
| `bloom_time_s`  | int   | 15 - 90      | 5    | Bloom duration          |
| `total_time_s`  | int   | 120 - 360    | 10   | Total brew duration     |
| `pour_count`    | int   | 1 - 6        | 1    | Number of pour steps    |

**Total search space size**: approximately 21 _ 17 _ 10 _ 31 _ 16 _ 25 _ 6 = ~26.7 million discrete combinations. Exhaustive search is infeasible; Bayesian optimization is required.

### 2.3 Derived Values

| Derived Value       | Computation                      | Purpose                    |
| ------------------- | -------------------------------- | -------------------------- |
| `water_total_g`     | `dose_g * ratio`                 | Total water weight         |
| `extraction_time_s` | `total_time_s - bloom_time_s`    | Time for actual extraction |
| `time_per_pour_s`   | `extraction_time_s / pour_count` | Approximate pour duration  |

---

## 3. Constraints

### 3.1 Hard Constraints (must be satisfied)

| ID  | Constraint                                  | Rationale                      |
| --- | ------------------------------------------- | ------------------------------ |
| C1  | `water_total_g <= 400.0`                    | V60 practical capacity limit   |
| C2  | `water_total_g >= 180.0`                    | Minimum for proper extraction  |
| C3  | `total_time_s >= bloom_time_s + 60`         | Minimum extraction after bloom |
| C4  | `pour_count <= 6`                           | Practical limit for pour-over  |
| C5  | `grind_setting >= 1`, `grind_setting <= 10` | Equipment limits               |

### 3.2 Soft Constraints (penalized, not forbidden)

| ID  | Constraint                                 | Penalty Weight | Rationale                                                                            |
| --- | ------------------------------------------ | -------------- | ------------------------------------------------------------------------------------ |
| S1  | Light roast: `water_temp_c >= 92.0`        | 0.5            | Light roasts need higher temperature for proper extraction (see `coffee-science.md`) |
| S2  | Dark roast: `water_temp_c <= 94.0`         | 0.5            | Dark roasts extract easily; high temp causes bitterness                              |
| S3  | Fine grind (1-3): `total_time_s <= 240`    | 0.3            | Fine grind extracts fast; long time = overextraction                                 |
| S4  | Coarse grind (8-10): `total_time_s >= 180` | 0.3            | Coarse grind extracts slowly; short time = underextraction                           |
| S5  | `ratio` between 15.0 and 17.0              | 0.2            | Center of SCA optimal range                                                          |
| S6  | `dose_g` between 14.0 and 18.0             | 0.1            | Standard single-cup range                                                            |

**Penalty computation:**

```python
def constraint_penalty(params, bean_profile):
    penalty = 0.0
    roast = bean_profile.roast_level

    # S1: Light roast should use higher temp
    if roast in ("light", "medium-light") and params.water_temp_c < 92.0:
        penalty += 0.5 * (92.0 - params.water_temp_c) / 7.0  # normalized

    # S2: Dark roast should use lower temp
    if roast in ("dark", "medium-dark") and params.water_temp_c > 94.0:
        penalty += 0.5 * (params.water_temp_c - 94.0) / 6.0  # normalized

    # S3: Fine grind should have shorter time
    if params.grind_setting <= 3 and params.total_time_s > 240:
        penalty += 0.3 * (params.total_time_s - 240) / 120.0

    # S4: Coarse grind should have longer time
    if params.grind_setting >= 8 and params.total_time_s < 180:
        penalty += 0.3 * (180 - params.total_time_s) / 60.0

    return penalty
```

### 3.3 Objective Function (with penalties)

```python
def objective(params, bean_profile, user_features, taste_predictor):
    features = encode_features(bean_profile, params, user_features)
    predicted_score = taste_predictor.predict(features)
    penalty = constraint_penalty(params, bean_profile)
    return predicted_score - penalty
```

---

## 4. Optimization Algorithm

### 4.1 Optuna Configuration

| Parameter          | Value        | Rationale                                                             |
| ------------------ | ------------ | --------------------------------------------------------------------- |
| Sampler            | `TPESampler` | Tree-structured Parzen Estimator; efficient for mixed parameter types |
| Direction          | `maximize`   | Maximizing predicted taste score                                      |
| N trials           | 100          | Sufficient for convergence in 7D space                                |
| Random seed        | 42           | Reproducibility                                                       |
| Bootstrap trials   | 10           | Random exploration before TPE starts modeling                         |
| `n_startup_trials` | 10           | Matches bootstrap count                                               |

### 4.2 Initialization from Best-Matching Recipe

Rather than starting optimization from random points, initialize with the best-matching recipe from the retrieval pipeline (`specs/recipe-retrieval.md`).

**Initialization strategy:**

1. Retrieve top recipe from `specs/recipe-retrieval.md` for the given bean profile.
2. Set that recipe's parameters as the starting point (trial 0).
3. Generate 9 more random trials within +/- 20% of the initial recipe's parameters.
4. From trial 11 onward, use TPE sampling.

This provides a warm start that dramatically improves convergence.

### 4.3 Search Space Definition

```python
def suggest_params(trial):
    dose_g = trial.suggest_float("dose_g", 12.0, 22.0, step=0.5)
    ratio = trial.suggest_float("ratio", 14.0, 18.0, step=0.25)
    grind_setting = trial.suggest_int("grind_setting", 1, 10)
    water_temp_c = trial.suggest_float("water_temp_c", 85.0, 100.0, step=0.5)
    bloom_time_s = trial.suggest_int("bloom_time_s", 15, 90, step=5)
    total_time_s = trial.suggest_int("total_time_s", 120, 360, step=10)
    pour_count = trial.suggest_int("pour_count", 1, 6)

    # Hard constraint check
    water_total = dose_g * ratio
    if water_total > 400.0 or water_total < 180.0:
        # Tell Optuna this is an invalid combination; it will learn to avoid it
        raise optuna.exceptions.TrialPruned()

    return RecipeParams(dose_g, ratio, grind_setting,
                       water_temp_c, bloom_time_s, total_time_s, pour_count)
```

---

## 5. Convergence

### 5.1 Convergence Target

| Metric                         | Target | Measurement                     |
| ------------------------------ | ------ | ------------------------------- |
| Trials to reach 80% of optimal | < 5    | After warm-start initialization |
| Trials to reach 95% of optimal | < 20   | Including warm-start            |
| Total trials                   | 50-100 | Budget for thorough exploration |
| Improvement after trial 30     | < 2%   | Diminishing returns threshold   |

**"Optimal"** is defined as the best score found across 200 trials (a budget that is affordable offline but not in real-time).

### 5.2 Early Stopping

If the best score does not improve by more than 0.05 (on the 1-10 scale) over 15 consecutive trials, stop optimization early. This prevents wasting compute on diminishing returns.

### 5.3 Convergence Monitoring

Track and log:

- Best score per trial (for convergence curve visualization).
- Parameter values of the best trial so far.
- Which constraints were active (penalized) in the best trial.
- Improvement rate (delta score per 10 trials).

---

## 6. Output Contract

```python
@dataclass
class OptimizationResult:
    optimized_params: RecipeParams    # Best parameter set found
    predicted_score: float            # Predicted taste score
    baseline_score: float             # Score of initial (retrieved) recipe
    improvement: float                # predicted_score - baseline_score
    n_trials: int                     # Number of optimization trials
    convergence_reached: bool         # Whether early stopping kicked in
    parameter_changes: dict[str, tuple[float, float]]  # param -> (baseline, optimized)
    constraint_violations: list[str]  # Any remaining soft constraint violations
```

### Guarantees

1. `optimized_params` always satisfies all hard constraints.
2. `predicted_score >= baseline_score` (optimization never makes things worse than the starting recipe).
3. `parameter_changes` documents every parameter that changed by more than 1 step from baseline.
4. If the optimizer fails, fall back to the initial recipe with `improvement = 0.0`.

---

## 7. Pour Schedule Generation

After optimization produces the 7 parameters, a pour schedule is generated for the brew instructions.

### 7.1 Pour Distribution Strategy

| Strategy                         | Rules                                                                                |
| -------------------------------- | ------------------------------------------------------------------------------------ |
| **Kasuya 4:6** (pour_count >= 4) | First 40% of water in 2 pours (flavor), remaining 60% in subsequent pours (strength) |
| **Multi-pour** (pour_count 3-4)  | Bloom pour (2x dose weight), then equal pours at regular intervals                   |
| **Simple** (pour_count 1-2)      | Bloom pour, then single large pour                                                   |

### 7.2 Pour Timing

```
bloom:    time_offset = 0,    water = 2 * dose_g
pour 2:   time_offset = bloom_time_s,  water = (water_total - bloom_water) / remaining_pours
pour 3-n: time_offset = previous + (total_time_s - bloom_time_s) / (pour_count - 1)
          water = remaining / remaining_pours
```

---

## 8. Edge Cases

| Case                                                | Handling                                                                                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Optimizer fails to improve on baseline              | Return baseline recipe; log "optimization did not improve"                                  |
| All trials pruned (hard constraints too tight)      | Return baseline recipe; log constraint violation details                                    |
| Bean profile is mostly "unknown"                    | Optimization relies more on user features and interaction terms; wider confidence intervals |
| Bean-aware user (0 brews)                           | Optimize against global model only (no user bias); result is a generic best-fit             |
| Extreme user bias (user consistently rates 1 or 10) | Cap user bias at +/- 1.5 points to prevent unrealistic predictions                          |
| Very dark roast with all temperatures penalized     | Soft constraints guide toward lower temp; penalty is advisory, not prohibitive              |

---

## 9. Performance Requirements

| Metric                                 | Target                                    |
| -------------------------------------- | ----------------------------------------- |
| Optimization time (50 trials)          | < 5 seconds                               |
| Optimization time (100 trials)         | < 10 seconds                              |
| Memory usage                           | < 500 MB                                  |
| Improvement over random initialization | > 30% faster convergence                  |
| Improvement over baseline recipe       | > 0.5 points (predicted score) on average |

---

## 10. Dependencies

| Dependency                  | Purpose                                     |
| --------------------------- | ------------------------------------------- |
| `specs/taste-prediction.md` | Prediction model used as objective function |
| `specs/recipe-retrieval.md` | Provides initial recipe for warm start      |
| `specs/coffee-science.md`   | Constraint definitions and rationale        |
| `specs/data-models.md`      | Recipe schema for parameter ranges          |
| `optuna`                    | Bayesian optimization framework             |
| `lightgbm`                  | Underlying prediction model                 |

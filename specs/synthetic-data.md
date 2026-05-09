# Synthetic Data Generation Specification

## 1. Overview

BrewMatch uses synthetic data to train the taste prediction model and populate the demo user experience. This document specifies how synthetic data is generated, validated, and structured. The synthetic data must be realistic enough to train a model that generalizes to real brew outcomes while being transparently artificial.

---

## 2. Data Requirements

### 2.1 Volume Targets

| Data Type               | Target Volume            | Purpose                             |
| ----------------------- | ------------------------ | ----------------------------------- |
| Synthetic ratings       | 5,000 - 10,000 rows      | Training the taste prediction model |
| Curated recipes         | 50 - 80 entries          | Recipe knowledge base               |
| Virtual users           | 100 - 200 profiles       | Collaborative filtering and demo    |
| Expert-labeled pairings | 50 - 80 rows             | Validation and calibration          |
| Demo user brews         | 15 rows (Alex's history) | Demo mode pre-seeded data           |

### 2.2 Row Schema

Each synthetic row represents a single brew event:

```
{
    "user_id": str,
    "bean_profile": {
        "origin_country": str,
        "origin_region": str | null,
        "process": str,
        "roast_level": str,
        "flavor_notes": [str],
        "flavor_clusters": [str],
        "variety": str | null,
        "altitude_min_m": int | null,
        "altitude_max_m": int | null
    },
    "recipe_params": {
        "dose_g": float,
        "ratio": float,
        "grind_setting": int,
        "water_temp_c": float,
        "bloom_time_s": int,
        "total_time_s": int,
        "pour_count": int
    },
    "rating": int,  // 1-10
    "directional_flags": [str],  // subset of valid flags
    "timestamp": str  // ISO-8601
}
```

---

## 3. Generation Strategy

### 3.1 Response Surface from Extraction Theory

The core of synthetic data generation is a parameter-response surface derived from coffee science (`specs/coffee-science.md`).

**Base quality function:**

Given bean profile B and recipe parameters R, compute an "ideal extraction score" based on how well the parameters match the bean:

```python
def extraction_quality_score(bean: BeanProfile, recipe: RecipeParams) -> float:
    """
    Returns a score in [0, 1] representing how well the recipe parameters
    match the bean's ideal extraction, based on coffee science.
    """
    score = 0.5  # baseline

    # Roast-Temperature alignment
    roast_temp_score = compute_roast_temp_alignment(bean.roast_level, recipe.water_temp_c)
    score += 0.20 * roast_temp_score

    # Grind-Time alignment
    grind_time_score = compute_grind_time_alignment(recipe.grind_setting, recipe.total_time_s)
    score += 0.15 * grind_time_score

    # Ratio quality (centered around 15.5-16.5)
    ratio_score = 1.0 - abs(recipe.ratio - 16.0) / 3.0
    score += 0.10 * max(0, ratio_score)

    # Dose reasonableness (14-18g is ideal for single cup V60)
    dose_score = 1.0 - abs(recipe.dose_g - 16.0) / 6.0
    score += 0.05 * max(0, dose_score)

    # Process-Grind alignment
    process_grind_score = compute_process_grind_alignment(bean.process, recipe.grind_setting)
    score += 0.10 * process_grind_score

    return clip(score, 0.0, 1.0)
```

**Alignment functions:**

| Function                                  | Optimal Range | Penalties                                     |
| ----------------------------------------- | ------------- | --------------------------------------------- |
| `roast_temp_alignment(light, temp)`       | temp 93-98C   | Penalty for each degree below 93              |
| `roast_temp_alignment(dark, temp)`        | temp 85-93C   | Penalty for each degree above 93              |
| `grind_time_alignment(fine, time)`        | time 150-210s | Penalty for each 10s above 210                |
| `grind_time_alignment(coarse, time)`      | time 240-330s | Penalty for each 10s below 240                |
| `process_grind_alignment(natural, grind)` | grind 5-8     | Natural processed benefits from coarser grind |

### 3.2 Rating Generation

The rating is derived from the extraction quality score with noise and user-specific bias:

```python
def generate_rating(quality_score: float, user: VirtualUser, noise_std: float = 0.8) -> int:
    """
    Generate a rating in [1, 10] from quality score, user bias, and noise.
    """
    # Base rating from quality (maps [0, 1] to [3, 9])
    base_rating = 3.0 + quality_score * 6.0

    # User bias (generosity vs harshness)
    biased_rating = base_rating + user.rating_bias

    # User preference alignment (does this bean match their taste?)
    preference_bonus = compute_preference_alignment(user, bean_profile)
    biased_rating += preference_bonus * 1.5

    # Gaussian noise
    noisy_rating = biased_rating + np.random.normal(0, noise_std)

    # Clip and round
    return int(round(clip(noisy_rating, 1, 10)))
```

**Noise levels by data quality tier:**

| Tier                       | `noise_std` | Rationale                                       |
| -------------------------- | ----------- | ----------------------------------------------- |
| Expert-labeled             | 0.3         | Experts rate consistently                       |
| Virtual user (calibrated)  | 0.8         | Realistic human noise                           |
| Virtual user (exploratory) | 1.2         | Higher noise for unusual parameter combinations |

### 3.3 Directional Flag Generation

Flags are generated from the gap between the recipe's parameters and the bean's ideal parameters:

```python
def generate_directional_flags(bean: BeanProfile, recipe: RecipeParams, rating: int) -> list[str]:
    flags = []
    if rating >= 7:
        return flags  # Good brews don't get flags

    # Check underextraction indicators
    if is_underextracted(bean, recipe):
        if random() < 0.6:
            flags.append("too_sour")
        if random() < 0.3:
            flags.append("too_weak")

    # Check overextraction indicators
    if is_overextracted(bean, recipe):
        if random() < 0.6:
            flags.append("too_bitter")
        if random() < 0.3:
            flags.append("too_harsh")

    # Astringency from severe overextraction
    if rating <= 3 and is_overextracted(bean, recipe):
        if random() < 0.4:
            flags.append("astringent")

    return flags

def is_underextracted(bean, recipe):
    # Low temp for light roast, coarse grind with short time, low ratio
    temp_too_low = (bean.roast_level in ("light", "medium-light") and recipe.water_temp_c < 91)
    grind_time_mismatch = (recipe.grind_setting >= 7 and recipe.total_time_s < 200)
    ratio_too_high = recipe.ratio >= 17.5
    return temp_too_low or grind_time_mismatch or ratio_too_high

def is_overextracted(bean, recipe):
    # High temp for dark roast, fine grind with long time, low ratio
    temp_too_high = (bean.roast_level in ("dark", "medium-dark") and recipe.water_temp_c > 95)
    grind_time_mismatch = (recipe.grind_setting <= 3 and recipe.total_time_s > 250)
    ratio_too_low = recipe.ratio <= 14.5
    return temp_too_high or grind_time_mismatch or ratio_too_low
```

---

## 4. Virtual Expert Panel

### 4.1 Expert Profiles

Generate 3-5 virtual coffee experts with distinct but consistent rating styles.

| Expert                              | Specialty           | Rating Bias | Preference                              | Noise |
| ----------------------------------- | ------------------- | ----------- | --------------------------------------- | ----- |
| "Expert A" - SCA judge              | Balanced assessment | +0.0        | Prefers 18-20% extraction               | 0.3   |
| "Expert B" - Light roast specialist | Favors brightness   | +0.5        | Prefers light roasts, berry/citrus      | 0.3   |
| "Expert C" - Traditional cupper     | Favors body         | -0.3        | Prefers medium/dark, chocolate/nutty    | 0.3   |
| "Expert D" - Modern barista         | Favors clarity      | +0.2        | Prefers clean, tea-like, complex        | 0.4   |
| "Expert E" - Home brewer            | Forgiving           | +0.8        | Generally rates higher, wider tolerance | 0.5   |

### 4.2 Expert Labeling Protocol

For each bean-recipe pairing in the validation set:

1. Each expert generates an independent rating.
2. Final label = mean of all expert ratings (rounded to nearest integer).
3. If expert disagreement > 2 points on the 1-10 scale, flag as "controversial" (these rows are kept but marked in metadata).

---

## 5. Virtual User Generator

### 5.1 User Profile Generation

Generate 100-200 virtual users with distinct taste profiles.

**Distribution of experience levels:**

| Level        | Proportion | Rating Behavior                                         |
| ------------ | ---------- | ------------------------------------------------------- |
| Beginner     | 30%        | Higher noise (1.0), narrower preference range           |
| Intermediate | 50%        | Standard noise (0.8), moderate preference strength      |
| Advanced     | 20%        | Lower noise (0.6), strong preferences, rates critically |

**User taste profile dimensions:**

| Dimension              | Distribution                   | Effect on Ratings                                    |
| ---------------------- | ------------------------------ | ---------------------------------------------------- |
| `roast_preference`     | Uniform over 5 roast levels    | +1 bonus for matching roast, -1 penalty for opposite |
| `preferred_clusters`   | 2-4 clusters randomly selected | +0.5 bonus per matching cluster                      |
| `rating_bias`          | Normal(0, 0.8)                 | Global generosity/harshiness                         |
| `acidity_tolerance`    | Uniform(-1, 1)                 | Bonus/penalty for acidic beans                       |
| `body_preference`      | Uniform(-1, 1)                 | Bonus/penalty for full-bodied beans                  |
| `sweetness_preference` | Uniform(-1, 1)                 | Bonus/penalty for sweet beans                        |

### 5.2 Brew History Generation

For each virtual user, generate a brew history of 0-30 brews:

1. **Early brews (1-5):** Random parameter selections within valid ranges. Ratings follow the response surface with high noise. This simulates the "exploration" phase.
2. **Mid brews (6-15):** Parameters begin to cluster around the user's preference region. Lower noise. This simulates the "learning" phase.
3. **Late brews (16+):** Parameters tightly clustered. Lowest noise. Occasional exploratory brews (10% chance). This simulates the "exploitation" phase.

### 5.3 Demo User "Alex"

Alex is a specific virtual user with a hand-crafted profile for demonstration purposes.

| Attribute              | Value                         |
| ---------------------- | ----------------------------- |
| `user_id`              | "demo-alex-001"               |
| `experience_level`     | "intermediate"                |
| `roast_preference`     | "light"                       |
| `preferred_clusters`   | ["Berry", "Citrus", "Floral"] |
| `rating_bias`          | +0.3                          |
| `acidity_tolerance`    | +0.5                          |
| `body_preference`      | -0.2                          |
| `sweetness_preference` | +0.3                          |

Alex's 15 brew history is generated using the response surface with noise_std=0.7, covering a progression from exploration to exploitation. The last 5 brews should show ratings consistently above 7.0 to demonstrate personalization effectiveness.

---

## 6. Recipe Knowledge Base Generation

### 6.1 Curated Recipes (from real sources)

Manually encode 30-50 recipes from well-known sources (Hoffmann, Kasuya, Rao, Barista Hustle, Onyx). Each recipe is stored as a JSON file per `specs/data-models.md` Section 1. All recipes must be pour-over methods only (V60, Kalita Wave, Origami).

### 6.2 Generated Recipe Variations

From each curated recipe, generate 0-1 variations by systematically perturbing 1-2 parameters. The total knowledge base (curated + variations) must not exceed 80 recipes. Variation count is capped per the formula: `max_variations = min(1, 80 - total_curated)`. Target: 50-80 total.

| Variation Type    | Parameter Changed | Delta                | Purpose                      |
| ----------------- | ----------------- | -------------------- | ---------------------------- |
| Temperature shift | `water_temp_c`    | +/- 2C               | Test temperature sensitivity |
| Grind shift       | `grind_setting`   | +/- 2                | Test grind sensitivity       |
| Ratio shift       | `ratio`           | +/- 1.0              | Test ratio sensitivity       |
| Time shift        | `total_time_s`    | +/- 30s              | Test time sensitivity        |
| Combined          | 2 parameters      | Small deltas on both | Test interaction effects     |

**Recipe IDs for variations:** `{source_recipe_id}-var-{n}` (e.g., `hoffmann-v60-classic-var-1`).

### 6.3 Validation Against Constraints

Every generated recipe must pass validation against `specs/data-models.md` Section 1:

1. `water_total_g == sum(pours[].water_g)` (within 0.1g tolerance).
2. `ratio == water_total_g / dose_g` (within 0.1 tolerance).
3. `total_time_s >= last_pour.time_offset_s + 30`.
4. All parameters within valid ranges.

---

## 7. Validation Protocol

### 7.1 Statistical Validation

| Check                        | Method                           | Pass Criterion                                       |
| ---------------------------- | -------------------------------- | ---------------------------------------------------- |
| Rating distribution          | Histogram + Shapiro-Wilk         | Roughly normal, centered 5-7                         |
| Parameter distributions      | Histogram per parameter          | Roughly uniform within valid ranges                  |
| Rating-parameter correlation | Spearman correlation             | Expected direction (per coffee-science.md) confirmed |
| Expert agreement             | Inter-class correlation (ICC)    | ICC > 0.6 across expert panel                        |
| User diversity               | t-SNE of user preference vectors | Users cluster but with spread                        |

### 7.2 Domain Validation

| Check                                                      | Method                         | Pass Criterion                        |
| ---------------------------------------------------------- | ------------------------------ | ------------------------------------- |
| Light roast + high temp rated higher than light + low temp | Grouped mean comparison        | Mean difference > 0.5 points          |
| Dark roast + low temp rated higher than dark + high temp   | Grouped mean comparison        | Mean difference > 0.5 points          |
| Optimal extraction parameters rated highest                | Response surface peak analysis | Peak in 18-22% extraction yield range |
| Expert ratings more consistent than user ratings           | Variance comparison            | Expert variance < user variance       |

### 7.3 Model Validation

After training the taste prediction model on synthetic data:

| Check                                         | Pass Criterion                                 |
| --------------------------------------------- | ---------------------------------------------- |
| RMSE on synthetic test set                    | < 1.5                                          |
| Feature importance aligns with coffee science | Temperature, grind, roast among top 5 features |
| Cold-start performance                        | RMSE < 2.0 without user features               |
| No systematic bias by roast level             | RMSE within 0.3 across all roast levels        |

---

## 8. Output Files

| File                | Path                               | Format                | Purpose                                   |
| ------------------- | ---------------------------------- | --------------------- | ----------------------------------------- |
| Synthetic ratings   | `data/synthetic/ratings.csv`       | CSV                   | Training data                             |
| Virtual users       | `data/synthetic/users.json`        | JSON                  | User profiles for collaborative filtering |
| Expert labels       | `data/synthetic/expert_labels.csv` | CSV                   | Validation set                            |
| Curated recipes     | `data/recipes/*.json`              | JSON (one per recipe) | Knowledge base                            |
| Demo user data      | `data/synthetic/demo_alex.json`    | JSON                  | Demo mode seeding                         |
| Generation metadata | `data/synthetic/metadata.json`     | JSON                  | Random seeds, counts, validation results  |

---

## 9. Reproducibility

| Control                   | Value                   | Purpose                           |
| ------------------------- | ----------------------- | --------------------------------- |
| Random seed               | 42 (configurable)       | Reproducible synthetic data       |
| NumPy seed                | Set at generation start | Reproducible array operations     |
| Generation timestamp      | Recorded in metadata    | Audit trail                       |
| Generation script version | Recorded in metadata    | Track changes to generation logic |

Running the generation script with the same seed must produce identical data files.

---

## 10. Edge Cases

| Case                                                | Handling                                                     |
| --------------------------------------------------- | ------------------------------------------------------------ |
| Rating clips to 1 or 10                             | Record in metadata; ensure < 5% of ratings are at boundaries |
| User with all same roast                            | Valid; represents a user with strong preference              |
| Recipe with unusual parameters (e.g., 1 pour, 360s) | Include; represents real variation                           |
| Expert disagreement > 3 points                      | Keep row, flag as "controversial"                            |
| Generation produces < 5000 rows                     | Log warning; generation parameters may be too restrictive    |

---

## 11. Dependencies

| Dependency                  | Purpose                                                   |
| --------------------------- | --------------------------------------------------------- |
| `specs/coffee-science.md`   | Parameter-response surface theory, constraint definitions |
| `specs/data-models.md`      | Recipe and BeanProfile schemas                            |
| `specs/taste-prediction.md` | Feature engineering requirements                          |
| `specs/personalization.md`  | User taste profile schema, directional flag definitions   |
| `specs/user-interface.md`   | Demo user "Alex" requirements                             |
| `numpy`                     | Random number generation, distributions                   |
| `pandas`                    | Data manipulation and CSV output                          |

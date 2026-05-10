# Coffee Science Foundations Specification

## 1. Overview

This document specifies the coffee extraction theory that underpins parameter constraints, interaction effects, and diagnostic rules throughout the BrewMatch system. All domain-specific rules in other specs reference this document as the authority.

---

## 2. Extraction Theory

### 2.1 Extraction Yield

Extraction yield is the percentage of coffee solids dissolved into the brew water.

| Metric          | Value     | Source                             |
| --------------- | --------- | ---------------------------------- |
| Optimal range   | 18% - 22% | Specialty Coffee Association (SCA) |
| Underextraction | < 18%     | Sour, weak, lacking sweetness      |
| Overextraction  | > 22%     | Bitter, harsh, astringent          |

**Extraction yield formula (approximate):**

```
extraction_yield % = (TDS % * brewed_coffee_g) / dose_g * 100
```

Where:

- TDS = Total Dissolved Solids (measured by refractometer)
- `brewed_coffee_g` = final beverage weight (less than `water_total_g` due to absorption)
- `dose_g` = dry coffee weight

**Approximate water absorption:** coffee grounds absorb approximately 2x their weight in water. So:

```
brewed_coffee_g ≈ water_total_g - (dose_g * 2)
```

### 2.2 Strength (TDS)

| Target    | Range             | Description            |
| --------- | ----------------- | ---------------------- |
| SCA ideal | 1.15% - 1.45% TDS | Pour-over target range |
| Weak      | < 1.15%           | Watery, thin           |
| Strong    | > 1.45%           | Heavy, intense         |

**TDS formula:**

```
TDS % = (dose_g * extraction_yield) / brewed_coffee_g * 100
```

For the system, we use extraction yield as the primary metric (not TDS) because it directly relates to taste quality.

---

## 3. Parameter Effects on Extraction

### 3.1 Individual Parameter Effects

| Parameter                   | Direction               | Effect on Extraction           | Taste Impact                            |
| --------------------------- | ----------------------- | ------------------------------ | --------------------------------------- |
| **Grind finer**             | grind_setting decreases | Increases (more surface area)  | More extraction, toward bitter          |
| **Grind coarser**           | grind_setting increases | Decreases (less surface area)  | Less extraction, toward sour            |
| **Temperature up**          | water_temp_c increases  | Increases (faster dissolution) | More extraction, toward bitter          |
| **Temperature down**        | water_temp_c decreases  | Decreases                      | Less extraction, toward sour            |
| **Time longer**             | total_time_s increases  | Increases (more contact time)  | More extraction, toward bitter          |
| **Time shorter**            | total_time_s decreases  | Decreases                      | Less extraction, toward sour            |
| **Ratio up** (more water)   | ratio increases         | Increases (more solvent)       | More extraction; also dilutes           |
| **Ratio down** (less water) | ratio decreases         | Decreases                      | Less extraction; more concentrated      |
| **Dose up**                 | dose_g increases        | Decreases per-gram extraction  | Stronger but potentially underextracted |
| **Dose down**               | dose_g decreases        | Increases per-gram extraction  | Weaker but potentially overextracted    |

### 3.2 Grind Setting Scale

| Setting | Category | Description            | Typical for V60          |
| ------- | -------- | ---------------------- | ------------------------ |
| 1-3     | Fine     | Table salt consistency | Dark roasts, short brews |
| 4-6     | Medium   | Sand consistency       | Most V60 recipes         |
| 7-10    | Coarse   | Sea salt / raw sugar   | Light roasts, long brews |

---

## 4. Parameter Interaction Effects

### 4.1 Grind x Temperature

The most important interaction. Grind determines surface area; temperature determines extraction speed.

| Grind         | Low Temp (85-89C)      | Medium Temp (90-94C)                    | High Temp (95-100C)                          |
| ------------- | ---------------------- | --------------------------------------- | -------------------------------------------- |
| Fine (1-3)    | Balanced but slow      | Fast extraction, risk of overextraction | Severe overextraction, harsh                 |
| Medium (4-6)  | Underextraction likely | Balanced, sweet spot for most beans     | Moderate extraction, works for light roasts  |
| Coarse (7-10) | Severe underextraction | Underextraction, sour                   | Balanced for light roasts, long brews needed |

**Constraint for optimization:** Fine grind + high temperature should be penalized (overextraction risk). Coarse grind + low temperature should be penalized (underextraction risk).

### 4.2 Grind x Time

| Grind         | Short Time (<180s)         | Medium Time (180-270s)      | Long Time (>270s)                    |
| ------------- | -------------------------- | --------------------------- | ------------------------------------ |
| Fine (1-3)    | Acceptable for dark roasts | Risk of overextraction      | Severe overextraction                |
| Medium (4-6)  | Underextraction likely     | Sweet spot                  | Slight overextraction possible       |
| Coarse (7-10) | Severe underextraction     | Acceptable for light roasts | Balanced, preferred for light roasts |

### 4.3 Ratio x Dose

```
water_total_g = dose_g * ratio
```

This is a deterministic relationship, not an independent variable. The constraint is on `water_total_g`:

| Constraint              | Range       | Rationale                            |
| ----------------------- | ----------- | ------------------------------------ |
| `water_total_g` minimum | 180g        | Minimum for V60 filter bed stability |
| `water_total_g` maximum | 400g        | V60 practical capacity               |
| `ratio` range           | 14.0 - 18.0 | SCA recommended range for pour-over  |

A ratio of 1:16 with 15g dose = 240g water. A ratio of 1:18 with 15g dose = 270g water.

### 4.4 Roast Level x Temperature

The roast level determines how easily the coffee extracts. Darker roasts are more soluble (cell structure is more broken down from longer roasting).

| Roast Level  | Recommended Temp Range | Rationale                                  |
| ------------ | ---------------------- | ------------------------------------------ |
| Light        | 92-98C                 | Dense bean, needs high energy to extract   |
| Medium-Light | 92-96C                 | Moderate density                           |
| Medium       | 91-95C                 | Balanced solubility                        |
| Medium-Dark  | 89-94C                 | High solubility, avoid overextraction      |
| Dark         | 85-93C                 | Very soluble, low temp prevents bitterness |

**Constraint for optimization:** Temperature should be inversely correlated with roast level. Light + low temp = underextraction. Dark + high temp = overextraction (bitterness, harshness).

### 4.5 Process x Grind x Temperature

| Process    | Solubility                      | Grind Suggestion | Temp Suggestion            |
| ---------- | ------------------------------- | ---------------- | -------------------------- |
| Washed     | Standard                        | Medium (4-6)     | Standard for roast         |
| Natural    | Higher (more soluble compounds) | Slightly coarser | Standard or slightly lower |
| Honey      | Higher                          | Slightly coarser | Standard                   |
| Anaerobic  | Variable (often higher)         | Medium-coarse    | Slightly lower             |
| Wet-hulled | High (low density)              | Coarser          | Lower                      |

---

## 5. SCA Brewing Control Chart

The Specialty Coffee Association's Brewing Control Chart maps extraction yield against TDS strength. BrewMatch uses this as a reference framework.

```
         STRONG
           ^
           |  [Harsh, Bitter]
    1.45%  +------------------+
           |  * OPTIMAL *     |
           |  (18-22% EY,     |
           |   1.15-1.45% TDS)|
    1.15%  +------------------+
           |  [Sour, Weak]    |
           +------------------+-----> EXTRACTION YIELD
           18%              22%
         UNDER               OVER
         EXTRACTED          EXTRACTED
```

**Application in BrewMatch:**

- The taste prediction model implicitly learns the relationship between parameters and extraction quality from training data.
- The optimization constraints encode the relationships that keep parameters in the "optimal" zone.
- The diagnosis page maps directional flags to regions of this chart.

---

## 6. Tetsu Kasuya 4:6 Method Theory

The 4:6 method is one of the most well-known structured pour-over recipes. It divides the total water into two phases:

### 6.1 Principle

| Phase     | Water Portion | Purpose                                           | Controls                    |
| --------- | ------------- | ------------------------------------------------- | --------------------------- |
| First 40% | 4 parts of 10 | Flavor determination (acidity, sweetness balance) | Acidity vs sweetness ratio  |
| Last 60%  | 6 parts of 10 | Strength determination                            | Overall concentration / TDS |

### 6.2 Acid-Sweetness Control

Within the first 40% (4 pours):

| Pour pattern                    | Effect                         |
| ------------------------------- | ------------------------------ |
| Equal pours (10-10-10-10)       | Balanced acidity and sweetness |
| More in first pours (15-10-7-8) | Higher acidity, brighter cup   |
| More in later pours (8-7-10-15) | More sweetness, rounder cup    |

### 6.3 Application in BrewMatch

- The 4:6 method is one of the recipe sources in the knowledge base.
- The pour schedule generator in `specs/recipe-optimization.md` uses a simplified version of this theory for multi-pour recipes (4+ pours).
- The method demonstrates that pour structure affects taste, not just total parameters.

---

## 7. Diagnostic Rules

These rules map directional feedback flags to parameter adjustments. They are used in the diagnosis page (`specs/user-interface.md`) and the directional phase of personalization (`specs/personalization.md`).

### 7.1 Flag-to-Extraction Mapping

| Flag         | Extraction Zone            | Primary Parameter to Adjust | Secondary Adjustments                     |
| ------------ | -------------------------- | --------------------------- | ----------------------------------------- |
| `too_sour`   | Underextracted             | Increase temperature        | Finer grind, longer time, lower ratio     |
| `too_bitter` | Overextracted              | Decrease temperature        | Coarser grind, shorter time, higher ratio |
| `too_weak`   | Low strength               | Increase dose               | Lower ratio, finer grind                  |
| `too_harsh`  | Overextracted + channeling | Coarser grind               | Lower temperature, gentler pouring        |
| `astringent` | Overextracted (late-stage) | Shorter time                | Lower temperature, coarser grind          |

### 7.2 ML-Powered Diagnosis Algorithm

The diagnosis engine uses the taste predictor (`specs/taste-prediction.md`) to rank candidate adjustments rather than applying rules blindly. This makes the diagnosis ML-powered: the model decides which adjustment will most improve the predicted score for this specific bean-user-recipe combination.

**Algorithm: Perturb-and-Score**

1. **Collect candidates.** For each reported directional flag, look up the primary and secondary adjustments from the table above. Each candidate is a (parameter, delta) pair. For example, `too_sour` produces candidates: (temperature, +2), (grind_setting, -1), (total_time_s, +15), (ratio, -0.5).

2. **Perturb and predict.** For each candidate, create a copy of the current recipe with that single parameter changed. Run each through the taste predictor to get `predicted_score(candidate)`.

3. **Rank by improvement.** Score each candidate as `delta = predicted_score(candidate) - predicted_score(current_recipe)`. Rank candidates by delta descending.

4. **Select recommendation.** The top-ranked candidate is the primary recommendation. Show the top 2-3 candidates with their predicted improvements on the diagnosis page.

5. **Roast-aware weighting.** Apply a multiplier to candidates based on roast-specific diagnoses (Section 7.3). For a light roast with `too_sour`, temperature adjustments get a 1.5x bonus because the coffee-science table identifies temperature as the likely root cause. This narrows the candidate set before the model ranks them.

**Why this is ML, not rules:** The rules define the _candidate set_ (which parameters are worth trying). The taste predictor decides _which candidate wins_ for this specific bean and user. Two users with the same "too sour" flag but different beans will get different recommendations because the model's prediction surface is bean-aware. A light-roast Ethiopian will rank "increase temperature" higher than "finer grind" because the model has learned that temperature matters more for light roasts.

**Cold-start behavior:** For a user with zero brew history, the taste predictor uses only bean features and recipe parameters (no user bias terms). The diagnosis is bean-aware but user-agnostic — still more specific than generic rules because the model's response surface varies by bean profile. After 3+ brews, user bias terms activate, making the diagnosis personalized.

**Compound flags:** When multiple flags appear (e.g., `too_sour + too_weak`), collect candidates from both flags, deduplicate, then rank all candidates by predicted improvement. The top candidate addresses the combined signal. If the best candidates from each flag conflict (one says increase temp, other says decrease), the model's prediction surface resolves the conflict based on which direction improves the score more.

### 7.3 Compound Diagnoses

When multiple flags appear together:

| Flags                  | Diagnosis                      | Suggested Fix                                 |
| ---------------------- | ------------------------------ | --------------------------------------------- |
| too_sour + too_weak    | Severe underextraction         | Increase temp, increase dose, finer grind     |
| too_bitter + too_harsh | Severe overextraction          | Decrease temp, coarser grind, shorter time    |
| too_sour + too_bitter  | Channeling (uneven extraction) | Coarser grind for more even flow, medium temp |
| too_weak + too_bitter  | Mixed extraction (channeling)  | Coarser grind, slower pouring                 |

### 7.3 Roast-Specific Diagnoses

| Roast  | Common Issue                | Likely Parameter Problem                |
| ------ | --------------------------- | --------------------------------------- |
| Light  | Tastes sour, tea-like, weak | Temperature too low or time too short   |
| Light  | Tastes balanced but thin    | Ratio too high (too much water)         |
| Medium | Tastes flat, boring         | Grind too coarse, not enough extraction |
| Dark   | Tastes bitter, ashy         | Temperature too high                    |
| Dark   | Tastes harsh, metallic      | Grind too fine or time too long         |

---

## 8. Key Numbers Reference

| Constant                     | Value                     | Context                           |
| ---------------------------- | ------------------------- | --------------------------------- |
| SCA optimal extraction yield | 18-22%                    | Primary quality metric            |
| SCA optimal TDS (pour-over)  | 1.15-1.45%                | Strength metric                   |
| V60 filter capacity          | ~400g water               | Hard constraint                   |
| Coffee water absorption      | ~2x dose weight           | Used for yield estimation         |
| Light roast density          | ~0.30 g/mL                | Affects grind and extraction rate |
| Dark roast density           | ~0.25 g/mL                | Less dense = more soluble         |
| Bloom time                   | 15-45 seconds             | Degassing period                  |
| Standard V60 ratio           | 1:15 to 1:17              | Most recipes in this range        |
| Hoffmann standard            | 15g, 1:16, 93C, ~3:30     | Reference recipe                  |
| Kasuya 4:6 standard          | 15g, 1:15, 5 pours, ~3:30 | Reference recipe                  |

---

## 9. Relationship to Other Specs

| Spec                     | How It Uses This Document                                                          |
| ------------------------ | ---------------------------------------------------------------------------------- |
| `taste-prediction.md`    | Interaction features encode grind x temp, grind x time, roast x temp relationships |
| `recipe-optimization.md` | Hard and soft constraints encode parameter interaction boundaries                  |
| `personalization.md`     | Directional flag processing maps to diagnostic rules                               |
| `user-interface.md`      | Diagnosis page explanations reference extraction theory                            |
| `synthetic-data.md`      | Response surface generation uses parameter-effect relationships                    |

# Personalization Specification

## 1. Overview

BrewMatch is a diagnosis-first product. Personalization is not the front-door feature — it is the emergent benefit. The user's primary interaction is: "I brewed this and it tasted too sour, what do I change?" Every diagnosis round produces data. Over time, this data accumulates into a user taste profile that improves starting recipes and makes future diagnoses faster and more accurate.

BrewMatch is bean-aware from brew 1 — the system uses the extracted bean profile and coffee science rules immediately. User-awareness layers on progressively as feedback accumulates. The personalization layer handles this progression, transitioning through four phases as user data grows. At low data, the system relies on coffee science rules for diagnosis. At high data, it uses learned user preferences to pre-adjust recipes and provide history-informed diagnoses.

---

## 2. Personalization Phases

### 2.1 Phase Overview

| Phase         | Brews | Data Source                  | Model                              | User-Facing Behavior                         |
| ------------- | ----- | ---------------------------- | ---------------------------------- | -------------------------------------------- |
| Bean-Aware    | 0     | Onboarding quiz              | Global model + quiz priors         | "Based on your preferences, try this recipe" |
| Directional   | 1-4   | Quiz + few ratings           | Global model + linear user bias    | "Adjusting based on your feedback"           |
| Content-Based | 5-9   | Moderate rating history      | LightGBM with user features        | "Learning your taste profile"                |
| Full Hybrid   | 10+   | Rich history + similar users | Full model + collaborative signals | "Personalized for your taste"                |

### 2.2 Phase Transition Logic

Phase is determined by `user.stats.total_brews` from `specs/data-models.md` Section 3.

```python
def get_personalization_phase(total_brews: int) -> str:
    if total_brews == 0:
        return "bean_aware"
    elif total_brews < 5:
        return "directional"
    elif total_brews < 10:
        return "content_based"
    else:
        return "full_hybrid"
```

Phase transitions are automatic and immediate. There is no "lock-in" -- the system upgrades as soon as the threshold is crossed.

---

## 3. Onboarding Quiz (Bean-Aware Phase)

### 3.1 Quiz Flow

Presented to every new user before their first brew recommendation.

**Question 1: Roast preference**
"How do you like your coffee?"

| Option                     | Maps To                                                                                  |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| "Bright, fruity, tea-like" | `roast_preference = "light"`, `preferred_clusters = ["Citrus", "Floral", "Berry"]`       |
| "Balanced, sweet, smooth"  | `roast_preference = "medium"`, `preferred_clusters = ["Sweet", "Balanced", "Chocolate"]` |
| "Bold, rich, full-bodied"  | `roast_preference = "dark"`, `preferred_clusters = ["Chocolate", "Roasted", "Nutty"]`    |

**Question 2: Flavor preference** (select up to 3)

Present 15 flavor cluster names as clickable tags. User selects 1-3.

| Clusters                           | Signal                         |
| ---------------------------------- | ------------------------------ |
| "Berry, Citrus, Floral"            | Prefers acidity and brightness |
| "Chocolate, Sweet, Nutty"          | Prefers sweetness and body     |
| "Tropical, Stone Fruit, Fermented" | Prefers complexity and funk    |
| Any combination                    | Direct taste signal            |

**Question 3: Experience level**

| Option                                     | Maps To                             |
| ------------------------------------------ | ----------------------------------- |
| "I'm new to specialty coffee"              | `experience_level = "beginner"`     |
| "I brew regularly and know the basics"     | `experience_level = "intermediate"` |
| "I experiment with parameters and recipes" | `experience_level = "advanced"`     |

**Question 4: Dripper equipment** (determines recipe parameter space)

| Option        | Maps To         |
| ------------- | --------------- |
| "V60"         | V60 recipes     |
| "Kalita Wave" | Kalita recipes  |
| "Origami"     | Origami recipes |

Multi-select allowed. Users who select multiple drippers will choose which one at brew time.

### 3.2 Bean-Aware Recipe Selection

From the quiz responses, construct a synthetic "virtual bean" and retrieve recipes:

1. Create a pseudo-bean profile from quiz answers:
   - `roast_level` = quiz roast preference
   - `flavor_clusters` = quiz preferred clusters
   - `origin_country` = "unknown"
   - `process` = "unknown"
2. Retrieve top 3 recipes via `specs/recipe-retrieval.md` using this pseudo-bean.
3. Present as "Recommended starting recipes based on your preferences."

### 3.3 Bean-Aware Default Learned Preferences

| Preference              | Default       | Source             |
| ----------------------- | ------------- | ------------------ |
| `acidity_bias`          | 0.0 (neutral) | No data yet        |
| `body_bias`             | 0.0           | No data yet        |
| `sweetness_bias`        | 0.0           | No data yet        |
| `preferred_temp_range`  | [91.0, 95.0]  | SCA standard range |
| `preferred_ratio_range` | [15.0, 17.0]  | SCA standard range |

---

## 4. Directional Phase (1-4 Brews)

### 4.1 Feedback Processing

After each brew, the user provides:

1. **Thumbs up/down** (required): `feedback.thumbs_up` from `data-models.md` Section 3.
2. **Optional rating** (1-10): `feedback.score`.
3. **Optional directional flags**: `feedback.directional_flags` from the set {"too_sour", "too_bitter", "too_weak", "too_harsh", "astringent"}.

### 4.2 Directional Flag Processing

When a directional flag is present, the diagnosis engine runs the Perturb-and-Score algorithm (`specs/coffee-science.md` Section 7.2) to select the best parameter adjustment. The flag also produces a preference bias adjustment:

Each flag produces a preference adjustment:

| Flag         | `acidity_bias` delta | `body_bias` delta | `sweetness_bias` delta | Parameter adjustment hint                       |
| ------------ | -------------------- | ----------------- | ---------------------- | ----------------------------------------------- |
| `too_sour`   | -0.1                 | 0.0               | 0.0                    | Increase temp, decrease ratio, or increase time |
| `too_bitter` | 0.0                  | -0.1              | 0.0                    | Decrease temp, increase ratio, or decrease time |
| `too_weak`   | 0.0                  | +0.1              | 0.0                    | Increase dose, decrease ratio, or finer grind   |
| `too_harsh`  | -0.05                | -0.1              | +0.05                  | Decrease temp, coarser grind                    |
| `astringent` | 0.0                  | 0.0               | -0.1                   | Decrease time or temp                           |

**Delta application rule:** Each flag adjusts biases by its delta. Biases are clipped to [-1.0, 1.0]. Multiple flags can combine.

### 4.3 Linear User Bias

With 1-4 brews, the per-user bias is a weighted average of residuals:

```python
def compute_directional_bias(user_ratings, predictions):
    residuals = [actual - predicted for actual, predicted in zip(user_ratings, predictions)]
    if not residuals:
        return 0.0
    # Weight recent feedback more heavily
    weights = [0.5 ** (len(residuals) - 1 - i) for i in range(len(residuals))]
    weighted_mean = sum(w * r for w, r in zip(weights, residuals)) / sum(weights)
    return 0.3 * weighted_mean  # conservative: only 30% correction
```

The 0.3 factor prevents the model from overreacting to noisy early feedback.

### 4.4 Parameter Adjustment Hints

Based on directional flags from the most recent brew, suggest specific parameter changes for the next brew:

| Flag         | Suggested Adjustment                                                                      |
| ------------ | ----------------------------------------------------------------------------------------- |
| `too_sour`   | "Try increasing water temperature by 1-2 degrees or extending brew time by 15-30 seconds" |
| `too_bitter` | "Try lowering water temperature by 1-2 degrees or using a slightly coarser grind"         |
| `too_weak`   | "Try using more coffee (increase dose by 0.5g) or a finer grind setting"                  |
| `too_harsh`  | "Try a coarser grind or lower temperature"                                                |
| `astringent` | "Try a shorter brew time or lower temperature"                                            |

These hints are educational (this is a demo for an ML course) and directly traceable to extraction theory in `coffee-science.md`.

---

## 5. Content-Based Phase (5-9 Brews)

### 5.1 Feature Activation

At 5+ brews, the full set of user history features from `specs/taste-prediction.md` Section 3.3 becomes available and meaningful:

- `user_avg_rating`
- `user_rating_count`
- `user_roast_pref_encoded`
- `user_temp_pref`
- `user_grind_pref`
- `user_ratio_pref`
- `user_acidity_bias`
- `user_body_bias`
- `user_sweetness_bias`

### 5.2 Per-User Bias Upgrade

The linear bias transitions from the conservative 0.3 factor to a fuller estimate:

```python
def compute_content_bias(user_ratings, predictions, timestamps):
    residuals = [actual - predicted for actual, predicted in zip(user_ratings, predictions)]
    # Exponential decay: recent brews matter more
    decay = 0.9
    ages = [max(timestamps) - t for t in timestamps]
    weights = [decay ** (age / median_age) for age in ages]
    return sum(w * r for w, r in zip(weights, residuals)) / sum(weights)
```

No more 0.3 damping -- the model has enough data to trust the bias direction.

### 5.3 Learned Preference Extraction

From the user's highly-rated brews (rating >= user_avg_rating), extract concrete preference ranges:

```python
def extract_learned_preferences(high_rated_brews):
    return LearnedPreferences(
        preferred_temp_range=[
            percentile(brews.water_temp_c, 25),
            percentile(brews.water_temp_c, 75)
        ],
        preferred_ratio_range=[
            percentile(brews.ratio, 25),
            percentile(brews.ratio, 75)
        ],
        acidity_bias=mean(brews.acidity_signals),
        body_bias=mean(brews.body_signals),
        sweetness_bias=mean(brews.sweetness_signals),
    )
```

These are stored in `user.learned_preferences` per `data-models.md` Section 3.

---

## 6. Full Hybrid Phase (10+ Brews)

### 6.1 Collaborative Filtering at Flavor-Cluster Level

At 10+ brews, the system can find similar users based on flavor cluster preferences.

**Similarity metric**: Cosine similarity between users' flavor cluster preference vectors (15-dimensional, one dimension per cluster, value = average rating given to brews with that cluster).

```python
def find_similar_users(target_user, all_users, top_k=5):
    target_vector = user_cluster_preference_vector(target_user)
    similarities = []
    for other in all_users:
        if other.user_id == target_user.user_id:
            continue
        if other.stats.total_brews < 5:
            continue  # skip users without enough data
        other_vector = user_cluster_preference_vector(other)
        sim = cosine_similarity(target_vector, other_vector)
        similarities.append((other, sim))
    return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]
```

### 6.2 Collaborative Score Blending

The final predicted score blends content-based and collaborative predictions:

```python
def hybrid_score(content_score, collaborative_score, user_brew_count):
    # Blend weight shifts toward collaborative as data grows
    collab_weight = min(0.3, (user_brew_count - 10) * 0.03)
    content_weight = 1.0 - collab_weight
    return content_weight * content_score + collab_weight * collaborative_score
```

| Brews | Collaborative Weight | Rationale                                       |
| ----- | -------------------- | ----------------------------------------------- |
| 10    | 0.0                  | Just entered hybrid; not enough similarity data |
| 15    | 0.15                 | Starting to trust similar users                 |
| 20    | 0.30                 | Full collaborative contribution                 |
| 20+   | 0.30                 | Capped; content-based remains primary           |

### 6.3 Collaborative Filtering Limitations

- For the demo (single-user Streamlit app), collaborative filtering is simulated using the synthetic user population from `specs/synthetic-data.md`.
- In production, this would query a real user database.
- The demo's "Alex" user (see `specs/user-interface.md`) has a pre-seeded history of 15 brews, demonstrating the full hybrid phase.

---

## 7. Feedback Processing Pipeline

### 7.1 Feedback Flow

```
User submits feedback (thumbs + optional rating + optional flags)
    |
    v
Validate feedback schema
    |
    v
Update user brew history
    |
    v
Recompute user biases and learned preferences
    |
    v
Update taste prediction model (per-user bias only; global model not retrained)
    |
    v
Return updated recommendations
```

### 7.2 Feedback Validation

| Check               | Rule                                            | On Failure                            |
| ------------------- | ----------------------------------------------- | ------------------------------------- |
| `thumbs_up`         | Must be boolean                                 | Reject                                |
| `score`             | Null or int in [1, 10]                          | Reject                                |
| `directional_flags` | Each must be in valid set                       | Filter invalid flags, keep valid ones |
| Duplicate brew      | Same `brew_id` cannot have two feedback entries | Reject                                |

### 7.3 Bias Update Frequency

User biases and learned preferences are recomputed after every new feedback submission. This is inexpensive (O(n) in user history size) and keeps the profile current.

---

## 8. Output Contract

```python
@dataclass
class PersonalizationState:
    phase: str                           # "bean_aware", "directional", "content_based", "full_hybrid"
    user_bias: float                     # Current per-user bias
    learned_preferences: LearnedPreferences  # Extracted preferences
    similar_users_count: int             # Number of similar users found (0 unless full_hybrid)
    confidence: float                    # 0.0 - 1.0, how confident the system is
    next_milestone: str                  # Human-readable: "Rate 3 more brews to unlock X"
```

### Guarantees

1. Phase is always one of the four valid strings.
2. `user_bias` is in [-2.0, 2.0] (capped to prevent extreme adjustments).
3. `confidence` increases monotonically with brew count (never decreases).
4. `similar_users_count` is 0 for phases before `full_hybrid`.

---

## 9. Confidence Model

| Phase         | Confidence Range | Formula                           |
| ------------- | ---------------- | --------------------------------- |
| Bean-aware    | 0.1 - 0.3        | Based on quiz completeness        |
| Directional   | 0.3 - 0.5        | 0.3 + 0.05 \* min(brews, 4)       |
| Content-based | 0.5 - 0.7        | 0.5 + 0.04 \* (brews - 5)         |
| Full hybrid   | 0.7 - 0.9        | 0.7 + 0.01 \* min(brews - 10, 20) |

Confidence is displayed to the user as "Low / Medium / High" and in the evaluation dashboard.

---

## 10. Edge Cases

| Case                                                       | Handling                                                                                       |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| User skips onboarding quiz                                 | Use default neutral preferences; phase = "bean_aware" with confidence 0.1                      |
| User gives only thumbs up/down, never numeric ratings      | Derive rating from thumbs: up=7, down=3; bias still computed                                   |
| User rates everything 10 or everything 1                   | Cap user bias at +/- 1.5; signal high variance to evaluation dashboard                         |
| User gives contradictory flags ("too_sour" + "too_bitter") | Process both; net effect may be neutral. Log for diagnosis view.                               |
| User has 50+ brews of the same recipe                      | Profile converges to that recipe's parameter space; collaborative filtering provides diversity |
| No similar users found in hybrid phase                     | Fall back to content-based only; `similar_users_count = 0`                                     |

---

## 11. Dependencies

| Dependency                       | Purpose                                                  |
| -------------------------------- | -------------------------------------------------------- |
| `specs/data-models.md` Section 3 | User taste profile schema, personalization phases        |
| `specs/taste-prediction.md`      | Prediction model, user features, per-user bias           |
| `specs/recipe-retrieval.md`      | Bean-aware recipe selection                              |
| `specs/recipe-optimization.md`   | Personalized parameter optimization                      |
| `specs/synthetic-data.md`        | Virtual user population for collaborative filtering demo |
| `specs/user-interface.md`        | Onboarding quiz UI, feedback capture UI                  |
| `specs/coffee-science.md`        | Parameter adjustment hint rationale                      |

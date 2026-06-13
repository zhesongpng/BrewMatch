# Data Models Specification

## 1. Recipe

The recipe entity is the core of the knowledge base. Each recipe represents a complete brewing method with all parameters specified.

A recipe record serves **two distinct purposes** at once, which is why its fields fall into two groups:

1. **Brewable parameters** — the values a person follows to make the cup: `dose_g`, `water_total_g`, `ratio`, `grind_setting`, `water_temp_c`, `bloom_time_s`, `total_time_s`, the structured `pours` schedule, and the natural-language `instructions`. Unlike free-text recipe sites, the pour schedule is stored as discrete, machine-checkable steps (`pours[]`) with enforced invariants (see Validation Rules), so the same record can be brewed by a human and reasoned over by the optimizer.
2. **Matching metadata** — the `suitable_for` block (`roast_levels`, `origins`, `processes`, `flavor_profiles`). This group is what makes BrewMatch a recommendation engine rather than a recipe library: it lets the retriever pick the right starting recipe for a given bean, instead of asking the user to browse. A recipe with no `suitable_for` block is unusable for matching — it is a required field.

### Schema

| Field                          | Type   | Required | Constraints                     | Description                                  |
| ------------------------------ | ------ | -------- | ------------------------------- | -------------------------------------------- |
| `recipe_id`                    | string | YES      | Unique, kebab-case              | Identifier (e.g., "hoffmann-v60-classic")    |
| `source`                       | string | YES      | Non-empty                       | Attribution (e.g., "James Hoffmann")         |
| `source_url`                   | string | NO       | Valid URL                       | Link to original source                      |
| `method`                       | enum   | YES      | "V60", "Kalita Wave", "Origami" | Brew method / dripper type                   |
| `dose_g`                       | float  | YES      | 12.0 - 35.0                     | Coffee dose in grams                         |
| `water_total_g`                | float  | YES      | 180.0 - 600.0                   | Total water weight in grams                  |
| `ratio`                        | float  | YES      | 14.0 - 18.0                     | Water:coffee ratio (e.g., 16.67 = 1:16.67)   |
| `grind_setting`                | int    | YES      | 1 - 10                          | Relative grind (1=very fine, 10=very coarse) |
| `water_temp_c`                 | float  | YES      | 85.0 - 100.0                    | Water temperature in Celsius                 |
| `bloom_time_s`                 | int    | YES      | 15 - 90                         | Bloom/degassing time in seconds              |
| `total_time_s`                 | int    | YES      | 120 - 360                       | Total brew time in seconds                   |
| `pours`                        | array  | YES      | 1-6 elements                    | Ordered list of pour steps                   |
| `suitable_for.roast_levels`    | array  | YES      | Subset of roast enum            | Compatible roast levels                      |
| `suitable_for.origins`         | array  | YES      | Non-empty                       | Compatible origin countries                  |
| `suitable_for.processes`       | array  | YES      | Subset of process enum          | Compatible processing methods                |
| `suitable_for.flavor_profiles` | array  | YES      | Flavor cluster names            | Compatible flavor profiles (at least 1)      |
| `instructions`                 | string | YES      | Non-empty                       | Natural language brewing instructions        |

### Pour Step Schema

| Field           | Type  | Required | Constraints             |
| --------------- | ----- | -------- | ----------------------- |
| `step`          | int   | YES      | 1-indexed, sequential   |
| `time_offset_s` | int   | YES      | 0 for bloom, increasing |
| `water_g`       | float | YES      | 10.0 - 200.0            |

### Validation Rules

- `water_total_g` must be within 5% of sum of all `pours[].water_g` (allows for filter rinse water)
- `ratio` must equal `water_total_g / dose_g` (within rounding tolerance 0.1)
- `total_time_s` must be >= last pour's `time_offset_s + 30`
- `grind_setting` 1-3 = fine, 4-6 = medium, 7-10 = coarse
- Each `suitable_for` array must have at least 1 element

---

## 2. Bean Profile

### Schema

| Field                   | Type   | Required | Constraints                                                         |
| ----------------------- | ------ | -------- | ------------------------------------------------------------------- |
| `origin_country`        | string | YES      | Known coffee-producing country                                      |
| `origin_region`         | string | NO       | Sub-region (e.g., "Yirgacheffe", "Huila")                           |
| `process`               | enum   | YES      | "washed", "natural", "honey", "anaerobic", "wet-hulled", "unknown"  |
| `roast_level`           | enum   | YES      | "light", "medium-light", "medium", "medium-dark", "dark", "unknown" |
| `flavor_notes`          | array  | NO       | Individual descriptors from WCR lexicon                             |
| `flavor_clusters`       | array  | YES      | Mapped to 15-cluster SCA-based taxonomy                             |
| `variety`               | string | NO       | Cultivar (e.g., "Gesha", "Bourbon", "SL28")                         |
| `altitude_min_m`        | int    | NO       | Minimum altitude in meters                                          |
| `altitude_max_m`        | int    | NO       | Maximum altitude in meters                                          |
| `source_text`           | string | YES      | Original free-text description                                      |
| `extraction_confidence` | float  | NO       | 0.0 - 1.0, confidence of LLM extraction                             |
| `roaster`               | string | NO       | Roaster name; set when the bean comes from a saved bag              |
| `name`                  | string | NO       | Coffee / product name (e.g. "Ethiopia Guji"); set from a saved bag  |

`roaster` and `name` default to `None`. Brew records created before these fields
existed deserialize with both as `None` (backward-compatible).

### Flavor Clusters (15 top-level)

1. Floral (jasmine, chamomile, rose, lavender)
2. Berry (blueberry, strawberry, raspberry, blackberry)
3. Citrus (bergamot, lemon, grapefruit, lime, orange)
4. Stone Fruit (peach, apricot, plum, cherry)
5. Tropical (mango, pineapple, passion fruit, guava)
6. Sweet (caramel, honey, vanilla, brown sugar, maple syrup)
7. Chocolate (milk chocolate, dark chocolate, cocoa, mocha)
8. Nutty (almond, hazelnut, peanut, walnut, pecan)
9. Spice (cinnamon, clove, nutmeg, pepper, cardamom)
10. Roasted (tobacco, leather, pipe tobacco, toasted bread)
11. Vegetal (herbal, grassy, green tea, olive)
12. Tea-like (earl grey, oolong, black tea, green tea)
13. Fermented (winey, whisky, rum, overripe fruit)
14. Syrupy (molasses, treacle, maple, agave)
15. Balanced (clean, smooth, round, well-integrated)

---

## 2.5 Coffee Bag

A saved bag of coffee the user owns. Entered once when a bag is opened, then
picked for each brew until it runs out. Implemented as the `CoffeeBag` dataclass
in `src/data_models.py`.

### Schema

| Field          | Type        | Required | Constraints / Default | Description                                         |
| -------------- | ----------- | -------- | --------------------- | --------------------------------------------------- |
| `bag_id`       | string      | YES      | Non-empty             | Identifier (12-char hex via `create_bag_id()`)      |
| `roaster`      | string      | YES      | Non-empty             | Roaster name                                        |
| `name`         | string      | YES      | Non-empty             | Coffee / product name (e.g. "Ethiopia Guji")        |
| `bean_profile` | BeanProfile | YES      | —                     | Full bean details carried by the bag                |
| `bag_size_g`   | float       | NO       | > 0; default 250.0    | Bag weight in grams; drives the "running low" count |
| `date_opened`  | string      | NO       | default `None`        | ISO date the bag was opened                         |
| `active`       | bool        | NO       | default `True`        | False once the bag is marked finished               |

### Validation Rules

- `bag_id`, `roaster` (non-whitespace), and `name` (non-whitespace) are required.
- `bag_size_g` must be > 0.

---

## 3. User Taste Profile

### Schema

| Field                                       | Type           | Description                                                               |
| ------------------------------------------- | -------------- | ------------------------------------------------------------------------- |
| `user_id`                                   | UUID           | Anonymous identifier                                                      |
| `onboarding`                                | object         | Quiz responses at sign-up                                                 |
| `onboarding.preferred_clusters`             | array          | 1-5 flavor cluster selections                                             |
| `onboarding.roast_preference`               | enum           | Stated roast level preference                                             |
| `onboarding.experience_level`               | enum           | "beginner", "intermediate", "advanced"                                    |
| `brew_history`                              | array          | Chronological list of brew records                                        |
| `brew_history[].brew_id`                    | UUID           | Unique brew identifier                                                    |
| `brew_history[].timestamp`                  | ISO-8601       | When the brew was made                                                    |
| `brew_history[].bean_profile`               | object         | Bean profile at time of brew                                              |
| `brew_history[].recipe_used`                | object         | Recipe parameters used (the dose-scaled recipe actually brewed)           |
| `brew_history[].bag_id`                     | string \| null | Bag this brew drew from; null for a one-off brew                          |
| `brew_history[].actual_dose_g`              | float \| null  | Real dose weighed (mirror of `recipe_used.dose_g`); drives running-low    |
| `brew_history[].feedback.thumbs_up`         | boolean        | Primary feedback signal                                                   |
| `brew_history[].feedback.score`             | int            | Optional 1-10 rating                                                      |
| `brew_history[].feedback.directional_flags` | array          | Optional: "too_sour", "too_bitter", "too_weak", "too_harsh", "astringent" |
| `learned_preferences`                       | object         | Model-derived preferences                                                 |
| `learned_preferences.acidity_bias`          | float          | -1.0 to 1.0 (negative = prefers less acidic)                              |
| `learned_preferences.body_bias`             | float          | -1.0 to 1.0                                                               |
| `learned_preferences.sweetness_bias`        | float          | -1.0 to 1.0                                                               |
| `learned_preferences.preferred_temp_range`  | [float, float] | Celsius range                                                             |
| `learned_preferences.preferred_ratio_range` | [float, float] | Water:coffee range                                                        |
| `stats.total_brews`                         | int            | Count of all brews                                                        |
| `stats.avg_score`                           | float          | Average rating given                                                      |
| `stats.favorite_origins`                    | array          | Top 3 most-rated origin countries                                         |
| `stats.favorite_clusters`                   | array          | Top 3 flavor clusters from highly-rated brews                             |

### Personalization Phases

| Phase                            | Brews | Model                              | Data Source       |
| -------------------------------- | ----- | ---------------------------------- | ----------------- |
| Bean-Aware (Pre-Personalization) | 0     | Onboarding quiz → global best-fit  | Quiz answers only |
| Directional                      | 1-4   | Global model + linear user bias    | Few ratings       |
| Content-Based                    | 5-9   | LightGBM with user features        | Moderate ratings  |
| Full Hybrid                      | 10+   | Full model + collaborative signals | Rich history      |

---

## 4. Relationships

```
User 1──N BrewHistory 1──1 BeanProfile
                   1──1 Recipe
                   1──1 Feedback
```

- A User has many BrewHistory entries
- Each BrewHistory links to one BeanProfile and one Recipe (snapshot at brew time)
- Each BrewHistory has one Feedback
- Each BrewHistory MAY link to one CoffeeBag (`brew_history.bag_id`, nullable);
  brews logged before bags existed and one-off brews have no bag
- A User has many CoffeeBags
- Recipes are shared (many users can brew the same recipe)
- BeanProfiles can be shared (many users can have the same beans)
- Feedback belongs to exactly one BrewHistory

---

## 5. Storage

The user database runs on SQLite locally (`data/users.db`) and on PostgreSQL
(Supabase) for the hosted app; `src/app/db.py` issues dialect-portable DDL/queries
against both. Tables: `users`, `brew_history`, `sessions`, `coffee_bags`.

| Data Type               | Storage                     | Format                                                                        |
| ----------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| Recipes                 | `data/recipes/` directory   | JSON files, one per recipe                                                    |
| Bean Profiles           | In-memory during session    | Extracted on-the-fly by LLM                                                   |
| User Taste Profiles     | SQLite / PostgreSQL `users` | Row per user with JSON columns                                                |
| Brew History            | `brew_history` table        | Row per brew; `bag_id` + `actual_dose_g` link a brew to its bag and real dose |
| Coffee Bags             | `coffee_bags` table         | Row per bag; bean details in `bean_json`, `active` as INTEGER 0/1             |
| Synthetic Training Data | `data/synthetic/`           | CSV files                                                                     |
| External Reference Data | `data/external/`            | CSV files (CQI, etc.)                                                         |
| Model Artifacts         | `models/`                   | Pickle/joblib files                                                           |

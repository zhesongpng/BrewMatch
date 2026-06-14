# User Interface Specification (Streamlit Web App)

## 1. Overview

BrewMatch is a Streamlit web application — a coffee troubleshooting tool. The user gets a starting recipe, brews, reports what went wrong, and gets a specific diagnosis with a prescription. The UI presents all five ML components through this diagnosis-first workflow. The UI is designed for a single-user demo experience, not multi-tenant SaaS.

---

## 2. Technology Stack

| Component | Choice                                  | Rationale                                               |
| --------- | --------------------------------------- | ------------------------------------------------------- |
| Framework | Streamlit                               | Rapid prototyping, Python-native, suitable for ML demos |
| Layout    | Wide mode, sidebar navigation           | Maximize content area for brew parameters               |
| State     | `st.session_state`                      | Session-scoped state for demo flow                      |
| Storage   | SQLite via `data/users.db`              | Persistent user data across sessions                    |
| Charts    | Altair / Plotly                         | Interactive visualizations for evaluation dashboard     |
| Styling   | Streamlit default theme with custom CSS | Minimal customization, focus on functionality           |

---

## 3. Application Pages

### 3.1 Page Map

| Page                  | Route         | Purpose                                                         |
| --------------------- | ------------- | --------------------------------------------------------------- |
| Landing               | `/`           | App introduction and entry point                                |
| Onboarding            | `/onboarding` | New user quiz (4 questions: roast, flavor, experience, dripper) |
| Your Coffees          | `/bean-input` | Pick a saved bag to brew with, or add a new bag                 |
| Recipe Recommendation | `/recommend`  | View recommended recipes + optimized parameters                 |
| Brew Session          | `/brew`       | Follow brewing instructions, record feedback                    |
| History               | `/history`    | View past brews, ratings, and taste profile evolution           |
| Diagnosis             | `/diagnosis`  | Parameter-specific diagnosis of brew issues                     |
| Demo Mode             | `/demo`       | Pre-seeded "Alex" user for live demonstration                   |
| Evaluation Dashboard  | `/evaluation` | ML pipeline metrics and performance                             |

---

## 4. Page Specifications

### 4.1 Landing Page

**Layout:**

```
+----------------------------------------------+
|            BrewMatch                          |
|   Your Coffee Troubleshooting Tool            |
|                                               |
|   [Get Started]  [Demo Mode]                  |
|                                               |
|   -- How It Works --                          |
|   1. Tell us about your beans                 |
|   2. Get a starting recipe                    |
|   3. Brew and report what went wrong          |
|   4. Get a specific diagnosis and fix         |
+----------------------------------------------+
```

**Behavior:**

- "Get Started" navigates to `/onboarding` if no user exists, or to `/bean-input` if returning user.
- "Demo Mode" navigates to `/demo` with the pre-seeded "Alex" user.

### 4.2 Onboarding Page

**Layout:** Sequential 4-step form (one question per screen for clarity).

**Step 1: Roast preference**

```
+----------------------------------------------+
|   Step 1 of 4: How do you like your coffee?  |
|                                               |
|   ( ) Bright, fruity, tea-like               |
|   ( ) Balanced, sweet, smooth                |
|   ( ) Bold, rich, full-bodied                |
|                                               |
|                          [Next -->]           |
+----------------------------------------------+
```

**Step 2: Flavor preference**

```
+----------------------------------------------+
|   Step 2 of 4: Pick up to 5 flavor profiles  |
|                                               |
|   [Floral]  [Berry]  [Citrus]  [Stone Fruit]  |
|   [Tropical] [Sweet] [Chocolate] [Nutty]      |
|   [Spice]  [Roasted] [Vegetal] [Tea-like]     |
|   [Fermented] [Syrupy] [Balanced]             |
|                                               |
|   Selected: Berry, Citrus, Floral             |
|                                               |
|              [<-- Back]  [Next -->]           |
+----------------------------------------------+
```

**Step 3: Experience level**

```
+----------------------------------------------+
|   Step 3 of 4: What's your brewing experience?|
|                                               |
|   ( ) I'm new to specialty coffee             |
|   ( ) I brew regularly and know the basics    |
|   ( ) I experiment with parameters and recipes|
|                                               |
|              [<-- Back]  [Next -->]           |
+----------------------------------------------+
```

**Step 4: Equipment selection**

```
+----------------------------------------------+
|   Step 4 of 4: What dripper(s) do you use?   |
|                                               |
|   [x] V60                                    |
|   [ ] Kalita Wave                            |
|   [ ] Origami                                |
|                                               |
|   Select all that apply.                      |
|                                               |
|              [<-- Back]  [Start Brewing!]     |
+----------------------------------------------+
```

**Validation:** Cannot proceed past Step 1 without a selection. Cannot finish without at least 1 flavor cluster. Cannot finish without at least 1 dripper selected. On completion, store in `user.onboarding` and navigate to `/bean-input`.

### 4.3 Your Coffees Page (bag picker)

Implemented in `src/app/pages/bean_input.py` (route name `bean_input`). A user
saves a bag of coffee once when they open it, then picks it for each brew until
it runs out — instead of re-entering the bean every cup.

**Layout:**

```
+----------------------------------------------+
|   Your Coffees                                |
|   Pick a bag to brew with, or add a new one.  |
|                                               |
|   Your open bags                              |
|   +-----------------------------------------+ |
|   | Onyx Coffee Lab — Ethiopia Guji         | |
|   | Ethiopia · ≈22 brews left   [Brew this] | |
|   +-----------------------------------------+ |
|                                               |
|   v Add a new bag                             |
|     Roaster*  Coffee name*  Bag size (g)      |
|     [ manual bean form fields ]               |
|     [Save bag]                                |
+----------------------------------------------+
```

**Behavior:**

1. List the user's active bags as cards (`Roaster — Coffee`, origin, and an
   estimated "≈N brews left"). When there are none, show a prompt to add the
   first bag and open the add-bag form by default.
2. "Brew this" on a card sets the bag's bean as `current_bean`, records
   `current_bag_id`, and navigates to `/recommend`.
3. "Add a new bag" reveals a form: roaster, coffee name, bag size (default
   250 g), plus the bean fields. "Save bag" validates, saves the bag, and
   selects it for brewing.
4. "Finished" on a card marks the bag empty (`active = 0`) so it drops off the
   list.
5. Roaster and coffee name are attached to the bean so they flow into history
   and diagnosis.

Bags are persisted per user via `src.app.db` (coffee_bags table), so they
survive logout and reappear on next login. The picker is login-gated, so a
`user_id` is always present when it renders.

The "≈N brews left" estimate uses a nominal dose until real per-brew doses are
tracked; running-low becomes exact once doses are captured at brew time.

**Add-bag form fields:**

| Field           | Widget            | Options                                                |
| --------------- | ----------------- | ------------------------------------------------------ |
| Roaster\*       | `st.text_input`   | Free text (required)                                   |
| Coffee name\*   | `st.text_input`   | Free text (required)                                   |
| Bag size (g)    | `st.number_input` | 50–2000, default 250                                   |
| Origin country  | `st.selectbox`    | Common origin list + "Other"                           |
| Region          | `st.text_input`   | Free text                                              |
| Process         | `st.selectbox`    | washed, natural, honey, anaerobic, wet-hulled, unknown |
| Roast level     | `st.selectbox`    | light through dark                                     |
| Flavor clusters | `st.multiselect`  | 15 cluster names (at least 1)                          |
| Variety         | `st.text_input`   | Free text                                              |
| Altitude (m)    | `st.text_input`   | Single value or range                                  |

### 4.4 Recipe Recommendation Page

**Layout:**

```
+----------------------------------------------+
|   Recommended Recipes for Your Beans          |
|                                               |
|   Bean: Ethiopia Yirgacheffe (Light, Washed)  |
|   Personalization: Learning (6 brews)         |
|                                               |
|   -- Recipe 1 (Best Match) --                |
|   Hoffmann V60 Classic     Score: 8.2/10      |
|   Dose: 15g | Ratio: 1:16.5 | Grind: 5/10   |
|   Temp: 93C  | Bloom: 30s  | Time: 210s      |
|   Pours: 3     [View Full Instructions]        |
|                                               |
|   -- Recipe 2 (Alternative) --               |
|   Kasuya 4:6 Method       Score: 7.8/10      |
|   Dose: 15g | Ratio: 1:15  | Grind: 4/10    |
|   Temp: 94C  | Bloom: 45s  | Time: 240s      |
|   Pours: 5     [View Full Instructions]        |
|                                               |
|   -- Recipe 3 (Explore) --                   |
|   Rao-style High Extraction Score: 7.5/10    |
|   Dose: 18g | Ratio: 1:16  | Grind: 6/10    |
|   Temp: 95C  | Bloom: 30s  | Time: 195s      |
|   Pours: 4     [View Full Instructions]        |
|                                               |
|   -- Optimized Recipe --                      |
|   [Optimize for my taste]                     |
|   (Runs parameter optimization via Optuna)    |
|                                               |
|   [Start Brewing with Recipe 1]               |
+----------------------------------------------+
```

**Behavior:**

1. Call recipe retrieval (`specs/recipe-retrieval.md`) with the bean profile.
2. Call taste prediction (`specs/taste-prediction.md`) for each recipe to show predicted scores.
3. Display 3 recipes ranked by predicted score. Each card shows a source-tier trust badge below the attribution line: `champion` → "🏆 Championship recipe", `barista` → "☕ Pro recipe", `enthusiast` → no badge (see `data-models.md` `Recipe.source_tier`).
4. "Optimize for my taste" runs recipe optimization (`specs/recipe-optimization.md`) and shows the optimized parameters alongside the best recipe.
5. "Start Brewing" saves the selected recipe and navigates to `/brew`.

### 4.5 Brew Session Page

**Layout:**

```
+----------------------------------------------+
|   Brewing: Hoffmann V60 Classic              |
|   From your bag: Onyx — Ethiopia Guji         |
|     ≈14 brews left (218 g remaining)          |
|                                               |
|   Your Dose: [ 15.0 ] g  (water 240 g, 1:16)  |
|                                               |
|   Step 1: Rinse filter with hot water         |
|   Step 2: Add 15g ground coffee               |
|   Step 3: Bloom - Pour 30g water, wait 30s    |
|   Step 4: Pour to 100g at 0:30               |
|   Step 5: Pour to 165g at 1:15               |
|   Step 6: Pour to 250g at 2:00               |
|   Step 7: Allow to draw down until 3:30       |
|                                               |
|   [Timer: 3:30] [Start Timer]                 |
|                                               |
|   -- How did it taste? --                     |
|   Thumbs: [Up] [Down]                         |
|   Rating (optional): [---slider 1-10---]      |
|   Flags (optional):                           |
|   [ ] Too sour  [ ] Too bitter  [ ] Too weak  |
|   [ ] Too harsh [ ] Astringent                |
|   Notes (optional): [___________________]     |
|                                               |
|   [Submit Feedback]                           |
+----------------------------------------------+
```

**Behavior:**

1. Display step-by-step brewing instructions from the selected recipe.
2. An editable "Your Dose" field at the top is pre-filled with the recipe's dose.
   Changing it rescales the brewing guidance — the water total and every pour —
   by `your_dose ÷ recipe_dose`, holding the coffee-to-water ratio constant;
   grind, water temperature, bloom time, and all pour timings are unchanged. The
   field offers 12–25 g (widening to include the recipe's own dose if it falls
   outside that band); a dose that would build an out-of-range recipe is rejected
   and the original dose is shown instead.
3. When the brew came from a saved bag (a bag was picked on the Your Coffees
   screen), a line shows the bag's roaster and coffee name and "≈N brews left"
   from the real grams used so far. A one-off brew with no bag shows no such line.
4. Provide a countdown timer matching `total_time_s`.
5. Feedback is required (thumbs up/down at minimum). Rating and flags are optional.
6. On submit, save feedback to user brew history and update personalization state.
   The brew record stores the **scaled** recipe (so its dose, water, and pours
   are what was actually brewed) and mirrors the real dose into `actual_dose_g`.
   If the brew came from a bag, the bag id is stored too, so the bag's
   "running low" countdown decrements by the real dose; a no-bag brew stores a
   null bag id and nothing decrements.
7. If directional flags are present, show a brief diagnosis hint (see `/diagnosis`).
8. Navigate to `/recommend` for next brew, or `/history` to review.

### 4.6 History Page

**Layout:**

```
+----------------------------------------------+
|   Your Brewing History                        |
|                                               |
|   Total brews: 8 | Avg rating: 6.9           |
|   Personalization: Content-Based (Phase 3)    |
|   Taste Profile:                              |
|     Acidity: [====----] prefers moderate      |
|     Body:    [=======--] prefers full          |
|     Sweet:   [======---] prefers sweet         |
|                                               |
|   Favorite origins: Ethiopia, Colombia        |
|   Favorite clusters: Berry, Citrus, Floral    |
|                                               |
|   -- Recent Brews --                          |
|   #8  Ethiopia Yirgacheffe  7/10  Thumbs Up   |
|       Hoffmann V60, 15g, 1:16.5, 93C          |
|   #7  Colombia Huila       5/10  Thumbs Down  |
|       Rao Method, 18g, 1:16, 95C               |
|   ...                                         |
+----------------------------------------------+
```

**Behavior:**

1. Display `user.stats` from the taste profile.
2. Show taste preference radar chart (15 flavor clusters, weighted by rating).
3. List brews in reverse chronological order with bean, recipe, and rating.
4. Parameter trend charts: show how user's preferred temp/grind/ratio have evolved.

### 4.7 Diagnosis Page

**Layout:**

```
+----------------------------------------------+
|   Brew Diagnosis                              |
|                                               |
|   Your last brew:                             |
|   Ethiopia Yirgacheffe | Hoffmann V60        |
|   Flags: too_sour, too_weak                   |
|                                               |
|   -- What happened --                         |
|   Sourness suggests underextraction:          |
|   the coffee compounds weren't fully          |
|   dissolved. This can happen when water       |
|   is too cool, grind is too coarse, or        |
|   brew time is too short.                     |
|                                               |
|   -- Suggestions --                           |
|   1. Increase water temp by 1-2C              |
|      (was 93C, try 94-95C)                    |
|   2. Use a slightly finer grind               |
|      (was 5/10, try 4/10)                     |
|   3. Extend brew time by 15-30s               |
|      (was 210s, try 225-240s)                 |
|                                               |
|   -- Extraction Theory --                     |
|   Underextraction occurs when extraction      |
|   yield falls below 18%. Sour, weak, and      |
|   lacking sweetness are the hallmarks.        |
|   See: coffee-science.md for details.         |
|                                               |
|   [Try Again with Adjustments]                |
+----------------------------------------------+
```

**Behavior:**

1. Load the most recent brew with directional flags.
2. If the user has 0-2 prior brews: show rule-based diagnosis using bean profile + feedback flags (e.g., "Light-roast Ethiopian + too_sour typically indicates under-extraction. Try: finer grind or higher temperature."). No brew-history pattern analysis is attempted.
3. If the user has 3+ prior brews: show pattern-based diagnosis from brew history, comparing current parameters against the user's highly-rated brews.
4. Map flags to extraction theory explanations from `coffee-science.md`.
5. Suggest specific parameter adjustments based on the flag + current recipe parameters.
6. "Try Again" pre-fills `/recommend` with the adjusted parameters.

### 4.8 Demo Mode Page

**Layout:**

```
+----------------------------------------------+
|   Demo Mode: Meet Alex                        |
|                                               |
|   Alex is a coffee enthusiast who:            |
|   - Prefers light roasts with berry notes     |
|   - Has brewed 15 times over the past month   |
|   - Average rating: 7.2/10                    |
|   - Personalization: Full Hybrid (Phase 4)    |
|                                               |
|   [Explore Alex's Profile]  [Brew as Alex]    |
|                                               |
|   -- Alex's Taste Journey --                  |
|   (Timeline chart: rating vs brew number,     |
|    showing personalization improvement)       |
|                                               |
|   -- Alex's Parameter Evolution --            |
|   (Chart: preferred temp/grind/ratio over     |
|    time as the system learned preferences)    |
|                                               |
|   [Reset Demo]  [Exit Demo Mode]              |
+----------------------------------------------+
```

**Demo User "Alex" Profile:**

| Attribute            | Value                             |
| -------------------- | --------------------------------- |
| `experience_level`   | "intermediate"                    |
| `roast_preference`   | "light"                           |
| `preferred_clusters` | ["Berry", "Citrus", "Floral"]     |
| `total_brews`        | 15                                |
| `avg_score`          | 7.2                               |
| `favorite_origins`   | ["Ethiopia", "Kenya", "Colombia"] |
| `favorite_clusters`  | ["Berry", "Floral", "Citrus"]     |
| Phase                | "full_hybrid"                     |
| `acidity_bias`       | 0.3                               |
| `body_bias`          | -0.1                              |
| `sweetness_bias`     | 0.2                               |

Alex's 15 brew history is pre-generated from `specs/synthetic-data.md` and stored in SQLite.

**Behavior:**

1. Load Alex's pre-seeded profile from an in-memory SQLite database (`:memory:`). Demo mode is activated by environment variable `BREWMATCH_DEMO_MODE=true`.
2. All pages operate on Alex's profile (bean input, recommend, brew, history, diagnosis).
3. New feedback during demo is appended to Alex's in-memory profile and is lost on reload (in-memory SQLite naturally resets).
4. "Reset Demo" clears the in-memory database and re-seeds Alex's initial 15-brew state.

### 4.9 Evaluation Dashboard

**Layout:**

```
+----------------------------------------------+
|   ML Pipeline Evaluation                      |
|                                               |
|   -- Bean Extraction --                       |
|   Accuracy: 92% | Avg confidence: 0.78       |
|   [Confusion matrix: roast level accuracy]    |
|                                               |
|   -- Recipe Retrieval (RAG) --                |
|   Precision@3: 0.83 | MRR: 0.74             |
|   [Retrieval quality chart]                   |
|                                               |
|   -- Taste Prediction --                      |
|   RMSE: 1.32 | MAE: 0.98 | R-sq: 0.56       |
|   [Predicted vs actual scatter plot]          |
|   [Feature importance bar chart]              |
|                                               |
|   -- Recipe Optimization --                   |
|   Avg improvement: +0.7 points               |
|   Trials to convergence: 12 avg              |
|   [Convergence curve: score vs trials]        |
|                                               |
|   -- Personalization --                       |
|   Bean-aware RMSE: 1.85 | Hybrid RMSE: 1.28  |
|   Improvement: 31%                            |
|   [RMSE vs number of user ratings]            |
+----------------------------------------------+
```

**Behavior:**

1. Loads pre-computed evaluation metrics from `models/evaluation_results.json`.
2. All charts are generated on page load from test-set predictions stored at evaluation time.
3. This page demonstrates the full ML pipeline quality for the course submission.
4. Metrics are computed per `specs/evaluation.md`.

---

## 5. Navigation

### 5.1 Sidebar

```
+-------------------+
|  BrewMatch        |
|                   |
|  [Home]           |
|  [New Brew]  -->  |
|    - Bean Input   |
|    - Recommend    |
|    - Brew         |
|    - Feedback     |
|  [History]        |
|  [Diagnosis]      |
|  [Demo Mode]      |
|  [Evaluation]     |
|                   |
|  -- User Info --  |
|  Phase: Content   |
|  Brews: 8         |
|  Avg: 6.9/10      |
+-------------------+
```

### 5.2 Flow Order

The primary flow follows the brew lifecycle:

```
Landing -> Onboarding (first time) -> Bean Input -> Recommend -> Brew -> Feedback -> Recommend (next brew)
                                                                                      |
                                                                       History <-- --+
                                                                       Diagnosis <-+
```

Users can navigate freely via the sidebar, but the primary flow is sequential.

---

## 6. State Management

### 6.1 Session State Keys

| Key                     | Type       | Purpose                                        |
| ----------------------- | ---------- | ---------------------------------------------- |
| `user_id`               | str (UUID) | Current user identifier                        |
| `current_bean`          | dict       | Currently entered bean profile                 |
| `current_recipes`       | list[dict] | Retrieved recipe recommendations               |
| `selected_recipe`       | dict       | Recipe chosen for current brew                 |
| `optimized_params`      | dict       | Optimized parameters (if optimization was run) |
| `personalization_phase` | str        | Current personalization phase                  |
| `demo_mode`             | bool       | Whether running in demo mode                   |

### 6.2 Persistence

| Data          | Storage                                                   | Persistence         |
| ------------- | --------------------------------------------------------- | ------------------- |
| User profile  | SQLite (`data/users.db`)                                  | Across sessions     |
| Brew history  | SQLite                                                    | Across sessions     |
| Session state | `st.session_state`                                        | Within session only |
| Demo data     | In-memory SQLite (`:memory:`, `BREWMATCH_DEMO_MODE=true`) | Resets on reload    |

---

## 7. Error Handling

| Error                 | UI Response                                                                        |
| --------------------- | ---------------------------------------------------------------------------------- |
| Bean extraction fails | "Could not analyze your description. Please try entering details manually."        |
| No recipes found      | "No matching recipes found. Try a different bean description."                     |
| Optimization fails    | "Optimization did not improve on the baseline recipe. Using the best match as-is." |
| Model not loaded      | "The ML models have not been trained yet. Please run the training pipeline first." |
| SQLite error          | "Could not save your data. Your session data will not persist."                    |

---

## 8. Performance Requirements

| Metric                                          | Target       |
| ----------------------------------------------- | ------------ |
| Page load time                                  | < 2 seconds  |
| Bean extraction (LLM call)                      | < 5 seconds  |
| Recipe retrieval                                | < 2 seconds  |
| Optimization (50 trials)                        | < 10 seconds |
| Feedback processing                             | < 1 second   |
| Total end-to-end (bean input to recommendation) | < 10 seconds |

---

## 9. Dependencies

| Dependency                     | Purpose                           |
| ------------------------------ | --------------------------------- |
| `specs/data-models.md`         | All entity schemas                |
| `specs/bean-extraction.md`     | Bean input page behavior          |
| `specs/recipe-retrieval.md`    | Recommendation page data source   |
| `specs/taste-prediction.md`    | Score display, feature importance |
| `specs/recipe-optimization.md` | Optimization UI                   |
| `specs/personalization.md`     | Phase display, quiz flow          |
| `specs/coffee-science.md`      | Diagnosis page explanations       |
| `specs/evaluation.md`          | Evaluation dashboard metrics      |
| `specs/synthetic-data.md`      | Demo user data                    |
| `streamlit`                    | Web framework                     |
| `altair` or `plotly`           | Charts                            |

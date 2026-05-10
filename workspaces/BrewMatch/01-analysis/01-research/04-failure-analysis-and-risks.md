# Failure Point Analysis and Risk Assessment

## Executive Summary

BrewMatch faces three dominant risk clusters: (1) the "chronic not acute" product trap, where users tolerate mediocre coffee and lack urgency to adopt a tool; (2) a cold-start data wall, where meaningful personalization requires 10+ rated brews per user but the product must deliver value on brew one; and (3) course-project scope creep, where five distinct ML components across a semester timeline invites shallow implementation of each. The single highest-leverage mitigation for all three is a staged demo strategy that treats the course submission as the primary "user" and uses simulated data to demonstrate the ML pipeline end-to-end, while the product design narrows v1 to a single brew method (pour-over only) and a single input modality (manual text entry, no OCR).

Overall complexity: **Moderate** (score 16/30 -- driven primarily by the course-timeline constraint, not technical difficulty).

---

## Risk Register

| ID   | Risk                                                                                                      | Category  | Likelihood | Impact | Level       | Mitigation                                                                                                                                                                                                                   |
| ---- | --------------------------------------------------------------------------------------------------------- | --------- | ---------- | ------ | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-01 | Cold start delivers generic recipes for first 10+ brews; users perceive no value vs. free YouTube recipes | Product   | High       | High   | Critical    | Bootstrap with global "best fit" recipes tagged by bean profile similarity; deliver a compelling single-session experience before personalization kicks in                                                                   |
| R-02 | "Chronic not acute" pain -- users never form the habit of rating brews; feedback loop starves             | Product   | High       | High   | Critical    | Reduce rating to 2 taps (thumbs up/down + one optional tag); send no reminders (annoying); accept 30% rating rate as success                                                                                                 |
| R-03 | Course timeline insufficient for 5 ML components at demo quality                                          | Project   | High       | High   | Critical    | Stage demo; use synthetic data; prioritize taste prediction + optimization as the ML showcase; treat RAG retrieval and bean extraction as LLM integration demonstrations                                                     |
| R-04 | Overfitting on per-user sparse data (1-2 ratings/day, ~10-30 data points by semester end)                 | ML        | High       | Medium | Major       | Use global model as strong prior; per-user model only adjusts last layer; regularize aggressively; demo with simulated 100+ rating history                                                                                   |
| R-05 | Recipe knowledge base (50-80 recipes) is laborious to curate and may lack coverage for less common beans  | Data      | Medium     | High   | Major       | Start with 50-80 high-quality recipes from 5-6 canonical sources (Hoffmann, Rao, Kasuya); seed remaining via LLM-generated variants constrained by validated parameter ranges                                                |
| R-06 | Bean profile extraction from free text inconsistent -- roaster descriptions use non-standard terminology  | Data      | High       | Medium | Major       | Define a fixed extraction schema (origin, process, roast_level, flavor_notes[]) and validate via structured output; accept 80% accuracy for v1                                                                               |
| R-07 | LLM dependency -- bad recipe generation, hallucinated parameters, or API outage breaks core flow          | Technical | Medium     | High   | Major       | Validate all LLM outputs against parameter constraints before surfacing; cache generated recipes; maintain a fallback set of static recipes                                                                                  |
| R-08 | Flavor descriptor normalization ("bright" vs "clean" vs "juicy") unreliable across users                  | ML        | Medium     | Medium | Significant | Map to a fixed vocabulary of ~15 flavor clusters via SCA wheel; LLM normalizes user input to cluster labels; do not attempt user-defined descriptors in v1                                                                   |
| R-09 | Feedback quality low -- users rate inconsistently (same coffee, different ratings on different days)      | Data      | High       | Low    | Significant | Use directional flags (too sour/too bitter) as primary signal, not the 1-10 score; score is secondary; accept noise and average over multiple ratings                                                                        |
| R-10 | Recipe fatigue -- users find 2-3 good recipes and stop using the app                                      | Product   | High       | Medium | Significant | This is the retention risk acknowledged in the brief; for course demo, not relevant. For product, solve via "new bean" trigger and seasonal/limited-release bean push                                                        |
| R-11 | Espresso exclusion alienates significant portion of specialty coffee audience                             | Product   | Medium     | Low    | Minor       | Acknowledge in demo as deliberate v1 scope; pour-over (V60, Kalita, Origami) covers the methods most amenable to parameter-space optimization                                                                                |
| R-12 | OCR on coffee bag labels unreliable (glossy bags, artistic fonts, non-English)                            | Technical | High       | Low    | Minor       | De-prioritize photo input for v1; manual text entry is reliable and fast (3 fields: origin, process, roast level)                                                                                                            |
| R-13 | Mobile vs web platform choice wrong for brew-time context (wet hands, near kettle)                        | Technical | Medium     | Low    | Minor       | Web app for v1 (course demo); recipe displayed before brewing; no need to interact during brew. Mobile is a product concern, not a demo concern                                                                              |
| R-14 | Training data for taste prediction unavailable without real users                                         | Data      | High       | High   | Critical    | Generate synthetic preference dataset from expert-annotated recipe-bean pairings; use Coffee Research Institute SCA flavor wheel as ground truth for cluster mapping                                                         |
| R-15 | Evaluation of "personalization works" has no ground truth in demo setting                                 | Project   | Medium     | High   | Major       | Define proxy metrics: (a) predicted score correlation with simulated user preferences >0.7, (b) optimization converges within 5 iterations on held-out beans, (c) cold-start recipe matches expert baseline >70% of the time |

---

## 1. Data Failure Points

### 1.1 Cold Start Problem: First 10 Brews

**Assessment: Critical for product, manageable for course demo.**

The brief acknowledges this directly ("Cold start cliff" in section 8.3). The personalization layer (section 6.5) defines three stages: global best-fit (0 brews), directional preferences (3-5 brews), full personalized prediction (10+ brews). This means the first 10 brews -- roughly 1-2 weeks of daily use -- the product delivers recommendations that are essentially "best guess from global recipes."

**How damaging is this?** For a real product launch, it is potentially fatal. The user's first experience with the app is the most generic. They compare it against a Hoffmann YouTube recipe (free, trusted, bean-specific) and find no advantage. They churn before reaching brew 10.

**Mitigation:**

- The "global best-fit" recipe must be genuinely good -- grounded in the curated knowledge base with bean-profile matching, not a random pick. If the first recipe works well, the user has no reason to leave; personalization is the upgrade, not the value proposition.
- For the course demo, this is a non-issue. Demo with a simulated user who already has 15+ ratings and show the personalization delta. Then reset to zero ratings and show the cold-start recipe quality (which should be good on its own).

**Recommendation:** Invert the value proposition framing. The app's pitch is not "it gets better over time" (which admits it starts weak). The pitch is "the best recipe for YOUR beans, right now" (which the knowledge base + RAG delivers on day one). Personalization is the retention mechanism, not the acquisition hook.

### 1.2 Recipe Knowledge Base: 50-80 Recipes

**Assessment: 50-80 curated recipes is achievable from 5-6 canonical expert sources.**

Breaking down where recipes come from:

| Source                                  | Estimated Unique Recipes | Parameter Coverage                                    | Quality                                    |
| --------------------------------------- | ------------------------ | ----------------------------------------------------- | ------------------------------------------ |
| James Hoffmann (YouTube + books)        | 30-50                    | High (dose, ratio, grind, temp, time, pour structure) | Excellent -- well-documented, reproducible |
| Scott Rao (books)                       | 20-30                    | High (especially extraction theory parameters)        | Excellent -- precise, technical            |
| Tetsu Kasuya 4:6 method                 | 5-10                     | Medium (ratio-focused, less on grind/temp)            | Good -- well-defined parameter space       |
| Barista Hustle                          | 20-30                    | High                                                  | Excellent                                  |
| Onyx Coffee (published recipes)         | 15-25                    | High                                                  | Excellent                                  |
| Reddit r/coffee, r/pourover (top posts) | 30-50                    | Low-Medium (incomplete parameters)                    | Variable -- needs validation               |
| LLM-generated variants of above         | 100-300                  | Depends on constraints                                | Needs validation                           |

**The real number for high-quality, fully-parameterized recipes is 80-120 from curated sources.** Reaching 200+ requires either (a) LLM-generated variants (valid but needs constraint validation) or (b) including recipes with incomplete parameter sets (less useful for the optimization engine).

**Recommendation:** Target 80-100 curated recipes with full parameter coverage for the course demo. This is sufficient to demonstrate RAG retrieval and provides enough parameter-space coverage for meaningful optimization. Each recipe must have: dose, ratio, grind setting (relative scale), water temp, bloom time, pour structure (number of pours, timing), total time, and bean-profile tags (origin, process, roast level).

### 1.3 Bean Profile Extraction from Free Text

**Assessment: 80-85% accuracy achievable with structured LLM output. Not a blocker.**

Roaster descriptions follow semi-predictable patterns:

- "Ethiopia Yirgacheffe, washed process, light roast, notes of blueberry, jasmine, bergamot" -- this is the easy case.
- "Bright and effervescent, with a sparkling acidity reminiscent of stone fruit" -- this is the hard case (no origin/process/roast explicitly stated).

The extraction schema should be:

```
{
  "origin_region": string,          // "Ethiopia", "Colombia", "Sumatra", etc.
  "origin_subregion": string|null,  // "Yirgacheffe", "Huila", etc.
  "process": enum,                  // "washed" | "natural" | "honey" | "anaerobic" | "wet-hulled" | "unknown"
  "roast_level": enum,              // "light" | "medium-light" | "medium" | "medium-dark" | "dark" | "unknown"
  "flavor_notes": string[],         // ["blueberry", "jasmine", "bergamot"]
  "altitude": string|null,          // "1800-2000m" if provided
  "variety": string|null            // "Gesha", "Bourbon", "SL28", etc.
}
```

**Failure modes and handling:**

- Missing process/roast: Default to "unknown"; the knowledge base can still match on origin and flavor notes.
- Conflicting terminology: "fully washed" vs "washed", "dry process" vs "natural" -- standardize via a lookup table, not the LLM.
- Artistic descriptions with no technical data: LLM infers roast level from flavor description ("chocolate, nutty" -> medium-dark; "floral, citrus" -> light). Accuracy drops but the system still produces a usable profile.

**Recommendation:** Use structured JSON output from the LLM with a fixed schema. Validate that required fields are populated. Accept "unknown" as a valid value for any field. Test against 20 real roaster descriptions from Singapore roasters (Common Man, PPP, Nylon, Tiong Hoe) to measure accuracy.

### 1.4 User Feedback Quality

**Assessment: The 1-10 score is noisy; directional flags are the reliable signal.**

Coffee taste perception is inherently variable:

- Same beans, same recipe, different day: users can rate 2 points apart based on mood, food pairing, time of day.
- Users do not calibrate their scale consistently -- one person's "7" is another's "5".
- The 1-10 scale provides false precision for a sensory experience.

Directional flags ("too sour", "too bitter", "weak", "harsh") are more reliable because:

- They are binary (present/absent), reducing scale ambiguity.
- They map directly to recipe parameters (too sour -> increase extraction: finer grind, higher temp, longer time; too bitter -> decrease extraction).
- They align with the SCA extraction theory framework that professional cuppers use.

**Recommendation:** Redesign feedback capture to prioritize directional flags:

- Primary input: binary thumbs-up/thumbs-down (1 tap).
- Secondary input: optional directional tags (tap to add: too sour, too bitter, weak, harsh, astringent).
- Tertiary input: optional 1-10 score (for users who want granular control).
- The ML model should weight directional tags higher than the raw score for recipe adjustment.

---

## 2. ML Model Failure Points

### 2.1 Taste Prediction with Sparse Data

**Assessment: Per-user model is infeasible with 1-2 ratings/day in a semester timeline. Must use global model + user-specific bias terms.**

Timeline math:

- Semester: ~14 weeks. -假设 user starts immediately and rates daily: 14 \* 7 = 98 ratings maximum (unrealistic).
- Realistic for an engaged tester: 30-50 ratings over the semester.
- Cold-start phase (first 10 ratings): model has essentially no user-specific data.

A gradient-boosted tree (the brief's proposed model) typically needs 200+ samples per user to learn individual preferences reliably. At 30-50 samples, the model will overfit aggressively.

**Recommendation: Hybrid architecture:**

1. **Global model** (trained on aggregated/synthetic data): Predicts rating based on bean profile + recipe parameters. This is the workhorse -- it works for everyone from day one.
2. **User bias layer** (simple linear adjustment): After 5+ ratings, compute a per-user offset on top of the global prediction. This captures "this user rates everything 1 point lower" or "this user prefers higher extraction."
3. **Per-user fine-tuning** (gradient-boosted on user data only): After 50+ ratings, allow the model to specialize. For the course demo, this is shown with simulated data.

This architecture also solves the course demo problem: the global model is the main demonstration piece, and you can show the bias-layer adjustment with a live demo of 5 simulated ratings.

### 2.2 Recipe Optimization: 7 Constrained Parameters with Noisy Feedback

**Assessment: Converges with bounded search. Bayesian optimization is overkill for v1; grid search is sufficient and more interpretable for a demo.**

The 7 parameters and their constraints:

| Parameter      | Type       | Range                          | Notes                                                     |
| -------------- | ---------- | ------------------------------ | --------------------------------------------------------- |
| Dose           | Continuous | 12-22g                         | Discretize to 0.5g steps                                  |
| Ratio          | Continuous | 1:14 to 1:18 (pour-over)       | Discretize to 0.5 steps                                   |
| Grind          | Ordinal    | 1-10 scale (relative)          | Most impactful parameter; hardest to quantify             |
| Water temp     | Continuous | 85-96C                         | Light roasts = higher, dark = lower (constrained by bean) |
| Bloom time     | Continuous | 15-60s                         | Relatively narrow effective range                         |
| Pour structure | Discrete   | Number of pours (1-5) + timing | Limited to 5-8 common patterns                            |
| Total time     | Continuous | 2:00-5:00 (pour-over)          | Constrained by pour structure                             |

**The search space is manageable.** With discretization, the total parameter space is roughly:

- 20 dose values _ 8 ratio values _ 10 grind values _ 12 temp values _ 10 bloom values \* 8 pour patterns = ~1.5M combinations.
- This is too large for brute-force grid search but small enough for a bounded search that varies 2-3 parameters at a time.

**Recommendation: Iterative single-parameter optimization for v1.**

- Start from the knowledge base's best-match recipe.
- Each user rating adjusts the single most impactful parameter (based on the directional flag: too sour -> grind finer; too bitter -> coarser grind or lower temp; weak -> increase dose or decrease ratio).
- After 3-4 iterations, switch to varying a second parameter.
- This is explainable to the user ("based on your feedback, try a slightly finer grind next time") and demonstrates the optimization concept clearly in a demo.
- Bayesian optimization (e.g., Optuna) is a clean "SHOULD HAVE" extension that can be demonstrated on synthetic data with convergence plots.

### 2.3 Flavor Cluster Mapping

**Assessment: Solved problem domain. Use the SCA Flavor Wheel as the fixed vocabulary.**

The Specialty Coffee Association publishes a standardized flavor wheel with ~100 descriptors organized hierarchically. This is the industry standard and provides:

- A fixed vocabulary for flavor notes.
- Hierarchical clustering (e.g., "blueberry" is a sub-descriptor of "berry" under "fruity").
- A mapping from descriptors to roast-level expectations (fruity/floral -> light roast; chocolate/nutty -> medium-dark).

**Recommendation:**

- Define ~15 top-level flavor clusters from the SCA wheel: fruity, floral, sweet, nutty, cocoa, spice, roasted, vegetal, sour, bold, clean, tea-like, syrupy, juicy, balanced.
- LLM maps roaster descriptions and user feedback into these 15 clusters.
- Two beans with similar cluster profiles are considered "similar" for recipe matching (cosine similarity on the cluster vector).
- Do not attempt to learn user-defined flavor terms in v1. The fixed vocabulary is a feature, not a limitation -- it ensures the model works consistently.

### 2.4 Overfitting Risk

**Assessment: High risk for per-user models. Low risk for global model with proper regularization.**

The per-user dataset problem:

- 30 ratings, 7+ features: classic p > n territory where overfitting is the default, not the exception.
- A gradient-boosted tree with 30 samples will memorize the training data.
- Even with cross-validation, 30 samples provides at most 5 folds of 6 samples -- the validation variance is enormous.

**Recommendation:**

- Global model: Use conservative hyperparameters (max_depth=4, n_estimators=100, learning_rate=0.05). Train on synthetic data (500+ samples) and validate on held-out synthetic data.
- Per-user model: Do not train a separate gradient-boosted model per user. Use the global model and apply a linear bias correction (2-3 parameters: sweetness bias, body bias, acidity bias). This requires only 5-10 ratings to estimate reliably.
- For the course demo, show a learning curve plot: simulated per-user accuracy improves from ~0.5 (random) to ~0.75 (personalized) as rating count grows from 5 to 50. This demonstrates the concept without requiring real user data.

---

## 3. Product Failure Points

### 3.1 "Chronic Not Acute" Pain: The Activation Trigger Problem

**Assessment: This is the single most important product risk and the one with the least satisfying answer.**

The brief correctly identifies this: "Users tolerate mediocre coffee rather than solve it." The pain is real (S$1-2 wasted per bad brew, S$15-30 per ruined bag) but not urgent (the next brew might be fine).

**Activation triggers that could work:**

1. **The "wasted bag" moment.** User opens a new S$25 bag, brews it with their usual recipe, and it tastes terrible (natural-process Ethiopian brewed like a medium-roast Colombian). This is the acute pain within the chronic. The activation trigger is: "Scan your new beans BEFORE you brew them."
2. **The "dialing in" frustration.** User has been trying to get a specific bag right for 3-4 brews, wasting S$6-8 and 20 minutes. They are actively frustrated. The trigger is: "Stop guessing. Let the system find the right recipe in 2-3 attempts instead of your 5-6."
3. **The aspirational pull.** User follows Hoffmann's method and gets a good cup at a cafe. They want to replicate it at home. The trigger is: "This is the exact recipe that cafe uses for those beans."

**For the course demo, this is a presentation/framing challenge, not a product challenge.** The demo should open with the "wasted bag" scenario to establish urgency in the first 30 seconds.

### 3.2 Feedback Loop Friction

**Assessment: Critical design constraint. Rating must take under 5 seconds or users will not do it.**

Current design: "overall 1-10, plus directional flags." This is 2-3 taps minimum (select score, optionally add flags). In practice, users will:

- Skip the rating entirely (most likely).
- Rate immediately after brewing while the coffee is still hot (requires the app to be open and accessible).
- Rate later from memory (less accurate).

**Recommendation: Minimize to 1 tap for primary action.**

- After each brew, show a single screen: "How was it?" with a big thumbs-up button and a big thumbs-down button.
- One tap dismisses the screen and logs the rating.
- If thumbs-down: immediately show 4-6 directional tags (too sour, too bitter, weak, harsh, astringent, other). Tapping one is optional.
- If thumbs-up: done. No further input needed.
- Target: 3 seconds from brew completion to rating logged.

For the course demo, this UX refinement is not critical. The demo can use the 1-10 scale as designed.

### 3.3 Recipe Fatigue

**Assessment: Valid product concern, irrelevant for course demo.**

After finding 2-3 recipes that work for their current beans, users have no reason to return until they buy new beans. This means:

- Active usage spikes with new bean purchases (roughly every 2-3 weeks for the target persona).
- Between new beans, the app sits unused.
- Monthly active users will be much lower than registered users.

**This is not a failure per se** -- it is the natural usage pattern for a tool app. For commercial potential, a one-time premium unlock (S$10-15) is more viable than subscription — users pay once regardless of usage frequency. The diagnosis-first approach also increases engagement: users open the app when something is wrong, not just to browse recipes.

**For the course demo:** Not relevant. The demo shows the full cycle (add beans -> get recipe -> rate -> get adjusted recipe) in a single session.

### 3.4 Espresso Exclusion

**Assessment: Low risk for course demo, medium risk for product.**

Many specialty coffee drinkers own espresso machines. Excluding espresso from v1 is a deliberate trade-off:

- Espresso parameter space is different (pressure, puck prep, distribution, channeling) and harder to model with user-friendly inputs.
- Espresso "dialing in" has a different vocabulary (channeling, choking, gushing) that requires different feedback capture.
- Including it would roughly double the recipe curation effort.

**Recommendation:** Keep espresso out of v1. In the demo, mention it as a v2 expansion area. The pour-over scope (V60, Kalita Wave, Origami) is defensible because these methods share a unified parameter space and have the most accessible equipment for the target persona. AeroPress could be a v2 addition.

---

## 4. Technical Failure Points

### 4.1 LLM Dependency

**Assessment: Manageable with output validation and fallback recipes.**

The LLM layer is used for three functions:

1. Bean profile extraction from free text (section 6.2).
2. Natural-language recipe instruction generation (section 6.1).
3. Flavor note normalization (section 2.3 above).

**What breaks if the LLM fails:**

- Bean profile extraction: Manual entry fallback (user fills in 3 fields: origin, process, roast). This is already in the user flow.
- Recipe instruction generation: Pre-written templates for the 50-80 curated recipes. "Use 15g coffee to 250g water at 93C. Grind at medium-fine (7/20). Bloom for 30s with 30g water. Pour in 3 equal stages at 0:30, 1:00, 1:30. Total time: 3:00-3:30."
- Flavor normalization: Fixed lookup table for common terms.

**What breaks if the LLM produces bad output:**

- Bean profile: Invalid values (roast_level = "crispy"). Mitigation: validate against the enum; reject and re-prompt.
- Recipe instructions: Physically impossible parameters (water at 200C, dose of 500g). Mitigation: validate all parameters against constraints before surfacing to user.
- Flavor mapping: Novel terms not in the vocabulary. Mitigation: map to "unknown" and rely on origin/process matching instead.

**Recommendation:** Every LLM output must pass through a validation layer that checks parameter values against the constraint table (section 2.2). Invalid outputs are rejected and the system falls back to the knowledge base's closest match. For the course demo, the LLM dependency is a feature (it demonstrates LLM integration), not a risk.

### 4.2 Platform: Mobile vs Web

**Assessment: Web app is the correct choice for course demo. Mobile is a product decision for later.**

For the course demo:

- A web application (Streamlit or Flask) is fastest to build, easiest to demo (projector/screen share), and requires no app store distribution.
- Brewing happens near the kettle, but the recipe is read BEFORE brewing. The user does not need to interact with the app during the brew.
- A simple "start timer" feature in the web app (showing pour stages with countdown) would be a nice addition but not required for demo.

For a real product:

- Progressive web app (PWA) would be the pragmatic choice -- web technology, installable on phones, no app store.
- Native mobile is a significant additional investment with no clear advantage over PWA for this use case.

**Recommendation:** Build as a web application for the course demo. Use Streamlit for rapid prototyping (suitable for an ML demo). If the project continues beyond the course, wrap as a PWA.

### 4.3 Offline Usage

**Assessment: Not a concern for v1. The recipe is fetched before brewing; no interaction during brewing is required.**

The use case is:

1. User opens app, sees beans, selects brew method.
2. App shows recipe.
3. User brews (phone is away, hands are wet).
4. User finishes, dries hands, picks up phone, rates the brew.

Steps 1-2 and 4 require connectivity. Step 3 does not. As long as the recipe is displayed (not streamed), there is no offline requirement during the brew itself.

### 4.4 Photo-Based Bean Input (OCR)

**Assessment: De-prioritize for v1. Manual entry is reliable and fast.**

Coffee bag labels present specific OCR challenges:

- Glossy/reflective packaging.
- Artistic fonts (calligraphy, hand-lettered).
- Non-English text (Japanese, Ethiopian region names).
- Information scattered across front and back of bag.
- Varying label formats between roasters.

**Recommendation:** Drop photo input from v1. Manual entry is:

- Faster (type 3 fields in 15 seconds vs. photograph, wait for OCR, correct errors in 45 seconds).
- More reliable (100% vs. 70-85% for OCR on varied bag designs).
- Simpler to implement (no camera integration, no OCR pipeline, no error correction UI).

Photo input is a v2 feature that adds a "nice" UX touch but provides no functional advantage for a course project.

---

## 5. Course Project Risks

### 5.1 Scope Creep

**Assessment: The brief IS ambitious. Five ML components in 14 weeks requires strict prioritization.**

The brief defines 5 ML components:

1. Recipe Knowledge Base + RAG Retrieval (Week 5)
2. Bean Profile Feature Extraction (Week 5/6)
3. Taste Score Prediction (Week 3 -- Supervised)
4. Recipe Optimization (Week 4 -- Optimization)
5. Personalization Layer (Hybrid Cold-Start)

Each of these could be a standalone course project. Delivering all five at demo quality in a single semester requires:

- Aggressive use of existing tools and libraries (no custom implementations where off-the-shelf works).
- Synthetic/simulated data where real data collection is infeasible.
- Clear separation of "demo-essential" vs. "product-essential" features.

**Recommendation:** Structure the project as three tiers:

- **Core pipeline (must work end-to-end):** Bean input -> recipe retrieval -> recipe display -> feedback capture -> model update. This is the demo. It must work in a live demo setting.
- **ML showcase (must demonstrate understanding):** Taste prediction model trained on synthetic data, recipe optimization demonstrated with convergence plots, personalization shown via simulated user history. These demonstrate ML competence without requiring real user data.
- **Product polish (if time allows):** Nice UI, photo input, timer, multiple brew methods. These are bonus, not required.

### 5.2 ML Demonstration

**Assessment: All 5 components can be demonstrated with synthetic data, but the demo must be carefully structured.**

| Component           | Demo Strategy                                                                  | Data Source                                  |
| ------------------- | ------------------------------------------------------------------------------ | -------------------------------------------- |
| RAG Retrieval       | Live query: "Ethiopian washed light roast" -> return top 3 recipes             | Curated 80-100 recipes                       |
| Bean Extraction     | Live demo: paste a real roaster description -> see structured output           | Real descriptions from Singapore roasters    |
| Taste Prediction    | Show trained model; predict rating for new bean+recipe combos                  | Synthetic dataset (500+ samples with noise)  |
| Recipe Optimization | Show convergence: starting recipe -> 5 iterations -> optimized recipe          | Synthetic user with known preference profile |
| Personalization     | Side-by-side: same bean, global recommendation vs. personalized recommendation | Simulated user with 20-50 ratings            |

**Recommendation:** The demo should be a single narrative: "Meet Alex, who likes bright, fruity coffees. Alex buys a new Ethiopian natural. Here's what BrewMatch recommends..." The narrative walks through all 5 components in a natural sequence, using pre-seeded data for Alex's history.

### 5.3 Data Collection

**Assessment: Synthetic data generation is the only viable path for a course project. No real user data will be available in sufficient quantity.**

**Synthetic data generation strategy:**

1. **Recipe-bean pairings with expert ratings:** Create a panel of 3-5 "virtual experts" (defined by preference profiles: one prefers bright/acidic, one prefers sweet/balanced, one prefers bold/chocolatey). For each recipe-bean combination, assign a rating based on the expert's profile + bean characteristics + recipe parameters + noise. This generates 500-1000 labeled samples.

2. **Parameter-response surface:** Define a mathematical relationship between recipe parameters and taste outcomes (based on extraction theory: yield = f(grind, temp, time, ratio); taste balance = g(yield, bean_acidity, bean_body)). Add noise to simulate user variability. This gives a ground truth for testing the optimization engine.

3. **Cold-start simulation:** Generate 100 virtual users with random preference profiles. Each "rates" 5-50 recipes using the parameter-response surface + their preference bias. This tests the personalization layer.

**Recommendation:** Invest 1-2 sessions in building a robust synthetic data generator. This is the foundation for demonstrating all ML components. The generator itself is a legitimate ML engineering artifact for the course.

### 5.4 Evaluation Metrics

**Assessment: Define measurable success criteria for each ML component.**

| Component           | Metric                                                              | Target               | How to Measure                                                               |
| ------------------- | ------------------------------------------------------------------- | -------------------- | ---------------------------------------------------------------------------- |
| RAG Retrieval       | Precision@3 (fraction of retrieved recipes that match bean profile) | >0.8                 | Expert-labeled ground truth for 20 test queries                              |
| Bean Extraction     | Field-level accuracy (correct value for origin, process, roast)     | >0.8 per field       | Test against 20 real roaster descriptions with manually labeled ground truth |
| Taste Prediction    | RMSE between predicted and actual (synthetic) ratings               | <1.5 (on 1-10 scale) | Train/test split on synthetic dataset                                        |
| Recipe Optimization | Convergence (number of iterations to reach >0.8 of optimal score)   | <5 iterations        | Run optimization on 20 test beans with known optimal parameters              |
| Personalization     | Rating improvement: personalized vs. global recommendation          | >0.5 points average  | Compare personalized and global predictions on simulated user test set       |

**Recommendation:** These five metrics form the "evaluation" section of the course report. Each has a clear target, a defined measurement method, and a quantitative success threshold. The report should present results as a table with actual vs. target values.

---

## 6. Requirements Breakdown

### MUST HAVE (MVP / Course Demo)

These are the minimum requirements for a passing course demo. Without any one of these, the project fails to demonstrate the core concept.

| ID   | Requirement                                                                       | Rationale                                                                             |
| ---- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| M-01 | Web application with bean input (manual text) and brew method selection           | Core user flow; the demo entry point                                                  |
| M-02 | Recipe knowledge base with at least 50 curated, fully-parameterized recipes       | Minimum viable for RAG retrieval; fewer than 50 is too sparse for meaningful matching |
| M-03 | Recipe retrieval given bean profile (embedding similarity or rule-based matching) | Demonstrates information retrieval / unsupervised learning component                  |
| M-04 | Bean profile extraction from free text (LLM-based, structured output)             | Demonstrates NLP / LLM integration component                                          |
| M-05 | Taste prediction model trained on synthetic data (gradient-boosted or equivalent) | Demonstrates supervised learning component                                            |
| M-06 | Recipe optimization (grid search or iterative single-parameter adjustment)        | Demonstrates optimization component                                                   |
| M-07 | Feedback capture UI (rating + directional flags)                                  | Closes the learning loop; essential for personalization demonstration                 |
| M-08 | Synthetic data generator for training and evaluation                              | Enables ML demonstration without real users                                           |
| M-09 | Evaluation metrics table with actual vs. target values for all 5 components       | Course requirement: measurable ML outcomes                                            |
| M-10 | End-to-end demo script (single narrative walking through all components)          | Presentation requirement; the demo must tell a coherent story                         |

### SHOULD HAVE (Compelling Demo)

These elevate the project from "passes" to "impresses." Implement these if the MUST HAVE items are complete with at least 2 weeks remaining.

| ID   | Requirement                                                                                                   | Rationale                                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| S-01 | 80-100 curated recipes (up from 50)                                                                           | Improves retrieval quality and demo credibility                                 |
| S-02 | Personalization layer with simulated user history (show global vs. personalized recommendations side-by-side) | Demonstrates the "learning over time" concept visually                          |
| S-03 | Convergence plots for recipe optimization (show score improving over iterations)                              | Visual evidence of optimization working                                         |
| S-04 | Learning curve analysis (model accuracy vs. number of training samples)                                       | Demonstrates understanding of data requirements and cold-start impact           |
| S-05 | Bayesan optimization (e.g., Optuna) as an alternative to grid search                                          | Demonstrates advanced optimization technique; easy to add on top of grid search |
| S-06 | Timer/brew guide display (pour stages with countdown)                                                         | Makes the demo feel like a real product; one "wow" feature                      |
| S-07 | Comparison table: BrewMatch vs. ChatGPT on 5 test queries                                                     | Directly addresses the "why not just use ChatGPT?" question from the brief      |

### NICE TO HAVE (Full Product)

These are for post-course development if the project continues.

| ID   | Requirement                                     | Rationale                                                        |
| ---- | ----------------------------------------------- | ---------------------------------------------------------------- |
| N-01 | Photo-based bean input (OCR)                    | Nice UX; significant engineering effort; no functional advantage |
| N-02 | AeroPress support (in addition to pour-over)    | Expands user base; requires separate recipe knowledge base       |
| N-03 | Mobile-first responsive design or PWA           | Product requirement; unnecessary for course demo                 |
| N-04 | User authentication and persistent storage      | Product requirement; demo can use single-session state           |
| N-05 | Multiple brew method support                    | Product expansion; demo focuses on one method                    |
| N-06 | Social features (sharing recipes, leaderboards) | Product feature; not relevant to ML demonstration                |
| N-07 | Espresso support                                | Different parameter space; significant additional scope          |

### Explicitly Out of Scope

| Item                          | Why Out of Scope                                                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Espresso recipes              | Different parameter space (pressure, puck prep); would roughly double the ML model scope                         |
| Equipment recommendations     | Not an ML problem; better served by existing content (YouTube, blogs)                                            |
| Social features               | Adds product complexity without ML value; not relevant to personalization                                        |
| Roasting guidance             | Entirely different domain; the user buys roasted beans, not green beans                                          |
| Cupping/scoring               | Professional skill; target persona does not cup their coffee                                                     |
| Real user data collection     | Infeasible in course timeline; synthetic data is sufficient for demonstration                                    |
| Mobile native app             | Significant development overhead; web app demonstrates the ML equally well                                       |
| French press, moka, cold brew | Each method has different parameter sets; v1 focuses on pour-over where parameter optimization is most impactful |

---

## Architecture Decision Record: ADR-001

### Staged Demo Strategy for Course Project

**Status: Proposed**

**Context:** BrewMatch has 5 ML components to demonstrate in a 14-week semester. Real user data will not be available in sufficient quantity. The product faces a cold-start problem that a course demo cannot solve organically. The evaluation must show measurable ML outcomes.

**Decision:** Structure the project around a staged demo that uses synthetic data to demonstrate each ML component at its best, while maintaining a coherent end-to-end narrative.

**Consequences:**

Positive:

- Each ML component can be demonstrated with sufficient data to show meaningful results.
- Evaluation metrics have clear targets and measurable outcomes.
- The demo tells a compelling story without relying on real user adoption.
- Project can be completed within semester timeline.

Negative:

- The demo demonstrates ML capability, not product-market fit.
- Synthetic data results may not generalize to real user preferences.
- The personalization demo is simulated, not learned from real usage.

**Alternatives Considered:**

1. **Real user beta test**: Recruit 10-20 classmates to use the app for 4 weeks. Rejected: insufficient data volume (10 users _ 2 ratings/day _ 28 days = 560 ratings -- borderline for meaningful per-user personalization; high coordination overhead; ethical considerations for data collection from classmates).

2. **Reduced scope (drop 2 ML components)**: Focus on taste prediction + optimization only. Rejected: the course likely requires demonstrating multiple ML techniques; the RAG and NLP components are valuable demonstrations.

3. **Wizard-of-Oz demo**: Manually adjust recipes behind the scenes, present as ML output. Rejected: academically dishonest; defeats the purpose of an ML course project.

**Implementation Plan:**

- Phase 1 (Weeks 1-3): Build data foundation (synthetic data generator, recipe knowledge base schema, bean extraction pipeline).
- Phase 2 (Weeks 4-6): Implement ML components (taste prediction, recipe optimization, RAG retrieval).
- Phase 3 (Weeks 7-8): Build web UI and integrate all components into end-to-end flow.
- Phase 4 (Weeks 9-10): Evaluate each component against target metrics; iterate on underperforming components.
- Phase 5 (Weeks 11-12): Polish demo script, prepare presentation materials, finalize course report.

---

## Implementation Roadmap

### Phase 1: Data Foundation (Weeks 1-3)

- Define recipe schema and bean profile schema.
- Curate 50-80 recipes from public sources with full parameter coverage.
- Build synthetic data generator (parameter-response surface, virtual expert panel, virtual user generator).
- Build bean profile extraction pipeline (LLM + structured output + validation).
- Deliverable: `data/` directory with recipes.json, synthetic_ratings.csv, bean_profiles.json.

### Phase 2: ML Components (Weeks 4-6)

- Train taste prediction model on synthetic data; evaluate RMSE.
- Implement recipe retrieval (embedding-based or rule-based matching).
- Implement recipe optimization (iterative single-parameter or grid search).
- Implement personalization layer (global model + user bias).
- Deliverable: `models/` directory with trained model, retrieval index, optimization engine.

### Phase 3: Web UI Integration (Weeks 7-8)

- Build Streamlit (or Flask) web application.
- Wire bean input -> recipe retrieval -> recipe display -> feedback capture -> model update.
- Ensure end-to-end flow works for demo narrative.
- Deliverable: Working web application with all components integrated.

### Phase 4: Evaluation (Weeks 9-10)

- Run evaluation metrics for all 5 components.
- Generate comparison tables, convergence plots, learning curves.
- Iterate on underperforming components.
- Deliverable: `evaluation/` directory with metrics tables and plots.

### Phase 5: Demo Preparation (Weeks 11-12)

- Write demo script (single narrative).
- Prepare presentation slides.
- Finalize course report with methodology, results, and discussion.
- Deliverable: Demo-ready application, presentation, and course report.

---

## Success Criteria

- [ ] End-to-end demo: user inputs bean description, receives recipe, rates brew, receives adjusted recipe -- all within the web application.
- [ ] RAG retrieval precision@3 > 0.8 on 20 test queries.
- [ ] Bean profile extraction accuracy > 0.8 per field on 20 real roaster descriptions.
- [ ] Taste prediction RMSE < 1.5 on held-out synthetic test data.
- [ ] Recipe optimization converges (reaches >0.8 of optimal) in < 5 iterations on 20 test beans.
- [ ] Personalization improves predicted rating by > 0.5 points over global model on simulated user test set.
- [ ] All 5 ML components demonstrated in a single coherent demo narrative.
- [ ] Course report includes evaluation metrics table with actual vs. target values for all components.

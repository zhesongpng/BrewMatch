# BrewMatch Architecture Plan

Date: 2026-05-09
Status: Phase 01 — Architecture Plan
Updated: Diagnosis-first framing — optimization serves diagnosis, personalization is emergent

---

## 1. System Architecture

```
[User Input: Bean Description + Dripper (V60/Kalita/Origami)]
        |
        v
[Bean Profile Extractor (LLM)] ──> Structured Feature Vector
        |
        v
[Recipe Retriever (RAG)] ──> Top-K Matching Recipes for selected dripper
        |
        v
[Taste Predictor (LightGBM)] ──> Predicted Ratings per Recipe
        |
        v
[Recipe Ranker] ──> Best Starting Recipe + Confidence
        |
        v
[User Brews + Reports Issue]
        |
        v
[Diagnosis Engine] ──> Perturb-and-Score: taste predictor ranks candidate adjustments
        |                    (candidates from coffee-science rules, winner chosen by ML model)
        v
[Recipe Optimizer (Optuna)] ──> Minimum parameter change to fix the issue
        |
        v
[Adjusted Recipe + Explanation]
        |
        v
[Feedback Processor] ──> Update User Taste Profile (emergent personalization)
```

---

## 2. Data Architecture

### 2.1 Recipe Knowledge Base Schema

```json
{
  "recipe_id": "string",
  "source": "string",
  "method": "V60|Kalita Wave|Origami",
  "parameters": {
    "dose_g": 15,
    "water_total_g": 250,
    "ratio": 16.67,
    "grind_setting": 7,
    "water_temp_c": 93,
    "bloom_time_s": 30,
    "total_time_s": 210,
    "pours": [
      { "step": 1, "time_offset_s": 0, "water_g": 50 },
      { "step": 2, "time_offset_s": 30, "water_g": 100 },
      { "step": 3, "time_offset_s": 90, "water_g": 100 }
    ]
  },
  "suitable_for": {
    "roast_levels": ["light", "medium-light"],
    "origins": ["Ethiopia", "Kenya", "Colombia"],
    "processes": ["washed", "natural"],
    "flavor_profiles": ["Berry", "Citrus", "Floral"]
  },
  "instructions": "string",
  "source_url": "string"
}
```

### 2.2 Bean Profile Schema

```json
{
  "origin_country": "string",
  "origin_region": "string | null",
  "process": "washed | natural | honey | anaerobic | unknown",
  "roast_level": "light | medium-light | medium | medium-dark | dark | unknown",
  "flavor_notes": ["string"],
  "flavor_clusters": ["string"],
  "variety": "string | null",
  "altitude_min_m": "int | null",
  "altitude_max_m": "int | null",
  "source_text": "string",
  "extraction_confidence": "float | null"
}
```

### 2.3 User Taste Profile

```json
{
  "user_id": "uuid",
  "onboarding": {
    "preferred_clusters": ["string"],
    "roast_preference": "string",
    "experience_level": "string",
    "drippers": ["V60", "Kalita Wave", "Origami"]
  },
  "brew_history": [
    {
      "brew_id": "uuid",
      "timestamp": "ISO-8601",
      "bean_profile": {},
      "recipe_used": {},
      "feedback": {
        "thumbs_up": true,
        "score": 7,
        "directional_flags": [],
        "notes": "string | null"
      }
    }
  ],
  "learned_preferences": {
    "acidity_bias": 0.0,
    "body_bias": 0.0,
    "sweetness_bias": 0.0,
    "preferred_temp_range": [90, 94],
    "preferred_ratio_range": [15.0, 16.5]
  },
  "stats": {
    "total_brews": 0,
    "avg_score": 0.0,
    "favorite_origins": [],
    "favorite_clusters": []
  }
}
```

### 2.4 Synthetic Data Generation

The synthetic data generator creates:

1. **Virtual experts** (3-5 defined preference profiles)
2. **Parameter-response surface** based on extraction theory
3. **Virtual users** (100+ with random preference profiles)
4. **Rating generation**: expert_profile(bean, recipe) + noise

This is the foundation for demonstrating all ML components without real users.

---

## 3. ML Component Architecture

### 3.1 Component: Bean Profile Extractor

- **Input**: Free-text roaster description
- **Output**: Structured JSON (bean profile schema)
- **Method**: LLM with structured output mode + validation layer
- **Validation**: Check fields against known taxonomy (origin countries, process types, roast levels)
- **Fallback**: Manual entry form if extraction fails

### 3.2 Component: Recipe Retriever (RAG)

- **Indexing**: Each recipe → text representation → embedding vector → ChromaDB
- **Query**: Bean profile vector → cosine similarity → top-K recipes
- **Hybrid**: Dense embedding + BM25 keyword matching, fused via Reciprocal Rank Fusion
- **Reranking**: Score by (retrieval similarity × parameter constraint fit)

### 3.3 Component: Taste Predictor

- **Model**: LightGBM regression
- **Features**: Bean profile (encoded) + recipe parameters + user history features + interaction terms
- **Training**: Synthetic dataset (5,000-10,000 samples from virtual experts)
- **Also powers diagnosis**: The taste predictor ranks candidate parameter adjustments via the Perturb-and-Score algorithm (`specs/coffee-science.md` Section 7.2). This is the ML contribution to diagnosis — the model decides which adjustment most improves the predicted score for this specific bean and user.
- **Bean-aware (0 brews)**: Global model as strong prior, per-user linear bias layer after 5+ ratings
- **Evaluation**: RMSE < 1.5 on held-out synthetic test set

### 3.4 Component: Recipe Optimizer

- **Method**: Optuna TPE sampler (Bayesian optimization)
- **Search space**: 7 constrained parameters (grind, temp, ratio, bloom, pours, interval, dose)
- **Objective**: Maximize predicted taste score from taste predictor, with diagnosis-alignment bonus when a directional flag is present (reward parameter changes consistent with the flag's diagnostic rules from `specs/coffee-science.md`)
- **Initialization**: Start from best-matching recipe parameters (from RAG) for first brew; start from last-brewed recipe after feedback cycle
- **Convergence**: Target < 5 iterations to reach >0.8 of optimal

### 3.5 Component: Taste Profile Adaptation (Emergent from Diagnosis)

- **Phase 0 (0 brews)**: Onboarding quiz → initial flavor cluster preferences → global best-fit recipes (bean-aware, pre-personalization)
- **Phase 1 (1-4 brews)**: Global model + user bias estimation (linear correction)
- **Phase 2 (5-9 brews)**: Content-based model with user features
- **Phase 3 (10+ brews)**: Full hybrid model with collaborative signals (flavor cluster level)
- **Demo strategy**: Show phases side-by-side with simulated user history

---

## 4. Demo Architecture

The demo follows a single narrative: "Meet Alex, who likes bright, fruity coffees."

### Demo Flow

1. **Bean Input**: Alex enters "Ethiopia Yirgacheffe, washed, light roast, notes of blueberry, jasmine, bergamot"
2. **Extraction Demo**: Show LLM extracting structured profile from free text
3. **Retrieval Demo**: Show top-3 matching recipes from knowledge base with similarity scores
4. **Prediction Demo**: Show predicted ratings for each recipe using the taste model (with confidence interval — bean-aware means wider uncertainty before user data)
5. **Optimization Demo**: Show Optuna convergence plot — starting recipe → 5 iterations → optimized
6. **Feedback Demo**: Alex rates the brew (thumbs down: "too sour")
7. **Diagnosis Demo (ML-powered)**: Show the Perturb-and-Score algorithm in action — the taste predictor evaluates each candidate adjustment (increase temp +2, finer grind -1, longer time +15s) and ranks them by predicted improvement. Display the top 3 with predicted deltas, explaining why "increase temperature from 91C to 93C" is the winner for this light-roast Ethiopian. This demonstrates that the diagnosis uses the ML model, not just a lookup table.
8. **Adjustment Demo**: Show how feedback updates user profile, optimizer warm-starts from the brewed recipe (not from RAG), and produces an adjusted recipe that specifically addresses the reported issue.
9. **ML Deep Dive**: Show learning curve (RMSE vs. data size), SHAP feature importance, and a case where the model's prediction deviates from the rule-based expectation — demonstrating actual learning beyond encoded rules.
10. **Accumulated Improvement Demo**: Side-by-side comparison of global vs. diagnosis-informed recommendation for the same bean, using Alex's pre-seeded 15-brew history.

---

## 5. Project Structure

```
BrewMatch/
├── data/
│   ├── recipes/              # Curated recipe JSON files
│   ├── synthetic/            # Generated synthetic data
│   └── external/             # CQI datasets, reference data
├── src/
│   ├── bean_extractor/       # LLM-based bean profile extraction
│   ├── recipe_retriever/     # RAG pipeline (embeddings + ChromaDB)
│   ├── taste_predictor/      # LightGBM model training + inference
│   ├── recipe_optimizer/     # Optuna optimization engine
│   ├── taste_profile/        # User profile management + bean-aware adaptation
│   ├── data_generator/       # Synthetic data generation
│   └── api/                  # FastAPI or Streamlit app
├── models/                   # Trained model artifacts
├── evaluation/               # Metrics, plots, results
├── tests/                    # Unit + integration tests
├── app.py                    # Streamlit entry point
└── pyproject.toml
```

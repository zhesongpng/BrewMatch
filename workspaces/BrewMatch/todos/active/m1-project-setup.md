# Milestone 1: Project Setup & Data Layer

Estimated sessions: 3-4
Depends on: Nothing (start here)

---

## 1.1 Project scaffolding

- [ ] **Create project structure and `pyproject.toml`**
      Implements: Architecture plan Section 5
  - Directory structure: `src/bean_extractor/`, `src/recipe_retriever/`, `src/taste_predictor/`, `src/recipe_optimizer/`, `src/personalization/`, `src/data_generator/`, `data/recipes/`, `data/synthetic/`, `models/`, `tests/`
  - `pyproject.toml` with dependencies: streamlit, lightgbm, optuna, chromadb, sentence-transformers, rank-bm25, scikit-learn, pandas, numpy, shap, joblib, python-dotenv
  - `.env.example` with `LLM_MODEL`, `LLM_API_KEY`, `BREWMATCH_DEMO_MODE`
  - `app.py` Streamlit entry point (placeholder)

## 1.2 Data models

- [ ] **Implement Python data model classes**
      Implements: `specs/data-models.md` Sections 1-3
  - `Recipe` dataclass with validation (pour schema, ratio check, water_total constraint)
  - `BeanProfile` dataclass with 15-cluster taxonomy enum
  - `UserTasteProfile` dataclass with onboarding, brew_history, learned_preferences, stats
  - `Feedback` dataclass (thumbs_up, score, directional_flags, notes)
  - `BrewRecord` dataclass linking bean + recipe + feedback
  - Validation functions for each model (per data-models.md validation rules)
  - Unit tests for all validation rules

## 1.3 Recipe knowledge base

- [ ] **Curate 50-80 pour-over recipe JSON files**
      Implements: `specs/recipe-retrieval.md` Section 2, `specs/synthetic-data.md` Section 6
  - Recipes from: Hoffmann (3-5), Kasuya 4:6 (3-5), Rao (2-3), Barista Hustle (5-10), Onyx (3-5), Lance Hedrick (5-10), Kalita adaptations (5-8), Origami (3-5), generated variations (15-25)
  - Each recipe: recipe_id, source, method, dose_g, ratio, grind_setting, water_temp_c, bloom_time_s, total_time_s, pours[], suitable_for{}, instructions
  - Every recipe passes validation against `data-models.md` Section 1
  - Recipes rejected by curation filter logged to `data/recipes/rejected/`
  - Method filter: V60, Kalita Wave, Origami only

- [ ] **Build recipe validation script**
      Implements: `specs/data-models.md` Section 1 validation rules
  - Validates all JSON files in `data/recipes/` against schema
  - Checks: water_total ≈ sum(pours), ratio = water_total/dose_g, total_time >= last_pour + 30s, all params in range
  - Outputs validation report with pass/fail per recipe
  - Run as `python scripts/validate_recipes.py`

## 1.4 Synthetic data generation

- [ ] **Build synthetic data generator**
      Implements: `specs/synthetic-data.md` Sections 3-5
  - Extraction quality score function with 5 weighted terms (roast-temp, grind-time, ratio, dose, process-grind alignment)
  - Rating generation: base_rating + user_bias + preference_bonus + noise
  - Directional flag generation from under/overextraction indicators (92C threshold)
  - Virtual expert panel (5 experts with distinct profiles)
  - Virtual user generator (200 users, 30% beginner / 50% intermediate / 20% advanced)
  - Brew history generation per user (exploration → learning → exploitation phases)
  - Demo user "Alex" generation (15-brew history, light-roast preference, berry/citrus/floral)
  - Reproducibility: seed=42, metadata output
  - Output: `data/synthetic/ratings.csv`, `data/synthetic/users.json`, `data/synthetic/expert_labels.csv`, `data/synthetic/demo_alex.json`, `data/synthetic/metadata.json`

- [ ] **Build synthetic user loading for collaborative filtering**
      Implements: `specs/synthetic-data.md` Section 11
  - SyntheticUser schema (user_id, roast_preference, preferred_clusters, rating_bias, tolerance dimensions, experience_level)
  - Generate 200 synthetic user profiles alongside ratings
  - Store in `data/synthetic/users.json`
  - Seed script `scripts/seed_synthetic_users.py` loads into SQLite at startup

- [ ] **Generate all synthetic data**
  - Run the generator with seed=42
  - Validate output: row counts (5K-10K ratings, 200 users, 50-80 expert labels, 15 Alex brews)
  - Statistical validation: rating distribution, parameter correlations, expert agreement
  - Domain validation: light roast + high temp rated higher, dark roast + low temp rated higher

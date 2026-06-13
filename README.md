# BrewMatch

A pour-over coffee troubleshooting tool that diagnoses brew issues and recommends recipe adjustments — giving you a bean-matched starting recipe, then telling you exactly what to change when a cup tastes off.

## What It Does

Home brewers buy specialty beans but get inconsistent results. BrewMatch addresses this with a diagnosis-first approach: given a bean and a dripper, it recommends a starting recipe, then after you brew and report what went wrong (too sour, too bitter, too weak, etc.), it prescribes specific parameter adjustments. Over time, recommendations improve based on accumulated brew history.

## Scope

**Brewers**: V60, Kalita Wave, Origami. No AeroPress, no espresso, no French press, no cold brew.

**Recipes**: 46 hand-crafted recipes from real baristas -- James Hoffmann, Scott Rao, Tetsu Kasuya, Lance Hedrick, Onyx Coffee Lab, and others. Each recipe is tagged with suitable bean profiles (roast level, origin, process, flavor clusters).

**Feedback**: Thumbs up/down with directional flags (too sour, too bitter, too weak, too harsh, astringent).

## Project Structure

```
src/
  data_models.py          BeanProfile, Recipe, Feedback, BrewRecord, UserTasteProfile
  bean_extractor/         LLM-based extraction from roaster description text
  data_generator/         Synthetic data pipeline (users, ratings, expert labels)
  recipe_retriever/       Embedding-based recipe search with BM25 + semantic hybrid
  taste_predictor/        LightGBM regression model for score prediction
  recipe_optimizer/       Optuna TPE for parameter adjustment recommendations
  personalization/        Learned preference updates from brew history

tests/
  unit/                   Data model validation, alignment functions, edge cases
  integration/            End-to-end pipeline tests (generation through prediction)
  regression/             LOC invariants and structural guards
```

## Setup

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env: set LLM_MODEL and LLM_API_KEY (used for bean profile extraction)

# 2. Install dependencies
pip install -e ".[dev]"
# Or with uv:
uv sync --extra dev
```

Requires Python 3.11+.

## Data Pipeline

The synthetic data generator produces reproducible training data (seed=42):

- **200 virtual users** with varied roast preferences, flavor affinities, and experience levels (beginner / intermediate / advanced)
- **0--30 brews per user** across three phases: exploration (random params, high noise), learning (params cluster toward preferences), exploitation (tight params, low noise)
- **5 expert labelers** (SCA judge, light-roast specialist, traditional cupper, modern barista, home brewer) rating 60 bean-recipe pairings
- **1 demo user** (Alex) with 15 brews showing improvement trajectory

Run generation:

```bash
python -m src.data_generator.generator
```

Output goes to `data/synthetic/` (ratings.csv, users.json, expert_labels.csv, demo_alex.json, metadata.json).

## Running Tests

```bash
python -m pytest tests/unit/ tests/integration/ -v
```

## ML Architecture

| Component           | Method                            | Purpose                                               |
| ------------------- | --------------------------------- | ----------------------------------------------------- |
| Recipe Retrieval    | ChromaDB embeddings + BM25 hybrid | Find recipes matching a bean profile                  |
| Taste Prediction    | LightGBM regression               | Predict brew score from bean + recipe + user features |
| Recipe Optimization | Optuna TPE (Bayesian)             | Find minimum parameter change to fix a reported issue |
| Personalization     | Learned preference drift          | Adjust starting recipes based on accumulated history  |

The taste predictor also powers diagnosis via a perturb-and-score approach: evaluate candidate parameter adjustments through the model, rank by predicted improvement, and prescribe the best one.

## License

© 2026 BrewMatch. All rights reserved. (License terms to be finalized.)

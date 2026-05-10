# BrewMatch ML Architecture Research

**Date:** 2026-05-09
**Project:** BrewMatch -- Personalized Coffee Brewing Assistant
**Course:** MGMT655 - Machine Learning For Decision Making

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Coffee Extraction Science Foundations](#2-coffee-extraction-science-foundations)
3. [Component 1: Recipe Knowledge Base + RAG System](#3-component-1-recipe-knowledge-base--rag-system)
4. [Component 2: Bean Profile Feature Extraction](#4-component-2-bean-profile-feature-extraction)
5. [Component 3: Taste Score Prediction (Supervised Learning)](#5-component-3-taste-score-prediction-supervised-learning)
6. [Component 4: Recipe Optimization](#6-component-4-recipe-optimization)
7. [Component 5: Personalization Layer (Hybrid Cold-Start)](#7-component-5-personalization-layer-hybrid-cold-start)
8. [Data Requirements Summary](#8-data-requirements-summary)
9. [Existing Coffee Data Sources](#9-existing-coffee-data-sources)
10. [Privacy Considerations](#10-privacy-considerations)
11. [Technology Stack Recommendations](#11-technology-stack-recommendations)
12. [Sources](#12-sources)

---

## 1. Executive Summary

BrewMatch requires five interconnected ML components. This research covers the scientific foundations of coffee extraction, the state of the art for each component, data requirements, and practical implementation recommendations for an MBA course project. Key findings:

- **RAG for recipes** is well-proven in the food domain (RecipeRAG, LlamaIndex patterns). Hybrid retrieval (dense embeddings + BM25) with structured recipe schemas is the recommended architecture.
- **LLM-based extraction** significantly outperforms traditional NER for free-text roaster descriptions. The WCR Sensory Lexicon (110+ terms) provides the canonical taxonomy.
- **Gradient-boosted regression** (LightGBM or XGBoost) is the right choice for taste score prediction, but requires careful cold-start handling via Bayesian priors and global averages.
- **Bayesian optimization** (via Optuna) is strongly preferred over grid search for recipe optimization -- achieving similar results in 15-30 iterations instead of hundreds.
- **Hybrid cold-start** combining content-based features with collaborative signals is the industry-standard approach for personalization with sparse data.

---

## 2. Coffee Extraction Science Foundations

Understanding how brewing parameters interact is critical for every ML component. Coffee extraction is a complex physicochemical process where multiple variables interact nonlinearly.

### 2.1 Key Parameters and Their Effects

| Parameter             | Range (Pour Over)                                          | Effect on Extraction                                             | Effect on Taste                                                   |
| --------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Grind Size**        | Fine (200um) to Coarse (1200um)                            | Finer = more surface area = faster extraction                    | Too fine = bitter/overextracted; Too coarse = sour/underextracted |
| **Water Temperature** | 85-96C (light roast: 90-96C; medium: 88-91C; dark: 80-88C) | Higher temp = faster dissolution of compounds                    | Higher extracts more acids, aromatics; too high = bitterness      |
| **Brew Ratio**        | 1:14 to 1:18 (coffee:water by weight)                      | Does NOT affect extraction rate, but affects concentration (TDS) | Lower ratio = stronger, more concentrated cup                     |
| **Contact Time**      | 2:00-5:00 (pour over)                                      | Longer = more extraction                                         | Longer shifts balance toward bitter compounds                     |
| **Bloom Time**        | 30-60 seconds                                              | Allows CO2 degassing, improving water contact                    | Insufficient bloom = channeling = uneven extraction               |
| **Pour Structure**    | 2-5 pours, varying flow rates                              | Affects agitation and extraction uniformity                      | More pours = more agitation = higher extraction                   |

### 2.2 The Extraction Yield Framework (SCA Standard)

The Specialty Coffee Association (SCA) defines the ideal extraction window:

- **Optimal Extraction Yield:** 18-22% of coffee mass dissolved into brew
- **Filter Coffee TDS:** 1.15-1.35% (total dissolved solids as percentage of brew weight)
- **Espresso TDS:** 8-12%

These targets are measured with a refractometer. Extraction yield is calculated as:

```
Extraction Yield (%) = (TDS% x Brew Weight) / Coffee Dose x 100
```

### 2.3 Interaction Effects (Critical for Optimization)

Research from a peer-reviewed study (ScienceDirect, 2023) on immersion brewing found:

1. **Grind size x Temperature:** Finer grind + higher temperature compounds extraction rate. A fine grind at 96C may overextract in 2 minutes, while the same grind at 85C may be balanced at 3 minutes.
2. **Grind size x Time:** Extraction rate and yield increased with decreasing grind size and increasing temperature, but brew ratio did NOT affect extraction rate (only final concentration).
3. **Ratio x Yield:** Brew ratio significantly affects extraction yield and titratable acidity, but not the extraction rate itself. This means ratio primarily controls strength, while grind/temp/time control flavor balance.
4. **Nonlinear dynamics:** The first 40% of water extracts different compounds than the last 60%. This is the insight behind Tetsu Kasuya's 4:6 method -- the first 2 pours (40% of water) control sweetness/acidity balance, while the last 3 pours (60%) control strength.

**Implication for BrewMatch:** These interactions mean the optimization cannot treat parameters independently. A multi-dimensional optimization approach (Bayesian optimization) that captures these interactions is essential.

### 2.4 Structured Recipe Data from Expert Sources

Research into expert recipe databases yielded the following parameter structures:

| Source                 | Typical Dose | Ratio       | Temp                     | Grind       | Pours                       | Total Time |
| ---------------------- | ------------ | ----------- | ------------------------ | ----------- | --------------------------- | ---------- |
| **James Hoffmann V60** | 15-30g       | 1:15-1:16.6 | 100C                     | Medium-fine | 1 bloom + continuous        | 3:00-3:30  |
| **Tetsu Kasuya 4:6**   | 20g          | 1:15        | 80-94C (roast-dependent) | Coarse      | 5 equal pours               | ~3:30      |
| **Scott Rao**          | 15-22g       | 1:15-1:16.7 | ~100C                    | Medium-fine | 2-3 structured + swirl      | ~3:30      |
| **Onyx Coffee Lab**    | 19-20g       | 1:16        | 94C                      | Medium      | 3-6 pours                   | ~2:30-3:00 |
| **Barista Hustle**     | Variable     | 1:16        | Variable                 | Variable    | Bloom + dilution + drawdown | Variable   |

Sources: [Home-Barista](https://www.home-barista.com/brewing/science-behind-kasuya-4-6-method-t75697.html), [Pour Over Project](https://pouroverproject.com/v60-recipes-rao-hoffman-kasuya-drip-coffee/), [Onyx Coffee Lab Brew Guides](https://onyxcoffeelab.com/pages/brew-guides), [unpacking.coffee](https://unpacking.coffee)

---

## 3. Component 1: Recipe Knowledge Base + RAG System

### 3.1 Architecture Overview

The RAG system needs to handle both **structured data** (recipe parameters: grind size, temperature, ratio, timings) and **unstructured data** (brewing instructions, tasting notes, technique descriptions). Research points to a **hybrid retrieval architecture** as best practice.

**Recommended Architecture: HybridRAG / STAG Pattern**

```
User Query (bean profile + preferences)
        |
        v
[Query Embedding]  +  [BM25 Keyword Search]
        |                    |
        v                    v
  [Dense Retriever]   [Sparse Retriever]
        |                    |
        +------- OR --------+
                 |
         [Reranker / Fusion]
                 |
                 v
         [Top-K Recipe Chunks]
                 |
                 v
         [LLM Generation Layer]
                 |
                 v
    Natural Language Brewing Instructions
```

### 3.2 Embedding Models for Recipe Retrieval

Based on the MTEB (Massive Text Embedding Benchmark) leaderboard research:

| Model                               | MTEB Score           | Size      | Best For                    | Notes                                 |
| ----------------------------------- | -------------------- | --------- | --------------------------- | ------------------------------------- |
| **all-MiniLM-L6-v2**                | ~56                  | 80MB      | Fast, lightweight retrieval | Good baseline for course project      |
| **all-mpnet-base-v2**               | ~58                  | 420MB     | Strong general-purpose      | Used in academic RAG benchmarks       |
| **GritLM-7B**                       | Top-tier             | 7B params | Best retrieval quality      | Requires GPU                          |
| **Qwen3-Embedding-8B**              | 70.58 (multilingual) | 8B params | SOTA multilingual           | Overkill for English-only recipes     |
| **text-embedding-3-small** (OpenAI) | Strong               | API       | Production ease             | $0.02/1M tokens, easiest to integrate |

**Recommendation for BrewMatch:** Start with `all-MiniLM-L6-v2` (free, fast, runs locally) or OpenAI's `text-embedding-3-small` (best quality-to-effort ratio). For a course project, either provides sufficient retrieval quality.

Sources: [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard), [Modal Blog MTEB](https://modal.com/blog/mteb-leaderboard-article), [RAG Benchmarks Leaderboard](https://awesomeagents.ai/leaderboards/rag-benchmarks-leaderboard/)

### 3.3 RAG Architecture for Mixed Data Types

Research into structured + unstructured RAG (2025) reveals several patterns:

1. **STAG (Structure Augmented Generation):** Bridges structured and unstructured data by encoding structured fields as text chunks alongside natural language content. Each recipe becomes a hybrid document with both parameter tables and prose instructions.

2. **HybridRAG:** Merges knowledge graph edges (structured relationships like "Ethiopia Yirgacheffe pairs well with Kasuya 4:6 method") with free-text retrieval for enhanced information extraction.

3. **RecipeRAG:** An academic approach using knowledge graph-driven personalized recipe generation. Published in CEUR Workshop Proceedings (Vol. 4079), this system combines structured recipe attributes with user preference modeling via graph-based retrieval.

**Recommendation for BrewMatch:** Use STAG pattern -- encode each recipe as a structured JSON object with both parameter fields and text instructions. Store as a single vector per recipe chunk. This is the simplest approach that handles both data types well.

### 3.4 Recipe Schema Design

Based on research into expert recipe structures:

```json
{
  "recipe_id": "kasuya-4-6-v60",
  "source": "Tetsu Kasuya (2016 WBrC Champion)",
  "method": "V60 pour over",
  "parameters": {
    "dose_g": 20,
    "water_total_g": 300,
    "ratio": "1:15",
    "grind": "coarse",
    "water_temp_c": { "light": 94, "medium": 88, "dark": 80 },
    "bloom_time_s": 45,
    "total_time_s": 210,
    "pours": [
      { "step": 1, "time_s": 0, "water_g": 60 },
      { "step": 2, "time_s": 45, "water_g": 60 },
      { "step": 3, "time_s": 90, "water_g": 60 },
      { "step": 4, "time_s": 135, "water_g": 60 },
      { "step": 5, "time_s": 180, "water_g": 60 }
    ]
  },
  "suitable_for": {
    "roast_levels": ["light", "medium"],
    "origins": ["Ethiopia", "Kenya", "Colombia"],
    "processes": ["washed", "natural"]
  },
  "instructions": "Five equal pours of 60g each. First two pours (40%) control sweetness/acidity balance; last three pours (60%) control strength. Use coarse grind, similar to French press.",
  "tips": "The first pour adjusts sweetness vs acidity. 60g first pour = standard, 50g = sweeter. Adjust last three pours for desired strength."
}
```

### 3.5 Data Requirements for RAG

- **Minimum viable:** 50-100 well-structured recipes from 3-5 expert sources
- **Target:** 50-80 recipes covering V60, Kalita Wave, Origami
- **Chunking strategy:** One recipe = one chunk (recipes are self-contained units)
- **Vector database:** ChromaDB (free, local, easy setup) or FAISS (fast, lightweight)

---

## 4. Component 2: Bean Profile Feature Extraction

### 4.1 The Problem

Roaster descriptions are free-text and highly variable:

- "Ethiopia Yirgacheffe, washed, light roast, notes of blueberry, jasmine, bergamot"
- "Colombian single-origin from Huila. Honey process. Stone fruit, caramel, milk chocolate. Medium roast."
- "Natural processed Ethiopian from Guji. Very fruity with intense strawberry and tropical notes."

The extraction system must convert these into structured feature vectors for downstream ML components.

### 4.2 LLM-Based Extraction vs. Traditional NER

Research comparing approaches:

| Approach                                                  | Pros                                                                                  | Cons                                              | Accuracy                                   |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------ |
| **LLM with structured output** (GPT-4, Claude, local LLM) | Handles variable phrasing; zero-shot; extracts relationships; outputs structured JSON | Cost per extraction; latency                      | ~90-95% F1 on product attribute extraction |
| **Traditional NER** (spaCy, GLiNER, BERT-NER)             | Fast; cheap; runs locally                                                             | Requires training data; brittle to novel phrasing | ~70-85% F1 depending on domain             |
| **Hybrid** (LLM + NER verification)                       | Best of both; LLM extracts, NER validates                                             | More complex pipeline                             | ~95%+                                      |

Key research findings:

- **GPT-NER** (NAACL 2025): Proposes adding a verification step where the LLM confirms its own extractions, significantly improving reliability.
- **llmNER** (arXiv 2406.04528): A Python library for zero-shot and few-shot NER with LLMs, providing an easy interface.
- **LLM-based extraction for product descriptions** is now the dominant approach for e-commerce feature extraction due to its flexibility with variable phrasing.

**Recommendation for BrewMatch:** Use LLM-based extraction with structured JSON output (via function calling or structured output mode). This handles the wide variety of roaster description formats without requiring labeled training data. Add a simple validation layer that checks extracted fields against known taxonomy values.

### 4.3 Coffee Flavor Taxonomy

The canonical taxonomies for structuring coffee flavor data:

#### World Coffee Research (WCR) Sensory Lexicon

- **110+ standardized flavor and aroma terms**
- Purely descriptive (not quality-ranking)
- Created by WCR in collaboration with SCA and UC Davis
- Free to download and use
- Latest edition: Version 1.1 (2016)
- Available at: [worldcoffeeresearch.org/resources/sensory-lexicon](https://worldcoffeeresearch.org/resources/sensory-lxicon)

#### SCA Coffee Taster's Flavor Wheel

- Visual companion to the WCR Lexicon
- Hierarchical structure: broad categories (Floral, Fruity, Sweet) branching into specific terms (Jasmine, Blueberry, Caramel)
- Largest collaborative research on coffee flavor ever completed
- Available at: [sca.coffee/research/coffee-tasters-flavor-wheel](https://sca.coffee/research/coffee-tasters-flavor-wheel)

#### Proposed Bean Profile Feature Vector

```json
{
  "origin": {
    "country": "Ethiopia",
    "region": "Yirgacheffe",
    "farm": null,
    "altitude_m": { "min": 1800, "max": 2200 }
  },
  "bean": {
    "species": "arabica",
    "variety": ["Heirloom"],
    "process": "washed"
  },
  "roast": {
    "level": "light",
    "roaster": "Onyx Coffee Lab"
  },
  "flavor": {
    "primary_notes": ["blueberry", "jasmine"],
    "secondary_notes": ["bergamot", "tea-like"],
    "clusters": ["floral", "fruity"]
  },
  "metadata": {
    "source_text": "Ethiopia Yirgacheffe, washed, light roast, notes of blueberry, jasmine, bergamot",
    "extraction_confidence": 0.92
  }
}
```

### 4.4 Flavor Clustering Strategy

For the taste prediction model, individual flavor notes are too sparse. Cluster them using the SCA Flavor Wheel hierarchy:

1. **Floral**: jasmine, chamomile, rose, lavender
2. **Fruity**: berry (blueberry, strawberry, raspberry), citrus (bergamot, lemon, grapefruit), stone fruit (peach, apricot), tropical (mango, pineapple)
3. **Sweet**: caramel, honey, vanilla, brown sugar, maple
4. **Nutty/Cocoa**: almond, hazelnut, peanut, chocolate (milk, dark), cocoa
5. **Spices**: cinnamon, clove, nutmeg, pepper
6. **Roasted**: tobacco, leather, pipe tobacco, toasted
7. **Vegetal/Green**: herbal, grassy, olive, tea-like
8. **Fermented**: winey, whisky, rum, overripe fruit

This reduces hundreds of individual notes to ~8-10 clusters that serve as features for the prediction model.

---

## 5. Component 3: Taste Score Prediction (Supervised Learning)

### 5.1 Problem Formulation

**Task:** Predict a user's rating (1-10) for a specific coffee brewed with a specific recipe.

**Features:**

- Bean profile features (origin, process, roast level, flavor clusters)
- Recipe parameters (grind, temp, ratio, bloom time, pour structure)
- User history features (average rating, preferred clusters, number of prior brews)
- Interaction features (roast_level x water_temp, origin x process)

**Target:** User-reported taste rating (1-10 scale, treated as continuous for regression)

### 5.2 Model Choice: Gradient-Boosted Regression

Research comparing XGBoost vs LightGBM vs CatBoost:

| Model        | Training Speed  | Memory         | Accuracy                             | Categorical Support   |
| ------------ | --------------- | -------------- | ------------------------------------ | --------------------- |
| **XGBoost**  | Baseline        | Higher         | Strong for ranking tasks             | Requires encoding     |
| **LightGBM** | Faster (1.5-2x) | More efficient | Slightly better in some benchmarks   | Native support        |
| **CatBoost** | Slowest         | Moderate       | Best with heavy categorical features | Native, best-in-class |

**Recommendation:** **LightGBM** for BrewMatch because:

1. Native categorical feature support (origin country, process, roast level, flavor clusters)
2. Faster training -- important for iterative development
3. More memory-efficient -- relevant if deploying on limited infrastructure
4. Comparable accuracy to XGBoost in practice

However, **XGBoost** is equally viable and has better documentation/community support, which matters for a course project.

### 5.3 Cold-Start Strategy

The cold-start problem is central to BrewMatch. Research (BayesCNS, arXiv 2410.02126) proposes unified Bayesian approaches for this exact scenario.

**Proposed Cold-Start Strategy:**

| Phase                        | Data Available       | Approach                                                                                                                                 | Expected RMSE            |
| ---------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| **Global (0 brews)**         | No user data         | Global average rating per recipe-bean combination. Use Bayesian shrinkage: weighted average of (global mean + recipe-bean specific mean) | ~2.0-2.5 (on 1-10 scale) |
| **Directional (3-5 brews)**  | Few user ratings     | Content-based features + global priors. LightGBM trained on global data, with user bias term estimated from their few ratings            | ~1.5-2.0                 |
| **Personalized (10+ brews)** | Sufficient user data | Full LightGBM model with user-specific features. Collaborative filtering signals incorporated                                            | ~1.0-1.5                 |

### 5.4 Bootstrap Strategy for Cold Start

Since we lack user data initially, we need to bootstrap:

1. **Public ratings data:** Use CQI/Cup of Excellence scores (100-point scale, rescale to 1-10) as initial training data
2. **Global priors:** Compute Bayesian average per (origin x process x roast_level) group:
   ```
   Bayesian_avg = (n * group_mean + m * global_mean) / (n + m)
   ```
   where `n` = number of ratings in group, `m` = smoothing parameter (typically 5-10)
3. **Expert heuristics:** Encode known coffee science rules as synthetic training examples:
   - "Light roast + high temp (93-96C) + fine grind = bright, acidic cup" -> rating depends on user preference for acidity
   - "Dark roast + low temp (85-88C) + coarse grind = mellow, sweet cup"

### 5.5 Data Requirements

For the prediction model to work well:

| Data Volume          | What's Achievable                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------- |
| **< 50 ratings**     | Unreliable. Use global priors only.                                                                           |
| **50-200 ratings**   | Directional predictions with high uncertainty. LightGBM with heavy regularization (few trees, shallow depth). |
| **200-1000 ratings** | Reasonable predictions. Model can learn interaction effects.                                                  |
| **1000+ ratings**    | Full model capability. Can identify complex patterns.                                                         |
| **5000+ ratings**    | Strong personalized predictions with collaborative filtering.                                                 |

**Practical reality for a course project:** Expect 50-200 ratings during the project. Design the system to work well with this constraint by leaning heavily on global priors and content-based features rather than collaborative filtering.

---

## 6. Component 4: Recipe Optimization

### 6.1 Problem Formulation

**Goal:** Find the recipe parameters that maximize predicted taste score for a given bean and user.

**Parameters to Optimize (~7):**

| Parameter          | Type       | Range                                 | Notes                      |
| ------------------ | ---------- | ------------------------------------- | -------------------------- |
| Grind size         | Discrete   | 1-10 scale (very fine to very coarse) | Mapped to grinder settings |
| Water temperature  | Continuous | 85-96C                                | Constrained by roast level |
| Coffee:water ratio | Continuous | 1:14 to 1:18                          |                            |
| Bloom time         | Continuous | 30-90 seconds                         |                            |
| Number of pours    | Discrete   | 2, 3, 4, 5                            |                            |
| Pour interval      | Continuous | 15-60 seconds                         |                            |
| Total water weight | Continuous | 200-500g                              | Function of dose and ratio |

**Constraints:**

- Extraction yield should target 18-22% (SCA standard)
- Dark roasts should use lower temperature (80-88C)
- Light roasts should use higher temperature (90-96C)
- Very fine grind + very high temperature + very long time = infeasible (overextracted)

### 6.2 Approach Comparison

| Approach                  | Experiments Needed        | Handles Constraints | Handles Mixed Types            | Adaptive |
| ------------------------- | ------------------------- | ------------------- | ------------------------------ | -------- |
| **Grid Search**           | 240+ (5 x 4 x 4 x 3 grid) | By exclusion        | With discretization            | No       |
| **Random Search**         | 50-100                    | By rejection        | Yes                            | No       |
| **Bayesian Optimization** | 15-30                     | Natively            | Yes (with TPE)                 | Yes      |
| **SMAC**                  | 20-40                     | Yes                 | Yes (designed for categorical) | Yes      |

**The coffee brewing constraint makes Bayesian optimization strongly preferred.** Each "experiment" requires the user to physically brew a cup of coffee -- making every evaluation expensive in time and materials. Grid search testing 5 grind sizes x 4 temperatures x 4 ratios x 3 bloom times = 240 brews is impractical. Bayesian optimization can find near-optimal parameters in 15-30 brews.

### 6.3 Recommended Tool: Optuna

[Optuna](https://optuna.readthedocs.io/) is the recommended framework for several reasons:

1. **Native mixed parameter support:**
   ```python
   def objective(trial):
       grind = trial.suggest_int("grind", 1, 10)          # discrete
       temp = trial.suggest_float("temp", 85.0, 96.0)     # continuous
       ratio = trial.suggest_float("ratio", 14.0, 18.0)   # continuous
       bloom = trial.suggest_int("bloom", 30, 90)          # discrete
       pours = trial.suggest_categorical("pours", [2,3,4,5]) # categorical
       interval = trial.suggest_int("interval", 15, 60)    # discrete
       return predicted_taste_score(grind, temp, ratio, bloom, pours, interval)
   ```
2. **Constraint support:** OptunaHub provides constrained samplers (inequality constraints via `SCBO` or custom constraint functions)
3. **TPE sampler (default):** Tree-structured Parzen Estimator handles mixed discrete/continuous spaces well
4. **GP sampler:** For fully continuous subspaces, Gaussian Process-based Bayesian optimization is available
5. **Active research:** EACL 2026 paper demonstrates Bayesian optimization specifically for RAG pipeline tuning, confirming its applicability to multi-parameter optimization

### 6.4 Optimization Strategy

**Phase 1: Initialization (Global Search)**

- Use the RAG system to retrieve the best-matching expert recipe for the bean profile
- Start from the expert recipe's parameters as the initial point
- Run 5-10 random exploration samples around this point (+/- 20% variation)

**Phase 2: Exploitation (Local Search)**

- Fit a surrogate model to accumulated brew results
- Use Expected Improvement (EI) acquisition function to suggest next parameters
- Each suggested brew is presented to the user with an explanation of what changed and why

**Phase 3: Convergence**

- After 10-15 brews for a specific bean, the surrogate model should identify a near-optimal region
- Present the optimized recipe to the user with confidence intervals

### 6.5 Practical Constraint: User Must Brew

Unlike typical optimization problems where the objective function is cheap to evaluate, here each evaluation requires:

1. User grinds coffee (~30 seconds)
2. User heats water to specific temperature (~1-2 minutes)
3. User performs pour-over with specific timing (~3-4 minutes)
4. User tastes and rates (~1 minute)

Total: ~6-8 minutes per evaluation. This makes sample efficiency critical.

**Recommendation:** Present optimization as a "brew session" where the user commits to 3-5 sequential brews. After each brew, the system suggests parameters for the next one, explaining what changed and why.

---

## 7. Component 5: Personalization Layer (Hybrid Cold-Start)

### 7.1 Architecture

The personalization layer must handle three distinct phases:

```
New User (0 brews)
    |
    v
[Onboarding Quiz: 5-7 questions]
    - Preferred flavor clusters (fruity? chocolatey? floral?)
    - Usual roast preference (light/medium/dark)
    - Brewing equipment (V60? Kalita Wave? Origami?)
    - Experience level (beginner/intermediate/advanced)
    |
    v
[Initial Profile -> Global Best-Fit Recipes]
    |
    v
Directional Phase (3-5 brews)
    |
    v
[Content-Based Model + User Bias]
    |
    v
Personalized Phase (10+ brews)
    |
    v
[Full Hybrid Model: Content + Collaborative]
```

### 7.2 Research on Hybrid Cold-Start

Research consistently confirms that hybrid systems outperform pure collaborative or content-based approaches for cold-start:

- **Hybrid (CF + Content-based + Demographic):** Best for new-user cold-start (JATIT 2022, KTH 2022)
- **Knowledge-based + CF:** Particularly effective for small datasets (Frontiers in Computer Science, 2024)
- **BayesCNS (arXiv 2410.02126):** Unified Bayesian approach treating cold-start as an online learning problem with probabilistic priors that update with each new observation

**Key insight for BrewMatch:** The "knowledge-based" component is BrewMatch's coffee science rules (extraction science, roast-temperature relationships). These provide strong priors that reduce the cold-start data requirement.

### 7.3 Recommendation Strategies by Phase

#### Phase 0: Onboarding (0 brews)

- Ask 5-7 preference questions to establish initial user profile
- Map answers to flavor clusters and roast preferences
- Use content-based filtering: match bean profiles to user's stated preferences
- Recommend the most popular recipes for similar bean types
- **Data needed:** Just the onboarding quiz answers

#### Phase 1: Global Best-Fit (1-3 brews)

- Recommend recipes with highest global average ratings for the bean type
- Use Bayesian shrinkage estimator for recipe ratings
- Learn initial user bias: does this user rate higher/lower than average?
- **Data needed:** User's 1-3 ratings + global rating database

#### Phase 2: Directional (3-5 brews)

- LightGBM model with user bias term
- Content features dominate (bean profile + recipe parameters)
- User-specific features: average rating, rating variance, preference drift
- **Data needed:** 3-5 user ratings

#### Phase 3: Full Personalized (10+ brews)

- Full hybrid model
- Collaborative signals emerge: "users who liked Bean A with Recipe X also liked Bean B with Recipe Y"
- Recipe optimization becomes personalized (optimizer uses user-specific taste model)
- **Data needed:** 10+ user ratings

### 7.4 Collaborative Filtering Considerations

Traditional matrix factorization (user x item rating matrix) is not ideal for BrewMatch because:

1. **Items are not static:** Each brew is a unique combination of (bean + recipe + parameters)
2. **Sparse matrix:** Even with 1000 users, each rates maybe 20-50 brews out of thousands of possible combinations
3. **Cold-start dominant:** Most users are new

**Better approach:** Treat collaborative filtering at the **flavor cluster level** rather than individual recipe level:

- "Users who prefer fruity Ethiopian coffees also tend to prefer washed process with medium grind"
- This generalizes much better with sparse data

---

## 8. Data Requirements Summary

### 8.1 Per-Component Minimums

| Component                   | Minimum Data      | Target Data              | Notes                                              |
| --------------------------- | ----------------- | ------------------------ | -------------------------------------------------- |
| **RAG Knowledge Base**      | 50 recipes        | 50-80 recipes            | From 5+ expert sources; each recipe has ~10 fields |
| **Bean Profile Extraction** | 0 (zero-shot LLM) | 0 (zero-shot works)      | LLM handles extraction without training data       |
| **Taste Score Prediction**  | 50 global ratings | 500+ ratings             | For personalization, need 10+ per user             |
| **Recipe Optimization**     | 5 brews per bean  | 15-30 brews per bean     | Bayesian optimization converges with ~15-30        |
| **Personalization**         | Onboarding quiz   | 50 users x 10 brews each | Collaborative filtering needs 500+ user-brew pairs |

### 8.2 Data Collection Strategy

1. **Pre-launch (during project):**
   - Curate 100-200 recipes from expert sources (Hoffmann, Kasuya, Rao, Onyx, Barista Hustle)
   - Collect 50-100 public ratings from coffee forums, Reddit, coffee review sites
   - Use CQI database (1,310+ Arabica reviews) for bean quality scores

2. **Soft launch (first users):**
   - Onboarding quiz captures initial preferences
   - Each brew generates a data point (bean + recipe + parameters + rating)
   - Recipe optimization creates structured data automatically

3. **Growth phase:**
   - User-generated recipes add to knowledge base
   - Rating volume enables collaborative filtering
   - Flavor preference clusters become more refined

---

## 9. Existing Coffee Data Sources

### 9.1 Coffee Quality Data

| Source                            | Data Type                                                              | Volume                      | Access                                                                                                                                |
| --------------------------------- | ---------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **CQI Database (via Kaggle)**     | Arabica/Robusta quality scores, origin, processing, sensory attributes | ~1,310 Arabica, ~28 Robusta | Free - [Kaggle: volpatto/coffee-quality-database-from-cqi](https://www.kaggle.com/datasets/volpatto/coffee-quality-database-from-cqi) |
| **CQI May 2023 (Kaggle)**         | Updated CQI scrape with more recent reviews                            | Larger than original        | Free - [Kaggle: fatihb/coffee-quality-data-cqi](https://www.kaggle.com/datasets/fatihb/coffee-quality-data-cqi)                       |
| **Coffee Quality with Locations** | Quality scores + geographic origin data                                | Moderate                    | Free - [Kaggle: adampq/coffee-quality-with-locations](https://www.kaggle.com/datasets/adampq/coffee-quality-with-locations-of-origin) |
| **Cup of Excellence**             | Competition results with detailed scoring                              | Annual winners only         | Free - [cupofexcellence.org](https://cupofexcellence.org)                                                                             |
| **WCR Sensory Lexicon**           | 110+ flavor terms with definitions and references                      | Taxonomy                    | Free - [worldcoffeeresearch.org](https://worldcoffeeresearch.org/resources/sensory-lexicon)                                           |
| **SCA Flavor Wheel**              | Hierarchical flavor categorization                                     | Taxonomy                    | Free - [sca.coffee](https://sca.coffee/research/coffee-tasters-flavor-wheel)                                                          |

### 9.2 Recipe Data Sources (Manual Curation Required)

| Source                            | Recipes Available      | Structure                       | URL                                 |
| --------------------------------- | ---------------------- | ------------------------------- | ----------------------------------- |
| **James Hoffmann (YouTube/Blog)** | 50+ methods            | Unstructured (video/text)       | youtube.com/@jameshoffmann          |
| **Barista Hustle**                | 20+ structured courses | Semi-structured (course format) | baristahustle.com                   |
| **Onyx Coffee Lab**               | 10+ brew guides        | Structured (step-by-step)       | onyxcoffeelab.com/pages/brew-guides |
| **unpacking.coffee**              | 30+ recipes            | Structured (consistent fields)  | unpacking.coffee                    |
| **Honest Coffee Guide**           | 20+ recipes            | Structured (parameter tables)   | honestcoffeeguide.com               |
| **Pour Over Project**             | 10+ V60 recipes        | Structured comparison           | pouroverproject.com                 |

### 9.3 Note on Data Availability

There is **no existing machine-readable database** of coffee brewing recipes with parameters. All recipe data requires manual curation from the sources above. This is actually an advantage for BrewMatch -- the curated knowledge base is a proprietary asset that adds value.

The CQI datasets on Kaggle are the most valuable for bootstrapping the taste prediction model, as they contain professional cupping scores broken down by attribute (aroma, flavor, aftertaste, acidity, body, balance, etc.) alongside origin and processing information.

---

## 10. Privacy Considerations

### 10.1 Classification of Data

| Data Type                   | Classification       | Examples                                         |
| --------------------------- | -------------------- | ------------------------------------------------ |
| **Brew parameters**         | Non-personal         | Grind size, temperature, ratio                   |
| **Bean preferences**        | Potentially personal | Preferred origins, roast levels, flavor clusters |
| **Taste ratings**           | Personal data        | Individual ratings, rating patterns              |
| **Onboarding quiz answers** | Personal data        | Flavor preferences, experience level             |
| **Usage patterns**          | Personal data        | Brew frequency, time of day, recipe exploration  |
| **Device/equipment info**   | Potentially personal | Grinder model, kettle type, scale model          |

### 10.2 GDPR and Privacy Framework

Research into coffee app privacy practices (GrindSize, COFE App) reveals:

1. **Taste preference data qualifies as personal data** under GDPR when it can identify a natural person
2. **Dietary preferences** can escalate to special category data if they reveal health conditions (e.g., decaf preferences suggesting caffeine sensitivity)
3. **Lawful basis** for processing: Consent (most appropriate for personalization features)

### 10.3 Recommended Privacy Architecture

**Data Minimization:**

- Store only what is needed: ratings, basic preferences, brew history
- Do not collect: name, email, location, payment info (not needed for core functionality)
- Use anonymous identifiers (UUID) rather than personal identifiers

**Privacy by Design:**

- All personalization runs on-device or on-user-data-isolated infrastructure
- Global model training uses anonymized, aggregated data only
- Users can export and delete all their data
- Clear consent flows for any data collection

**Data Retention:**

- Active preference data: retained as long as user is active
- Brew history: retained for personalization, deletable on request
- Global model contributions: anonymized and irreversible

**Practical approach for course project:**

- Store user data locally (SQLite or local JSON files)
- No cloud storage of personal data
- Privacy notice included in app documentation
- User data exportable as JSON

---

## 11. Technology Stack Recommendations

### 11.1 ML/AI Stack

| Component                         | Recommended Tool                                          | Alternative              | Rationale                                  |
| --------------------------------- | --------------------------------------------------------- | ------------------------ | ------------------------------------------ |
| **Embedding Model**               | all-MiniLM-L6-v2 (local) or OpenAI text-embedding-3-small | all-mpnet-base-v2        | Free/cheap, sufficient quality             |
| **Vector Database**               | ChromaDB                                                  | FAISS, Qdrant            | Easy setup, local, good Python integration |
| **LLM (Extraction + Generation)** | OpenAI GPT-4o-mini or Claude Haiku                        | Local LLM (Llama 3.1 8B) | Cost-effective, good structured output     |
| **Prediction Model**              | LightGBM                                                  | XGBoost                  | Native categorical support, fast           |
| **Optimization**                  | Optuna (TPE sampler)                                      | BoTorch                  | Easy mixed parameter spaces                |
| **Framework**                     | Python + scikit-learn                                     | -                        | Standard ML stack                          |

### 11.2 Data Stack

| Component           | Recommended Tool                | Rationale                                    |
| ------------------- | ------------------------------- | -------------------------------------------- |
| **Recipe Storage**  | JSON files (version controlled) | Simple, human-readable, easy to curate       |
| **User Data**       | SQLite                          | Local, no server, SQL queries                |
| **Bean Data**       | Pandas DataFrames + CSV         | Standard, interoperable with Kaggle datasets |
| **API (if needed)** | FastAPI                         | Lightweight, Python-native                   |

### 11.3 Integration Architecture

```
[User Input: Bean Description + Preferences]
        |
        v
[Bean Profile Extractor (LLM)] --> Structured Feature Vector
        |
        v
[Recipe Retriever (RAG)] --> Top-5 Matching Recipes
        |
        v
[Taste Predictor (LightGBM)] --> Predicted Ratings for Each Recipe
        |
        v
[Recipe Optimizer (Optuna)] --> Optimized Parameters for Best Recipe
        |
        v
[Instruction Generator (LLM)] --> Natural Language Brew Guide
        |
        v
[User Brews + Rates] --> Feedback to Personalization Layer
```

---

## 12. Sources

### Coffee Science

- [Coffee Extraction Chart Chemistry (Barista Life)](https://baristalife.co/blogs/blog/coffee-extraction-chart)
- [Effects of Grind Size, Temperature, and Brewing Ratio on Immersion Brewed Coffee (ScienceDirect, 2023)](https://www.sciencedirect.com/science/article/pii/S2772502223000719)
- [TDS, EY, and Sensory Evaluation in Coffee Brewing (Coffee Fanatics)](https://coffeefanatics.jp/en/tds-ey-and-sensory-evaluation-in-coffee-brewing/)
- [Brewing Fundamentals (Coffee Science Foundation)](https://coffeescience.foundation/brewing-fundamentals)
- [The Science Behind Kasuya 4:6 Method (Home-Barista)](https://www.home-barista.com/brewing/science-behind-kasuya-4-6-method-t75697.html)

### RAG and Embedding Models

- [MTEB Leaderboard (Hugging Face)](https://huggingface.co/spaces/mteb/leaderboard)
- [Top Embedding Models on MTEB (Modal Blog)](https://modal.com/blog/mteb-leaderboard-article)
- [RAG Benchmarks Leaderboard (AwesomeAgents)](https://awesomeagents.ai/leaderboards/rag-benchmarks-leaderboard/)
- [Structure Augmented Generation (STAG) (Meibel.ai)](https://www.meibel.ai/post/structure-augmented-generation-bridging-structured-and-unstructured-data-for-enhanced-rag-systems)
- [HybridRAG: Merging Structured and Unstructured Data (ADaSci)](https://adasci.org/blog/hybridrag-merging-structured-and-unstructured-data-for-cutting-edge-information-extraction)
- [RecipeRAG: Knowledge Graph-Driven Personalized Recipe Generation (CEUR WS Vol. 4079)](https://ceur-ws.org/Vol-4079/paper5.pdf)
- [LlamaIndex Advanced RAG Cheat Sheet](https://www.llamaindex.ai/blog/a-cheat-sheet-and-some-recipes-for-building-advanced-rag-803a9d94c41b)
- [Leveraging Bayesian Optimization for Accelerating RAG Pipeline Tuning (EACL 2026)](https://aclanthology.org/2026.eacl-industry.19.pdf)

### Bean Profile and Flavor Taxonomy

- [WCR Sensory Lexicon (World Coffee Research)](https://worldcoffeeresearch.org/resources/sensory-lexicon)
- [SCA Coffee Taster's Flavor Wheel](https://sca.coffee/research/coffee-tasters-flavor-wheel)
- [GPT-NER: Named Entity Recognition via Large Language Models (NAACL 2025)](https://tianweiz07.github.io/Papers/25-naacl.pdf)
- [llmNER: Zero/Few-Shot NER with LLMs (arXiv)](https://arxiv.org/html/2406.04528v1)

### Gradient Boosting and Recommendation Systems

- [Mastering Gradient Boosting: XGBoost vs LightGBM vs CatBoost](https://medium.com/@phoenixarjun007/mastering-gradient-boosting-xgboost-vs-lightgbm-vs-catboost-explained-simply-3bfcf9d9524d)
- [XGBoost vs LightGBM (xgboosting.com)](https://xgboosting.com/xgboost-vs-lightgbm/)
- [BayesCNS: A Unified Bayesian Approach to Cold Start (arXiv)](https://arxiv.org/html/2410.02126v1)
- [Applications of Bayesian Recommender Systems (University of Manchester)](https://test.pure.manchester.ac.uk/ws/portalfiles/portal/234005876/FULL_TEXT.PDF)
- [Hybrid Recommendation System for Cold Start (JATIT)](http://www.jatit.org/volumes/Vol100No11/7Vol100No11.pdf)
- [Hybrid Attribute-Based Recommender (Frontiers in Computer Science, 2024)](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2024.1404391/full)

### Optimization

- [Optuna Documentation](https://optuna.readthedocs.io/)
- [OptunaHub Bayesian Optimization Samplers](https://hub.optuna.org/tags/bayesian-optimization/)
- [State-of-the-Art ML Hyperparameter Optimization with Optuna (Towards Data Science)](https://towardsdatascience.com/state-of-the-art-machine-learning-hyperparameter-optimization-with-optuna-a315d8564de1)

### Coffee Data Sources

- [Coffee Quality Database from CQI (Kaggle)](https://www.kaggle.com/datasets/volpatto/coffee-quality-database-from-cqi)
- [Coffee Quality Data CQI May 2023 (Kaggle)](https://www.kaggle.com/datasets/fatihb/coffee-quality-data-cqi)
- [Coffee Quality with Locations (Kaggle)](https://www.kaggle.com/datasets/adampq/coffee-quality-with-locations-of-origin)
- [Cup of Excellence](https://cupofexcellence.org)

### Privacy

- [GrindSize Coffee Brewing Tracker Privacy Policy](https://co.ffee.app/privacy)
- [COFE App Terms and Conditions (GDPR Compliant)](https://www.cofeapp.com/terms-and-conditions-users/)
- [OriginCollective Coffee Analytics Privacy](https://www.origin-collective.com/privacy)

### Recipe Sources

- [Onyx Coffee Lab Brew Guides](https://onyxcoffeelab.com/pages/brew-guides)
- [Pour Over Project: V60 Recipes](https://pouroverproject.com/v60-recipes-rao-hoffman-kasuya-drip-coffee/)
- [Barista Hustle Brewing Courses](https://www.baristahustle.com)
- [4:6 Method Download (Scribd)](https://www.scribd.com/document/920815022/4-6-Method-Download)

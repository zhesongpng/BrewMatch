# BrewMatch Implementation Roadmap

Date: 2026-05-09
Status: Phase 01 — Implementation Roadmap

---

## Phase Overview

| Phase                   | Weeks | Focus                                                          | Deliverable                          |
| ----------------------- | ----- | -------------------------------------------------------------- | ------------------------------------ |
| 1: Data Foundation      | 1-3   | Schema, recipes, synthetic data, extraction pipeline           | `data/` directory with all artifacts |
| 2: ML Components        | 4-6   | Taste prediction, RAG retrieval, optimization, personalization | `models/` + trained components       |
| 3: Web UI + Integration | 7-8   | Streamlit app wiring all components end-to-end                 | Working web application              |
| 4: Evaluation           | 9-10  | Metrics, plots, iteration on underperforming components        | `evaluation/` with results           |
| 5: Demo Prep            | 11-12 | Demo script, presentation, course report                       | Submission-ready package             |

---

## Phase 1: Data Foundation (Weeks 1-3)

### Week 1: Schema + Recipe Curation

- Define recipe JSON schema, bean profile schema, user taste profile schema
- Curate 50-80 recipes from expert sources (Hoffmann, Kasuya, Rao, Onyx, Barista Hustle)
- Each recipe must have ALL parameters: dose, ratio, grind, temp, bloom, pours, total time
- Tag each recipe with suitable_for (roast levels, origins, processes, flavor profiles)

### Week 2: Synthetic Data Generator

- Build parameter-response surface from extraction theory (yield = f(grind, temp, time, ratio))
- Define 3-5 virtual expert preference profiles (bright/acidic, sweet/balanced, bold/chocolatey)
- Generate 500-1000 synthetic (bean, recipe, rating) triples
- Generate 100 virtual users with random profiles and 5-50 ratings each

### Week 3: Bean Extraction Pipeline

- Build LLM-based bean profile extractor with structured JSON output
- Implement validation layer (check against known taxonomy values)
- Test against 20 real roaster descriptions from Singapore roasters
- Build fallback manual entry form

---

## Phase 2: ML Components (Weeks 4-6)

### Week 4: Taste Prediction + RAG Retrieval

- **Taste Predictor**: Train LightGBM on synthetic data
  - Features: bean profile (encoded) + recipe parameters + user history
  - Evaluate RMSE on held-out test set (target < 1.5)
  - Implement global model + per-user bias layer
- **Recipe Retriever**: Build RAG pipeline
  - Embed recipes using all-MiniLM-L6-v2
  - Store in ChromaDB
  - Implement query → retrieval → ranking
  - Evaluate precision@3 on 20 test queries (target > 0.8)

### Week 5: Recipe Optimization

- Implement Optuna TPE sampler for recipe parameter optimization
- Define search space with constraints (grind, temp, ratio, bloom, pours)
- Implement initialization from best-matching recipe
- Test convergence on 20 synthetic beans (target < 5 iterations)
- Generate convergence plots

### Week 6: Personalization Layer

- Implement onboarding quiz → initial taste profile
- Implement Phase 1 (global + user bias): 1-4 brews
- Implement Phase 2 (content-based): 5-9 brews
- Implement Phase 3 (hybrid): 10+ brews
- Build demo mode with simulated user history

---

## Phase 3: Web UI + Integration (Weeks 7-8)

### Week 7: Streamlit Application

- Bean input page (text entry + extraction display)
- Recipe recommendation page (top-3 with predicted ratings)
- Brew feedback page (thumbs up/down + directional flags)
- Recipe adjustment page (shows what changed and why)

### Week 8: Integration + Demo Mode

- Wire all components into end-to-end flow
- Add demo mode with pre-seeded "Alex" user
- Add side-by-side comparison view (global vs. personalized)
- Add evaluation dashboard (metrics table + convergence plots)
- End-to-end testing

---

## Phase 4: Evaluation (Weeks 9-10)

### Week 9: Component Evaluation

- Run all 5 evaluation metrics against targets
- RAG retrieval: precision@3 on 20 queries
- Bean extraction: field-level accuracy on 20 descriptions
- Taste prediction: RMSE on held-out synthetic test set
- Recipe optimization: convergence on 20 test beans
- Personalization: rating improvement global vs. personalized

### Week 10: Iteration + Polish

- Fix any underperforming components
- Generate final evaluation plots and tables
- Write evaluation section of course report

---

## Phase 5: Demo Preparation (Weeks 11-12)

### Week 11: Presentation + Report

- Write demo script (Flow 3 from user flows)
- Prepare presentation slides
- Write course report (methodology, architecture, results, discussion)

### Week 12: Final Polish

- Rehearse demo
- Prepare backup screenshots in case of live demo failure
- Finalize all deliverables

---

## Risk Mitigations

| Risk                              | Mitigation                                                   | Trigger                            |
| --------------------------------- | ------------------------------------------------------------ | ---------------------------------- |
| Recipe curation too slow          | Start with 50 recipes; generate LLM variants for coverage    | End of Week 2, <30 recipes curated |
| Synthetic data doesn't generalize | Add noise and variation; validate against expert heuristics  | RMSE > 2.0 on validation set       |
| LightGBM overfits on small data   | Use conservative hyperparams (max_depth=4, n_estimators=100) | Training RMSE << validation RMSE   |
| Optuna doesn't converge           | Fall back to iterative single-parameter optimization         | >10 iterations for convergence     |
| Streamlit too limiting            | Switch to Flask + simple HTML; demo still works              | Week 7, UI blocks progress         |

---

## Requirements Traceability

Each brief requirement maps to an implementation component:

| Brief Requirement                          | Implementation Component                         | Phase |
| ------------------------------------------ | ------------------------------------------------ | ----- |
| "Bean profile input via manual text entry" | Bean Profile Extractor (LLM) + manual entry form | 1     |
| "Initial recipe recommendation"            | Recipe Retriever (RAG) + Taste Predictor ranking | 2     |
| "Post-brew taste feedback capture"         | Feedback UI (thumbs + directional flags)         | 3     |
| "Personalization adjustments"              | Personalization Layer (4 phases)                 | 2     |
| "Recipe knowledge base 50-80 curated"      | Curated recipes + parameter-space variations     | 1     |
| "Taste Score Prediction (Supervised)"      | LightGBM regression                              | 2     |
| "Recipe Optimization (Optimization)"       | Optuna TPE sampler                               | 2     |
| "Bean Profile Extraction"                  | LLM structured output + validation               | 1     |
| "Personalization Layer"                    | Bean-aware to full hybrid with onboarding        | 2     |
| "Embedding-based retrieval (RAG)"          | ChromaDB + all-MiniLM-L6-v2                      | 2     |

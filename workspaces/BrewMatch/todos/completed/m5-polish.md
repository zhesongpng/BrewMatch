# Milestone 5: Polish & Course Submission

Estimated sessions: 1
Depends on: Milestone 4 complete (evaluation results generated)

---

- [x] **Update brief to reflect 5 directional flags**
  - Verified: "astringent" already present in brief Section 4 and Section 5

- [x] **Final demo walkthrough and polish**
  - Full demo flow: landing → demo mode → Alex's profile → bean input → recommendation → brew → feedback → diagnosis → history
  - Evaluation dashboard: all metrics display correctly (added NDCG@10, Recall@10, learning curve, convergence charts)
  - Both demo mode (in-memory) and production mode (file-based SQLite) verified
  - 652 tests pass, 0 failures
  - All 46 recipes indexed by retriever
  - Predictor loads and is trained

## Verification

- All 9 pages import and have `render()`: landing, onboarding, bean_input, recommend, brew_session, diagnosis, history, demo, evaluation
- DB schema creates `users` and `brew_history` tables
- Recipe knowledge base: 46 recipes from 47 JSON files
- Taste predictor: loads from `models/taste_predictor.joblib`, `is_trained=True`
- Evaluation dashboard: reads `models/evaluation_results.json` with all 5 sections
- Added learning curve chart (was computed but never displayed)
- Added NDCG@10, Recall@10 metrics and convergence chart to evaluation page
- Full test suite: 652 pass, 0 fail, 2 cosmetic warnings (Optuna ratio)

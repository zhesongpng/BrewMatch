# Milestone 3: Streamlit Web Application

Estimated sessions: 5-7
Depends on: Milestone 2 complete (ML models trained and serialized)

---

## 3.1 App skeleton

- [ ] **Build Streamlit app skeleton with navigation**
      Implements: `specs/user-interface.md` Sections 2, 5, 6
  - Wide mode, sidebar navigation
  - `st.session_state` keys: user_id, current_bean, current_recipes, selected_recipe, optimized_params, personalization_phase, demo_mode
  - Page routing via sidebar buttons
  - SQLite persistence layer: file-based for production, in-memory for demo mode (`BREWMATCH_DEMO_MODE=true`)
  - Model loading on startup: load LightGBM model + feature encoder from `models/` at Streamlit init
  - ChromaDB initialization on startup: load or create collection at `data/chroma/`
  - Returning-user identification: detect existing user via session state or stored profile on app load
  - Error handling: extraction failure, no recipes found, optimization fails, model not loaded, SQLite error

## 3.2 Individual pages (build)

- [ ] **Build landing page**
      Implements: `specs/user-interface.md` Section 4.1
  - Title, tagline, "How It Works" 4-step summary
  - "Get Started" button (→ onboarding or bean-input)
  - "Demo Mode" button (→ demo page)

- [ ] **Build onboarding page (4-step quiz)**
      Implements: `specs/user-interface.md` Section 4.2
  - Step 1: Roast preference (3 radio options)
  - Step 2: Flavor clusters (up to 5 from 15-cluster taxonomy)
  - Step 3: Experience level (3 radio options)
  - Step 4: Dripper selection (V60 / Kalita Wave / Origami multi-select)
  - Validation: cannot proceed without selection
  - Store onboarding to user profile on completion

- [ ] **Build bean input page**
      Implements: `specs/user-interface.md` Section 4.3
  - Free-text area for roaster description
  - "Analyze Beans" button calls extraction pipeline
  - Display extracted profile with confidence indicator (green/yellow/red)
  - Manual entry form (dropdowns, sliders, multi-select)
  - "Find Recipes" navigates to recommend page

- [ ] **Build recipe recommendation page**
      Implements: `specs/user-interface.md` Section 4.4
  - Display 1-3 recommended recipes ranked by predicted score
  - Each recipe card: name, score, dose, ratio, grind, temp, bloom, time, pours
  - "Optimize for my taste" button (runs optimizer, shows optimized params alongside)
  - "Start Brewing" saves selected recipe, navigates to brew page

- [ ] **Build brew session page**
      Implements: `specs/user-interface.md` Section 4.5
  - Step-by-step brewing instructions from selected recipe
  - Countdown timer matching `total_time_s`
  - Feedback form: thumbs up/down (required), rating slider 1-10 (optional), 5 directional flags (optional), notes (optional)
  - Thumbs-to-score mapping utility: thumbs_up = score 7, thumbs_down = score 3 (per RT2-20, used by taste predictor when no explicit score)
  - "Submit Feedback" saves to brew history, updates personalization
  - Navigation to diagnosis if flags present, or back to recommend

- [ ] **Build history page**
      Implements: `specs/user-interface.md` Section 4.6
  - User stats: total brews, avg rating, personalization phase
  - Taste preference radar chart (15 clusters weighted by rating)
  - Brew list in reverse chronological order
  - Error state components: display graceful messages for empty history, corrupted data, failed reads
  - Parameter trend charts (temp, grind, ratio over time)

- [ ] **Build diagnosis page**
      Implements: `specs/user-interface.md` Section 4.7
  - Load most recent brew with directional flags
  - Two branches: 0-2 brews → rule-based diagnosis; 3+ brews → pattern-based diagnosis
  - "What happened" explanation from extraction theory
  - Top 2-3 suggested parameter adjustments with specific values
  - "Try Again" pre-fills recommend page with adjusted parameters

- [ ] **Build demo mode page**
      Implements: `specs/user-interface.md` Section 4.8
  - Alex profile display (experience, preferences, 15 brews)
  - "Explore Alex's Profile" and "Brew as Alex" buttons
  - Taste journey timeline chart (rating vs brew number)
  - Parameter evolution chart
  - "Reset Demo" clears in-memory DB and re-seeds
  - "Exit Demo Mode" switches back to production

- [ ] **Build evaluation dashboard page**
      Implements: `specs/user-interface.md` Section 4.9
  - Load pre-computed metrics from `models/evaluation_results.json`
  - Bean extraction: accuracy, avg confidence, confusion matrix
  - Recipe retrieval: precision@3, MRR, retrieval quality chart
  - Taste prediction: RMSE, MAE, R², predicted-vs-actual scatter, feature importance bar chart
  - Recipe optimization: avg improvement, trials to convergence, convergence curve
  - Personalization: bean-aware vs hybrid RMSE, RMSE vs brew count curve
  - Demonstration scorecard table

## 3.3 Wiring (connect pages to ML components)

- [ ] **Wire bean input page to extraction pipeline**
  - "Analyze Beans" → call bean extractor → display results
  - Low confidence → show manual entry form with pre-filled partial extraction
  - Manual entry → construct BeanProfile directly (confidence=null)
  - Store bean profile in session state

- [ ] **Wire recommendation page to retrieval + prediction**
  - Bean profile → recipe retrieval (RAG) → top 1-3 recipes
  - Each recipe → taste prediction → predicted score + confidence interval
  - "Optimize" → recipe optimizer (Optuna) → optimized parameters
  - Store recipes and optimized params in session state

- [ ] **Wire brew session to feedback processing + personalization**
  - Feedback form → validate → save to SQLite brew history
  - Update personalization state (bias recomputation)
  - If directional flags present → navigate to diagnosis page
  - Thumbs up/down → score mapping (up=7, down=3) for taste predictor

- [ ] **Wire onboarding quiz to SQLite persistence**
  - Quiz completion → create/update user profile in SQLite
  - Store preferred_flavor_clusters, roast_preference, experience_level, dripper_selection
  - Subsequent sessions load existing profile instead of re-running quiz

- [ ] **Wire history page to SQLite reads**
  - Load brew history from SQLite for display
  - Compute stats (total_brews, avg_rating) on read from brew_history
  - Parameter trends from historical recipe parameters

- [ ] **Wire diagnosis page to Perturb-and-Score engine**
  - Load latest brew + flags from session state / SQLite
  - Run diagnosis engine (candidate generation + perturbation + ranking)
  - Display top adjustments with predicted improvements
  - "Try Again" → pre-fill recommendation page with adjusted recipe

- [ ] **Wire evaluation dashboard to computed metrics**
  - Load `models/evaluation_results.json`
  - Generate charts from stored test predictions
  - Display all metrics per `specs/evaluation.md`

## 3.4 Persistence + demo setup

- [ ] **Build SQLite persistence layer**
      Implements: `specs/data-models.md` Section 5, `specs/user-interface.md` Section 6.2
  - `data/users.db` with tables: users, brew_history
  - User profile CRUD (create from onboarding, read on return, update on feedback)
  - Brew history append (insert new brew record on feedback submission)
  - Stats computed on read from brew_history (not materialized)
  - Demo mode: `:memory:` SQLite when `BREWMATCH_DEMO_MODE=true`

- [ ] **Build demo mode setup (Alex seed)**
      Implements: `specs/user-interface.md` Section 4.8, `specs/synthetic-data.md` Section 5.3
  - Load Alex's 15-brew history from `data/synthetic/demo_alex.json`
  - Seed into in-memory SQLite on demo mode activation
  - "Reset Demo" clears and re-seeds
  - All pages operate on Alex's profile in demo mode

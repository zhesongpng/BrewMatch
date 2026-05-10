# BrewMatch Analysis Synthesis

Date: 2026-05-09
Status: Phase 01 — Analysis Complete

---

## 1. Strategic Framing

**Product positioning**: Coffee troubleshooting tool — the user's "coffee doctor." BrewMatch gives you a starting recipe for your beans, then diagnoses what went wrong and prescribes a specific fix.

**Core value proposition**: Diagnosis, not personalization. The strongest value is immediate — brew 1, something's off, BrewMatch tells you exactly what to change and why. Personalization emerges naturally as the system accumulates diagnosis history.

**Why this framing**:

- Diagnosis delivers value on brew 1 (no 10-brew cold start)
- Diagnosis is hard to replicate with generic advice — BrewMatch knows the exact parameters used
- The coffee science (extraction theory, parameter interactions) is genuine domain expertise that ChatGPT cannot apply contextually
- Personalization is the emergent benefit: "you may have noticed the first recipe keeps getting better" rather than "we'll learn your taste over 10 brews"

**What this means for the ML pipeline**: All 5 ML components still exist, but they serve the diagnosis engine rather than the personalization engine. The taste predictor powers the diagnosis ("which parameter change would most improve the predicted score?"), the optimizer finds the minimum change to fix the specific problem, and personalization accumulates passively from diagnosis history.

---

## 2. Key Research Findings

### Competitive Landscape

- **No current app offers bean-specific personalization with a taste learning loop.** The gap is real and unoccupied.
- Beanconqueror is the market leader (free, open-source, comprehensive logging) — but it's a journal, not an advisor.
- ChatGPT is the real competitive threat, not other coffee apps. But it cannot run regressions on brew history or systematically optimize parameters.
- Singapore has ~10,000+ home baristas — credible launch market.

### ML Architecture

- **LightGBM** recommended for taste prediction (native categorical support, fast training)
- **Optuna (TPE sampler)** for Bayesian recipe optimization — converges in 15-30 iterations vs 240+ for grid search
- **Hybrid RAG** (dense embeddings + BM25) with `all-MiniLM-L6-v2` or OpenAI embeddings
- **SCA Flavor Wheel** provides canonical taxonomy (~15 clusters for feature engineering)
- CQI Kaggle datasets (1,310+ Arabica reviews) available for bootstrapping taste model
- No existing machine-readable recipe database — manual curation required (advantage for uniqueness)

### Critical Risks

1. **Cold start + chronic pain** — users churn before personalization activates (10+ brews needed)
2. **Course timeline** — 5 ML components in 14 weeks requires synthetic data and staged demo
3. **Training data unavailability** — synthetic data generator is the only viable path
4. **Per-user overfitting** — 30-50 ratings in a semester is insufficient for individual models

### Value Proposition

- **Primary value: diagnosis** — "my coffee is too sour, what do I change?" with a specific, contextual answer grounded in the exact recipe and bean
- **Secondary value: knowledge building** — starting recipes grounded in expert sources, not generic YouTube advice
- **Emergent value: personalization** — after several rounds of diagnosis, the starting recipe gets better because the system has learned what works for this user
- The catch-22 is less severe with diagnosis: users don't need to rate on a 1-10 scale — they just say "too sour" (binary + directional, which anyone can do)
- The first recipe must be genuinely good (knowledge-base grounded) — the diagnosis kicks in when it's not perfect

---

## 3. Scope Decisions

### In Scope (Course Demo MVP)

| Decision                                       | Rationale                                                                                  |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **Pour-over only** (V60, Kalita Wave, Origami) | Three drippers share 90% parameter space; demonstrates all ML concepts with recipe variety |
| **Manual text entry** (no OCR)                 | OCR is unreliable on coffee bags, adds 2 weeks of work, no functional advantage            |
| **Web app (Streamlit)**                        | Fastest to build, easiest to demo (projector/screen share), no app store needed            |
| **50-80 curated recipes**                      | Sufficient for RAG retrieval demonstration                                                 |
| **Synthetic data**                             | Only viable path for course timeline; the generator itself is a legitimate ML artifact     |
| **Feedback: thumbs + directional flags**       | More reliable than 1-10 scale; maps directly to recipe parameters                          |

### Explicitly Out of Scope

| Item              | Why                                                                                |
| ----------------- | ---------------------------------------------------------------------------------- |
| Espresso          | Different parameter space; doubles ML scope                                        |
| AeroPress         | Different parameter space (pressure-based); pour-over demonstrates all ML concepts |
| Photo/OCR input   | Unreliable, time-consuming, no ML demonstration value                              |
| Mobile native app | Web app demonstrates ML equally well                                               |
| Payment/freemium  | Post-launch consideration — build first, monetize if demand emerges                |
| Social features   | No ML value; adds product complexity                                               |

---

## 4. Unique Selling Points

1. **Diagnosis-first approach**: No other tool provides contextual diagnosis tied to the exact recipe and bean parameters. YouTube gives generic advice; ChatGPT doesn't know what temperature you used.
2. **Coffee science grounded**: Every diagnosis is backed by SCA extraction theory, parameter interaction tables, and real expert recipes — not opinions.
3. **5 ML techniques in one pipeline**: Supervised (taste prediction), optimization (parameter adjustment), unsupervised/embeddings (recipe retrieval), RAG (knowledge base), hybrid cold-start (emergent personalization)
4. **Bayesian optimization for a physical process**: Each "evaluation" requires a real brew — sample efficiency is a genuine engineering challenge
5. **Feedback mechanism anyone can use**: "Too sour" is something every coffee drinker can identify — no 1-10 rating expertise needed

---

## 5. Evaluation Metrics

| Component           | Metric                         | Target                   |
| ------------------- | ------------------------------ | ------------------------ |
| RAG Retrieval       | Precision@3                    | >0.8                     |
| Bean Extraction     | Field-level accuracy           | >0.8                     |
| Taste Prediction    | RMSE (1-10 scale)              | <1.5                     |
| Recipe Optimization | Convergence iterations         | <5 to reach >0.8 optimal |
| Personalization     | Rating improvement over global | >0.5 points              |
| End-to-End Pipeline | Full flow completion rate      | 5/5 test beans           |

---

## 6. Technology Stack

| Component    | Tool                       | Why                                        |
| ------------ | -------------------------- | ------------------------------------------ |
| Language     | Python                     | Course standard, ML ecosystem              |
| ML Framework | LightGBM + scikit-learn    | Fast, handles categoricals natively        |
| Optimization | Optuna (TPE)               | Mixed parameter spaces, Bayesian           |
| Embeddings   | all-MiniLM-L6-v2 (local)   | Free, fast, sufficient quality             |
| Vector Store | ChromaDB                   | Local, easy setup, good Python integration |
| LLM          | GPT-4o-mini / Claude Haiku | Structured output, cost-effective          |
| Web UI       | Streamlit                  | Rapid prototyping, built-in widgets        |
| Data Storage | SQLite + JSON files        | Local, no server, simple                   |

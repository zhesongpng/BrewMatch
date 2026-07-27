# BrewMatch Specs Index

| File                     | Domain               | Description                                                                  |
| ------------------------ | -------------------- | ---------------------------------------------------------------------------- |
| `data-models.md`         | Data                 | All entities, schemas (V60/Kalita/Origami), relationships, constraints       |
| `bean-extraction.md`     | NLP                  | Bean profile extraction from free-text roaster descriptions                  |
| `recipe-retrieval.md`    | RAG                  | Starting recipe retrieval from curated knowledge base                        |
| `taste-prediction.md`    | ML (Supervised)      | Taste score prediction; powers recipe ranking and diagnosis engine           |
| `recipe-optimization.md` | ML (Optimization)    | Minimum parameter change to fix diagnosed brew issues                        |
| `personalization.md`     | ML (Personalization) | Bean-aware to full-hybrid personalization from accumulated diagnosis history |
| `web-frontend.md`        | UI (current)         | React/Next front-end on Vercel: screens, brain client, identity, on-device state |
| `user-interface.md`      | UI (legacy)          | Streamlit troubleshooting app — superseded by `web-frontend.md`, pending retirement |
| `coffee-science.md`      | Domain               | Extraction theory, SCA standards, diagnostic rules                           |
| `synthetic-data.md`      | Data Engineering     | Synthetic data generation strategy and validation                            |
| `evaluation.md`          | Quality              | Metrics, targets, measurement methods for all components                     |

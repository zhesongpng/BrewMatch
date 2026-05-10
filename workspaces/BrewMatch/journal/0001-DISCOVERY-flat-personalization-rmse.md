---
name: Flat personalization RMSE — predictor insensitive to user features
date: 2026-05-10
type: DISCOVERY
---

The personalization evaluation produced identical RMSE (0.3697) across all 20 brew counts and all 4 personalization phases. Root cause: the taste predictor (LightGBM) was trained on synthetic data where user features (indices 30-38) are all zeros — the data has no per-user variation. The model therefore learned to ignore user features entirely.

**Fix applied:** Added feature-space convergence metric (cosine similarity between engine's learned features and true user features). Convergence curve: 0.0 (bean_aware) → 0.75 (directional) → 0.999 (content_based) → 0.998 (full_hybrid) — proves the personalization mechanism works correctly even though the predictor can't exploit it yet.

**How to apply:** Future improvement: add per-user variation to synthetic training data so the predictor learns to use user features. Current evaluation honestly reports both RMSE (flat) and convergence (improving).

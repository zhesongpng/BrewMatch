---
type: DECISION
date: 2026-05-12
project: BrewMatch
topic: Streamlit Community Cloud deployment fixes
phase: deploy
tags: [deployment, streamlit-cloud, torch, sqlite, path-resolution]
---

## Decision

Deploy BrewMatch to Streamlit Community Cloud with three defensive fixes for cloud-specific constraints:

1. **sys.path injection** — Add repo root to `sys.path` at app startup so `from src.*` imports resolve regardless of Streamlit's working directory
2. **CPU-only torch** — Set `CUDA_VISIBLE_DEVICES=""` and `TOKENIZERS_PARALLELISM="false"` before torch/sentence-transformers loads
3. **Writable DB fallback** — Detect read-only filesystems and fall back to in-memory SQLite when `data/` is not writable

Additionally: force-added `models/*.joblib` files to git (were gitignored) so the deployed app can load trained ML models. Created `requirements.txt`, `packages.txt`, and `.python-version` for Streamlit Cloud's build system.

## Alternatives Considered

- **Docker/Fly.io deployment** — More control but significantly more setup for an MBA course project
- **Pinning older sentence-transformers version** — Avoids meta tensor error but creates dependency maintenance debt
- **Remote PostgreSQL for cloud DB** — Overkill for a demo app; in-memory SQLite is sufficient

## Rationale

Streamlit Community Cloud mounts the repo as read-only, runs from a temp directory, and uses CPU-only containers. The three fixes address each constraint with minimal code changes and no architectural impact. In-memory SQLite means user accounts don't persist across deploys, which is acceptable for a course demo.

The `device="cpu"` parameter alone was insufficient — the meta tensor error also required `CUDA_VISIBLE_DEVICES=""` set at the OS level before torch initializes.

## Consequences

- App works on Streamlit Cloud but user data (accounts, brew history) resets on each redeploy
- Repo-root-relative paths (`Path(__file__).resolve().parent.parent.parent`) used everywhere — models, data, chroma — so the app works from any working directory
- If Streamlit Cloud's `exit status 1` persists on update, user must reboot or delete-and-redeploy the app from the Streamlit dashboard
- All 652 tests continue to pass with these changes

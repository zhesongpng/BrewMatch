# BrewMatch Master Todo List

Status: Pending human approval
Date: 2026-05-09

---

> **Completion status (2026-05-17):** Milestones 1–5 are complete and the app
> is deployed and verified on Streamlit Cloud. The unchecked `[ ]` boxes in
> the per-milestone files are stale tracking artifacts, not outstanding work —
> the codebase is built (661 tests passing), all evaluation artifacts exist in
> `models/`, and the report is finalized. See journal entries 0019–0021 for the
> deployment, cloud-mode bug, and evaluation-honesty record. Only remaining
> deferred item: persistent-database migration (accounts/history reset on
> cloud restart — accepted limitation for the course demo).

---

## Decisions Resolved

- **RT2-13**: Keep 5 directional flags (too_sour, too_bitter, too_weak, too_harsh, astringent). Brief updated.
- **Diagnosis-first**: Architecture prioritizes diagnosis over personalization (journal 0005).
- **Pour-over only**: V60, Kalita Wave, Origami (journal 0006).
- **Optimizer**: 4 tunable parameters (grind, temp, dose, ratio); pour schedule fixed from retrieved recipe.
- **Demo mode**: In-memory SQLite via `BREWMATCH_DEMO_MODE=true`.

---

## Milestone Index

| Milestone                   | File                                           | Todos  | Sessions  | Depends on           |
| --------------------------- | ---------------------------------------------- | ------ | --------- | -------------------- |
| **1: Project Setup & Data** | [m1-project-setup.md](m1-project-setup.md)     | 7      | 3-4       | Nothing (start here) |
| **2: ML Pipeline**          | [m2-ml-pipeline.md](m2-ml-pipeline.md)         | 10     | 4-5       | Milestone 1          |
| **3: Web Application**      | [m3-web-application.md](m3-web-application.md) | 18     | 5-7       | Milestone 2          |
| **4: Evaluation**           | [m4-evaluation.md](m4-evaluation.md)           | 8      | 3-4       | Milestone 3          |
| **5: Polish**               | [m5-polish.md](m5-polish.md)                   | 2      | 1         | Milestone 4          |
| **Total**                   |                                                | **45** | **16-21** |                      |

## Dependency Order

```
M1 → M2 → M3 (pages can be built in parallel, wiring is sequential) → M4 → M5
```

Within Milestone 2: bean extraction and feature encoder can run in parallel. Taste predictor must complete before optimizer and diagnosis engine. Retriever can run in parallel with predictor. Personalization depends on predictor.

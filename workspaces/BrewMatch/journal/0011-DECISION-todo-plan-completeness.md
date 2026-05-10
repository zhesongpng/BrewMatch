---
type: DECISION
date: 2026-05-09
created_at: 2026-05-09T12:00:00Z
author: co-authored
session_id: continuation
session_turn: 1
project: BrewMatch
topic: Todo plan completeness — 45 todos across 5 milestones
phase: todos
tags: [planning, todos, scope, ml-pipeline]
---

## Decision

Created a comprehensive 45-todo implementation plan covering the entire BrewMatch project across 5 milestones: Project Setup & Data (7), ML Pipeline (10), Web Application (18), Evaluation (8), Polish (2). Estimated 16-21 autonomous execution sessions.

## Alternatives Considered

1. **Phase-1 only**: Write todos only for the current phase, defer later phases. Rejected — the COC `/todos` skill requires writing ALL todos for the ENTIRE project, not just current work.
2. **Coarse-grained**: 15-20 high-level todos without build/wire separation. Rejected — would collapse the build-then-wire discipline that prevents mock data from shipping to production.
3. **Per-spec todos**: One todo per spec file. Rejected — specs cover multiple implementation concerns that benefit from independent sharding.

## Rationale

- **Build + wire pattern**: Every data-consuming component gets two todos — one for structure, one for real data flow. This prevents the common failure mode where a page displays mock data that's never replaced.
- **Red-team validated**: Two parallel analyst agents audited the initial 42-todo list and found 14 gaps (9 missing tasks, 5 missing wires). All incorporated.
- **Autonomous session estimates**: Framed in sessions, not human-days, per COC autonomous execution model.

## Consequences

- 45 todos is substantial but each is scoped to ≤500 LOC load-bearing logic, fitting within one session
- Evaluation (Milestone 4) is the largest risk — many evaluation targets depend on synthetic data quality
- The 5th directional flag ("astringent") was confirmed by the user at the `/todos` gate

## For Discussion

1. **Counterfactual**: If we had limited the plan to 25 todos (dropping evaluation details and polish), would we have enough structure to execute autonomously, or would `/implement` sessions stall on ambiguous acceptance criteria?
2. **Data dependency**: The synthetic data generator (todo 1.4) is the critical path — if generated data doesn't meet quality targets, every downstream ML component is compromised. Should we add a validation gate between Milestone 1 and Milestone 2?
3. **Session estimate**: 16-21 sessions assumes no rework. What's the realistic rework rate for an ML pipeline built on synthetic data, and should we budget 25% contingency sessions?

# 0013 DECISION — Parallel Agent Strategy for Red Team Remediation

Date: 2026-05-10

## Context

Milestone 2 red team produced 18 MEDIUM findings (M01-M18) and 1 LOW finding (L12) requiring code fixes, new tests, and cross-cutting changes (logging, robustness). Sequential fixing would take 4-5 sessions.

## Decision

Parallelized 8 agents across non-overlapping file groups:

- **Group A**: Optimizer tests + code (M05, M10, M17)
- **Group B**: Personalization tests + code (M06, M07, M14)
- **Group C**: Retriever tests + code (M08, M09, M16)
- **Group D**: Cross-cutting — logging (M13), diagnosis magnitude (M15), extractor JSON parsing (M18), encoder/predictor bias tests (M11, M12)
- **Group E**: Full pipeline regression test (L12)

File ownership boundaries prevented merge conflicts. All 583 tests pass.

## Why

Grouping by file ownership (not by finding severity) is the key insight — it eliminates merge conflicts between parallel agents while keeping related fixes together for coherent review.

## How to apply

For future multi-finding remediation: map findings to files first, group agents by non-overlapping file sets, then parallelize. Avoid grouping by severity (scattered file ownership) or by component type (same files touched by multiple agents).

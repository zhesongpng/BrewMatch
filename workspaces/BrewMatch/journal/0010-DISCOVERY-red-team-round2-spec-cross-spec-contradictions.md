---
type: DISCOVERY
date: 2026-05-09
project: BrewMatch
topic: Red team round 2 — spec cross-spec contradictions found
phase: analyze
tags: [red-team, specs, cross-spec-consistency]
---

## What Was Discovered

Ran a 4-agent parallel adversarial audit across all 10 spec files and the product brief. Identified 33 findings (3 CRITICAL, 10 HIGH, 12 MEDIUM, 8 LOW). The three CRITICAL findings are cross-spec contradictions that will produce incorrect ML behavior:

1. **too_harsh bias direction opposes across specs** — taste-prediction says "increase acidity" while personalization says "decrease acidity" for the same flag
2. **Feature count is wrong** — claimed 44, actual 55 (interaction features are 16 not 6, bean features are 23 not 22)
3. **Temperature threshold uses three values** — 91C (synthetic data), 92C (optimizer), 93C (coffee science)

All three will break the ML pipeline at training or inference time if unresolved.

## Why It Matters

These are not cosmetic inconsistencies. The bias direction conflict (RT2-01) means the optimizer receives contradictory signals. The feature count mismatch (RT2-02) means the training data columns won't match the model's expected input. The temperature threshold disagreement (RT2-03) means synthetic data labels disagree with both the optimizer's constraints and the domain knowledge spec.

## Follow-Up

- Present findings at `/todos` gate for user approval
- Resolve 4 MUST-fix findings before implementation begins
- Full report at `workspaces/BrewMatch/04-validate/red-team-findings.md`

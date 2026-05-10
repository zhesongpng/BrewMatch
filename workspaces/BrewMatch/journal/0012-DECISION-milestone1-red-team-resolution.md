---
type: DECISION
date: 2026-05-09
project: BrewMatch
topic: Milestone 1 red team synthesis — resolution of all findings
phase: redteam
tags: [milestone1, red-team, data-quality, test-coverage]
---

## Decision

Resolved all 20 findings from the milestone 1 red team audit. 15 fixed, 12 skipped by user decision, 1 future enhancement. Zero remaining open findings.

## What was fixed

- **Data quality**: Rating distribution rebalanced (mean 6.67), learning progression added, timestamps made monotonic, brew count aligned to spec (0-30), flavor notes derived from clusters via CLUSTER_NOTE_MAP
- **Data model**: Whitespace-only rejection, LearnedPreferences range validation, dose_g widened to 12-35g (was 12-22g), water_total_g widened to 180-600g (was 180-400g) to accommodate real recipes like Hoffman 30g/500g
- **Recipe KB**: Removed 20 synthetic variations (broken pour timing). Added 6 real recipes for dark roast, natural, honey, wet-hulled coverage. Now 46 total hand-crafted recipes.
- **Tests**: 77 new tests for generator.py (was zero). 140 total tests passing.
- **Project docs**: BrewMatch-specific README, shared conftest.py with 8 fixtures, flavor_notes added to CSV export

## What was skipped (user decision)

Pour-step validations (pour structure = recipe identity, not optimization parameter), negative tests (validation in **post_init**), validator script tests (data model catches at load time), expert ICC (realistic variance), altitude_max_m (minor), generated recipe instructions (variations removed), cold-brew naming (no such recipe exists), grinder-specific settings (post-MVP).

## Consequences

- Milestone 1 data pipeline is solid and tested — ready for ML model training
- Grinder-specific grind translation deferred to future enhancement
- Recipe coverage now spans all roast levels and processes

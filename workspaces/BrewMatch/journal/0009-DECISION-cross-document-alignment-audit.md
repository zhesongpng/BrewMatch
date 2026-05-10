---
type: DECISION
date: 2026-05-09
project: BrewMatch
topic: Cross-document alignment audit — 8 misalignments fixed
phase: redteam
tags: [alignment, specs, terminology, phase-boundaries]
---

## Decision

Ran a full cross-document alignment audit across all 11 specs, the architecture plan, implementation roadmap, user flows, and brief. Fixed 8 misalignments to ensure specs are the single source of truth.

## Fixes Applied

1. **Personalization phase boundaries**: Aligned to Directional=1-4, Content-Based=5-9, Full Hybrid=10+ across data-models.md, arch-plan, roadmap (was inconsistent at 1-5, 5-10)
2. **Architecture plan flavor_profiles example**: "fruity" (not a cluster) replaced with "Berry, Citrus, Floral" (actual 15-cluster names)
3. **Architecture plan altitude fields**: Nested object → flat fields matching data-models.md spec
4. **Architecture plan missing fields**: Added source_text, extraction_confidence, stats, drippers
5. **Synthetic data recipe count**: Calibrated to 30-50 curated + 0-1 variations with 80-recipe cap
6. **"Cold start" → "bean-aware"**: Updated product-facing terminology across 10 files (kept "cold-start" only as standard ML metric term)
7. **Roadmap traceability**: Updated to match current brief (50-80 recipes, manual text entry, 4 phases)
8. **Spec \_index.md**: Updated personalization domain label

## Rationale

Specs are the authority per specs-authority.md. Plans and analysis documents must derive from specs, not the other way around. Cross-document drift was causing phase boundary confusion and terminology inconsistency.

## Consequences

- All documents now use consistent phase boundaries and terminology
- Implementation can proceed from a single consistent baseline
- Remaining "cold-start" occurrences are standard ML terminology (metric names, test methodology), not product framing

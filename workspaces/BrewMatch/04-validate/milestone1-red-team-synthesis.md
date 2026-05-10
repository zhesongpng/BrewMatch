# Milestone 1 Red Team Synthesis — Implementation Adversarial Audit

Date: 2026-05-09
Scope: Data models, synthetic data generator, recipe knowledge base, test coverage, security & project structure
Agents: 5 parallel specialists (reviewer, testing-specialist x2, analyst, security-reviewer)
Prior round: `red-team-findings.md` (spec-level audit, all CRITICAL/HIGH resolved)

---

## Executive Summary

140 tests pass, 0 runtime bugs. No security vulnerabilities. 46 hand-crafted recipes covering all roast levels, processes, and brew methods. Generator fully tested with 77 tests. BrewMatch-specific README and shared test fixtures in place.

**Bottom line**: Milestone 1 data pipeline is solid, tested, and documented. Remaining: validator parity check (#5).

---

## Fixed Findings

| #   | Finding                                                 | Fix Applied                                                                                                                                                                                                                              |
| --- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C2  | Rating distribution ceiling-biased (mean 8.18)          | Reduced preference_bonus multiplier from 1.5 to 0.5, lowered base_rating range. Mean now 6.67, spread 2-10.                                                                                                                              |
| C3  | No learning progression across brew phases              | Added `_biased_recipe()` helper. Early: random. Mid: params gradually cluster toward preferences. Late: tight params, low noise. Alex now shows 6.6 -> 6.8 -> 7.4 progression.                                                           |
| C4  | Timestamps non-chronological                            | Changed from `i * rng.randint(1,5)` to accumulated `elapsed_days += rng.randint(1,5)`. All sampled users now monotonically increasing.                                                                                                   |
| C5  | Brew count range violates spec (20-50 vs 0-30)          | Changed to `rng.randint(0, 30)`. 10 cold-start users with 0 brews now present.                                                                                                                                                           |
| C6  | .env.example has hardcoded model name                   | Replaced `gpt-4o-mini` with `your-model-name-here`.                                                                                                                                                                                      |
| C7  | Temperature alignment ranges mismatch coffee-science.md | Aligned: light 92-98C, medium-dark 89-94C, medium 91-95C, center 93C.                                                                                                                                                                    |
| H6  | np.random used alongside seeded rng                     | Replaced `np.random.normal/uniform` with `rng.gauss/uniform` in `generate_user()`.                                                                                                                                                       |
| 1   | Whitespace-only strings accepted                        | Added `.strip()` non-empty checks for source, instructions, origin_country in data_models.py.                                                                                                                                            |
| 2   | LearnedPreferences range tuples not validated           | Added low<=high and bounds validation for preferred_temp_range (80-100C) and preferred_ratio_range (12-20).                                                                                                                              |
| 3   | Synthetic recipe variations with broken pour timing     | Removed `_add_variations()` entirely. Now ships only 40 hand-crafted real recipes. 20 synthetic variations deleted.                                                                                                                      |
| 7   | Flavor notes and clusters independently sampled         | Added `CLUSTER_NOTE_MAP` with specific tasting notes per cluster. Notes now derived from clusters — guaranteed semantic alignment.                                                                                                       |
| 8   | Demo Alex inverted progression                          | Resolved by C2 (rating distribution) and C3 (learning progression). Alex now shows 6.6 -> 6.8 -> 7.4 upward trend.                                                                                                                       |
| 9   | generator.py has zero tests                             | Created `tests/unit/test_generator.py` with 77 tests across 13 classes: alignment functions, scoring, rating generation, bean generation (CLUSTER_NOTE_MAP), biased recipes, brew history (timestamps, progression), demo Alex, experts. |
| 10  | Boundary values untested; dose/water ranges too narrow  | Updated dose_g 12-35g (was 12-22g), water_total_g 180-600g (was 180-400g). Updated boundary tests in test_data_models.py and test_generator.py. Accommodates real recipes like Hoffman 30g/500g.                                         |
| 14  | flavor_notes excluded from CSV                          | Added `flavor_notes` column to ratings.csv export in `generate_all()`. Notes now available for ML training.                                                                                                                              |
| 17  | Recipe coverage biased toward light roasts and washed   | Added 6 recipes: 3 dark roast (V60, Kalita, Origami), 1 natural-process fruity, 1 honey-process sweet, 1 wet-hulled rich. Now 46 total covering all roast levels and processes.                                                          |
| 18  | Root README is Kailash COC template                     | Replaced with BrewMatch-specific README covering scope, setup, data pipeline, and test instructions.                                                                                                                                     |
| 19  | No BrewMatch-specific conftest.py with test fixtures    | Created `tests/conftest.py` with 8 shared fixtures (make_pour, make_suitable, make_recipe, make_bean, make_user, make_bean_dict, make_recipe_dict, rng).                                                                                 |

---

## Remaining Findings — Priority-Ordered

None — all findings addressed or skipped.

---

## Skipped Findings (User Decision)

| Finding                                             | Reason                                                                                       |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Pour step sequence monotonicity validation          | Pour structure changes = different recipe. Optimizer adjusts grind/temp/dose only.           |
| Pour time_offset monotonicity validation            | Same as above.                                                                               |
| bloom_time_s vs second-pour-offset cross-validation | Pour timing is recipe identity, not an optimization parameter.                               |
| Vegetal flavor cluster zero recipe coverage         | Minimal impact. Very unlikely to matter in practice.                                         |
| 11. Missing negative tests for data model           | Validation already in `__post_init__`. Synthetic data generator, not security-critical path. |
| 12. validate_recipes.py has zero tests              | One-time validation script. Data model catches bad recipes at load time.                     |
| 13. Expert ICC falls below 0.6 threshold            | Realistic expert disagreement. Accept as natural variance.                                   |
| 14. altitude_max_m never populated                  | Minor data gap. Min altitude sufficient for ML purposes.                                     |
| 15. Generated recipe variation instructions generic | Synthetic variations removed. Only hand-crafted real recipes remain.                         |
| 16. "cold-brew-style" recipe name misleading        | No cold-brew recipe exists in current KB. Was from deleted synthetic variations.             |
| 20. Grinder-specific grind setting translation      | Future enhancement (post-MVP). UI concern, not data pipeline.                                |
| 5. Validator missing data-model parity checks       | Data model catches bad recipes at load time. One-time script, not critical path.             |

---

## Agent-by-Agent Raw Findings

| Agent                  | Specialist         | CRITICAL | HIGH | MEDIUM | LOW |
| ---------------------- | ------------------ | -------- | ---- | ------ | --- |
| 1 — Spec compliance    | Reviewer           | 5        | 7    | 6      | 4   |
| 2 — Synthetic data     | Testing-specialist | 2        | 4    | 5      | 3   |
| 3 — Recipe KB          | Analyst            | 0        | 3    | 4      | 3   |
| 4 — Security/structure | Security-reviewer  | 2        | 3    | 5      | 3   |
| 5 — Test coverage      | Testing-specialist | 0        | 7    | 14     | 4   |

Note: Many findings overlap across agents (e.g., pour-step validation surfaced by agents 1, 3, and 5 independently — convergent validation that this is a real gap). The synthesis above deduplicates and consolidates.

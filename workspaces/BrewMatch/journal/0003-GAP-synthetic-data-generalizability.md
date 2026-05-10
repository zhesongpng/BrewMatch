# GAP: Synthetic Data May Not Generalize to Real User Preferences

Date: 2026-05-09
Phase: /analyze
Source: Failure analysis (01-research/04-failure-analysis-and-risks.md)

## Gap

The course project relies entirely on synthetic data for training the taste prediction model. The synthetic data generator creates ratings based on extraction theory and defined "virtual expert" profiles. However:

1. Real user taste perception is noisier and less consistent than the synthetic model assumes
2. The virtual expert profiles are defined by the team — they encode assumptions about taste, not measured preferences
3. Parameter-response surface is based on extraction theory (yield = f(grind, temp, time, ratio)) but taste preference is subjective and culturally influenced
4. The model may overfit to the synthetic distribution and fail on real-world usage

## Impact

For the course demo: LOW — the demo uses synthetic data and the evaluation metrics are measured against synthetic test sets. The model will perform well on its own test data.

For any product continuation: HIGH — the model trained on synthetic data may not generalize to real user preferences. This is the classic sim-to-real gap.

## Follow-up Needed

- If the project continues beyond the course, the first priority is collecting real user ratings
- The synthetic data generator should include configurable noise levels to simulate real-world variability
- Consider adding a "real data validation" step: compare model predictions against 20-30 real brew ratings from the team

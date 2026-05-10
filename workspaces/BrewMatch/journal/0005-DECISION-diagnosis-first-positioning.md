# DECISION: Diagnosis-First Product Positioning

Date: 2026-05-09
Phase: /analyze
Source: Value audit + user confirmation

## Decision

BrewMatch is a coffee troubleshooting tool, not a personalization-first product. The core interaction is: user brews, something's off, user reports what went wrong, BrewMatch diagnoses the cause and prescribes a specific parameter fix.

## Why

The value audit identified three fatal flaws with the personalization-first framing:

1. **Personalization catch-22 is structural** — users who stay long enough for ML personalization to work (10+ brews) are the users who need it least. Users who need it churn before it activates.
2. **Diagnosis delivers immediate value** — brew 1, not brew 10. No cold-start period required.
3. **Diagnosis is hard to replicate** — ChatGPT can give generic advice ("try finer grind") but BrewMatch knows the exact parameters used and gives a specific prescription ("your 90°C water was too low for this Ethiopian — try 93°C").

The user confirmed: "better to be a troubleshooting tool as that is my idea of optimization."

## Impact on Architecture

- All 5 ML components still exist but serve the diagnosis engine
- Taste predictor powers diagnosis: "which parameter change would most improve the predicted score?"
- Recipe optimizer finds the minimum change to fix the reported issue
- Personalization is emergent: accumulates from diagnosis history, improves starting recipes over time
- The coffee science spec (extraction theory, diagnostic rules) is the foundation, not the ML model

## How to Apply

- Lead with diagnosis in all user flows, demo narrative, and product framing
- The diagnosis flow is Flow 2 (primary), not Flow 4 (side feature)
- Starting recipes are the baseline; diagnosis is the value
- Personalization is mentioned as "you may notice the first recipe keeps getting better"

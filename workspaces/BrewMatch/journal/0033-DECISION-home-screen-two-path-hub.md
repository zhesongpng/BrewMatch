---
type: DECISION
date: 2026-06-26
created_at: 2026-06-26T00:00:00Z
author: co-authored
session_id: session_011MRUeS95Q1tNvydLRFw8so
project: BrewMatch
topic: Home screen becomes a two-path hub (recipe vs. diagnose), revising diagnosis-first
phase: implement
tags: [react, ux, information-architecture, home-screen, diagnosis-first]
---

# Home screen is now a two-path hub, not diagnosis-first

During B3 the user asked: "shouldn't the first page be what coffee users want,
before getting to diagnose?" This revises the earlier **diagnosis-first home**
decision (`journal` history + memory `feedback_diagnosis_first`).

## Decision

The React app's home (`apps/web/app/page.tsx`) is a **two-path hub** — "What are
you up to?" with **Get a recipe** (primary) and **Fix it** (secondary, →
`/diagnose`). Diagnose moved from `/` to its own `/diagnose` route (back arrow,
"Fix a brew" title). The bottom tab bar now leads with **Home** (new HomeIcon)
instead of Diagnose; Diagnose is no longer a tab, reached via the hub card.

## Rationale

A brewing session has two entry moments: **before** ("I have beans, what do I
brew?" → recipes) and **after** ("that tasted off" → diagnose). The _before_
moment is the more common starting point; the old app opened on the _after_
moment. Key distinction: "signature feature" ≠ "front door." Diagnosis stays the
distinctive value, just not the landing screen. Both paths are top-billed on home.

## Alternatives considered

- **Recipe flow as the literal home** (diagnose demoted to a tab) — rejected:
  buries diagnosis too far.
- **Keep diagnose-first** — rejected: backwards for the common entry moment.
- **Taste-preferences questionnaire first** — explicitly NOT chosen; that is the
  personalization-first path the user rejected long ago (`feedback_diagnosis_first`).

## Consequences

- Mockup (`workspaces/BrewMatch/03-user-flows/phase2-mockup.html`) re-synced to
  the hub (6 screens now; Screen 1 Home, Screen 2 Fix a brew).
- Diagnose page lights no bottom tab (acceptable — it's a sub-screen of Home).

## For Discussion

1. Counterfactual: if usage data later shows most opens go straight to "Fix it",
   should the hub collapse back to diagnosis-first — or just reorder the cards?
2. The hub adds one tap before _either_ action vs. landing straight into one.
   Is that tap worth it, or should home default-render the recipe form inline?
3. Diagnose has no bottom tab now (two taps from anywhere). Does that under-serve
   the feature we still call BrewMatch's signature value?

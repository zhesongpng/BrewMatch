# CONNECTION — AeroPrecipe defines BrewMatch's "not-this" anchor

**Date**: 2026-06-13
**Type**: CONNECTION

## The connection

AeroPrecipe (aeroprecipe.com) — a 300+ recipe community library for AeroPress with
credibility tiering (Championship / Barista / Enthusiast / Experimental), upvotes, and a
mobile app — is the clearest real-world instance of the "recipe library" model BrewMatch is
deliberately NOT building. It connects three previously-separate threads:

1. **Recipe-model clarification (this session)**: BrewMatch recipes carry `suitable_for`
   matching metadata; AeroPrecipe has no equivalent. The field we just documented IS the gap
   AeroPrecipe leaves open.
2. **Diagnosis-first thesis**: AeroPrecipe answers "show me recipes," never "what do I change
   when it tastes sour." Diagnosis is the unsolved job.
3. **Prior moat critique (2026-05-09)**: recipes-as-text are scrapable; the matching +
   diagnosis ML loop is not. AeroPrecipe makes that distinction concrete.

## Why it matters

- Gives the go-to-market pitch a crisp competitive anchor: "AeroPrecipe is a library; BrewMatch
  is a diagnoser. AeroPrecipe is browse-and-self-select; BrewMatch is match-to-your-bean."
- Surfaces one cheap product borrow: a `source_tier` field on `Recipe` (Champion / Barista /
  Enthusiast) for user trust + a retriever tie-breaker. v1/v1.1, not a redesign.

## Apply

When presenting differentiation, lead with the AeroPrecipe (library) + ChatGPT (generic)
two-axis contrast. Consider `source_tier` if implementation is cheap. Do NOT add a community/
upvote layer in v1 — it dilutes the diagnosis thesis (it is the v2 reference if retention data
demands it). See `01-analysis/01-research/05-brief-reanalysis-2026-06-13.md`.

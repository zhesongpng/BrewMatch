# Design Plan — `source_tier` recipe credibility tiering

**Status:** SHIPPED 2026-06-14. Canonical behavior now lives in `specs/data-models.md`
(`Recipe.source_tier`), `specs/recipe-retrieval.md` §5.3a (near-tie breaker), and
`specs/user-interface.md` §4.4 (trust badge). This file is retained as the design
record + decision log.

## Decisions (locked 2026-06-14)

1. **Tier scale:** three tiers — `champion` / `barista` / `enthusiast`.
2. **Default tier:** `barista` (chosen over `enthusiast`). NOTE for v2: when
   user-submitted or scraped recipes enter the pool, revisit this — an unlabeled
   recipe currently defaults to "Pro recipe" credibility. Harmless in v1 (no
   unlabeled recipes; all 46 curated recipes resolve to champion/barista).
3. **Strict Champion:** `champion` is reserved for titled world-championship winners
   only — James Hoffmann, Tetsu Kasuya, Tim Wendelboe, Matt Perger (12 recipes).
   Everyone else (Scott Rao, Lance Hedrick, Barista Hustle, Onyx, Kalita, Origami)
   is `barista` (34 recipes).
4. **Tie-breaker:** Option A — near-tie band (`TIE_BAND = 0.02`). Tier only settles
   near-ties; never overrides a clear match-quality winner.
5. **Build scope:** Full — field + trust badge + ranking tie-breaker, all shipped together.

**Origin:** `01-analysis/01-research/05-brief-reanalysis-2026-06-13.md` §2 — the one cheap
borrow from the AeroPrecipe competitor. NOT a community/upvoting layer (explicitly out of scope for v1).

---

## 1. Purpose

Today every recipe carries a free-text `source` field (`"James Hoffmann"`, `"Kalita"`, …).
BrewMatch stores it but cannot reason about it — a world-champion recipe and an anonymous
blog post look equally credible to the system. `source_tier` adds a small, fixed credibility
label the system can both **display** and **rank on**.

Two payoffs:

1. **Trust (display).** Show "Championship recipe" / "Pro recipe" badges so users understand
   the pedigree of what they're following.
2. **Principled near-tie ordering (ranking).** When two recipes fit a bean almost equally
   well, prefer the more credible source instead of breaking the tie arbitrarily.

---

## 2. The tier taxonomy (the real design decision)

Proposed 3-tier scale, highest to lowest:

| Tier         | Meaning                                                          | Example sources                                                     |
| ------------ | ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| `champion`   | Competition winners / globally-recognized authorities            | World Barista/Brewers Cup champions, top-tier published methods     |
| `barista`    | Professional café / roaster / educator / equipment-maker methods | Pro roasters, brand official methods, professional education brands |
| `enthusiast` | Hobbyist, blog, or (future) user-submitted recipes               | community recipes, unverified blogs                                 |

**Assignment is the work, not the code.** The credibility judgment — "is Scott Rao a
champion or a barista tier?" — is human-owned. The code just stores and uses whatever label
is assigned.

### 2.1 Proposed mapping of the current 50-recipe set

The 10 distinct sources in `data/recipes/` today (all professionally curated — there are
**no** enthusiast-tier sources in the current set):

| Source          | Recipes | Proposed tier | Rationale (for human review)                                      |
| --------------- | ------- | ------------- | ----------------------------------------------------------------- |
| James Hoffmann  | 5       | `champion`    | Former UK Barista Champion; definitive published methods          |
| Tetsu Kasuya    | 5       | `champion`    | 2016 World Brewers Cup Champion (the "4:6 method")                |
| Tim Wendelboe   | 1       | `champion`    | 2004 World Barista Champion; elite roaster                        |
| Matt Perger     | 1       | `champion`    | World Brewers Cup finalist; founder of Barista Hustle             |
| Scott Rao       | 4       | `barista`     | Authority/author, but not a titled champion (strict rule applied) |
| Lance Hedrick   | 8       | `barista`     | Competitive barista + educator (borderline champion)              |
| Barista Hustle  | 8       | `barista`     | Professional education brand                                      |
| Onyx Coffee Lab | 5       | `barista`     | Award-winning specialty roaster                                   |
| Kalita          | 5       | `barista`     | Equipment maker's official method                                 |
| Origami         | 4       | `barista`     | Equipment maker's official method                                 |

**Observation that matters:** with today's curated data the field is _low variance_ — every
recipe is either `champion` or `barista`. So the **ranking tie-breaker payoff is modest right
now**; the **display/trust payoff is the immediate win**. `source_tier` earns its keep most
when the recipe pool later includes user-submitted or scraped recipes that genuinely vary in
credibility (a v2 concern). This is worth knowing before investing.

---

## 3. Data-model change

Add a `SourceTier` enum and an OPTIONAL `source_tier` field on `Recipe`.

```python
# src/data_models.py
class SourceTier(str, Enum):
    CHAMPION = "champion"
    BARISTA = "barista"
    ENTHUSIAST = "enthusiast"

@dataclass
class Recipe:
    ...
    source: str
    source_url: Optional[str] = None
    source_tier: SourceTier = SourceTier.ENTHUSIAST   # default = least-credible
```

**Backward compatibility (important):** the field is optional with a default, and the loader
already tolerates missing optional fields (`source_url` is parsed via `raw.get(...)`). So
existing recipe JSON files **without** a `source_tier` key still load — they fall back to the
default. This means we can ship the code first and backfill the labels into the JSON
incrementally.

**Default choice — `enthusiast` vs `barista`:** defaulting to `enthusiast` is the safe,
honest default (an untagged recipe is treated as least-credible until someone verifies it).
The alternative — defaulting to `barista` because today's set is all-professional — would
silently mislabel any future untagged recipe as more credible than it is. Recommend
`enthusiast` as the default; backfill the 50 curated recipes to their real tiers in the same
change so nothing user-visible regresses.

**Validation:** parse `raw.get("source_tier", "enthusiast")` through `SourceTier(...)` so an
unrecognized string raises a clear error at load time (consistent with how `method` and
`roast_levels` already validate).

---

## 4. Retrieval integration (the tie-breaker)

Today `_rerank()` (`src/recipe_retriever/retriever.py:664`) sorts candidates purely on the
weighted 5-signal `combined` score. There is no tie-breaker. Two ways to add tier:

**Option A — near-tie band tie-breaker (recommended).** Keep the 5-signal score exactly as
is. Only when two recipes' combined scores fall within a small band (e.g. `0.02`) do we order
by tier. Tier never overrides a clear winner; it only settles genuine near-ties.

```python
TIER_RANK = {SourceTier.CHAMPION: 2, SourceTier.BARISTA: 1, SourceTier.ENTHUSIAST: 0}
TIE_BAND = 0.02
# sort by combined desc; within TIE_BAND, higher tier wins
scored.sort(key=lambda x: (round(x[1] / TIE_BAND), TIER_RANK[recipes[x[0]].source_tier]),
            reverse=True)
```

- **Pro:** preserves the existing ranking semantics; tier intervenes only where the brief
  intended ("equally well-matched"). Easy to reason about; low risk of distorting results.
- **Con:** the band width (`0.02`) is a tunable knob that needs one sanity check against the
  real recipe set.

**Option B — tier as a 6th weighted signal.** Add `source_tier` to `SIGNAL_WEIGHTS` with a
small weight (e.g. `0.05`) and renormalize the others.

- **Pro:** tier becomes a continuous soft prior, always nudging.
- **Con:** changes every ranking, not just near-ties; requires re-tuning all 5 existing
  weights; risk of a credible-but-poorly-matched recipe out-ranking a great match. This is a
  bigger behavioral change than the brief asked for.

**Recommendation: Option A.** It matches the "tie-breaker" intent precisely and is the
smaller, safer change. Option B is a ranking-philosophy change that should be its own decision
if we ever want credibility to actively shape (not just settle) results.

---

## 5. UI surface (trust badge)

Display the tier wherever a recommended recipe is shown (recipe card / result list). Plain
labels, not raw enum values:

- `champion` → "🏆 Championship recipe"
- `barista` → "☕ Pro recipe"
- `enthusiast` → no badge (or "Community recipe" once user-submission exists)

This is the immediate, visible payoff and the lowest-risk part of the change. Exact copy and
placement is a `specs/user-interface.md` concern at build time.

---

## 6. Scope / non-goals

- **In:** the enum + field, backfilling 50 recipes, the near-tie tie-breaker, the trust badge.
- **Out (v1):** user-submitted recipes, community upvoting, any social layer, automated tier
  inference. Tiers are human-assigned from a fixed taxonomy.

---

## 7. Test plan

- **Data-model:** a recipe JSON _without_ `source_tier` loads and defaults to `enthusiast`
  (backward-compat regression); an invalid tier string raises at load.
- **Retrieval:** two recipes with combined scores inside `TIE_BAND` and different tiers →
  champion ranks first; two recipes with a clear score gap → tier does NOT reorder them
  (proves tier only breaks near-ties, never overrides a real winner).
- **Backfill integrity:** every recipe JSON in `data/recipes/` parses to a non-default tier
  after backfill (no curated recipe silently left at `enthusiast`).

---

## 8. Open decisions for the human (RESOLVED — see Decisions log at top)

All five were answered 2026-06-14 and are recorded in the Decisions log at the top of
this file. Retained below for the rationale the human weighed.

1. **Tier count & names** — 3 tiers (`champion` / `barista` / `enthusiast`) as proposed, or a
   different scale? Recommend 3.
2. **The §2.1 mapping** — sign off (or correct) the 10 source→tier assignments. Lance Hedrick
   and Scott Rao are the borderline calls.
3. **Default tier** — `enthusiast` (recommended, honest) vs `barista`.
4. **Tie-breaker mechanism** — Option A near-tie band (recommended) vs Option B weighted signal.
5. **Given the §2 low-variance observation** — do we build the ranking tie-breaker now, or ship
   _only_ the field + trust badge now and defer the tie-breaker until the recipe pool actually
   varies in credibility? Recommend: ship field + badge + Option-A tie-breaker together (the
   tie-breaker is ~15 lines and the test proves it's harmless), but it's a legitimate call to
   defer the ranking half.

```

```

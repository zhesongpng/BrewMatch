# Product Brief Re-Analysis (Delta) — 2026-06-13

**Method**: Re-scrutiny of `briefs/01-product-brief.md` against (a) the prior critique
`03-value-proposition-critique.md` (2026-05-09), (b) the now-BUILT system, and (c) two new
inputs this session — the clarified recipe data model (brief §6.1) and AeroPrecipe as a
concrete competitor.

This file is a DELTA. It does not restate the 2026-05-09 critique's standing verdicts
(platform score 3.4/10, retention cliff structural, moats weak, ML fit excellent) — those
hold. It records only what the new information CHANGES.

---

## 1. What changed since the last analysis

1. **The product is no longer speculative.** B1 (bag-based brew logging) shipped; the app
   runs end-to-end against a live database. The 2026-05-09 critique reasoned about a concept;
   this pass can reason about a working system. Net effect: the "is the scope achievable"
   risk (prior §6.2) is largely retired — it was achieved.
2. **The recipe data model was made explicit** (brief §6.1, spec §1): a recipe is two fused
   things — _brewable parameters_ + _`suitable_for` matching metadata_. This sharpens, rather
   than changes, the "recommender not library" positioning.
3. **A concrete competitor surfaced: AeroPrecipe** (aeroprecipe.com). The 2026-05-09
   competitive set (Beanconqueror, YouTube, ChatGPT) did not include it.

---

## 2. AeroPrecipe — the most useful competitive data point yet

AeroPrecipe is the clearest real-world instance of the "recipe library" model: 300+ AeroPress
recipes, community submit/upvote/comment, credibility tiering (Championship / Barista /
Enthusiast / Experimental), named marquee recipes (Hoffmann), and a companion mobile app.

**Why it strengthens BrewMatch's positioning rather than threatening it:**

- **It is a library, not a diagnoser.** AeroPrecipe answers "show me recipes." It does NOT
  answer "my cup tastes sour — what do I change?" That diagnosis gap is BrewMatch's entire
  thesis. AeroPrecipe is the concrete proof that the library model leaves the diagnosis job
  unsolved.
- **It has no per-bean matching.** AeroPrecipe has no `suitable_for` equivalent — the user
  browses and self-selects. BrewMatch's matching metadata is precisely the field AeroPrecipe
  lacks. The recipe-model clarification this session maps directly onto this gap.
- **It is AeroPress-only.** Different brewer; BrewMatch's pour-over scope does not collide.

**Reframe for the pitch:** AeroPrecipe is the best available "what BrewMatch is NOT" anchor.
"AeroPrecipe is a beautifully executed recipe _library_ — you still have to know which recipe
fits your bean and what to change when it tastes off. BrewMatch starts where AeroPrecipe stops."

**One concrete borrow (low effort, real payoff):** AeroPrecipe's credibility tiering is worth
adopting as a `source_tier` field on `Recipe` (Champion / Barista / Enthusiast). Today `source`
is a free string. A tier (a) builds user trust ("this came from a championship recipe") and
(b) gives the retriever a principled tie-breaker when two recipes match a bean equally well.
This is a v1-or-v1.1 enhancement, NOT a model redesign. See journal CONNECTION entry.

---

## 3. Does the recipe-model clarification change any verdict?

No verdict flips, but two things tighten:

- **"Recommender, not library" is now structurally legible.** The prior critique rated the
  knowledge base a weak moat ("scrapable in a weekend"). That is still true of the _recipes
  themselves_. But the `suitable_for` matching layer + diagnosis engine is the part that is
  NOT a scrape — it is the ML loop. The clarification makes it easier to argue the moat lives
  in the matching/diagnosis layer, not the recipe text. This is a narrative win, not a new moat.
- **Lower skill floor confirmed.** Diagnosis needs only "tastes sour/bitter/weak" input, not a
  calibrated 1–10 rating. The prior critique's "target-user catch-22" (MEDIUM severity) is
  partially dissolved by diagnosis-first framing — and the built directional-flag UI
  (`too_sour / too_bitter / too_weak / too_harsh / astringent`) is the realization of that
  lower floor. Verdict: catch-22 downgraded from MEDIUM to LOW for the diagnosis path.

---

## 4. Brief-vs-built drift (verify before the next gate)

- **Water-temp bound mismatch.** Brief §6.4 constrains optimization to "water temp 85–96°C",
  but the `Recipe` validation in `src/data_models.py` allows 85–100°C. Likely INTENTIONAL
  (optimizer search band tighter than the data-validation band), but it is undocumented. ACTION:
  confirm intent; if intentional, state both bounds in the spec; if not, reconcile. Filed as GAP.
- **Recipe constraint ranges** (dose, water) were already reconciled this session — spec now
  matches code (12–35 g, 180–600 g). No open drift there.

---

## 5. Network-effects re-look (unchanged verdict, sharper evidence)

AeroPrecipe demonstrates the ONE network-effect path BrewMatch deliberately forgoes:
community recipe upvoting. The prior critique flagged this as a speculative counter to the
retention cliff; AeroPrecipe is the proof it works for a competitor. This does NOT change the
v1 recommendation (stay single-player, diagnosis-focused — adding a community layer would dilute
the thesis and is out of scope). It does give the v2 roadmap a concrete, proven reference
("an AeroPrecipe-style community layer for pour-over") if retention data later demands it.

---

## 6. Net assessment

The 2026-06-13 information **confirms and sharpens** the 2026-05-09 conclusions; nothing
reverses. The single most actionable new finding is the AeroPrecipe contrast, which gives the
product (a) a crisp "what we are not" competitive anchor for go-to-market positioning, and
(b) one concrete, cheap product borrow (`source_tier`). The recipe-model clarification makes the
"recommender, not library" claim defensible at the data-model level. The diagnosis-first framing
continues to be the right spine: it is the gap AeroPrecipe leaves open and the job ChatGPT does
generically but not contextually.

**Standing recommendation unchanged:** build the diagnosis-first scalpel; price it as a one-time
unlock; lead the pitch with the AeroPrecipe/ChatGPT contrast (library vs. diagnoser; generic vs.
contextual). Add `source_tier` if cheap; do NOT add a community layer in v1.

# Product Brief: BrewMatch — Coffee Troubleshooting Tool

---

## 1. One-Line Pitch

A coffee troubleshooting tool that gives you a starting pour-over recipe for your beans, then diagnoses what went wrong and tells you exactly what to change — getting better with every brew.

## 2. Problem Statement

Casual home brewers buy specialty beans (S$15–30 per 250g bag) and produce mediocre coffee. They follow generic recipes from YouTube or the bag itself, get inconsistent results, and cannot diagnose what went wrong. The feedback loop between "this tastes bad" and "change this parameter next time" is broken because:

- They don't know which of ~7 parameters to adjust (grind, ratio, temp, bloom, pour pattern, total time, agitation)
- Generic recipes ignore bean-specific characteristics (origin, process, roast level)
- Personal taste varies — what tastes balanced to one drinker tastes sour to another
- The cost of a bad brew is real: ~S$1–2 of coffee wasted plus 5 minutes of effort

**The pain is chronic, not acute.** Users tolerate it rather than solve it. This is the most important constraint on the business case.

## 3. Target User

**Primary persona — "Aspiring home brewer"**:

- Owns a burr grinder and a V60, Kalita Wave, or Origami dripper
- Buys specialty beans from local roasters (Common Man, PPP, Nylon, etc. in Singapore)
- Watches Hoffmann / Lance Hedrick / Onyx YouTube content
- Has been brewing 6 months to 3 years
- Brews 1–2 cups per day at home

**Anti-persona** (NOT the user):

- Coffee professionals — don't need this
- Pure beginners with drip machines — don't care enough
- Commodity bean drinkers — no quality ceiling to chase

## 4. Scope (v1)

**In scope**:

- Pour-over (V60, Kalita Wave, Origami)
- Bean profile input via manual entry (origin dropdown with common origins + "Other", process, roast, flavor, variety, altitude)
- Grinder brand selection during onboarding (9 hand/electric grinders with specific grind settings, or "Other")
- Starting recipe recommendation based on bean profile
- Post-brew feedback: thumbs up/down + directional flags (too sour / too bitter / too weak / too harsh / astringent)
- Diagnosis: specific parameter adjustments based on what went wrong
- Personalization that emerges from accumulated diagnosis history
- Recipe knowledge base of 50–80 curated recipes from expert sources

**Out of scope (v1)**: AeroPress, espresso, French press, moka, cold brew, cupping, roasting, equipment recommendations, photo/OCR input, social features.

## 5. Core User Flow

1. User adds beans (manual entry: origin, process, roast, flavor profile)
2. User selects grinder (brand-specific grind recommendations, e.g. "~30 clicks on Comandante C40")
3. User selects dripper (V60 / Kalita Wave / Origami)
4. System recommends starting recipe (dose, ratio, grind with grinder-specific setting, water temp, bloom, pour schedule, total time)
5. User brews with step-by-step guide showing wait times and cumulative water totals
6. User reports result: thumbs up/down + directional flag if something's off (too sour / too bitter / too weak / too harsh / astringent)
7. System diagnoses the issue using ML: the taste predictor evaluates candidate parameter adjustments and prescribes the one with the highest predicted improvement ("for your light-roast Ethiopian, increasing temperature from 91C to 93C improves the predicted score by 1.2 points — the biggest gain across all options")
8. User adjusts, brews again, gets better coffee
9. Over time, starting recipes improve as the system learns from accumulated diagnosis history

## 6. ML / AI Architecture

### 6.1 Recipe Knowledge Base + Retrieval (Unsupervised + RAG)

- Curated database from public sources (Hoffmann, Barista Hustle, Tetsu Kasuya 4:6, Scott Rao, Onyx, Reddit top posts)
- Each recipe stores two kinds of data:
  - **Brewable parameters** — what you follow to make the cup: dose, water, ratio, grind setting, water temperature, bloom time, total time, and a step-by-step pour schedule. The pour schedule is stored as discrete numeric steps (not free text), so it can be both brewed by a person and adjusted by the optimizer.
  - **Matching metadata** ("suitable for") — which roast levels, origins, processes, and flavor profiles the recipe fits. This is the field that lets the system _pick_ the right recipe for your bean instead of making you browse a list — it's what makes BrewMatch a recommender, not a recipe library.
- Embedding-based retrieval given a query bean profile
- LLM layer generates natural-language brewing instructions

### 6.2 Bean Profile Input

- Input: manual entry form (origin country dropdown, process, roast level, flavor clusters, variety, altitude)
- Structured feature vector captured directly — no NLP extraction needed

### 6.3 Taste Score Prediction (Supervised)

- Target: user-reported rating (thumbs + directional flags mapped to score)
- Features: bean profile + recipe parameters + user history
- Model: gradient-boosted regression (LightGBM)
- **Also powers diagnosis**: The Perturb-and-Score algorithm evaluates each candidate parameter adjustment through the taste predictor and ranks them by predicted improvement. Coffee-science rules define the candidate set; the ML model picks the winner. This makes diagnosis bean-aware and (after 3+ brews) user-aware — not just a lookup table.

### 6.4 Recipe Optimization (Optimization)

- Given bean + user preferences + reported issue, find the minimum parameter change to fix the specific problem
- Constrained: grind discrete, water temp 85–98°C (recommendation ceiling; logged brews may record up to 100°C), ratio 1:14–1:18 for pour-over
- Bayesian optimization (Optuna TPE) starting from the recipe the user actually brewed

### 6.5 Personalization Layer (Emergent)

- New users: expert knowledge-base recipe
- After each diagnosis round: system learns what works for this user
- After several brews: starting recipes are pre-adjusted based on accumulated history
- Personalization is the emergent benefit, not the front-door feature

## 7. Differentiation: Why Not Just Use ChatGPT?

| Capability                         | ChatGPT                           | BrewMatch                                                                           |
| ---------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------- |
| Generate a recipe given a bean     | Yes, generic                      | Yes, grounded in real recipes                                                       |
| Remember what you brewed last time | Only if you tell it every time    | Yes, knows the exact parameters you used                                            |
| Diagnose a specific bad brew       | Generic guess ("try finer grind") | Specific prescription ("your 90°C water was too low for this Ethiopian — try 93°C") |
| Learn from your outcomes over time | No                                | Yes, every diagnosis improves future starting recipes                               |
| Constrain to your dripper          | Can be told, but won't remember   | Built into the parameter space                                                      |

**The defensible value is contextual diagnosis** — BrewMatch knows the exact recipe you used, the exact bean you brewed, and the exact problem you reported. ChatGPT can approximate this if you feed it all the context every time, but most users won't bother.

## 8. Business Case

### 8.1 Market

- Specialty coffee global: ~US$80B, ~10% YoY growth
- Singapore home brewing matured post-COVID
- Adjacent: Acaia (smart scales), Fellow (kettles), Beanconqueror (free, no ML)

### 8.2 Commercial Path

If the diagnosis-first approach resonates with users, the most viable path to revenue would be:

- **One-time premium unlock** (S$10-15): Aligns with what coffee apps charge successfully (Filtru, Coffely). Users pay once for the full ML pipeline — diagnosis, optimization, taste adaptation. Lower friction than subscription for a niche lifestyle app.
- **Freemium entry point**: Unlimited diagnosis for free (builds habit). Premium unlocks taste adaptation (the emergent personalization that makes starting recipes get better over time), recipe export, and multi-dripper support in a future version.

The subscription model (S$5-8/month) was evaluated and rejected — too expensive per-use for an app users open 2-3 times per week. One-time unlock matches both user expectations and competitive benchmarks.

### 8.3 Honest Commercial Risks

- **Willingness to pay is the biggest open question.** Free competition is abundant (Beanconqueror, YouTube, ChatGPT).
- **Retention risk**: users find a working recipe and stop opening the app — the diagnosis loop only activates when something goes wrong.
- **Cold start cliff**: weak taste adaptation for first 10+ brews — mitigated by diagnosis-first approach (value on brew 1, not brew 10).
- **Weak _social_ network effects**: no viral or friend-driven loop. (But real _data_ network effects do exist — see §8.4.)
- **Competing with free**: the value must be clearly better than typing "my V60 brew is too sour" into ChatGPT. The edge is contextual precision — BrewMatch knows the exact parameters you used.

### 8.4 Network Effects: Data, Not Social

BrewMatch has weak _social_ network effects but real _data_ network effects. It doesn't get better because your friends join — it gets better because every brew anyone logs improves the model for everyone buying similar beans. Three mechanisms:

- **Cohort cold-start**: new users don't start from zero. After a couple of brews we place them in a taste archetype learned from the existing user base, so personalized recommendations arrive on brew 1, not brew 10. _More users → faster value for every new user._
- **Shared brewing-physics model**: every logged (bean, recipe, outcome) sharpens the common base model underneath each person's taste. _More users → a smarter baseline for everyone._
- **Bean-level collective wisdom** (the strongest, and the local advantage): when many people brew the same bag from the same roaster, the next buyer inherits what worked for the previous ones. Because the target market clusters around a small set of local roasters, the same beans recur across users, so this compounds fast. _More users on the same beans → better starting recipes for those beans._

These are _data_ effects, so they strengthen the product at scale, not at launch — early users carry the cold-start cost so later users don't. There is still no social loop, and v1 does not build one; the diagnosis engine delivers value on day one regardless. The strongest pillar to build first is bean-level priors: it directly attacks the cold-start cliff and the roaster concentration makes it real rather than aspirational.

# Value Proposition Critique: BrewMatch

**Date**: 2026-05-09
**Auditor Perspective**: CTO / VP Product evaluating for investment decision
**Method**: Critical analysis of product brief (`workspaces/BrewMatch/briefs/01-product-brief.md`)

---

## Executive Summary

BrewMatch has a real user and a real behavior to optimize, but the original critique assumed a subscription SaaS model that has since been replaced with a more viable one-time premium unlock. The brief is unusually honest about its commercial risks (chronic-not-acute pain, willingness-to-pay unknown, retention cliff, weak network effects), which is refreshing and also useful for sharpening the product strategy. The re-scoped product -- a diagnosis-first, pour-over-only troubleshooting tool with a one-time S$10-15 premium unlock -- addresses several of the original critiques structurally: the one-time payment eliminates subscription friction, the diagnosis-first framing front-loads value before the retention cliff hits, and the narrowed scope (V60, Kalita Wave, Origami only; 50-80 curated recipes) matches what a small team can execute well within a course timeline.

**Single highest-impact recommendation**: Build BrewMatch as a diagnosis-first troubleshooting tool with a one-time premium unlock (S$10-15). Focus the core loop on "my brew tastes X, what should I change?" -- not personalization. Ship a polished, commercially viable product that also demonstrates ML competency end-to-end.

---

## 1. Value Proposition Critique

### 1.1 "Chronic, Not Acute" -- What This Means for Adoption

The brief says: "The pain is chronic, not acute. Users tolerate it rather than solve it. This is the most important constraint on the business case."

This is the most intellectually honest sentence in the brief. It was also the sentence that killed the original SaaS subscription case -- which is why the product has pivoted to a one-time unlock model. Here is why the chronic-pain constraint matters even with the new model:

**Chronic pain does not create urgency.** Urgency is what drives downloads, sign-ups, and credit card entries. When someone spills hot coffee on their lap, they buy a new shirt today. When their coffee tastes slightly sour, they drink it and try a different ratio tomorrow. The feedback loop the brief describes -- "this tastes bad" to "change this parameter" -- is already being solved by users through free, incremental experimentation. The "broken" feedback loop is not actually broken. It is slow, and users have accepted slow.

**What this means for the funnel:**

- Top of funnel: Users will not search for "coffee recipe optimizer." They will search for "why is my V60 sour" and land on a James Hoffmann video. BrewMatch competes for attention against YouTube, not against other apps.
- Activation: A user who finds BrewMatch must input their bean, select equipment, receive a recipe, brew, and rate. That is 6 steps before any personalization value kicks in. YouTube is 1 step (press play).
- Retention: The brief admits the retention cliff directly -- users find a working recipe and leave. This is the correct behavior from the user's perspective. They came to solve a problem; once solved, they stop using the tool. This makes BrewMatch a painkiller with a 2-week half-life.

**The adoption curve prediction**: 100 downloads in month 1 from the team's social circle and coffee-nerd communities. 15-20 will complete the first brew cycle. 3-5 will rate enough brews for the diagnosis engine to provide meaningful guidance. The one-time unlock model (S$10-15) is better suited to this funnel shape than a subscription: the user pays once when they are most engaged (during the troubleshooting moment), rather than committing to an ongoing payment for a tool they will use intermittently. A S$10-15 one-time payment is comparable to a bag of specialty coffee beans -- a familiar, justifiable expense for the target user.

### 1.2 "Reduce Bean Waste" -- Is This Compelling?

The brief claims "~S$1-2 of coffee wasted" per bad brew. Let us examine this.

**The math for a one-time unlock.** A 250g bag at S$20 yields approximately 15 cups at 15g dose. A bad brew wastes S$1.33 of beans. If a user ruins 2 cups per bag (which is generous -- most users salvage mediocre coffee rather than pour it out), that is S$2.66 wasted per bag, or roughly S$10.64 per month if they go through 4 bags. A one-time unlock at S$10-15 pays for itself if BrewMatch prevents even 1-2 bags' worth of bad brews over the user's entire brewing career. Unlike a subscription, the value threshold is reached once and never again. The comparison is intuitive: "this costs the same as one bag of beans and saves me from wasting beans going forward." However, the behavioral caveat remains: BrewMatch's diagnosis engine requires brew feedback to improve its recommendations, so early bad brews are still part of the learning curve. The value proposition is "fix future brews faster," not "never have a bad brew again."

**The behavioral reality**: Home brewers who care enough to buy S$20 bags already tolerate the learning curve. They do not throw away bad coffee -- they drink it and adjust next time. The "waste" framing assumes a discard behavior that most users do not practice.

**Verdict**: "Reduce bean waste" is a post-hoc rationalization, not a pain point. It sounds good in a pitch but will not drive a single download.

### 1.3 Is Personalization Actually Valuable?

The brief's core thesis is that personal taste varies and generic recipes fail. This is partially true but mostly irrelevant for the target user.

**The "good enough" problem**: A James Hoffmann V60 recipe works for 80-90% of light-roast beans with zero modification. The remaining 10-20% improvement requires grind adjustment (one variable), not a 7-parameter optimization. The brief's own target user -- "aspiring home brewer, 6 months to 3 years experience" -- already knows to adjust grind finer if the cup is sour. They learned this from the YouTube videos the brief says they watch.

**What personalization actually requires**: For ML personalization to outperform a good generic recipe, the system needs:

1. Accurate taste feedback from users who can reliably distinguish sour from bitter from astringent (most casual brewers cannot)
2. Enough rated brews to build a user vector (the brief says 10+, which means 10+ brews before value kicks in)
3. Parameter granularity that matters (the difference between 92C and 94C water is real but undetectable for most casual brewers)

**The uncomfortable truth**: A user who can provide accurate taste feedback (step 1) is skilled enough to adjust their own recipe. A user who cannot provide accurate feedback produces garbage-in data that makes the ML model worse than a generic recipe. The target user is stuck in a catch-22: if they are skilled enough to use BrewMatch well, they do not need it; if they need it, they cannot use it well.

**When personalization WOULD matter**: If the user switches beans frequently (new bag every 1-2 weeks), the taste model's transfer learning across bean profiles could provide genuine value. A generic recipe cannot say "based on your preference for lower acidity, try a slightly higher ratio with this Ethiopian." This is the one scenario where BrewMatch beats a YouTube recipe. But this scenario requires the user to (a) switch beans often, (b) buy into the rating discipline, and (c) care enough about marginal improvement to stick with it for 10+ brews. That is a narrow segment within an already narrow segment.

### 1.4 Does This Solve a Real Problem or a Coffee-Nerd Problem?

**The problem as described in the brief**: "Casual home brewers buy specialty beans and produce mediocre coffee."

**The problem as experienced by the user**: "My coffee is okay. Sometimes great, sometimes not. I wish it were more consistent."

These are different problems. The brief describes an objective quality gap. The user describes a subjective consistency desire. BrewMatch addresses the former (optimize parameters for objective quality) but the user wants the latter (consistent results with minimal effort).

**What the user actually wants** is a recipe that works reliably for the beans they buy regularly. They do not want to rate every cup on a 1-10 scale. They do not want to learn what "astringent" means. They want to scoop, pour, drink, and have it taste good.

**The coffee-nerd projection**: The brief was written by someone who cares deeply about coffee parameters (the 7-variable taxonomy, the named recipes from Hoffmann/Rao/Kasuya, the grind discretization). That person assumes other people care about these variables. They do not. Most aspiring home brewers want outcome, not process. The brief optimizes for process nerds who represent perhaps 5% of the stated target segment.

---

## 2. Differentiation Audit

### 2.1 The "Defensible Moat" Claim

The brief claims: "The defensible moat is the personalization loop and the curated knowledge base, not the LLM layer."

Let us evaluate each half:

**Personalization loop as moat**: A per-user taste vector is defensible only if (a) switching costs are high, (b) the data is hard to replicate, and (c) the model improves with scale. Here, switching costs are near zero (the user can recreate their taste profile in any competing app in 5 minutes by rating 3 cups). The data is trivially replicable (it is a small feature vector, not millions of interactions). And the model does NOT improve with more users -- the brief explicitly admits "per-user taste models don't benefit from other users," which means there are zero network effects. This is not a moat. It is a puddle.

**Curated knowledge base as moat**: 50-80 curated recipes sourced from publicly available content (Hoffmann videos, Barista Hustle articles, Reddit posts). This is curation, not creation. A competitor can replicate this in a weekend by scraping the same sources. The curation has value (quality filtering, tagging) but it is a speed bump, not a wall. ChatGPT already has most of this knowledge in its training data. However, the narrower scope (pour-over only, three drippers) means the curation can be meaningfully deeper per method -- every recipe tested and annotated for specific dripper geometry, which is harder to replicate quickly than a broad-but-shallow collection.

**Verdict**: Neither claimed moat would survive 30 minutes of competitive analysis from an actual investor.

### 2.2 ChatGPT Comparison -- Rate Each Differentiator

| Capability                    | Brief's Claim                           | Honest Assessment                                                                                                                                                                                                                                                                                                                                                                                                                                  | Rating                                        |
| ----------------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Grounded in real recipes      | ChatGPT generic, BrewMatch grounded     | ChatGPT with web browsing can access the same Hoffmann, Rao, and Barista Hustle recipes in real time. "Grounded" means BrewMatch hardcodes the recipes ChatGPT already knows.                                                                                                                                                                                                                                                                      | **WEAK** -- marginal advantage at best        |
| Persistent model              | ChatGPT has no memory                   | ChatGPT Memory and Custom Instructions now persist user preferences across sessions. A user who tells ChatGPT "I prefer lower acidity, brighter fruit notes" gets persistent personalization for free.                                                                                                                                                                                                                                             | **OBSOLETE** -- ChatGPT closed this gap       |
| Learn from outcomes           | ChatGPT cannot learn from brew outcomes | Genuine advantage. ChatGPT cannot run a regression on your last 10 cup ratings. But the question is: does this learning produce meaningfully better recommendations than "try a slightly finer grind"? For most users, the answer is no -- the parameter space is small enough that simple heuristics match ML performance.                                                                                                                        | **REAL BUT MARGINAL**                         |
| Equipment-aware               | ChatGPT is not                          | ChatGPT absolutely can be told "I have a Baratza Encore grinder and a V60" and factor that into recommendations. It does not have a structured equipment database, but for 2 brew methods and a handful of grinders, the "database" is trivially small.                                                                                                                                                                                            | **TRIVIAL**                                   |
| Taste-history-aware diagnosis | ChatGPT gives generic guesses           | This is the strongest differentiator in theory. A system that says "your last 3 Ethiopian brews were rated sour, and the common variable was water temp at 90C -- try 93C" is genuinely more useful than ChatGPT's general advice. This IS the diagnosis engine -- BrewMatch's primary value proposition as a troubleshooting tool, not a personalization layer. But this requires 10+ rated brews to activate, which most users will never reach. | **REAL BUT GATED** behind the retention cliff |
| Curated knowledge base        | ChatGPT has diluted knowledge           | The dilution claim is wrong. ChatGPT's knowledge of specialty coffee is excellent because the specialty coffee community extensively publishes online. Hoffmann's V60 recipe is one of the most-referenced coffee resources on the internet.                                                                                                                                                                                                       | **FALSE**                                     |

**Summary**: 1 real-but-marginal differentiator, 1 real-but-gated behind retention, 4 that do not survive scrutiny. The diagnosis-first re-scoping strengthens the "REAL BUT GATED" differentiator by making it the core value proposition rather than a secondary feature, but the fundamental challenge remains: most users will not rate enough brews to activate it.

### 2.3 What ChatGPT Actually Cannot Do

To be fair, there IS a capability gap, but the brief does not articulate it precisely:

1. **Structured parameter search with feedback**: ChatGPT cannot systematically explore a parameter space (grid search, Bayesian optimization) and close the loop with user ratings. This is genuinely an ML capability that goes beyond prompt engineering.

2. **Cross-bean transfer learning**: A trained model that learns "this user prefers higher extraction with African beans but standard extraction with Central American beans" and applies that to a new bag without explicit re-training. ChatGPT cannot do this because it lacks a numerical model.

3. **Cold-start recipe ranking**: Given a new bean profile (origin, process, roast level), rank the top-k recipes from a database by expected fit. This is a retrieval + ranking problem that benefits from embeddings and structured data.

These are ML competencies worth demonstrating. They are not product moats, but they ARE the reason this project earns marks in an ML course -- and with the diagnosis-first framing, they directly serve the commercial product case as well.

---

## 3. Business Model Critique

### 3.1 Willingness to Pay -- The Revised Question

The brief admits: "Willingness to pay is the biggest open question."

For a subscription model, this was a settled question with an answer the team did not want to hear. For a one-time unlock at S$10-15, the question is genuinely open. Here is the evidence in both directions:

**Comparable products that are free**:

- Beanconqueror (free, feature-rich brew logging)
- James Hoffmann YouTube (free, authoritative recipes)
- r/pourover subreddit (free, community troubleshooting)
- Coffee advection calculators (free, web-based)

**Comparable products that charge**:

- Acaia app (free, ships with S$200+ scale)
- Fellow Prismo app (free, ships with S$40+ attachment)
- There is no successful coffee recipe subscription app on the market. This is not because no one has tried. It is because the willingness to pay recurring fees is zero for recipe recommendations and minimal for brew logging. One-time purchase apps in this space have fared better (Acaia, various brew timer apps), which supports the one-time unlock model.

**The one-time unlock model (S$10-15)**: This is a substantially better model than the original subscription proposal. A one-time payment of S$10-15 is in the range of a single bag of specialty coffee beans -- a comparison the target user will intuitively understand. Unlike a recurring subscription, there is no cancellation decision, no monthly reminder on the credit card statement, and no "am I still using this?" churn moment. The user pays once during the moment of highest engagement (troubleshooting a bad brew) and keeps access forever. The risk is lower willingness-to-pay upfront compared to a free trial, but the conversion rate on users who do pay will be higher because the commitment is finite and tangible.

**Is the one-time model viable?** For a niche utility, it is the most viable option. Apps like Command Post, Helvetica Neue, and countless coffee-timer apps have demonstrated that coffee enthusiasts will pay a one-time fee in the S$5-15 range for a well-executed single-purpose tool. The model also aligns with the MBA course project: the team can demonstrate a functioning payment flow and unit economics without pretending to have recurring revenue.

### 3.2 One-Time Premium Unlock Design

**Does this create urgency?** Better than a freemium model, but the gating strategy matters. The one-time unlock model (S$10-15) works best when the free tier provides enough value to hook the user, with the unlock providing genuine additional capability.

**Recommended free/unlock split**: Free tier includes unlimited diagnosis and basic recipe recommendations for one dripper (e.g., V60 only). Premium unlock adds Kalita Wave and Origami support, cross-bean transfer learning, advanced diagnosis history, and the full curated recipe database (50-80 recipes). This lets users experience the core diagnosis loop for free with one method, creating genuine perceived value before the paywall. The unlock feels like gaining access to a deeper toolkit rather than paying to remove an arbitrary restriction.

### 3.3 Retention Risk

The brief says: "Users find a working recipe and stop opening the app."

This is correct and unsolvable within the current product scope. The user's goal is to make good coffee. Once they achieve that goal, they stop using the tool. This is the "therapist problem" -- a successful product makes itself unnecessary.

**Potential counters** (all speculative):

- New bean alerts: "You just bought a new Ethiopian -- want a recipe?" But this requires the user to manually input every new bag, which is friction.
- Seasonal recipe refreshes: "Your Kenyan recipe is optimized for last season's crop. This season's crop may need adjustment." Interesting but unproven.
- Community recipes: "Try this recipe that worked for 47 other users with the same bean." But social features are explicitly out of scope for v1.

**Verdict**: The retention cliff is structural. Accept it and design for a high-value 2-4 week engagement window rather than trying to create daily active usage.

---

## 4. Platform Model Evaluation

### 4.1 Producer/Consumer Dynamics

**Producer**: The BrewMatch team produces the curated recipe knowledge base and the ML diagnosis engine. In theory, users could also be producers (contributing rated brews that improve the global model), but the brief explicitly says per-user models do not benefit from other users, so user-to-user production is zero.

**Consumer**: Individual home brewers consuming personalized recipes.

**Transaction**: The user provides taste ratings (data) in exchange for optimized recipes (value). This is a data-for-value transaction, not a money-for-value transaction.

**Assessment**: This is not a platform. It is a single-sided service with no producer ecosystem. A platform requires independent producers creating value for independent consumers. BrewMatch has one producer (the team) and many consumers (users). Calling this a "platform" stretches the definition beyond usefulness.

### 4.2 Network Effects

The brief says network effects are "weak." This is accurate but undersells how weak they are.

**Same-side effects (user-to-user)**: Zero. Per-user taste models do not improve from other users' data.

**Cross-side effects (producer-to-consumer)**: Minimal. More recipes in the knowledge base slightly improves starting recommendations, but the knowledge base is curated by the team, not crowdsourced.

**Can network effects be strengthened?** Theoretically yes, through:

- Aggregated taste models (cold-start new users from cohort behavior)
- Community recipe sharing (users publish successful recipes)
- Roaster partnerships (roasters provide bean-specific starter recipes)

All of these require social features that are out of scope for v1 and would require significant product redesign.

### 4.3 Platform Scoring (1-10 scale)

| Dimension                   | Score | Justification                                                                                                                                                                  |
| --------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Accessibility               | 5     | Easy to understand conceptually, but the 8-step core flow and 10-brew cold start create real friction. Not immediately useful on first open.                                   |
| Engagement                  | 3     | Engagement requires daily brewing AND daily rating. Most users will engage 1-2x/day during the learning phase, then drop to near-zero once they find a working recipe.         |
| Personalization / Diagnosis | 7     | This IS the product -- now re-centered on diagnosis rather than personalization. If the ML works, diagnosis is genuinely valuable from brew 1. The strongest dimension by far. |
| Connection                  | 1     | Zero social features in v1. No community, no sharing, no discovery of others' recipes. The loneliest app in the app store.                                                     |
| Collaboration               | 1     | No collaborative features whatsoever. Not applicable in v1 scope.                                                                                                              |

**Aggregate: 3.4/10** -- This is a tool, not a platform. The platform framing adds no analytical value.

---

## 5. AAA Framework

### 5.1 Automate -- What Operational Costs Does This Reduce?

**For the user**: BrewMatch automates the recipe lookup and parameter adjustment process. Instead of watching a 12-minute Hoffmann video, reading a Reddit thread, and synthesizing advice, the user gets a recipe in 30 seconds.

**Operational cost reduced**: ~10-15 minutes of research per new bean. This is real but small. Most users do not research each new bean -- they apply the same recipe and adjust grind.

**Assessment**: Low automation value. The automated task (recipe lookup) is already low-friction. YouTube search is fast. Reddit is fast. The 10-15 minute savings is real but not life-changing.

### 5.2 Augment -- What Decision-Making Costs Does This Reduce?

**For the user**: The primary decision cost is "which parameter do I adjust and by how much?" The brief correctly identifies that users do not know which of 7 parameters to change. BrewMatch replaces this decision with a recommendation: "try 93C instead of 90C, same grind, slightly higher ratio."

**Decision cost reduced**: The cognitive load of causal reasoning about brewing parameters. This IS genuinely valuable for users who lack the mental model connecting brew variables to taste outcomes.

**Assessment**: Medium augmentation value. The strongest AAA dimension. This is what BrewMatch should optimize for -- and the re-scoped product correctly centers on this. The diagnosis-first framing ("I brewed this and it tastes sour. What should I change?") is the question worth answering. Personalization enhances diagnosis over time, but diagnosis is the immediate value that works from brew 1.

### 5.3 Amplify -- What Expertise Costs Does This Reduce?

**For the user**: BrewMatch amplifies casual brewer intuition to approximate a more experienced brewer's judgment. A 6-month brewer with BrewMatch should make decisions similar to a 2-year brewer without it.

**Expertise cost reduced**: The 1.5-2.5 year learning curve of developing brew intuition. This is meaningful in theory but requires the ML model to actually encode expert knowledge, which depends entirely on the quality and quantity of training data (which the team does not have yet).

**Assessment**: Potentially high amplify value, but entirely theoretical until the model is trained and validated against expert recommendations. The risk is that the model amplifies mediocre advice because the training data comes from casual brewers, not experts.

---

## 6. Academic Project Fit

### 6.1 ML Architecture vs. Course Requirements

The brief maps ML components to MGMT655 course weeks:

| Component               | Course Week                 | Fit                                                                                                                               | Assessment                                                                 |
| ----------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Taste score prediction  | Week 3 (Supervised)         | Gradient-boosted regression on (bean features + recipe params + user history) to predict rating (1-10). Clean supervised problem. | **STRONG** -- well-scoped, demonstrable, evaluable                         |
| Recipe optimization     | Week 4 (Optimization)       | Bounded optimization over recipe parameters to maximize predicted taste score. Constrained discrete + continuous search.          | **STRONG** -- genuine optimization problem with real constraints           |
| Recipe retrieval + RAG  | Week 5 (Unsupervised + RAG) | Embedding-based retrieval from curated recipe database. LLM layer for natural language output.                                    | **STRONG** -- RAG is highly relevant, embeddings are demonstrable          |
| Bean feature extraction | Week 5/6                    | LLM-based extraction of structured features from free-text roaster descriptions.                                                  | **MODERATE** -- mostly prompt engineering, not deep ML                     |
| Personalization layer   | Cross-cutting               | Hybrid cold-start with global priors transitioning to per-user models.                                                            | **STRONG** -- touches collaborative filtering, cold-start, online learning |

**Overall ML fit: EXCELLENT.** The architecture touches supervised learning, optimization, unsupervised learning (embeddings), RAG, and personalization -- covering at least 4 of the course's major topics in one project. This is significantly above average for an MBA ML course project.

### 6.2 Scope Achievement

**Is the scope achievable?** Let us separate "demo scope" from "product scope":

**Product scope (as re-scoped)**: 50-80 curated recipes for pour-over methods (V60, Kalita Wave, Origami), manual text entry for bean details (not photo OCR), equipment profiles for supported drippers, per-user diagnosis history, optimization engine, RAG pipeline, natural language generation. This is 2-3 months of engineering for a solo developer, or 4-6 weeks for a team of 3-4 with ML experience. The narrower scope is a strength -- it means each recipe can be deeper-annotated and the ML models can be tuned for the specific parameter space of pour-over brewing.

**Course timeline**: Assuming 6-8 weeks from concept to submission (typical for a semester project), the full product scope is achievable IF the team is disciplined about what to build in-house vs. what to use off-the-shelf.

**Risk areas**:

- Recipe knowledge base curation (50-80 recipes, pour-over only) is manageable within the course timeline. The team can start with 30-40 and demonstrate the retrieval pipeline works, then expand.
- Bean input uses manual text entry (not photo OCR), which avoids a significant engineering detour. This is the correct tradeoff for the course timeline.
- Per-user model training at inference time is computationally non-trivial. Recommend pre-trained global model with user-bias correction rather than full per-user retraining.

### 6.3 MVP That Demonstrates ML Competency vs. Full Vision

**The MVP (3-4 weeks, demonstrates all ML competencies)**:

1. **Supervised learning component**: Train a gradient-boosted model on a synthetic dataset of (bean features, recipe parameters, user taste profile) to predict rating. Generate synthetic training data from expert rules (if Ethiopian + washed + light, higher temp and lower ratio tend to score higher for users who prefer bright cups). Demonstrate the model predicts ratings with meaningful accuracy on a held-out test set. This proves supervised learning competency.

2. **Optimization component**: Given the trained model and a bean profile, run bounded grid search over recipe parameters to find the predicted-optimal recipe. Show the optimization converges and produces sensible recommendations. This proves optimization competency.

3. **RAG component**: Embed 50-80 curated pour-over recipes from public sources. Given a bean profile, retrieve the top-k most similar recipes using cosine similarity on embeddings. Show that retrieval surfaces relevant recipes (e.g., Ethiopian natural process beans retrieve recipes that emphasize higher ratios and longer bloom times). This proves RAG competency.

4. **Personalization demo**: Simulate a user rating 5-10 brews. Show that the model's recommendations shift based on the user's taste profile (e.g., a user who rates low-acidity cups higher gets recommendations with higher ratios and lower temps). This proves the personalization loop works.

5. **Streamlit interface**: A simple web UI where the user inputs bean details, selects a brew method, gets a recommendation, rates the result, and sees the next recommendation update. This proves the system is end-to-end functional.

**What to cut from the MVP**:

- Bean photo input (OCR) -- use text input (adopted)
- Methods beyond pour-over -- focus on V60, Kalita Wave, Origami (adopted -- AeroPress correctly scoped out)
- Recipe count -- use 50-80 curated recipes, not hundreds (adopted -- the original critique's recommendation was taken)
- LLM natural language generation -- show structured recipe output initially, add natural language later
- Subscription billing -- one-time premium unlock only (adopted -- subscription model was correctly rejected)
- Mobile app -- Streamlit demo is sufficient for course delivery; native app is a post-course consideration

**What this MVP demonstrates**: The team can frame an ML problem, collect/generate appropriate data, train and evaluate a supervised model, apply optimization to that model, build a retrieval pipeline with embeddings, and close the personalization loop. That is 4 course topics in one coherent demo. The professor will recognize this as ambitious and well-executed.

---

## 7. Severity Table

| Issue                                                                                                                                                                       | Severity              | Impact                                                                        | Fix Category                                                                                                                                               |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ~~SaaS subscription model is not viable~~ -- RESOLVED: replaced with one-time premium unlock (S$10-15)                                                                      | ~~CRITICAL~~ RESOLVED | Original subscription model was correctly rejected; one-time unlock is viable | RESOLVED -- one-time unlock aligns with user behavior (pay during engagement peak)                                                                         |
| Retention cliff is structural and unsolvable within v1 scope                                                                                                                | HIGH                  | Makes recurring LTV calculations meaningless; churn > 90% in month 1          | DESIGN -- reframe as high-intensity short-engagement tool; one-time unlock makes retention cliff less fatal (no recurring revenue to lose)                 |
| "Chronic not acute" pain means no organic acquisition channel                                                                                                               | HIGH                  | No search volume, no word-of-mouth, paid acquisition unaffordable             | NARRATIVE -- pitch as diagnosis-first troubleshooting tool, not personalization engine; diagnosis has higher perceived urgency than optimization           |
| 10-brew cold start means personalization value arrives AFTER most users churn                                                                                               | HIGH                  | Users experience 0 personalization during the critical first-session window   | DESIGN -- front-load value with diagnosis-first approach (expert recipes + parameter adjustment suggestions work from brew 1, no personalization required) |
| Moat claims remain weak (personalization data trivially replicable, knowledge base scrapable) -- but narrower pour-over scope enables deeper curation per method            | MEDIUM                | Undermines credibility in any investor/academic presentation                  | NARRATIVE -- lead with ML competency and diagnosis value, not defensibility; depth-over-breadth curation is the more honest differentiator                 |
| Target user catch-22 partially resolved by diagnosis-first framing: users need not rate accurately, they need to describe taste (sour/bitter/balanced) which is a lower bar | MEDIUM                | Core value hypothesis stronger for diagnosis than personalization             | DESIGN -- diagnosis requires only "tastes sour/bitter" feedback, not precise 1-10 rating; lowers the skill floor for value delivery                        |
| Bean waste value prop is post-hoc rationalization (users drink bad coffee, do not discard)                                                                                  | LOW                   | Weakens pitch but does not change product viability                           | NARRATIVE -- drop "reduce waste" entirely                                                                                                                  |
| Connection/Collaboration scores at 1/10 -- this is a tool, not a platform                                                                                                   | LOW                   | Platform framing adds no analytical value                                     | NARRATIVE -- call it what it is                                                                                                                            |

---

## Bottom Line

BrewMatch is a well-scoped ML project that has found its correct framing: a diagnosis-first, pour-over-only troubleshooting tool with a one-time premium unlock. The re-scoped product addresses several of the original critique's most serious findings structurally. The one-time unlock model (S$10-15) eliminates the subscription friction that made the original SaaS case terminal. The diagnosis-first centering means value arrives from brew 1 ("my coffee is sour, what should I change?") rather than requiring 10+ rated brews for personalization to activate. The narrowed scope (V60, Kalita Wave, Origami; 50-80 curated recipes) matches what the team can execute with depth and quality within the course timeline, rather than spreading thin across hundreds of recipes and multiple brew methods.

The ML architecture remains genuinely strong -- it covers supervised learning, optimization, RAG, and personalization in one coherent system, which is ambitious and impressive for MGMT655. The remaining risks (retention cliff, chronic-not-acute pain, weak network effects) are real but manageable within a one-time payment model where recurring revenue is not the success metric. The product does not need daily active users to succeed commercially -- it needs to deliver enough value during a 2-4 week engagement window that the user feels the S$10-15 was well spent.

The winning move: build the diagnosis-first troubleshooting tool with the one-time unlock model, prove the ML loop works end-to-end in Streamlit, and present it as both a commercially viable product concept and an ML portfolio piece that demonstrates mastery of course concepts. These goals are no longer in tension -- the diagnosis-first scope serves both.

Build the scalpel. Price it as a scalpel, not a subscription. Let the diagnosis speak for itself.

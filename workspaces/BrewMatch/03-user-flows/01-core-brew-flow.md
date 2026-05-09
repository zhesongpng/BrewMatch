# BrewMatch Core User Flows

Date: 2026-05-09
Updated: Diagnosis-first framing — BrewMatch is a coffee troubleshooting tool

---

## Flow 1: First Brew (New User)

**Precondition**: User has never used BrewMatch. They just bought a new bag of beans.

```
1. [Onboarding Quiz] (30 seconds)
   Q1: "What flavors do you enjoy?" → Select: Fruity / Floral / Chocolatey / Nutty / Balanced
   Q2: "What roast level do you usually prefer?" → Light / Medium / Dark
   Q3: "How long have you been brewing?" → <6 months / 6mo-1yr / 1-3yr / 3yr+
   Q4: "What dripper do you use?" → V60 / Kalita Wave / Origami (multi-select)
   → System builds initial taste profile from quiz answers

2. [Add Beans] (15 seconds)
   User types/pastes roaster description:
   "Ethiopia Yirgacheffe, washed, light roast, notes of blueberry, jasmine, bergamot"
   → Bean Profile Extractor produces structured profile

   2a. [Extraction succeeds] → User confirms/edits extracted fields (origin, process, roast, flavor notes)
   2b. [Extraction fails or LLM unavailable] → Manual entry form:
       - Origin: dropdown of coffee-producing countries
       - Process: dropdown (washed / natural / honey / anaerobic / unknown)
       - Roast level: dropdown (light / medium-light / medium / medium-dark / dark / unknown)
       - Flavor notes: free text, mapped to clusters on save

3. [Get Starting Recipe] (5 seconds)
   System retrieves best-matching recipe from knowledge base
   Ranks by: (bean profile match × predicted taste score for this user)
   Displays recipe with full parameters:
   - Dose: 15g, Water: 250g (1:16.67)
   - Grind: Medium-fine (7/10)
   - Temp: 93°C
   - Bloom: 30s with 50g water
   - Pour 2: 100g at 0:30
   - Pour 3: 100g at 1:30
   - Total time: ~3:00

4. [Brew] (3-4 minutes, app not needed)
   Recipe is displayed on screen. User brews.

5. [Report Result] (5 seconds)
   "How was it?" → Thumbs UP or Thumbs DOWN
   If down: "What was off?" → Too sour / Too bitter / Too weak / Too harsh / Astringent / Other
   → System logs feedback

6. [Diagnosis + Adjustment] (immediate)
   If thumbs up: "Great! This recipe is saved to your profile."
   If thumbs down with directional flag:
   "Too sour usually means under-extraction. Based on your recipe:
    - Water temp (90°C) is low for a light-roast Ethiopian
    - Try 93°C with the same grind and ratio
    This increases extraction to pull sweetness that balances the acidity."
   → System presents adjusted recipe with specific changes highlighted
```

**Critical design principle**: The first recipe must be genuinely good (grounded in expert knowledge). The diagnosis/adjustment on the first bad brew is what demonstrates the product's value — not personalization.

---

## Flow 2: Troubleshooting Loop (Core Value)

This is BrewMatch's primary flow — not a side feature. The user brews, something's off, BrewMatch diagnoses and prescribes a fix.

```
1. [User reports bad brew]
   "My coffee tasted off." → What was wrong?
   → Too sour / Too bitter / Too weak / Too harsh / Astringent

2. [System diagnoses]

   2a. [User has 0-2 prior brews — rule-based diagnosis]
   "Based on your bean (light roast Ethiopian, washed) and your feedback
    (too sour), this usually means under-extraction.
    Your recipe used 90°C water and grind 6/10 — both on the low end for
    light roasts. Try:
    1. Water temp: 90°C → 93°C
    2. Grind: 6/10 → 8/10
    These should increase extraction yield and reduce sourness."
   (Knowledge-base driven, not personalized — which is fine for the bean-aware phase.)

   2b. [User has 3+ brews — history-informed diagnosis]
   "Your last 3 Ethiopian brews were all rated 'too sour'. Common factor:
    water temp at 90°C. Ethiopian naturals often need 93-95°C for proper extraction.
    Also, your grind (6/10) may be too coarse for light roasts."

3. [Specific recommendation with parameters]
   "Try these changes:
    1. Water temp: 90°C → 93°C
    2. Grind: 6/10 → 8/10
    These should increase extraction yield and reduce sourness."
   → User gets a new adjusted recipe to try

4. [Track outcome]
   Next brew: user rates again
   System validates whether the diagnosis was correct
   → If fixed: positive reinforcement, update taste model, note the pattern
   → If not: try next most likely parameter (ratio or bloom time)
   → After 2-3 rounds: "Your personal recipe for this bean is locked in."
```

**Why this is the core flow**: Diagnosis delivers immediate value (brew 1), requires no learning period, and is hard to replicate with generic advice because BrewMatch knows the exact parameters used.

---

## Flow 3: Returning User (New Bag)

```
1. [Add New Beans] (15 seconds)
   User enters new bean description
   → Bean Profile Extractor produces structured profile

2. [Get Recipe — Now Pre-Adjusted] (5 seconds)
   System uses accumulated taste history from prior diagnoses
   Recipe starts closer to the user's preferences:
   "Based on your past brews, you tend to prefer higher extraction with
    African beans. For this Ethiopian, we recommend:
    - Temp: 93°C (not the standard 90°C for this recipe)
    - Grind: 8/10 (finer than default)
    This is based on what worked for your previous Ethiopian and Kenyan beans."

3. [Brew + Report] → Same as Flow 1 steps 4-5

4. [Troubleshooting if needed] → Same as Flow 2
   If the pre-adjusted recipe works: fewer troubleshooting rounds needed
   If not: diagnosis kicks in as normal
```

**Retention hook**: Every new bag triggers Flow 3. The starting recipe gets better over time because the system has learned from past diagnoses. Personalization is the emergent benefit — the user just notices "the first recipe keeps getting better."

---

## Flow 4: Demo Narrative (Presentation)

```
1. "Meet Alex" — Show Alex's profile: likes bright, fruity coffees, 1yr experience, V60
2. "Alex buys new beans" — Enter real roaster description, show extraction pipeline
3. "BrewMatch finds a starting recipe" — Show RAG retrieval with similarity scores
4. "BrewMatch predicts taste" — Show predicted rating for the top recipe
5. "Alex brews and reports" — Simulate: thumbs down, "too sour"
6. "BrewMatch diagnoses" — Show the diagnosis: extraction theory + specific parameter adjustment
   This is the hero moment — the ML pipeline closes the loop in real time
7. "Alex adjusts and re-brews" — Show the adjusted recipe and improved result
8. "3 beans later" — Show how starting recipes have improved from accumulated diagnoses
9. "Evaluation" — Show metrics table: all 5 components with actual vs. target values
```

---

## Flow 5: Extraction Failure (Edge Case)

```
1. User pastes description: "some random text that isn't a coffee description"
2. Bean Profile Extractor returns low confidence (< 0.5)
3. System shows: "I couldn't extract bean details from that description."
4. Manual entry form appears:
   - Origin: dropdown
   - Process: dropdown
   - Roast level: dropdown
   - Flavor notes: free text
5. User fills in what they know → continues to recipe retrieval
```

This flow handles LLM failures gracefully and keeps the user moving forward.

# Bean Profile Extraction Specification

## 1. Overview

Free-text roaster descriptions are the primary input for bean characterization. Users paste the text from a coffee bag label (e.g., "Ethiopia Yirgacheffe, washed, light roast, notes of blueberry, jasmine, bergamot"). The extraction pipeline converts this unstructured text into a structured `BeanProfile` conforming to the schema in `specs/data-models.md` Section 2.

This is the NLP component of the ML pipeline, demonstrating structured information extraction from natural language using LLM-based methods.

---

## 2. Input Format

### 2.1 Source Text

The raw input is a free-text string, typically 20-200 characters, copied from a coffee bag label. The text is unstructured and varies widely across roasters.

| Example Input                                                                               | Source                     |
| ------------------------------------------------------------------------------------------- | -------------------------- |
| "Ethiopia Yirgacheffe, washed, light roast, notes of blueberry, jasmine, bergamot"          | Common Man Coffee Roasters |
| "Colombia Huila Supremo. Medium-dark. Chocolate, caramel, nutty. Natural process."          | Nylon Coffee               |
| "Gesha variety from Panama, grown at 1800m. Anaerobic fermented. Tropical fruits, florals." | PPP Coffee                 |
| "Our signature house blend. Bold and full-bodied."                                          | Generic roaster            |
| "Sun-dried Ethiopian heirloom. Explosive blueberry and dark chocolate."                     | Artisan roaster            |

### 2.2 Input Validation

| Check    | Rule                                              | Error Handling                                       |
| -------- | ------------------------------------------------- | ---------------------------------------------------- |
| Length   | Minimum 5 characters                              | Return validation error, prompt for more text        |
| Language | English only (v1)                                 | Attempt extraction; flag low confidence              |
| Encoding | UTF-8                                             | Normalize to UTF-8 on input                          |
| Content  | Must contain at least one coffee-relevant keyword | Return low-confidence result with partial extraction |

---

## 3. Extraction Pipeline

### 3.1 Stage 1: LLM Structured Extraction

Use an LLM with structured output (JSON mode) to extract all `BeanProfile` fields from the source text.

**Prompt template:**

```
You are a specialty coffee expert. Extract a structured bean profile from this roaster description.

Source text: "{source_text}"

Extract the following fields as JSON:
- origin_country: string (coffee-producing country)
- origin_region: string or null (sub-region, e.g., "Yirgacheffe", "Huila")
- process: one of ["washed", "natural", "honey", "anaerobic", "wet-hulled", "unknown"]
- roast_level: one of ["light", "medium-light", "medium", "medium-dark", "dark", "unknown"]
- flavor_notes: array of individual descriptors from the WCR Sensory Lexicon
- flavor_clusters: array mapped to these 15 clusters: [Floral, Berry, Citrus, Stone Fruit,
  Tropical, Sweet, Chocolate, Nutty, Spice, Roasted, Vegetal, Tea-like, Fermented,
  Syrupy, Balanced]
- variety: string or null (cultivar, e.g., "Gesha", "Bourbon", "SL28")
- altitude_min_m: integer or null
- altitude_max_m: integer or null

Rules:
- Map flavor descriptors to the closest cluster(s). A single note may map to multiple clusters.
- If a field cannot be determined, use null (for optional fields) or "unknown" (for enum fields).
- Be conservative: only extract what is explicitly stated or strongly implied.
- Origin country is REQUIRED. If no origin is identifiable, set origin_country to "unknown".
```

**LLM configuration:**

| Parameter       | Value                               | Rationale                 |
| --------------- | ----------------------------------- | ------------------------- |
| Model           | Configured via `.env` (`LLM_MODEL`) | Per project convention    |
| Temperature     | 0.1                                 | Deterministic extraction  |
| Max tokens      | 512                                 | Bean profiles are compact |
| Response format | JSON                                | Structured output         |

### 3.2 Stage 2: Validation Layer

Validate the LLM output against the `BeanProfile` schema. Every field is checked for type, range, and constraint compliance.

| Field             | Validation                                                         | On Failure                  |
| ----------------- | ------------------------------------------------------------------ | --------------------------- |
| `origin_country`  | Non-empty string, must be in known coffee-producing countries list | Set to "unknown"            |
| `origin_region`   | String or null                                                     | Pass through                |
| `process`         | Must be in enum set                                                | Set to "unknown"            |
| `roast_level`     | Must be in enum set                                                | Set to "unknown"            |
| `flavor_notes`    | Array of strings, each non-empty                                   | Filter empty strings        |
| `flavor_clusters` | Array, each must be in 15-cluster taxonomy                         | Filter invalid clusters     |
| `variety`         | String or null                                                     | Pass through                |
| `altitude_min_m`  | Integer >= 0, <= 3000                                              | Set to null if out of range |
| `altitude_max_m`  | Integer >= altitude_min_m (if both present)                        | Set to null if inconsistent |

**Known coffee-producing countries** (primary list for v1): Ethiopia, Colombia, Brazil, Guatemala, Kenya, Costa Rica, Panama, Honduras, Nicaragua, El Salvador, Peru, Bolivia, Ecuador, Rwanda, Burundi, Tanzania, Uganda, Democratic Republic of Congo, Mexico, Jamaica, Haiti, Dominican Republic, Yemen, India, Indonesia, Vietnam, Thailand, Myanmar, Papua New Guinea, Hawaii (USA), Australia.

### 3.3 Stage 3: Confidence Scoring

Compute `extraction_confidence` as a weighted score of how many fields were successfully extracted.

| Component                                  | Weight | Score                            |
| ------------------------------------------ | ------ | -------------------------------- |
| `origin_country` extracted (not "unknown") | 0.25   | 1.0 if present, 0.0 if "unknown" |
| `process` extracted (not "unknown")        | 0.15   | 1.0 if present, 0.0 if "unknown" |
| `roast_level` extracted (not "unknown")    | 0.15   | 1.0 if present, 0.0 if "unknown" |
| `flavor_clusters` has >= 1 entry           | 0.25   | 1.0 if >= 1, 0.0 if empty        |
| `variety` extracted                        | 0.05   | 1.0 if present, 0.0 if null      |
| `altitude` extracted (either min or max)   | 0.05   | 1.0 if present, 0.0 if both null |
| `origin_region` extracted                  | 0.10   | 1.0 if present, 0.0 if null      |

**Confidence tiers:**

| Range      | Tier   | Behavior                                                  |
| ---------- | ------ | --------------------------------------------------------- |
| 0.7 - 1.0  | HIGH   | Proceed with bean profile as-is                           |
| 0.4 - 0.69 | MEDIUM | Proceed, but surface "incomplete profile" warning to user |
| 0.0 - 0.39 | LOW    | Offer manual entry fallback, explain what was missing     |

### 3.4 Stage 4: Flavor Note Normalization

Map individual flavor descriptors to the 15-cluster taxonomy. The LLM performs initial mapping; a validation pass ensures cluster names are exact.

| Raw Descriptor   | Mapped Cluster |
| ---------------- | -------------- |
| "blueberry"      | Berry          |
| "bergamot"       | Citrus         |
| "jasmine"        | Floral         |
| "caramel"        | Sweet          |
| "dark chocolate" | Chocolate      |
| "nutty"          | Nutty          |
| "tobacco"        | Roasted        |
| "winey"          | Fermented      |
| "clean, smooth"  | Balanced       |
| "molasses"       | Syrupy         |

A single descriptor can map to multiple clusters (e.g., "bergamot" maps to both Citrus and Floral). The minimum cluster count is 1; there is no maximum, but typical profiles have 2-5 clusters.

---

## 4. Edge Cases

### 4.1 Artistic / Poetic Descriptions

Roasters often use poetic language: "A symphony of summer fruits dancing on your palate" or "Sunshine in a cup."

**Handling:**

1. The LLM extracts what it can (flavor notes: "summer fruits" -> Berry, Tropical).
2. Fields not explicitly stated are set to null/"unknown".
3. Confidence is computed normally (will typically be MEDIUM or LOW).
4. User is offered manual entry for missing fields.

### 4.2 Minimal Descriptions

Some bags say only "Colombian coffee" or "House Blend Dark Roast."

**Handling:**

1. Extract what is present: `origin_country="Colombia"`, `roast_level="dark"`.
2. Remaining fields default to null/"unknown".
3. Confidence will be LOW-MEDIUM.
4. The system still proceeds -- origin + roast is enough for basic recipe matching.

### 4.3 Conflicting Information

Text says "light roast" but the flavor notes (dark chocolate, tobacco, leather) strongly suggest dark.

**Handling:**

1. Trust the explicit statement over inference. `roast_level="light"`.
2. The flavor clusters will capture Chocolate and Roasted.
3. The downstream recipe retrieval and optimization will reconcile via the full feature vector, not roast level alone.

### 4.4 Non-English Text

**Handling (v1):**

1. Attempt extraction as-is.
2. If confidence is LOW and language detection suggests non-English, return error with message: "Bean descriptions must be in English for this version."
3. Log for future multilingual support.

### 4.5 Missing Origin

If no origin country can be identified ("our special house blend"):

1. Set `origin_country="unknown"`.
2. This drops the origin-country weight from confidence, likely resulting in MEDIUM confidence.
3. Recipe retrieval falls back to matching on roast level, process, and flavor clusters only.

---

## 5. Fallback: Manual Entry

When LLM extraction fails or confidence is LOW, the system presents a manual entry form.

### Manual Entry Form Fields

| Field          | Input Type         | Required | Options/Constraints                                    |
| -------------- | ------------------ | -------- | ------------------------------------------------------ |
| Origin country | Dropdown           | YES      | Known countries list + "Other"                         |
| Region         | Text input         | NO       | Free text                                              |
| Process        | Radio buttons      | YES      | washed, natural, honey, anaerobic, wet-hulled, unknown |
| Roast level    | Slider with labels | YES      | light through dark + unknown                           |
| Flavor notes   | Multi-select tags  | NO       | 15-cluster names + common descriptors                  |
| Variety        | Text input         | NO       | Free text                                              |
| Altitude       | Number input       | NO       | 0-3000 meters                                          |

Manual entry bypasses the LLM entirely. The resulting `BeanProfile` has `extraction_confidence=null` to distinguish it from LLM-extracted profiles.

---

## 6. Output Contract

The extraction function returns:

```python
@dataclass
class ExtractionResult:
    bean_profile: BeanProfile     # Structured profile
    confidence: float             # 0.0 - 1.0
    confidence_tier: str          # "HIGH", "MEDIUM", "LOW"
    missing_fields: list[str]     # Fields that could not be extracted
    used_manual_entry: bool       # True if user filled the manual form
```

### Guarantees

1. `bean_profile.origin_country` is always set (may be "unknown").
2. `bean_profile.flavor_clusters` is always a non-empty list (defaults to ["Balanced"] if nothing extracted).
3. `bean_profile.source_text` is always the original input text.
4. `bean_profile.process` and `bean_profile.roast_level` are always valid enum values (may be "unknown").
5. `confidence` is always in [0.0, 1.0].
6. `missing_fields` lists every field that was set to null or "unknown".

---

## 7. Performance Requirements

| Metric                                  | Target                                |
| --------------------------------------- | ------------------------------------- |
| Extraction latency (LLM call)           | < 3 seconds                           |
| End-to-end including validation         | < 5 seconds                           |
| Field accuracy (origin, roast, process) | > 90% on typical roaster descriptions |
| Flavor cluster recall                   | > 80% of human-assigned clusters      |
| False positive rate (spurious clusters) | < 15%                                 |

---

## 8. Dependencies

| Dependency                 | Purpose                                                        | Version              |
| -------------------------- | -------------------------------------------------------------- | -------------------- |
| LLM API                    | Structured extraction                                          | Configured in `.env` |
| `data-models.md` Section 2 | `BeanProfile` schema definition                                | Canonical            |
| `coffee-science.md`        | Roast-process-parameter constraints for validation cross-check | Reference            |

---

## 9. Error Handling Summary

| Error                    | Response                               | User-Facing Message                                                                       |
| ------------------------ | -------------------------------------- | ----------------------------------------------------------------------------------------- |
| Source text < 5 chars    | Validation error                       | "Please enter a longer description from the coffee bag label."                            |
| LLM API timeout          | Retry once, then manual entry fallback | "Could not analyze the description. Please enter the details manually."                   |
| LLM returns invalid JSON | Retry once, then manual entry fallback | Same as above                                                                             |
| All fields "unknown"     | Offer manual entry                     | "Could not extract bean details. Please enter them manually."                             |
| Confidence < 0.4         | Offer manual entry                     | "The description was too vague to extract reliable details. Please fill in what you can." |

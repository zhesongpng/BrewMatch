# Recipe Retrieval Specification (RAG Pipeline)

## 1. Overview

The recipe retrieval pipeline finds the best-matching recipes from a curated knowledge base given a user's bean profile and brew preferences. This is the RAG (Retrieval-Augmented Generation) component of the ML pipeline, demonstrating dense vector retrieval combined with sparse (BM25) matching and reranking.

---

## 2. Knowledge Base

### 2.1 Recipe Sources

Recipes are curated from publicly available specialty coffee sources. Each recipe is stored as a JSON file in `data/recipes/` conforming to the `Recipe` schema in `specs/data-models.md` Section 1.

| Source                    | Expected Recipes | Characteristics                    |
| ------------------------- | ---------------- | ---------------------------------- |
| James Hoffmann V60 method | 3-5              | Multi-pour, detailed timing        |
| Tetsu Kasuya 4:6 method   | 3-5              | 5-pour structured, ratio-focused   |
| Scott Rao standard        | 2-3              | High extraction, agitation-focused |
| Barista Hustle            | 5-10             | Experimentally validated           |
| Onyx Coffee Lab           | 3-5              | Modern, high-TDS                   |
| Lance Hedrick methods     | 5-10             | Modern techniques, agitation       |
| Kalita Wave adaptations   | 5-8              | Flat-bottom specific recipes       |
| Origami dripper recipes   | 3-5              | Hybrid flat/wave recipes           |
| Generated variations      | 15-25            | Parameter-space coverage           |
| **Total target**          | **50-80**        | Focused coverage for v1            |

### 2.2 Ingestion Curation Filter

Before indexing, every recipe (regardless of source) must pass a curation gate:

1. **Method filter**: `recipe.method` must be one of `"V60"`, `"Kalita Wave"`, `"Origami"`. Recipes for AeroPress, Chemex, French press, espresso, or any other method are rejected.
2. **Parameter validation**: All parameters must fall within the ranges defined in `specs/data-models.md` Section 1. Out-of-range recipes are rejected, not clipped.
3. **Source normalization**: Recipes from community sources (Reddit, forums) must be manually reviewed to confirm pour-over method before inclusion. Generated variations inherit the source recipe's method.

Recipes failing any gate are logged to `data/recipes/rejected/` with the failure reason and excluded from the knowledge base.

### 2.3 Recipe Indexing

Each recipe (post-curation) is indexed on ingestion:

1. **Embedding generation**: Convert recipe metadata + instructions into a dense vector.
2. **BM25 tokenization**: Tokenize recipe fields for sparse retrieval.
3. **Metadata indexing**: Store structured fields for filtering.

---

## 3. Embedding Strategy

### 3.1 Embedding Model

| Parameter     | Value              | Rationale                                                 |
| ------------- | ------------------ | --------------------------------------------------------- |
| Model         | `all-MiniLM-L6-v2` | Good quality-speed tradeoff, 384 dimensions, runs locally |
| Dimensions    | 384                | Compact, sufficient for recipe similarity                 |
| Batch size    | 32                 | Balance throughput and memory                             |
| Normalization | L2-normalized      | Required for cosine similarity via dot product            |

### 3.2 Embedding Construction

Each recipe is embedded from a composite text representation:

```
"{method} {roast_level_suitability} {process_suitability} {origin_suitability}
{flavor_cluster_suitability} grind:{grind_setting} temp:{water_temp_c}C
ratio:1:{ratio} time:{total_time_s}s
{instructions}"
```

**Example:**

```
"V60 light natural Ethiopia Berry Floral grind:5 temp:93C ratio:1:16.5
time:210s Place filter, rinse with hot water. Add 15g coffee, bloom with
30g water at 0:00. Pour to 100g at 0:30. Pour to 250g at 1:15."
```

**Design decisions:**

- Numeric parameters are included as text tokens so the embedding captures parameter similarity.
- `suitable_for` fields provide the bean-matching signal.
- Instructions text captures brewing style.
- Roast level, process, and origin are included as explicit tokens to enable semantic matching.

### 3.3 Query Embedding

The query embedding is constructed from the user's bean profile:

```
"{origin_country} {origin_region} {process} {roast_level}
{flavor_clusters_joined} V60"
```

**Example:** `"Ethiopia Yirgacheffe washed light Berry Floral V60"`

---

## 4. Storage

### 4.1 ChromaDB Configuration

| Parameter         | Value                                                                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend           | ChromaDB (embedded, local)                                                                                                                   |
| Collection name   | `brewmatch_recipes`                                                                                                                          |
| Distance function | Cosine similarity                                                                                                                            |
| Persist directory | `data/chroma/`                                                                                                                               |
| Metadata fields   | `recipe_id`, `method`, `grind_setting`, `water_temp_c`, `ratio`, `total_time_s`, `roast_levels` (JSON), `processes` (JSON), `origins` (JSON) |

### 4.2 Indexing Protocol

On each recipe ingestion:

1. Validate recipe against schema (`specs/data-models.md` Section 1).
2. Construct composite text for embedding.
3. Generate embedding via `all-MiniLM-L6-v2`.
4. Upsert into ChromaDB with id=`recipe_id`, embedding, document text, and metadata.
5. Tokenize for BM25 (lowercase, remove stopwords, stem).

---

## 5. Retrieval Pipeline

### 5.1 Stage 1: Hybrid Retrieval

Combine dense vector search and sparse BM25 retrieval.

**Dense retrieval (ChromaDB):**

```python
# Pseudocode
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=20,
    include=["documents", "metadatas", "distances"]
)
```

**Sparse retrieval (BM25):**

Tokenize the query using the same tokenizer as indexing. Score all recipes using BM25. Return top 20.

**Hybrid fusion (Reciprocal Rank Fusion):**

| Parameter            | Value | Rationale                                              |
| -------------------- | ----- | ------------------------------------------------------ |
| Dense weight         | 0.6   | Primary signal is semantic similarity                  |
| Sparse weight        | 0.4   | Keyword matching catches exact process/origin mentions |
| RRF k                | 60    | Standard reciprocal rank fusion constant               |
| Candidates from each | 20    | Sufficient pool for reranking                          |

**RRF score formula:**

```
rrf_score(recipe) = dense_weight / (k + dense_rank(recipe))
                  + sparse_weight / (k + sparse_rank(recipe))
```

### 5.2 Stage 2: Hard Filtering

Remove candidates that violate hard constraints before reranking.

| Constraint          | Rule                                                   | Source                                 |
| ------------------- | ------------------------------------------------------ | -------------------------------------- |
| Method match        | `recipe.method in {user_selected_drippers}`            | User onboarding selection              |
| Roast compatibility | `bean.roast_level in recipe.suitable_for.roast_levels` | Bean profile                           |
| Parameter range     | Recipe parameters within valid ranges                  | `data-models.md` Section 1 constraints |

Recipes that fail any hard constraint are removed from the candidate set. If fewer than 3 candidates remain after filtering, relax the roast compatibility constraint and retry.

### 5.3 Stage 3: Reranking

Score each remaining candidate on multiple signals and combine into a final ranking score.

| Signal                   | Weight | Computation                                                                                   |
| ------------------------ | ------ | --------------------------------------------------------------------------------------------- |
| Semantic similarity      | 0.35   | Cosine similarity between query embedding and recipe embedding                                |
| Bean-profile match       | 0.25   | Overlap between bean's flavor clusters and recipe's `suitable_for.flavor_profiles`            |
| Process match            | 0.15   | Binary: bean process in recipe `suitable_for.processes`                                       |
| Origin match             | 0.10   | Binary: bean origin in recipe `suitable_for.origins`                                          |
| Parameter constraint fit | 0.15   | How well recipe parameters align with roast-temperature constraints (see `coffee-science.md`) |

**Bean-profile overlap score:**

```python
def cluster_overlap(bean_clusters, recipe_clusters):
    if not recipe_clusters:
        return 0.5  # neutral when recipe has no cluster preference
    overlap = len(set(bean_clusters) & set(recipe_clusters))
    return overlap / max(len(bean_clusters), 1)
```

**Parameter constraint fit score:**

Higher score when recipe parameters respect coffee science constraints:

- Light roast -> temperature >= 92C (higher extraction needed)
- Dark roast -> temperature <= 94C (avoid over-extraction/bitterness)
- Fine grind -> shorter total time (faster extraction)
- Coarse grind -> longer total time (slower extraction)

See `coffee-science.md` for the full constraint model.

### 5.4 Stage 4: Diversity Selection

From the reranked top candidates, select the final 3 recommendations with diversity.

| Rule                                                          | Purpose                                                                                  |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Top candidate is always included                              | Best match is always shown                                                               |
| Remaining candidates selected to maximize parameter diversity | Avoid showing 3 nearly-identical recipes                                                 |
| Minimum parameter distance                                    | Second and third recipes must differ from first by >= 2 parameters                       |
| Maximum parameter distance                                    | No recipe should be more than 2 standard deviations from the query's expected parameters |

**Diversity score for candidate c given already-selected set S:**

```
diversity(c, S) = min over s in S of euclidean_distance(normalized_params(c), normalized_params(s))
```

Select the candidate with the highest `alpha * relevance_score + (1 - alpha) * diversity_score` where `alpha = 0.7`.

---

## 6. Output Contract

```python
@dataclass
class RetrievalResult:
    recipes: list[RankedRecipe]  # Top 3 recommendations
    total_candidates: int         # Candidates after filtering
    query_embedding: list[float]  # For caching/debugging

@dataclass
class RankedRecipe:
    recipe: Recipe                # Full recipe object
    relevance_score: float        # Combined reranking score [0, 1]
    match_reasons: list[str]      # Human-readable explanation of why this matched
    parameter_diversity: float    # Distance from other selected recipes
```

### Guarantees

1. Always returns 1-3 recipes, up to 3 when available.
2. `relevance_score` is in [0, 1] for every recipe.
3. `match_reasons` contains at least one human-readable string per recipe.
4. Recipes are ordered by `relevance_score` descending.

### Fallback Tiers for Fewer Than 3 Results

If fewer than 3 recipes match after all constraint relaxation stages:

1. **Broad matches**: Fill remaining slots with the highest-relevance recipes for the same brew method, labeled as "broad match" in `match_reasons`.
2. **General recommendations**: If zero recipes exist for the requested method, return the 3 highest-relevance recipes across all methods, labeled as "general recommendation."
3. **Single result**: If only 1 recipe matches, return it alone. Do not duplicate it to fill 3 slots.

---

## 7. Precision Target

| Metric                     | Target | Measurement                                               |
| -------------------------- | ------ | --------------------------------------------------------- |
| Precision@3                | > 0.8  | At least 2.4 of 3 recommendations are relevant on average |
| Recall@10                  | > 0.6  | Most good matches appear in top 10                        |
| MRR (Mean Reciprocal Rank) | > 0.7  | Best match typically in position 1-2                      |
| Diversity score            | > 0.3  | Recommendations meaningfully different from each other    |

**"Relevant" definition**: A recipe is relevant if a coffee expert would rate it as a reasonable starting point for the given bean profile. Evaluated against a held-out set of 50 bean-recipe pairings judged by 3 expert annotators.

---

## 8. Caching Strategy

| Cache Level         | Key                                 | TTL       | Invalidation             |
| ------------------- | ----------------------------------- | --------- | ------------------------ |
| Embedding cache     | Hash of composite text              | Permanent | On recipe update         |
| Query result cache  | Hash of bean profile canonical form | Session   | On new recipe ingestion  |
| ChromaDB collection | N/A (persistent)                    | N/A       | Explicit rebuild command |

---

## 9. Edge Cases

| Case                                                         | Handling                                                                          |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Bean with "unknown" roast/process                            | Skip roast/process filtering; rely on flavor clusters and semantic similarity     |
| No recipes match hard constraints                            | Relax constraints progressively: roast -> origin -> process; log relaxation event |
| Very common bean (e.g., "Ethiopia Yirgacheffe washed light") | Return 3 diverse recipes; rely on diversity selection to avoid redundancy         |
| Very rare bean (e.g., "Myanmar natural medium")              | Fall back to process + roast matching; origin match is bonus                      |
| User's bean profile has no flavor clusters                   | Use "Balanced" as default; rely on roast + process for matching                   |
| Empty knowledge base                                         | Return error: "No recipes available. Please seed the knowledge base."             |

---

## 10. Dependencies

| Dependency                          | Purpose                                      |
| ----------------------------------- | -------------------------------------------- |
| `specs/data-models.md` Sections 1-2 | Recipe and BeanProfile schemas               |
| `specs/coffee-science.md`           | Roast-temperature and grind-time constraints |
| `specs/synthetic-data.md`           | Generated recipe variations                  |
| `all-MiniLM-L6-v2`                  | Sentence embedding model                     |
| `ChromaDB`                          | Vector storage and retrieval                 |
| `rank_bm25`                         | BM25 sparse retrieval                        |

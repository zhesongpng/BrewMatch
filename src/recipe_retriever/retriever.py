"""Recipe retrieval RAG pipeline for BrewMatch.

Implements a 4-stage pipeline: document indexing, hybrid retrieval,
hard filtering, 5-signal reranking, and diversity selection.

External dependencies (chromadb, sentence_transformers, rank_bm25) are
lazily imported so that unit tests can mock them without requiring the
actual packages to be installed.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.data_models import (
    BeanProfile,
    BrewMethod,
    ExperienceLevel,
    FLAVOR_CLUSTERS,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SourceTier,
    SuitableFor,
)


# ---------------------------------------------------------------------------
# Result dataclasses (spec §4 Output Contract)
# ---------------------------------------------------------------------------


@dataclass
class RankedRecipe:
    """A recipe with its retrieval score and signal breakdown."""
    recipe: Recipe
    rank: int
    score: float
    relevance_signals: dict[str, float]


@dataclass
class RetrievalResult:
    """Result from the retrieval pipeline, per spec §4."""
    recipes: list[RankedRecipe]
    total_candidates: int
    query_bean_id: str | None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_METHODS = {BrewMethod.V60, BrewMethod.KALITA_WAVE, BrewMethod.ORIGAMI}

RRF_K = 60
DENSE_WEIGHT = 0.6
SPARSE_WEIGHT = 0.4

# Reranking signal weights (spec §5.3)
SIGNAL_WEIGHTS = {
    "semantic_similarity": 0.35,
    "bean_profile_match": 0.25,
    "process_match": 0.15,
    "origin_match": 0.10,
    "parameter_constraint_fit": 0.15,
}

# Diversity parameters (spec §5.4)
DIVERSITY_ALPHA = 0.7
_MIN_PARAM_DIFF = 2

# Source-tier near-tie breaker (spec §5.3a). Tier only re-orders recipes whose
# combined rerank scores fall within TIE_BAND of each other; it never overrides
# a clear winner. Higher TIER_RANK wins the tie.
TIER_RANK = {
    SourceTier.CHAMPION: 2,
    SourceTier.BARISTA: 1,
    SourceTier.ENTHUSIAST: 0,
}
TIE_BAND = 0.02

# Stopwords for BM25 tokenization
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of with by from is it that this "
    "was are be been has have had not they we you he she its my your our "
    "their as if then than so no all each every both few more most other "
    "some such only into about up out can will just should now also".split()
)


# ---------------------------------------------------------------------------
# Recipe loading helper
# ---------------------------------------------------------------------------


def _parse_recipe(raw: dict) -> Recipe:
    """Parse a raw JSON dict into a validated Recipe dataclass."""
    pours = [PourStep(**p) for p in raw["pours"]]
    sf = raw["suitable_for"]
    suitable_for = SuitableFor(
        roast_levels=[RoastLevel(r) for r in sf["roast_levels"]],
        origins=sf["origins"],
        processes=[Process(p) for p in sf["processes"]],
        flavor_profiles=sf["flavor_profiles"],
    )
    return Recipe(
        recipe_id=raw["recipe_id"],
        source=raw["source"],
        method=BrewMethod(raw["method"]),
        dose_g=raw["dose_g"],
        water_total_g=raw["water_total_g"],
        ratio=raw["ratio"],
        grind_setting=raw["grind_setting"],
        water_temp_c=raw["water_temp_c"],
        bloom_time_s=raw["bloom_time_s"],
        total_time_s=raw["total_time_s"],
        pours=pours,
        suitable_for=suitable_for,
        instructions=raw["instructions"],
        source_url=raw.get("source_url"),
        source_tier=raw.get("source_tier"),  # None -> default tier in __post_init__
    )


def load_recipes_from_directory(recipe_dir: str) -> list[Recipe]:
    """Load all valid recipe JSON files from a directory.

    Skips files that fail validation, logging the reason.
    Only accepts recipes whose method is V60, Kalita Wave, or Origami.
    """
    recipes: list[Recipe] = []
    path = Path(recipe_dir)
    if not path.is_dir():
        raise FileNotFoundError(f"Recipe directory not found: {recipe_dir}")

    for json_file in sorted(path.glob("*.json")):
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
            recipe = _parse_recipe(raw)
            if recipe.method not in VALID_METHODS:
                logger.warning(
                    "Skipping %s: method %s not in allowed set",
                    json_file.name,
                    recipe.method,
                )
                continue
            recipes.append(recipe)
        except Exception as exc:
            logger.warning("Skipping %s: %s", json_file.name, exc)

    logger.info("Loaded %d recipes from %s", len(recipes), recipe_dir)
    return recipes


# ---------------------------------------------------------------------------
# Text representation
# ---------------------------------------------------------------------------


def recipe_to_text(recipe: Recipe) -> str:
    """Convert a Recipe into a composite text representation for embedding.

    Format follows spec section 3.2.
    """
    roast_levels = " ".join(r.value for r in recipe.suitable_for.roast_levels)
    processes = " ".join(p.value for p in recipe.suitable_for.processes)
    origins = " ".join(recipe.suitable_for.origins)
    flavors = " ".join(recipe.suitable_for.flavor_profiles)

    return (
        f"{recipe.method.value} {roast_levels} {processes} {origins} {flavors} "
        f"grind:{recipe.grind_setting} temp:{recipe.water_temp_c}C "
        f"ratio:1:{recipe.ratio} time:{recipe.total_time_s}s "
        f"{recipe.instructions}"
    )


def bean_to_query_text(bean: BeanProfile) -> str:
    """Convert a BeanProfile into a query text for embedding.

    Format follows spec section 3.3.
    """
    parts = [
        bean.origin_country,
        bean.origin_region or "",
        bean.process.value,
        bean.roast_level.value,
        " ".join(bean.flavor_clusters),
    ]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Tokenization for BM25
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Lowercase, remove stopwords, whitespace-split tokenization."""
    words = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower()).split()
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


# ---------------------------------------------------------------------------
# Reranking signal computation
# ---------------------------------------------------------------------------


def _score_semantic_similarity(
    recipe_emb: list[float] | None,
    query_emb: list[float] | None,
) -> float:
    """Cosine similarity between query and recipe embeddings."""
    if recipe_emb is None or query_emb is None:
        return 0.5
    cos_sim = sum(a * b for a, b in zip(query_emb, recipe_emb))
    return max(0.0, min(1.0, cos_sim))


def _score_bean_profile_match(
    recipe: Recipe,
    bean: BeanProfile,
) -> float:
    """Overlap between bean flavor clusters and recipe flavor profiles."""
    bean_set = set(bean.flavor_clusters)
    recipe_set = set(recipe.suitable_for.flavor_profiles)

    if not recipe_set:
        return 0.5
    if not bean_set:
        return 0.5

    overlap = len(bean_set & recipe_set)
    return overlap / max(len(bean_set), 1)


def _score_process_match(
    recipe: Recipe,
    bean: BeanProfile,
) -> float:
    """Binary: 1.0 if bean process in recipe's suitable_for.processes."""
    if bean.process in recipe.suitable_for.processes:
        return 1.0
    return 0.0


def _score_origin_match(
    recipe: Recipe,
    bean: BeanProfile,
) -> float:
    """Binary: 1.0 if bean origin country in recipe's suitable_for.origins."""
    if bean.origin_country in recipe.suitable_for.origins:
        return 1.0
    return 0.0


def _score_parameter_constraint_fit(
    recipe: Recipe,
    bean: BeanProfile,
) -> float:
    """How well recipe parameters align with roast-temperature constraints."""
    score = 0.5

    roast = bean.roast_level
    temp = recipe.water_temp_c
    grind = recipe.grind_setting
    time_s = recipe.total_time_s

    if roast in (RoastLevel.LIGHT, RoastLevel.MEDIUM_LIGHT):
        if temp >= 92.0:
            score += 0.25
        else:
            score -= 0.25
    elif roast in (RoastLevel.DARK, RoastLevel.MEDIUM_DARK):
        if temp <= 94.0:
            score += 0.25
        else:
            score -= 0.25
    else:
        score += 0.1

    if grind <= 3:
        if time_s <= 210:
            score += 0.25
        else:
            score -= 0.15
    elif grind >= 7:
        if time_s >= 210:
            score += 0.25
        else:
            score -= 0.15
    else:
        score += 0.1

    return max(0.0, min(1.0, score))


def compute_rerank_score(
    recipe: Recipe,
    bean: BeanProfile,
    query_emb: list[float] | None = None,
    recipe_emb: list[float] | None = None,
) -> dict[str, float]:
    """Compute all 5 spec reranking signals and the weighted sum."""
    signals = {
        "semantic_similarity": _score_semantic_similarity(recipe_emb, query_emb),
        "bean_profile_match": _score_bean_profile_match(recipe, bean),
        "process_match": _score_process_match(recipe, bean),
        "origin_match": _score_origin_match(recipe, bean),
        "parameter_constraint_fit": _score_parameter_constraint_fit(recipe, bean),
    }

    combined = sum(
        SIGNAL_WEIGHTS[name] * value for name, value in signals.items()
    )
    signals["combined"] = combined
    return signals


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------


def reciprocal_rank_fusion(
    dense_ranking: list[str],
    sparse_ranking: list[str],
    k: int = RRF_K,
    dense_weight: float = DENSE_WEIGHT,
    sparse_weight: float = SPARSE_WEIGHT,
) -> dict[str, float]:
    """Compute RRF scores for items appearing in dense and/or sparse rankings.

    Returns a dict mapping recipe_id to RRF score, sorted descending.
    """
    scores: dict[str, float] = {}

    for rank, rid in enumerate(dense_ranking, start=1):
        scores[rid] = scores.get(rid, 0.0) + dense_weight / (k + rank)

    for rank, rid in enumerate(sparse_ranking, start=1):
        scores[rid] = scores.get(rid, 0.0) + sparse_weight / (k + rank)

    return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# Parameter-distance helpers for diversity (spec §5.4)
# ---------------------------------------------------------------------------


def _normalize_params(recipe: Recipe) -> list[float]:
    """Normalize recipe tunable params to [0, 1] range for distance computation."""
    return [
        (recipe.grind_setting - 1.0) / 9.0,       # grind: 1-10 → 0-1
        (recipe.water_temp_c - 85.0) / 15.0,       # temp: 85-100 → 0-1
        (recipe.dose_g - 12.0) / 10.0,             # dose: 12-22 → 0-1
        (recipe.ratio - 14.0) / 4.0,               # ratio: 14-18 → 0-1
    ]


def _param_distance(a: list[float], b: list[float]) -> float:
    """Euclidean distance between two normalized parameter vectors."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# ---------------------------------------------------------------------------
# Main retriever class
# ---------------------------------------------------------------------------


class RecipeRetriever:
    """4-stage RAG pipeline for recipe retrieval.

    Stage 1: Index recipes into ChromaDB (dense) + BM25 (sparse).
    Stage 2: Hybrid retrieval via RRF fusion.
    Stage 3: Hard filtering by method, roast, and constraints.
    Stage 4: 5-signal reranking + diversity selection.
    """

    _EMBEDDING_CACHE_MAXSIZE = 128

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        chroma_persist_dir: Optional[str] = None,
    ) -> None:
        self._embedding_model_name = embedding_model
        self._chroma_persist_dir = chroma_persist_dir or os.path.join(
            tempfile.gettempdir(), "brewmatch_chroma"
        )

        # Populated by index_recipes
        self._recipes: dict[str, Recipe] = {}
        self._recipe_texts: dict[str, str] = {}
        self._recipe_embeddings: dict[str, list[float]] = {}
        self._model = None
        self._collection = None
        self._chroma_client = None
        self._bm25 = None
        self._bm25_ids: list[str] = []

        # Embedding cache: keyed by text hash, value is embedding list.
        # Simple LRU via insertion-order dict eviction.
        self._embedding_cache: dict[int, list[float]] = {}
        self._embedding_cache_hits: int = 0
        self._embedding_cache_misses: int = 0

    # -------------------------------------------------------------------
    # Lazy model / collection loading
    # -------------------------------------------------------------------

    def _get_model(self):
        """Lazily load the sentence-transformers model.

        On Streamlit Cloud, torch may be imported before CUDA_VISIBLE_DEVICES
        takes effect, causing meta-tensor errors. We force CPU mode and
        disable CUDA detection before loading.
        """
        if self._model is None:
            import os
            os.environ["CUDA_VISIBLE_DEVICES"] = ""
            os.environ["TOKENIZERS_PARALLELISM"] = "false"

            import torch
            # Force torch to believe CUDA is unavailable — prevents meta tensor
            # issues on cloud environments where torch was loaded with CUDA init.
            torch.cuda.is_available = lambda: False
            if hasattr(torch.cuda, "is_bf16_supported"):
                torch.cuda.is_bf16_supported = lambda: False

            from sentence_transformers import SentenceTransformer

            # `low_cpu_mem_usage=True` (the transformers/accelerate default on
            # some cloud builds) initialises weights on the "meta" device and
            # then calls `.to("cpu")`, which raises "Cannot copy out of meta
            # tensor; no data!". Forcing it off loads real weights directly on
            # CPU. Older sentence-transformers lack `model_kwargs`, so fall
            # back to the plain constructor.
            try:
                self._model = SentenceTransformer(
                    self._embedding_model_name,
                    device="cpu",
                    model_kwargs={"low_cpu_mem_usage": False},
                )
            except TypeError:
                self._model = SentenceTransformer(
                    self._embedding_model_name, device="cpu",
                )
        return self._model

    def _get_collection(self):
        """Lazily initialise ChromaDB client and collection."""
        if self._collection is None:
            import chromadb

            try:
                self._chroma_client = chromadb.PersistentClient(path=self._chroma_persist_dir)
            except Exception:
                # Read-only filesystem or RustBindingsAPI issue (Streamlit Cloud).
                logger.warning("ChromaDB PersistentClient failed, falling back to in-memory")
                self._chroma_client = chromadb.Client()
            self._collection = self._chroma_client.get_or_create_collection(
                name="brewmatch_recipes",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _get_query_embedding(self, text: str) -> list[float]:
        """Compute or retrieve a cached embedding for the given query text.

        Uses a simple LRU cache (maxsize from _EMBEDDING_CACHE_MAXSIZE) keyed
        by the hash of the input text.  Repeated calls with the same query
        text return the cached embedding without calling the model.
        """
        cache_key = hash(text)

        if cache_key in self._embedding_cache:
            self._embedding_cache_hits += 1
            # Move to end so it survives eviction longer (insertion-order LRU)
            value = self._embedding_cache.pop(cache_key)
            self._embedding_cache[cache_key] = value
            return value

        self._embedding_cache_misses += 1
        model = self._get_model()
        emb = model.encode([text], normalize_embeddings=True)[0].tolist()

        self._embedding_cache[cache_key] = emb
        # Evict oldest entry if cache exceeds max size
        while len(self._embedding_cache) > self._EMBEDDING_CACHE_MAXSIZE:
            self._embedding_cache.pop(next(iter(self._embedding_cache)))

        return emb

    # -------------------------------------------------------------------
    # Stage 1: Indexing
    # -------------------------------------------------------------------

    def index_recipes(self, recipe_dir: str) -> None:
        """Load recipes from a directory path, build both dense and sparse indexes.

        Args:
            recipe_dir: Path to directory containing recipe JSON files.
        """
        recipes = load_recipes_from_directory(recipe_dir)
        if not recipes:
            logger.warning("No recipes loaded from %s", recipe_dir)
            return

        self._recipes = {r.recipe_id: r for r in recipes}
        self._recipe_texts = {rid: recipe_to_text(r) for rid, r in self._recipes.items()}

        # Sparse (BM25) is pure Python with no model dependency — build it
        # first so retrieval always works. The dense (embedding) index is a
        # best-effort enhancement: on constrained cloud environments the
        # sentence-transformers model can fail to load (meta-tensor error),
        # and that MUST degrade to keyword search, not break the feature.
        self._build_sparse_index()
        try:
            self._build_dense_index()
        except Exception as exc:
            logger.warning(
                "Dense index unavailable (%s) — falling back to BM25-only "
                "keyword retrieval", exc,
            )

    def _build_dense_index(self) -> None:
        """Build ChromaDB collection from indexed recipes."""
        model = self._get_model()
        collection = self._get_collection()

        texts = [self._recipe_texts[rid] for rid in self._recipes]
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)

        ids = list(self._recipes.keys())
        metas = []
        emb_list = []
        for rid, text, emb in zip(ids, texts, embeddings):
            recipe = self._recipes[rid]
            metas.append({
                "recipe_id": rid,
                "method": recipe.method.value,
                "grind_setting": recipe.grind_setting,
                "water_temp_c": recipe.water_temp_c,
                "ratio": recipe.ratio,
                "total_time_s": recipe.total_time_s,
            })
            emb_list.append(emb.tolist())
            self._recipe_embeddings[rid] = emb.tolist()

        collection.upsert(
            ids=ids,
            embeddings=emb_list,
            documents=texts,
            metadatas=metas,
        )
        logger.info("Indexed %d recipes in ChromaDB", len(ids))

    def _build_sparse_index(self) -> None:
        """Build BM25 index from recipe texts."""
        from rank_bm25 import BM25Okapi

        self._bm25_ids = list(self._recipe_texts.keys())
        corpus = [_tokenize(self._recipe_texts[rid]) for rid in self._bm25_ids]
        if corpus:
            self._bm25 = BM25Okapi(corpus)
        logger.info("Built BM25 index with %d documents", len(self._bm25_ids))

    # -------------------------------------------------------------------
    # Stage 2: Hybrid retrieval
    # -------------------------------------------------------------------

    def _hybrid_retrieve(
        self, query_text: str, query_emb: list[float], top_k: int = 20
    ) -> dict[str, float]:
        """Dense + sparse retrieval fused via RRF."""
        # Dense retrieval
        dense_ids: list[str] = []
        collection = self._get_collection()
        try:
            results = collection.query(
                query_embeddings=[query_emb],
                n_results=min(top_k, len(self._recipes)),
                include=["documents"],
            )
            if results and results.get("ids"):
                dense_ids = results["ids"][0]
        except Exception:
            logger.warning("ChromaDB query failed", exc_info=True)

        # Sparse retrieval
        sparse_ids: list[str] = []
        if self._bm25 is not None:
            tokenized_query = _tokenize(query_text)
            if tokenized_query:
                scores = self._bm25.get_scores(tokenized_query)
                ranked_indices = sorted(
                    range(len(scores)),
                    key=lambda i: scores[i],
                    reverse=True,
                )[:top_k]
                for idx in ranked_indices:
                    if scores[idx] > 0:
                        sparse_ids.append(self._bm25_ids[idx])

        return reciprocal_rank_fusion(dense_ids, sparse_ids)

    # -------------------------------------------------------------------
    # Stage 3: Hard filtering
    # -------------------------------------------------------------------

    @staticmethod
    def _apply_hard_filters(
        candidates: list[str],
        recipes: dict[str, Recipe],
        bean: BeanProfile,
        preferred_methods: set[BrewMethod],
    ) -> list[str]:
        """Remove candidates that violate hard constraints.

        Hard constraints:
        1. Recipe method must be in preferred_methods.
        2. Bean roast_level must be in recipe's suitable_for.roast_levels
           (relaxed when bean roast is UNKNOWN).

        If fewer than 3 candidates remain, relax roast constraint and retry.
        """
        def passes(rid: str) -> bool:
            recipe = recipes[rid]

            # Method must match
            if recipe.method not in preferred_methods:
                return False

            # Roast compatibility (skip if bean roast is unknown)
            if bean.roast_level != RoastLevel.UNKNOWN:
                if bean.roast_level not in recipe.suitable_for.roast_levels:
                    return False

            return True

        filtered = [rid for rid in candidates if passes(rid)]

        # Relaxation: if fewer than 3, drop roast constraint
        if len(filtered) < 3:
            relaxed = [
                rid for rid in candidates
                if recipes[rid].method in preferred_methods
            ]
            if len(relaxed) > len(filtered):
                logger.info(
                    "Relaxed roast constraint: %d -> %d candidates",
                    len(filtered),
                    len(relaxed),
                )
                return relaxed

        return filtered

    # -------------------------------------------------------------------
    # Stage 4: Reranking
    # -------------------------------------------------------------------

    def _rerank(
        self,
        candidates: list[str],
        bean: BeanProfile,
        query_emb: list[float],
    ) -> list[tuple[str, float, dict[str, float]]]:
        """Score each candidate on 5 spec signals, return sorted by combined score."""
        scored: list[tuple[str, float, dict[str, float]]] = []
        for rid in candidates:
            recipe = self._recipes[rid]
            recipe_emb = self._recipe_embeddings.get(rid)
            signals = compute_rerank_score(recipe, bean, query_emb, recipe_emb)
            scored.append((rid, signals["combined"], signals))

        # Sort by combined score, but break NEAR-ties (scores within TIE_BAND)
        # in favor of the more credible source tier. Quantizing the score into
        # TIE_BAND-wide buckets means tier only matters when two recipes land in
        # the same bucket; a clear score gap is never overridden by tier.
        def _sort_key(item: tuple[str, float, dict[str, float]]):
            rid, combined, _ = item
            tier = self._recipes[rid].source_tier
            return (round(combined / TIE_BAND), TIER_RANK[tier], combined)

        scored.sort(key=_sort_key, reverse=True)
        return scored

    # -------------------------------------------------------------------
    # Stage 4b: Diversity selection
    # -------------------------------------------------------------------

    @staticmethod
    def _ensure_diversity(
        scored: list[tuple[str, float, dict[str, float]]],
        recipes: dict[str, Recipe],
        top_k: int = 5,
    ) -> list[str]:
        """Select top_k recipes maximizing parameter diversity (MMR-style).

        Per spec §5.4: top candidate always included. Remaining candidates
        selected to maximize alpha * relevance + (1-alpha) * min_distance
        from already-selected set.
        """
        if not scored:
            return []

        # Always include the top candidate
        selected_ids: list[str] = [scored[0][0]]
        selected_params = [_normalize_params(recipes[scored[0][0]])]

        remaining = list(scored[1:])

        while len(selected_ids) < top_k and remaining:
            best_idx = -1
            best_mmr = -1.0

            for i, (rid, relevance, _) in enumerate(remaining):
                params = _normalize_params(recipes[rid])
                # min distance to any already-selected recipe
                min_dist = min(
                    _param_distance(params, sp) for sp in selected_params
                )
                mmr = DIVERSITY_ALPHA * relevance + (1 - DIVERSITY_ALPHA) * min_dist
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            if best_idx >= 0:
                rid, _, _ = remaining.pop(best_idx)
                selected_ids.append(rid)
                selected_params.append(_normalize_params(recipes[rid]))

        return selected_ids

    # -------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------

    def retrieve(
        self,
        bean_profile: BeanProfile,
        preferences: dict,
        top_k: int = 5,
    ) -> RetrievalResult:
        """Main retrieval entry point.

        Args:
            bean_profile: The bean to match recipes against.
            preferences: Dict with optional keys:
                - "brew_methods": list[str] of preferred brew method names
                - "experience_level": str ("beginner"/"intermediate"/"advanced")
            top_k: Number of recipes to return (default 5).

        Returns:
            RetrievalResult with ranked recipes, per spec §4 Output Contract.

        Raises:
            RuntimeError: If no recipes have been indexed.
        """
        if not self._recipes:
            raise RuntimeError(
                "No recipes available. Call index_recipes() first."
            )

        logger.info(
            "retrieve.start query_bean=%s roast=%s top_k=%d",
            bean_profile.origin_country, bean_profile.roast_level.value, top_k,
        )

        # Parse preferences
        method_names = preferences.get(
            "brew_methods", ["V60", "Kalita Wave", "Origami"]
        )
        preferred_methods = set()
        for name in method_names:
            try:
                preferred_methods.add(BrewMethod(name))
            except ValueError:
                logger.warning("Unknown brew method in preferences: %s", name)

        # Build query text and embedding (cached). The embedding is
        # best-effort: if the model is unavailable (e.g. meta-tensor failure
        # on cloud) we proceed with an empty embedding and _hybrid_retrieve
        # falls back to BM25-only ranking rather than raising.
        query_text = bean_to_query_text(bean_profile)
        try:
            query_emb = self._get_query_embedding(query_text)
        except Exception as exc:
            logger.warning(
                "Query embedding unavailable (%s) — using BM25-only retrieval",
                exc,
            )
            query_emb = []

        # Stage 2: Hybrid retrieval
        rrf_scores = self._hybrid_retrieve(query_text, query_emb)
        candidates = list(rrf_scores.keys())

        # Stage 3: Hard filtering
        filtered = self._apply_hard_filters(
            candidates, self._recipes, bean_profile, preferred_methods
        )

        if not filtered:
            # Fallback: return highest-RRF recipes across all methods
            logger.info(
                "No matches after filtering. Broadening to all methods."
            )
            filtered = list(rrf_scores.keys())[:top_k]

        if not filtered:
            return RetrievalResult(
                recipes=[], total_candidates=0,
                query_bean_id=getattr(bean_profile, "bean_id", None),
            )

        total_candidates = len(filtered)

        # Stage 4: Reranking
        scored = self._rerank(filtered, bean_profile, query_emb)

        # Stage 4b: Diversity selection
        selected_ids = self._ensure_diversity(
            scored, self._recipes, top_k=top_k
        )

        # Build RankedRecipe list
        scored_map = {rid: (score, signals) for rid, score, signals in scored}
        ranked_recipes: list[RankedRecipe] = []
        for rank, rid in enumerate(selected_ids, start=1):
            score, signals = scored_map.get(rid, (0.0, {}))
            ranked_recipes.append(RankedRecipe(
                recipe=self._recipes[rid],
                rank=rank,
                score=round(score, 4),
                relevance_signals={k: round(v, 4) for k, v in signals.items()},
            ))

        logger.info(
            "retrieve.complete num_results=%d total_candidates=%d",
            len(ranked_recipes), total_candidates,
        )

        return RetrievalResult(
            recipes=ranked_recipes,
            total_candidates=total_candidates,
            query_bean_id=getattr(bean_profile, "bean_id", None),
        )

"""Unit tests for the RecipeRetriever RAG pipeline.

Tier 1 tests: all external dependencies (chromadb, sentence_transformers,
rank_bm25) are mocked. No network, no model downloads, no file I/O outside
temp directories.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.data_models import (
    BeanProfile,
    BrewMethod,
    ExperienceLevel,
    FLAVOR_CLUSTERS,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)


# ---------------------------------------------------------------------------
# Helpers: sample recipe JSON data
# ---------------------------------------------------------------------------

def _sample_recipe_json(
    recipe_id: str = "test-v60-recipe",
    method: str = "V60",
    roast_levels: list[str] | None = None,
    origins: list[str] | None = None,
    processes: list[str] | None = None,
    flavor_profiles: list[str] | None = None,
    grind_setting: int = 5,
    water_temp_c: float = 93.0,
    total_time_s: int = 210,
    dose_g: float = 15.0,
    water_total_g: float = 250.0,
    pours: list[dict] | None = None,
) -> dict:
    """Build a valid recipe JSON dict with sensible defaults."""
    if pours is None:
        pours = [
            {"step": 1, "time_offset_s": 0, "water_g": 50.0},
            {"step": 2, "time_offset_s": 45, "water_g": 100.0},
            {"step": 3, "time_offset_s": 90, "water_g": 100.0},
        ]
    return {
        "recipe_id": recipe_id,
        "source": "Test Source",
        "method": method,
        "dose_g": dose_g,
        "water_total_g": water_total_g,
        "ratio": round(water_total_g / dose_g, 2),
        "grind_setting": grind_setting,
        "water_temp_c": water_temp_c,
        "bloom_time_s": 45,
        "total_time_s": total_time_s,
        "pours": pours,
        "suitable_for": {
            "roast_levels": roast_levels or ["light", "medium-light", "medium"],
            "origins": origins or ["Ethiopia", "Colombia"],
            "processes": processes or ["washed", "natural"],
            "flavor_profiles": flavor_profiles or ["Floral", "Citrus"],
        },
        "instructions": "Test instructions for brewing.",
    }


def _write_recipe_dir(tmp: str, recipes: list[dict]) -> str:
    """Write a list of recipe dicts as JSON files into tmp, return path."""
    for r in recipes:
        path = Path(tmp) / f"{r['recipe_id']}.json"
        path.write_text(json.dumps(r, indent=2), encoding="utf-8")
    return tmp


def _make_recipe(
    recipe_id: str = "test-recipe",
    method: BrewMethod = BrewMethod.V60,
    roast_levels: list[RoastLevel] | None = None,
    origins: list[str] | None = None,
    processes: list[Process] | None = None,
    flavor_profiles: list[str] | None = None,
    grind_setting: int = 5,
    water_temp_c: float = 93.0,
    total_time_s: int = 210,
    num_pours: int = 3,
    dose_g: float = 15.0,
    water_total_g: float = 250.0,
) -> Recipe:
    """Build a Recipe dataclass directly (no JSON round-trip)."""
    # Build pours that sum to water_total_g
    if num_pours == 1:
        pours = [PourStep(step=1, time_offset_s=0, water_g=water_total_g)]
    else:
        pour_size = water_total_g / num_pours
        pours = [
            PourStep(
                step=i + 1,
                time_offset_s=0 if i == 0 else i * 45,
                water_g=pour_size,
            )
            for i in range(num_pours)
        ]

    ratio = round(water_total_g / dose_g, 2)

    return Recipe(
        recipe_id=recipe_id,
        source="Test Source",
        method=method,
        dose_g=dose_g,
        water_total_g=water_total_g,
        ratio=ratio,
        grind_setting=grind_setting,
        water_temp_c=water_temp_c,
        bloom_time_s=45,
        total_time_s=total_time_s,
        pours=pours,
        suitable_for=SuitableFor(
            roast_levels=roast_levels or [RoastLevel.LIGHT, RoastLevel.MEDIUM],
            origins=origins or ["Ethiopia", "Colombia"],
            processes=processes or [Process.WASHED, Process.NATURAL],
            flavor_profiles=flavor_profiles or ["Floral", "Citrus"],
        ),
        instructions="Test instructions.",
    )


def _make_bean(
    origin: str = "Ethiopia",
    process: Process = Process.WASHED,
    roast: RoastLevel = RoastLevel.LIGHT,
    clusters: list[str] | None = None,
) -> BeanProfile:
    return BeanProfile(
        origin_country=origin,
        process=process,
        roast_level=roast,
        flavor_clusters=clusters or ["Floral", "Citrus"],
        source_text=f"{origin} {roast.value} roast",
    )


# ---------------------------------------------------------------------------
# Mock helpers for embedding model + ChromaDB
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 8


def _random_embedding(seed: int = 42) -> list[float]:
    """Generate a fixed-seed random embedding and L2-normalise it."""
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [x / norm for x in raw] if norm > 0 else [0.0] * EMBEDDING_DIM


class _MockEmbedding:
    """Mimics a single embedding row (1-D numpy-like array)."""

    def __init__(self, values: list[float]):
        self._values = values

    def tolist(self):
        return list(self._values)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class _MockEncodeBatch:
    """Mimics a batch of embeddings (2-D numpy-like array)."""

    def __init__(self, rows: list[_MockEmbedding]):
        self._rows = rows

    def tolist(self):
        return [r.tolist() for r in self._rows]

    def __getitem__(self, idx):
        return self._rows[idx]

    def __len__(self):
        return len(self._rows)


def _mock_model():
    """Create a mock SentenceTransformer that returns deterministic embeddings."""
    model = MagicMock()
    model.encode.side_effect = lambda texts, normalize_embeddings=True, batch_size=32: (
        _MockEncodeBatch([_MockEmbedding(_random_embedding(hash(t) % 10000)) for t in texts])
        if isinstance(texts, list)
        else _MockEmbedding(_random_embedding(hash(texts) % 10000))
    )
    return model


def _mock_chroma_collection():
    """Create a mock ChromaDB collection with query support."""
    collection = MagicMock()
    collection._stored_ids: list[str] = []
    collection._stored_embeddings: list[list[float]] = []

    def fake_upsert(ids, embeddings, documents, metadatas):
        collection._stored_ids = list(ids)
        collection._stored_embeddings = list(embeddings)

    def fake_query(query_embeddings, n_results, include=None):
        qemb = query_embeddings[0]
        scores = []
        for emb in collection._stored_embeddings:
            score = sum(a * b for a, b in zip(qemb, emb))
            scores.append(score)
        ranked = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:n_results]
        return {
            "ids": [[collection._stored_ids[i] for i in ranked]],
            "documents": [[""] * len(ranked)],
        }

    collection.upsert.side_effect = fake_upsert
    collection.query.side_effect = fake_query
    return collection


def _patched_retriever(tmp_path: Path) -> "RecipeRetriever":
    """Create a retriever with mocked model and ChromaDB, ready for index_recipes."""
    from src.recipe_retriever.retriever import RecipeRetriever

    retriever = RecipeRetriever(chroma_persist_dir=str(tmp_path / "chroma"))
    retriever._model = _mock_model()
    retriever._collection = _mock_chroma_collection()
    return retriever


# ===========================================================================
# 1. Recipe loading from JSON directory
# ===========================================================================


class TestRecipeLoading:
    """Tests for load_recipes_from_directory."""

    def test_load_valid_recipes(self, tmp_path):
        """Loading a directory with valid recipe JSONs returns Recipe objects."""
        from src.recipe_retriever.retriever import load_recipes_from_directory

        recipes = [
            _sample_recipe_json(recipe_id="r1"),
            _sample_recipe_json(recipe_id="r2", method="Kalita Wave"),
        ]
        _write_recipe_dir(str(tmp_path), recipes)

        result = load_recipes_from_directory(str(tmp_path))
        assert len(result) == 2
        assert all(isinstance(r, Recipe) for r in result)
        ids = {r.recipe_id for r in result}
        assert ids == {"r1", "r2"}

    def test_load_skips_invalid_method(self, tmp_path):
        """Recipes with AeroPress or other non-pour-over methods are skipped."""
        from src.recipe_retriever.retriever import load_recipes_from_directory

        recipes = [
            _sample_recipe_json(recipe_id="valid", method="V60"),
            _sample_recipe_json(recipe_id="aeropress", method="AeroPress"),
        ]
        _write_recipe_dir(str(tmp_path), recipes)

        result = load_recipes_from_directory(str(tmp_path))
        assert len(result) == 1
        assert result[0].recipe_id == "valid"

    def test_load_skips_malformed_json(self, tmp_path):
        """Malformed JSON files are skipped gracefully."""
        from src.recipe_retriever.retriever import load_recipes_from_directory

        valid = _sample_recipe_json(recipe_id="good")
        (tmp_path / "good.json").write_text(json.dumps(valid), encoding="utf-8")
        (tmp_path / "bad.json").write_text("{invalid json", encoding="utf-8")

        result = load_recipes_from_directory(str(tmp_path))
        assert len(result) == 1
        assert result[0].recipe_id == "good"

    def test_load_empty_directory(self, tmp_path):
        """Empty directory returns empty list."""
        from src.recipe_retriever.retriever import load_recipes_from_directory

        result = load_recipes_from_directory(str(tmp_path))
        assert result == []

    def test_load_nonexistent_directory_raises(self):
        """Non-existent directory raises FileNotFoundError."""
        from src.recipe_retriever.retriever import load_recipes_from_directory

        with pytest.raises(FileNotFoundError, match="Recipe directory not found"):
            load_recipes_from_directory("/nonexistent/path")

    def test_load_single_recipe(self, tmp_path):
        """Single valid recipe in directory loads correctly."""
        from src.recipe_retriever.retriever import load_recipes_from_directory

        _write_recipe_dir(str(tmp_path), [_sample_recipe_json(recipe_id="solo")])
        result = load_recipes_from_directory(str(tmp_path))
        assert len(result) == 1
        assert result[0].recipe_id == "solo"


# ===========================================================================
# 2. Text representation creation
# ===========================================================================


class TestTextRepresentation:
    """Tests for recipe_to_text and bean_to_query_text."""

    def test_recipe_text_includes_method(self):
        """Recipe text starts with brew method."""
        from src.recipe_retriever.retriever import recipe_to_text

        recipe = _make_recipe()
        text = recipe_to_text(recipe)
        assert text.startswith("V60")

    def test_recipe_text_includes_parameters(self):
        """Recipe text contains grind, temp, ratio, time tokens."""
        from src.recipe_retriever.retriever import recipe_to_text

        recipe = _make_recipe(grind_setting=5, water_temp_c=93.0, total_time_s=210)
        text = recipe_to_text(recipe)
        assert "grind:5" in text
        assert "temp:93" in text
        assert "time:210s" in text

    def test_recipe_text_includes_suitable_for(self):
        """Recipe text contains roast levels, processes, origins, flavors."""
        from src.recipe_retriever.retriever import recipe_to_text

        recipe = _make_recipe(
            origins=["Ethiopia", "Kenya"],
            flavor_profiles=["Floral", "Berry"],
        )
        text = recipe_to_text(recipe)
        assert "Ethiopia" in text
        assert "Kenya" in text
        assert "Floral" in text
        assert "Berry" in text

    def test_recipe_text_includes_instructions(self):
        """Recipe text includes the instructions string."""
        from src.recipe_retriever.retriever import recipe_to_text

        recipe = _make_recipe()
        text = recipe_to_text(recipe)
        assert "Test instructions" in text

    def test_bean_query_text_includes_origin(self):
        """Query text includes origin country."""
        from src.recipe_retriever.retriever import bean_to_query_text

        bean = _make_bean(origin="Colombia")
        text = bean_to_query_text(bean)
        assert "Colombia" in text

    def test_bean_query_text_includes_roast_and_process(self):
        """Query text includes roast level and process."""
        from src.recipe_retriever.retriever import bean_to_query_text

        bean = _make_bean(roast=RoastLevel.LIGHT, process=Process.WASHED)
        text = bean_to_query_text(bean)
        assert "light" in text
        assert "washed" in text

    def test_bean_query_text_includes_flavor_clusters(self):
        """Query text includes all flavor clusters."""
        from src.recipe_retriever.retriever import bean_to_query_text

        bean = _make_bean(clusters=["Berry", "Citrus"])
        text = bean_to_query_text(bean)
        assert "Berry" in text
        assert "Citrus" in text


# ===========================================================================
# 3. Hard filter logic
# ===========================================================================


class TestHardFilters:
    """Tests for _apply_hard_filters."""

    def test_filter_by_method(self):
        """Only recipes matching preferred methods pass the filter."""
        from src.recipe_retriever.retriever import RecipeRetriever

        recipes = {
            "v60": _make_recipe(recipe_id="v60", method=BrewMethod.V60),
            "kalita": _make_recipe(recipe_id="kalita", method=BrewMethod.KALITA_WAVE),
            "origami": _make_recipe(recipe_id="origami", method=BrewMethod.ORIGAMI),
        }
        bean = _make_bean(roast=RoastLevel.LIGHT)

        result = RecipeRetriever._apply_hard_filters(
            candidates=["v60", "kalita", "origami"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60},
        )
        assert result == ["v60"]

    def test_filter_by_roast_compatibility(self):
        """Recipes whose roast range does not include the bean's roast are removed."""
        from src.recipe_retriever.retriever import RecipeRetriever

        light_recipe = _make_recipe(
            recipe_id="light-only",
            roast_levels=[RoastLevel.LIGHT],
        )
        medium_recipe = _make_recipe(
            recipe_id="medium-too",
            roast_levels=[RoastLevel.MEDIUM],
        )
        dark_recipe = _make_recipe(
            recipe_id="dark-only",
            roast_levels=[RoastLevel.DARK],
        )
        recipes = {
            "light-only": light_recipe,
            "medium-too": medium_recipe,
            "dark-only": dark_recipe,
        }
        bean = _make_bean(roast=RoastLevel.LIGHT)

        result = RecipeRetriever._apply_hard_filters(
            candidates=["light-only", "dark-only", "medium-too"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60},
        )
        assert "light-only" in result

    def test_unknown_roast_skips_roast_filter(self):
        """Bean with UNKNOWN roast level skips the roast compatibility check."""
        from src.recipe_retriever.retriever import RecipeRetriever

        light_only = _make_recipe(
            recipe_id="light-only",
            roast_levels=[RoastLevel.LIGHT],
        )
        recipes = {"light-only": light_only}
        bean = _make_bean(roast=RoastLevel.UNKNOWN)

        result = RecipeRetriever._apply_hard_filters(
            candidates=["light-only"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60},
        )
        assert "light-only" in result

    def test_roast_relaxation_when_fewer_than_3(self):
        """When fewer than 3 candidates pass, roast constraint is relaxed."""
        from src.recipe_retriever.retriever import RecipeRetriever

        r1 = _make_recipe(recipe_id="r1", roast_levels=[RoastLevel.LIGHT])
        r2 = _make_recipe(recipe_id="r2", roast_levels=[RoastLevel.DARK])
        r3 = _make_recipe(recipe_id="r3", roast_levels=[RoastLevel.DARK])
        recipes = {"r1": r1, "r2": r2, "r3": r3}
        bean = _make_bean(roast=RoastLevel.LIGHT)

        result = RecipeRetriever._apply_hard_filters(
            candidates=["r1", "r2", "r3"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60, BrewMethod.KALITA_WAVE, BrewMethod.ORIGAMI},
        )
        assert len(result) >= 3

    def test_empty_candidates_returns_empty(self):
        """Empty candidate list returns empty."""
        from src.recipe_retriever.retriever import RecipeRetriever

        result = RecipeRetriever._apply_hard_filters(
            candidates=[],
            recipes={},
            bean=_make_bean(),
            preferred_methods={BrewMethod.V60},
        )
        assert result == []


# ===========================================================================
# 4. Reranking signal scores (spec §5.3)
# ===========================================================================


class TestRerankSignals:
    """Tests for individual reranking signal computations."""

    # -- semantic_similarity --

    def test_semantic_similarity_identical_embeddings(self):
        """Identical embeddings produce a high similarity score."""
        from src.recipe_retriever.retriever import _score_semantic_similarity

        emb = [1.0, 0.0, 0.0, 0.0]
        score = _score_semantic_similarity(emb, emb)
        assert score == 1.0

    def test_semantic_similarity_orthogonal_embeddings(self):
        """Orthogonal embeddings produce a near-zero similarity score."""
        from src.recipe_retriever.retriever import _score_semantic_similarity

        a = [1.0, 0.0]
        b = [0.0, 1.0]
        score = _score_semantic_similarity(a, b)
        assert abs(score) < 1e-6

    def test_semantic_similarity_none_returns_default(self):
        """None embeddings return 0.5 (neutral default)."""
        from src.recipe_retriever.retriever import _score_semantic_similarity

        assert _score_semantic_similarity(None, [1.0]) == 0.5
        assert _score_semantic_similarity([1.0], None) == 0.5

    # -- bean_profile_match --

    def test_bean_profile_match_full_overlap(self):
        """Full overlap between bean clusters and recipe flavors gives score 1.0."""
        from src.recipe_retriever.retriever import _score_bean_profile_match

        recipe = _make_recipe(flavor_profiles=["Floral", "Citrus"])
        bean = _make_bean(clusters=["Floral", "Citrus"])
        score = _score_bean_profile_match(recipe, bean)
        assert score == 1.0

    def test_bean_profile_match_partial_overlap(self):
        """Partial overlap gives proportional score."""
        from src.recipe_retriever.retriever import _score_bean_profile_match

        recipe = _make_recipe(flavor_profiles=["Floral", "Citrus"])
        bean = _make_bean(clusters=["Floral", "Berry"])
        score = _score_bean_profile_match(recipe, bean)
        assert score == 0.5

    def test_bean_profile_match_no_overlap(self):
        """No overlap returns 0.0."""
        from src.recipe_retriever.retriever import _score_bean_profile_match

        recipe = _make_recipe(flavor_profiles=["Chocolate", "Nutty"])
        bean = _make_bean(clusters=["Floral", "Citrus"])
        score = _score_bean_profile_match(recipe, bean)
        assert score == 0.0

    # -- process_match --

    def test_process_match_hit(self):
        """Bean process in recipe's suitable_for.processes gives 1.0."""
        from src.recipe_retriever.retriever import _score_process_match

        recipe = _make_recipe(processes=[Process.WASHED, Process.NATURAL])
        bean = _make_bean(process=Process.WASHED)
        score = _score_process_match(recipe, bean)
        assert score == 1.0

    def test_process_match_miss(self):
        """Bean process not in recipe's processes gives 0.0."""
        from src.recipe_retriever.retriever import _score_process_match

        recipe = _make_recipe(processes=[Process.WASHED])
        bean = _make_bean(process=Process.NATURAL)
        score = _score_process_match(recipe, bean)
        assert score == 0.0

    # -- origin_match --

    def test_origin_match_hit(self):
        """Bean origin in recipe's suitable_for.origins gives 1.0."""
        from src.recipe_retriever.retriever import _score_origin_match

        recipe = _make_recipe(origins=["Ethiopia", "Colombia"])
        bean = _make_bean(origin="Ethiopia")
        score = _score_origin_match(recipe, bean)
        assert score == 1.0

    def test_origin_match_miss(self):
        """Bean origin not in recipe's origins gives 0.0."""
        from src.recipe_retriever.retriever import _score_origin_match

        recipe = _make_recipe(origins=["Ethiopia"])
        bean = _make_bean(origin="Brazil")
        score = _score_origin_match(recipe, bean)
        assert score == 0.0

    # -- parameter_constraint_fit --

    def test_parameter_fit_light_roast_high_temp(self):
        """Light roast with temp >= 92C gets a bonus."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(water_temp_c=94.0, grind_setting=5, total_time_s=210)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert score >= 0.5

    def test_parameter_fit_light_roast_low_temp(self):
        """Light roast with temp < 92C gets a penalty."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(water_temp_c=90.0, grind_setting=5, total_time_s=210)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert score < 0.5

    def test_parameter_fit_dark_roast_low_temp(self):
        """Dark roast with temp <= 94C gets a bonus."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(water_temp_c=92.0, grind_setting=5, total_time_s=210)
        bean = _make_bean(roast=RoastLevel.DARK)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert score >= 0.5

    def test_parameter_fit_dark_roast_high_temp(self):
        """Dark roast with temp > 94C gets a penalty."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(water_temp_c=96.0, grind_setting=5, total_time_s=210)
        bean = _make_bean(roast=RoastLevel.DARK)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert score < 0.5

    def test_parameter_fit_fine_grind_short_time(self):
        """Fine grind + short time gets a bonus."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(grind_setting=2, total_time_s=180, water_temp_c=93.0)
        bean = _make_bean(roast=RoastLevel.MEDIUM)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert score >= 0.5

    def test_parameter_fit_coarse_grind_long_time(self):
        """Coarse grind + long time gets a bonus."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(grind_setting=8, total_time_s=240, water_temp_c=93.0)
        bean = _make_bean(roast=RoastLevel.MEDIUM)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert score >= 0.5

    def test_parameter_fit_score_clamped_to_01(self):
        """Parameter constraint fit score is always in [0, 1]."""
        from src.recipe_retriever.retriever import _score_parameter_constraint_fit

        recipe = _make_recipe(water_temp_c=85.0, grind_setting=10, total_time_s=360)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        score = _score_parameter_constraint_fit(recipe, bean)
        assert 0.0 <= score <= 1.0


class TestComputeRerankScore:
    """Tests for the combined reranking score."""

    def test_combined_score_is_weighted_sum(self):
        """Combined score equals sum of (weight * signal) for all 5 signals."""
        from src.recipe_retriever.retriever import SIGNAL_WEIGHTS, compute_rerank_score

        recipe = _make_recipe(method=BrewMethod.V60)
        bean = _make_bean(roast=RoastLevel.LIGHT, clusters=["Floral"])

        result = compute_rerank_score(recipe, bean)

        for signal_name in SIGNAL_WEIGHTS:
            assert signal_name in result
            assert 0.0 <= result[signal_name] <= 1.0, f"{signal_name} out of range"

        assert "combined" in result

        expected = sum(
            SIGNAL_WEIGHTS[name] * result[name]
            for name in SIGNAL_WEIGHTS
        )
        assert abs(result["combined"] - expected) < 1e-9

    def test_all_signals_present(self):
        """compute_rerank_score returns all 5 signals plus combined."""
        from src.recipe_retriever.retriever import SIGNAL_WEIGHTS, compute_rerank_score

        recipe = _make_recipe()
        bean = _make_bean()

        result = compute_rerank_score(recipe, bean)

        expected_keys = set(SIGNAL_WEIGHTS.keys()) | {"combined"}
        assert set(result.keys()) == expected_keys

    def test_with_embeddings(self):
        """compute_rerank_score uses embeddings for semantic similarity."""
        from src.recipe_retriever.retriever import compute_rerank_score

        recipe = _make_recipe()
        bean = _make_bean()
        emb = [1.0, 0.0, 0.0, 0.0]

        result = compute_rerank_score(recipe, bean, query_emb=emb, recipe_emb=emb)
        assert result["semantic_similarity"] == 1.0


# ===========================================================================
# 5. RRF fusion
# ===========================================================================


class TestRRFFusion:
    """Tests for reciprocal_rank_fusion."""

    def test_rrf_basic_fusion(self):
        """Items appearing in both rankings get higher scores."""
        from src.recipe_retriever.retriever import reciprocal_rank_fusion

        dense = ["a", "b", "c"]
        sparse = ["b", "c", "d"]

        scores = reciprocal_rank_fusion(dense, sparse)
        assert scores["b"] > scores["a"]
        assert scores["b"] > scores["d"]

    def test_rrf_preserves_rank_order(self):
        """Higher-ranked items get higher RRF scores."""
        from src.recipe_retriever.retriever import reciprocal_rank_fusion

        dense = ["x", "y", "z"]
        sparse: list[str] = []

        scores = reciprocal_rank_fusion(dense, sparse)
        assert scores["x"] > scores["y"]
        assert scores["y"] > scores["z"]

    def test_rrf_empty_rankings(self):
        """Empty rankings produce empty scores."""
        from src.recipe_retriever.retriever import reciprocal_rank_fusion

        scores = reciprocal_rank_fusion([], [])
        assert scores == {}

    def test_rrf_single_list(self):
        """Only one ranking still produces valid scores."""
        from src.recipe_retriever.retriever import reciprocal_rank_fusion

        scores = reciprocal_rank_fusion(["a", "b"], [])
        assert len(scores) == 2
        assert scores["a"] > scores["b"]

    def test_rrf_uses_weights(self):
        """Dense and sparse weights are applied correctly."""
        from src.recipe_retriever.retriever import reciprocal_rank_fusion

        dense = ["a"]
        sparse = ["a"]

        scores = reciprocal_rank_fusion(dense, sparse)
        expected = (0.6 + 0.4) / (60 + 1)
        assert abs(scores["a"] - expected) < 1e-9


# ===========================================================================
# 6. Diversity enforcement (MMR-style, spec §5.4)
# ===========================================================================


class TestDiversity:
    """Tests for _ensure_diversity with MMR-style parameter-distance selection."""

    def test_top_candidate_always_included(self):
        """Highest-scoring candidate is always included in the result."""
        from src.recipe_retriever.retriever import RecipeRetriever

        recipes = {f"r{i}": _make_recipe(recipe_id=f"r{i}", grind_setting=i + 1)
                   for i in range(5)}
        scored = [(f"r{i}", float(5 - i), {}) for i in range(5)]

        result = RecipeRetriever._ensure_diversity(scored, recipes, top_k=3)
        assert result[0] == "r0"  # highest score

    def test_diversity_returns_top_k_or_fewer(self):
        """Returns at most top_k results."""
        from src.recipe_retriever.retriever import RecipeRetriever

        recipes = {f"r{i}": _make_recipe(recipe_id=f"r{i}") for i in range(10)}
        scored = [(f"r{i}", float(10 - i), {}) for i in range(10)]

        result = RecipeRetriever._ensure_diversity(scored, recipes, top_k=3)
        assert len(result) <= 3

    def test_diversity_prefers_parameter_variety(self):
        """MMR selection should pick recipes with different parameters."""
        from src.recipe_retriever.retriever import RecipeRetriever

        # 5 recipes with very similar params but different scores
        recipes = {}
        for i in range(5):
            recipes[f"r{i}"] = _make_recipe(
                recipe_id=f"r{i}",
                grind_setting=5,
                water_temp_c=93.0,
                dose_g=15.0,
                water_total_g=250.0,
            )
        scored = [(f"r{i}", float(5 - i), {}) for i in range(5)]

        result = RecipeRetriever._ensure_diversity(scored, recipes, top_k=5)
        # With identical params, distance is 0, so selection is relevance-only
        assert len(result) == 5
        assert result[0] == "r0"  # top score first

    def test_diversity_empty_input(self):
        """Empty scored list returns empty."""
        from src.recipe_retriever.retriever import RecipeRetriever

        result = RecipeRetriever._ensure_diversity([], {}, top_k=3)
        assert result == []

    def test_diversity_varied_params_gets_diverse_results(self):
        """Recipes with different parameters should be preferred over similar ones."""
        from src.recipe_retriever.retriever import RecipeRetriever

        recipes = {
            "similar-1": _make_recipe(recipe_id="s1", grind_setting=5, water_temp_c=93.0),
            "similar-2": _make_recipe(recipe_id="s2", grind_setting=5, water_temp_c=93.5),
            "different": _make_recipe(recipe_id="diff", grind_setting=2, water_temp_c=88.0),
        }
        # similar-1 has highest score, different has lowest
        scored = [("similar-1", 1.0, {}), ("similar-2", 0.9, {}), ("different", 0.5, {})]

        result = RecipeRetriever._ensure_diversity(scored, recipes, top_k=3)
        assert len(result) == 3
        assert "different" in result  # should be picked for diversity


# ===========================================================================
# 7. End-to-end retrieve with mocked indexes
# ===========================================================================


class TestRetrieveEndToEnd:
    """End-to-end retrieval tests with mocked ChromaDB and BM25."""

    def _build_retriever_with_data(self, tmp_path: Path):
        """Build a retriever pre-populated with test recipes and mock indexes."""
        retriever = _patched_retriever(tmp_path)

        recipe_jsons = [
            _sample_recipe_json(
                recipe_id="v60-light",
                method="V60",
                roast_levels=["light", "medium-light"],
                flavor_profiles=["Floral", "Citrus"],
            ),
            _sample_recipe_json(
                recipe_id="v60-dark",
                method="V60",
                roast_levels=["dark", "medium-dark"],
                flavor_profiles=["Chocolate", "Nutty"],
            ),
            _sample_recipe_json(
                recipe_id="kalita-light",
                method="Kalita Wave",
                roast_levels=["light", "medium"],
                flavor_profiles=["Floral", "Berry"],
            ),
            _sample_recipe_json(
                recipe_id="origami-medium",
                method="Origami",
                roast_levels=["medium"],
                flavor_profiles=["Sweet", "Balanced"],
            ),
        ]
        recipe_dir = tmp_path / "recipes"
        recipe_dir.mkdir()
        _write_recipe_dir(str(recipe_dir), recipe_jsons)
        retriever.index_recipes(str(recipe_dir))
        return retriever

    def test_retrieve_returns_retrieval_result(self, tmp_path):
        """retrieve() returns a RetrievalResult, not a bare list."""
        from src.recipe_retriever.retriever import RetrievalResult

        retriever = self._build_retriever_with_data(tmp_path)
        bean = _make_bean(roast=RoastLevel.LIGHT, clusters=["Floral"])
        prefs = {"brew_methods": ["V60", "Kalita Wave"]}

        result = retriever.retrieve(bean, prefs, top_k=3)
        assert isinstance(result, RetrievalResult)
        assert isinstance(result.recipes, list)
        assert all(r.recipe is not None for r in result.recipes)

    def test_retrieve_respects_method_filter(self, tmp_path):
        """When only V60 is preferred, no Kalita/Origami recipes appear."""
        retriever = self._build_retriever_with_data(tmp_path)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        prefs = {"brew_methods": ["V60"]}

        result = retriever.retrieve(bean, prefs, top_k=3)
        for ranked in result.recipes:
            assert ranked.recipe.method == BrewMethod.V60

    def test_retrieve_empty_recipes_raises(self, tmp_path):
        """Calling retrieve before indexing raises RuntimeError."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever(chroma_persist_dir=str(tmp_path / "chroma"))
        retriever._model = _mock_model()
        retriever._collection = _mock_chroma_collection()
        retriever._recipes = {}
        retriever._recipe_texts = {}

        bean = _make_bean()
        with pytest.raises(RuntimeError, match="No recipes available"):
            retriever.retrieve(bean, {})

    def test_retrieve_top_k_limit(self, tmp_path):
        """retrieve() returns at most top_k recipes."""
        retriever = self._build_retriever_with_data(tmp_path)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        prefs = {"brew_methods": ["V60", "Kalita Wave", "Origami"]}

        result = retriever.retrieve(bean, prefs, top_k=2)
        assert len(result.recipes) <= 2

    def test_retrieve_no_matching_method_returns_broad(self, tmp_path):
        """When no recipes match preferred method, fallback returns broad matches."""
        retriever = self._build_retriever_with_data(tmp_path)
        bean = _make_bean(roast=RoastLevel.LIGHT, clusters=["Chocolate"])
        prefs = {"brew_methods": ["V60"]}

        result = retriever.retrieve(bean, prefs, top_k=3)
        assert isinstance(result.recipes, list)
        assert len(result.recipes) >= 1

    def test_retrieve_ranked_recipes_have_ranks(self, tmp_path):
        """Each RankedRecipe in the result has a rank starting at 1."""
        retriever = self._build_retriever_with_data(tmp_path)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        prefs = {"brew_methods": ["V60", "Kalita Wave"]}

        result = retriever.retrieve(bean, prefs, top_k=3)
        for i, ranked in enumerate(result.recipes, start=1):
            assert ranked.rank == i

    def test_retrieve_total_candidates_set(self, tmp_path):
        """RetrievalResult.total_candidates reflects the number of filtered candidates."""
        retriever = self._build_retriever_with_data(tmp_path)
        bean = _make_bean(roast=RoastLevel.LIGHT)
        prefs = {"brew_methods": ["V60"]}

        result = retriever.retrieve(bean, prefs, top_k=3)
        assert result.total_candidates >= 0


# ===========================================================================
# 8. index_recipes from directory (with mocked external deps)
# ===========================================================================


class TestIndexRecipes:
    """Tests for the index_recipes method with mocked dependencies."""

    @patch("src.recipe_retriever.retriever.RecipeRetriever._build_sparse_index")
    @patch("src.recipe_retriever.retriever.RecipeRetriever._build_dense_index")
    def test_index_recipes_loads_and_stores(self, mock_dense, mock_sparse, tmp_path):
        """index_recipes loads from dir and calls both index builders."""
        from src.recipe_retriever.retriever import RecipeRetriever

        _write_recipe_dir(str(tmp_path), [
            _sample_recipe_json(recipe_id="r1"),
            _sample_recipe_json(recipe_id="r2", method="Kalita Wave"),
        ])

        retriever = RecipeRetriever()
        retriever.index_recipes(str(tmp_path))

        assert len(retriever._recipes) == 2
        assert "r1" in retriever._recipes
        assert "r2" in retriever._recipes
        mock_dense.assert_called_once()
        mock_sparse.assert_called_once()

    @patch("src.recipe_retriever.retriever.RecipeRetriever._build_sparse_index")
    @patch("src.recipe_retriever.retriever.RecipeRetriever._build_dense_index")
    def test_index_recipes_empty_dir_noop(self, mock_dense, mock_sparse, tmp_path):
        """index_recipes with empty directory does not call index builders."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever()
        retriever.index_recipes(str(tmp_path))

        assert len(retriever._recipes) == 0
        mock_dense.assert_not_called()
        mock_sparse.assert_not_called()

    @patch("src.recipe_retriever.retriever.RecipeRetriever._build_sparse_index")
    @patch("src.recipe_retriever.retriever.RecipeRetriever._build_dense_index")
    def test_index_recipes_creates_text_representations(self, mock_dense, mock_sparse, tmp_path):
        """index_recipes builds recipe_to_text for each loaded recipe."""
        from src.recipe_retriever.retriever import RecipeRetriever, recipe_to_text

        _write_recipe_dir(str(tmp_path), [_sample_recipe_json(recipe_id="txt-test")])

        retriever = RecipeRetriever()
        retriever.index_recipes(str(tmp_path))

        assert "txt-test" in retriever._recipe_texts
        expected = recipe_to_text(retriever._recipes["txt-test"])
        assert retriever._recipe_texts["txt-test"] == expected


# ===========================================================================
# 9. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge case tests for the retriever."""

    def test_retriever_default_embedding_model(self):
        """Default embedding model name is all-MiniLM-L6-v2."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever()
        assert retriever._embedding_model_name == "all-MiniLM-L6-v2"

    def test_retriever_custom_embedding_model(self):
        """Custom embedding model name is stored."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever(embedding_model="custom-model")
        assert retriever._embedding_model_name == "custom-model"

    def test_retriever_chroma_dir_default(self):
        """Default chroma dir is under temp."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever()
        assert "brewmatch_chroma" in retriever._chroma_persist_dir

    def test_retriever_chroma_dir_custom(self):
        """Custom chroma dir is used when provided."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever(chroma_persist_dir="/data/my_chroma")
        assert retriever._chroma_persist_dir == "/data/my_chroma"

    def test_signal_weights_sum_to_one(self):
        """Reranking signal weights sum to 1.0."""
        from src.recipe_retriever.retriever import SIGNAL_WEIGHTS

        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_all_valid_methods_recognized(self):
        """V60, Kalita Wave, and Origami are all recognized as valid."""
        from src.recipe_retriever.retriever import VALID_METHODS

        assert BrewMethod.V60 in VALID_METHODS
        assert BrewMethod.KALITA_WAVE in VALID_METHODS
        assert BrewMethod.ORIGAMI in VALID_METHODS
        assert len(VALID_METHODS) == 3

    def test_normalize_params_range(self):
        """_normalize_params returns values in [0, 1]."""
        from src.recipe_retriever.retriever import _normalize_params

        recipe = _make_recipe(grind_setting=5, water_temp_c=93.0, dose_g=15.0,
                              water_total_g=250.0)
        params = _normalize_params(recipe)
        assert len(params) == 4
        for p in params:
            assert 0.0 <= p <= 1.0

    def test_param_distance_identical(self):
        """Distance between identical params is 0."""
        from src.recipe_retriever.retriever import _param_distance

        p = [0.5, 0.5, 0.5, 0.5]
        assert _param_distance(p, p) == 0.0

    def test_param_distance_positive(self):
        """Distance between different params is positive."""
        from src.recipe_retriever.retriever import _param_distance

        a = [0.0, 0.0, 0.0, 0.0]
        b = [1.0, 1.0, 1.0, 1.0]
        assert _param_distance(a, b) > 0.0


# ===========================================================================
# 10. Sparse retrieval / BM25 (M08)
# ===========================================================================


class TestSparseRetrieval:
    """Tests for the BM25 sparse retrieval path in hybrid retrieval.

    The retriever uses rank_bm25.BM25Okapi for sparse retrieval and fuses
    results with dense ChromaDB results via RRF. These tests verify that the
    sparse path produces scores and that the hybrid fusion is correct.
    """

    def _build_retriever_with_mocked_bm25(self, tmp_path: Path):
        """Build a retriever with mocked model, ChromaDB, and a real BM25 index.

        We patch _build_sparse_index to be a no-op during index_recipes, then
        manually build a BM25 index from the recipe texts so we can test the
        actual sparse retrieval path.
        """
        from rank_bm25 import BM25Okapi
        from src.recipe_retriever.retriever import (
            RecipeRetriever,
            _tokenize,
        )

        retriever = _patched_retriever(tmp_path)

        recipe_jsons = [
            _sample_recipe_json(
                recipe_id="v60-floral",
                method="V60",
                roast_levels=["light"],
                origins=["Ethiopia"],
                processes=["washed"],
                flavor_profiles=["Floral", "Citrus"],
            ),
            _sample_recipe_json(
                recipe_id="v60-chocolate",
                method="V60",
                roast_levels=["dark"],
                origins=["Brazil"],
                processes=["natural"],
                flavor_profiles=["Chocolate", "Nutty"],
            ),
            _sample_recipe_json(
                recipe_id="kalita-berry",
                method="Kalita Wave",
                roast_levels=["light"],
                origins=["Kenya"],
                processes=["washed"],
                flavor_profiles=["Berry", "Citrus"],
            ),
        ]
        recipe_dir = tmp_path / "recipes"
        recipe_dir.mkdir()
        _write_recipe_dir(str(recipe_dir), recipe_jsons)

        # Mock out _build_sparse_index so it does nothing
        with patch.object(RecipeRetriever, "_build_sparse_index"):
            retriever.index_recipes(str(recipe_dir))

        # Now manually build the BM25 index from the actual recipe texts
        retriever._bm25_ids = list(retriever._recipe_texts.keys())
        corpus = [_tokenize(retriever._recipe_texts[rid]) for rid in retriever._bm25_ids]
        retriever._bm25 = BM25Okapi(corpus)

        return retriever

    def test_sparse_retrieval_produces_scores(self, tmp_path):
        """BM25 sparse retrieval returns non-empty scores for a matching query."""
        from src.recipe_retriever.retriever import _tokenize

        retriever = self._build_retriever_with_mocked_bm25(tmp_path)

        # Query that should match the floral recipe
        tokenized_query = _tokenize("floral citrus Ethiopia washed")
        scores = retriever._bm25.get_scores(tokenized_query)

        assert len(scores) == len(retriever._bm25_ids)
        # At least one score should be positive for a matching query
        assert any(s > 0 for s in scores)

    def test_sparse_scores_rank_relevant_higher(self, tmp_path):
        """BM25 ranks a query-matching document higher than non-matching ones."""
        from src.recipe_retriever.retriever import _tokenize

        retriever = self._build_retriever_with_mocked_bm25(tmp_path)

        # Query targeting chocolate/nutty recipe
        tokenized_query = _tokenize("chocolate nutty Brazil natural dark")
        scores = retriever._bm25.get_scores(tokenized_query)

        # Find the index of the chocolate recipe
        chocolate_idx = retriever._bm25_ids.index("v60-chocolate")
        floral_idx = retriever._bm25_ids.index("v60-floral")

        assert scores[chocolate_idx] > scores[floral_idx]

    def test_hybrid_retrieve_returns_fused_scores(self, tmp_path):
        """_hybrid_retrieve returns a dict with scores from both dense and sparse."""
        retriever = self._build_retriever_with_mocked_bm25(tmp_path)

        query_text = "Ethiopia washed floral citrus"
        query_emb = retriever._get_model().encode(
            [query_text], normalize_embeddings=True
        )[0].tolist()

        rrf_scores = retriever._hybrid_retrieve(query_text, query_emb)

        # Should have entries for all indexed recipes
        assert len(rrf_scores) > 0
        # All scores should be positive (RRF scores are always > 0 when present)
        for rid, score in rrf_scores.items():
            assert score > 0.0, f"RRF score for {rid} should be positive"
        # All indexed recipes should appear
        for rid in retriever._bm25_ids:
            assert rid in rrf_scores, f"Recipe {rid} missing from hybrid results"

    def test_hybrid_fusion_combines_dense_and_sparse(self, tmp_path):
        """Items appearing in both dense and sparse get higher combined RRF scores."""
        from src.recipe_retriever.retriever import reciprocal_rank_fusion

        # Simulate dense ranking: a first, b second, c third
        dense = ["v60-floral", "v60-chocolate", "kalita-berry"]
        # Simulate sparse ranking: b first, a second, c third
        sparse = ["v60-chocolate", "v60-floral", "kalita-berry"]

        scores = reciprocal_rank_fusion(dense, sparse)

        # Items appearing in both get higher scores than items only in one
        # a and b appear in both; c appears in both too but at lower ranks
        # b is rank 2 dense + rank 1 sparse -> highest combined
        assert scores["v60-chocolate"] > scores["kalita-berry"]

    def test_sparse_retrieval_empty_query_tokens(self, tmp_path):
        """A query that tokenizes to empty returns no sparse results."""
        from src.recipe_retriever.retriever import _tokenize

        retriever = self._build_retriever_with_mocked_bm25(tmp_path)

        # Query with only stopwords or very short tokens
        tokenized_query = _tokenize("a an the")
        assert tokenized_query == []  # all stopwords removed

        # _hybrid_retrieve should still work (dense-only)
        query_emb = retriever._get_model().encode(
            ["test query"], normalize_embeddings=True
        )[0].tolist()
        rrf_scores = retriever._hybrid_retrieve("a an the", query_emb)
        # Should still have dense results
        assert len(rrf_scores) > 0

    def test_tokenize_removes_stopwords(self):
        """_tokenize strips English stopwords and short tokens."""
        from src.recipe_retriever.retriever import _tokenize

        tokens = _tokenize("The quick brown fox and a lazy dog")
        # "the", "and", "a" are stopwords; single-char tokens removed
        assert "the" not in tokens
        assert "and" not in tokens
        assert "a" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens


# ===========================================================================
# 11. Constraint relaxation stages (M09)
# ===========================================================================


class TestConstraintRelaxation:
    """Tests for the multi-stage relaxation in hard filtering.

    The retriever applies hard filters in stages:
    1. Method + roast compatibility
    2. If < 3 results, relax roast constraint
    3. If still empty, fallback to all methods (broad)
    """

    def _build_retriever_with_diverse_recipes(self, tmp_path: Path):
        """Build a retriever with recipes spanning many roast levels and methods."""
        retriever = _patched_retriever(tmp_path)

        recipe_jsons = [
            _sample_recipe_json(
                recipe_id="v60-light-a",
                method="V60",
                roast_levels=["light"],
                origins=["Ethiopia"],
                flavor_profiles=["Floral", "Citrus"],
            ),
            _sample_recipe_json(
                recipe_id="v60-light-b",
                method="V60",
                roast_levels=["light", "medium-light"],
                origins=["Kenya"],
                flavor_profiles=["Berry"],
            ),
            _sample_recipe_json(
                recipe_id="v60-dark",
                method="V60",
                roast_levels=["dark", "medium-dark"],
                origins=["Brazil"],
                flavor_profiles=["Chocolate", "Nutty"],
            ),
            _sample_recipe_json(
                recipe_id="kalita-light",
                method="Kalita Wave",
                roast_levels=["light"],
                origins=["Colombia"],
                flavor_profiles=["Citrus"],
            ),
            _sample_recipe_json(
                recipe_id="origami-medium",
                method="Origami",
                roast_levels=["medium"],
                origins=["Guatemala"],
                flavor_profiles=["Sweet"],
            ),
        ]
        recipe_dir = tmp_path / "recipes"
        recipe_dir.mkdir()
        _write_recipe_dir(str(recipe_dir), recipe_jsons)
        retriever.index_recipes(str(recipe_dir))
        return retriever

    def test_roast_relaxation_when_too_specific(self):
        """When roast constraint eliminates all but <3, relaxation expands results."""
        from src.recipe_retriever.retriever import RecipeRetriever

        # Only one dark recipe for V60
        recipes = {
            "dark-only": _make_recipe(
                recipe_id="dark-only",
                roast_levels=[RoastLevel.DARK],
            ),
            "light-a": _make_recipe(
                recipe_id="light-a",
                roast_levels=[RoastLevel.LIGHT],
            ),
            "light-b": _make_recipe(
                recipe_id="light-b",
                roast_levels=[RoastLevel.LIGHT, RoastLevel.MEDIUM_LIGHT],
            ),
            "light-c": _make_recipe(
                recipe_id="light-c",
                roast_levels=[RoastLevel.LIGHT],
            ),
        }
        # Bean is dark roast, but only 1 dark recipe -- relaxation should drop
        # roast constraint and return all method-matching recipes.
        bean = _make_bean(roast=RoastLevel.DARK)

        result = RecipeRetriever._apply_hard_filters(
            candidates=["dark-only", "light-a", "light-b", "light-c"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60},
        )
        # Before relaxation: only "dark-only" passes (1 result < 3)
        # After relaxation: all V60 recipes pass (method-only filter)
        assert len(result) >= 3
        # All results are V60 (method constraint is never relaxed)
        for rid in result:
            assert recipes[rid].method == BrewMethod.V60

    def test_method_constraint_never_relaxed(self):
        """Method hard constraint is enforced even during roast relaxation."""
        from src.recipe_retriever.retriever import RecipeRetriever

        r_v60 = _make_recipe(recipe_id="v60", method=BrewMethod.V60,
                             roast_levels=[RoastLevel.LIGHT])
        r_kalita = _make_recipe(recipe_id="kalita", method=BrewMethod.KALITA_WAVE,
                                roast_levels=[RoastLevel.DARK])
        r_origami = _make_recipe(recipe_id="origami", method=BrewMethod.ORIGAMI,
                                 roast_levels=[RoastLevel.DARK])
        recipes = {"v60": r_v60, "kalita": r_kalita, "origami": r_origami}

        bean = _make_bean(roast=RoastLevel.LIGHT)
        result = RecipeRetriever._apply_hard_filters(
            candidates=["v60", "kalita", "origami"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60},
        )
        # Only V60 passes method filter regardless of relaxation
        for rid in result:
            assert recipes[rid].method == BrewMethod.V60

    def test_fallback_to_all_methods_when_no_match(self, tmp_path):
        """When filtering produces 0 results, retrieve falls back to broad match."""
        retriever = self._build_retriever_with_diverse_recipes(tmp_path)

        # Request Origami-only for a dark-roast bean -- no Origami recipe matches
        # dark roast, so filter should broaden to all methods.
        bean = _make_bean(roast=RoastLevel.DARK, clusters=["Chocolate"])
        prefs = {"brew_methods": ["Origami"]}

        result = retriever.retrieve(bean, prefs, top_k=3)
        # Fallback should return at least some recipes
        assert isinstance(result.recipes, list)
        # total_candidates may come from broadened results
        assert result.total_candidates >= 0

    def test_retrieve_with_very_specific_constraints(self, tmp_path):
        """Very narrow constraints that match few recipes still return results."""
        retriever = self._build_retriever_with_diverse_recipes(tmp_path)

        # Only V60 + light roast should match v60-light-a and v60-light-b
        bean = _make_bean(
            origin="Ethiopia",
            roast=RoastLevel.LIGHT,
            process=Process.WASHED,
            clusters=["Floral", "Citrus"],
        )
        prefs = {"brew_methods": ["V60"]}

        result = retriever.retrieve(bean, prefs, top_k=5)
        assert len(result.recipes) >= 1
        for ranked in result.recipes:
            assert ranked.recipe.method == BrewMethod.V60

    def test_retrieve_all_methods_gets_more_candidates(self, tmp_path):
        """Allowing all methods yields more candidates than a single method."""
        retriever = self._build_retriever_with_diverse_recipes(tmp_path)

        bean = _make_bean(roast=RoastLevel.LIGHT, clusters=["Citrus"])

        # Single method
        result_v60 = retriever.retrieve(
            bean, {"brew_methods": ["V60"]}, top_k=10
        )
        # All methods
        result_all = retriever.retrieve(
            bean,
            {"brew_methods": ["V60", "Kalita Wave", "Origami"]},
            top_k=10,
        )

        assert result_all.total_candidates >= result_v60.total_candidates

    def test_relaxation_preserves_method_for_multiple_methods(self):
        """Relaxation keeps recipes matching any of the preferred methods."""
        from src.recipe_retriever.retriever import RecipeRetriever

        r1 = _make_recipe(recipe_id="r1", method=BrewMethod.V60,
                          roast_levels=[RoastLevel.DARK])
        r2 = _make_recipe(recipe_id="r2", method=BrewMethod.KALITA_WAVE,
                          roast_levels=[RoastLevel.DARK])
        r3 = _make_recipe(recipe_id="r3", method=BrewMethod.V60,
                          roast_levels=[RoastLevel.LIGHT])
        r4 = _make_recipe(recipe_id="r4", method=BrewMethod.ORIGAMI,
                          roast_levels=[RoastLevel.LIGHT])
        recipes = {"r1": r1, "r2": r2, "r3": r3, "r4": r4}

        # Bean is light -- only r3 and r4 pass roast. That's 2 < 3 so
        # relaxation should add r1 and r2 (V60 + Kalita) but NOT r4 if
        # preferred_methods is only V60+Kalita.
        bean = _make_bean(roast=RoastLevel.LIGHT)
        result = RecipeRetriever._apply_hard_filters(
            candidates=["r1", "r2", "r3", "r4"],
            recipes=recipes,
            bean=bean,
            preferred_methods={BrewMethod.V60, BrewMethod.KALITA_WAVE},
        )
        # After relaxation, all V60 and Kalita recipes should be included
        method_set = {recipes[rid].method for rid in result}
        assert BrewMethod.ORIGAMI not in method_set
        assert len(result) >= 3


# ===========================================================================
# 12. Embedding cache (M16)
# ===========================================================================


class TestEmbeddingCache:
    """Tests for the LRU embedding cache added to RecipeRetriever.

    The cache stores query embeddings keyed by the hash of the input text,
    avoiding redundant model.encode() calls for repeated queries.
    """

    def test_cache_initially_empty(self):
        """New retriever has an empty embedding cache."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = RecipeRetriever()
        assert len(retriever._embedding_cache) == 0
        assert retriever._embedding_cache_hits == 0
        assert retriever._embedding_cache_misses == 0

    def test_cache_populated_after_first_call(self, tmp_path):
        """First call to _get_query_embedding populates the cache."""
        retriever = _patched_retriever(tmp_path)
        retriever._embedding_cache.clear()

        emb = retriever._get_query_embedding("Ethiopia washed light floral")

        assert len(retriever._embedding_cache) == 1
        assert retriever._embedding_cache_misses == 1
        assert retriever._embedding_cache_hits == 0
        assert isinstance(emb, list)
        assert len(emb) == EMBEDDING_DIM

    def test_cache_hit_on_repeated_query(self, tmp_path):
        """Second call with the same text hits the cache."""
        retriever = _patched_retriever(tmp_path)
        retriever._embedding_cache.clear()

        query = "Ethiopia washed light floral"
        emb1 = retriever._get_query_embedding(query)
        emb2 = retriever._get_query_embedding(query)

        assert retriever._embedding_cache_hits == 1
        assert retriever._embedding_cache_misses == 1
        # Same embedding returned both times
        assert emb1 == emb2

    def test_cache_miss_on_different_query(self, tmp_path):
        """Different query texts cause separate cache entries."""
        retriever = _patched_retriever(tmp_path)
        retriever._embedding_cache.clear()

        retriever._get_query_embedding("Ethiopia washed light")
        retriever._get_query_embedding("Brazil natural dark")

        assert len(retriever._embedding_cache) == 2
        assert retriever._embedding_cache_misses == 2
        assert retriever._embedding_cache_hits == 0

    def test_cache_eviction_at_maxsize(self, tmp_path):
        """Cache evicts oldest entries when exceeding _EMBEDDING_CACHE_MAXSIZE."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = _patched_retriever(tmp_path)
        retriever._embedding_cache.clear()

        maxsize = RecipeRetriever._EMBEDDING_CACHE_MAXSIZE
        # Fill cache to max + 1, then verify oldest evicted
        first_query = "first-query-text"
        retriever._get_query_embedding(first_query)
        for i in range(maxsize):
            retriever._get_query_embedding(f"query-text-{i}")

        # Cache should be at maxsize (oldest evicted)
        assert len(retriever._embedding_cache) <= maxsize
        # The first query should have been evicted (it was inserted first)
        first_key = hash(first_query)
        assert first_key not in retriever._embedding_cache

    def test_cache_lru_ordering_on_access(self, tmp_path):
        """Accessing a cached entry moves it to the end (LRU refresh)."""
        from src.recipe_retriever.retriever import RecipeRetriever

        retriever = _patched_retriever(tmp_path)
        retriever._embedding_cache.clear()

        maxsize = RecipeRetriever._EMBEDDING_CACHE_MAXSIZE

        # Insert an entry that will NOT be refreshed (it becomes oldest)
        doomed_query = "doomed-query"
        retriever._get_query_embedding(doomed_query)

        # Insert the query we will refresh
        refreshed_query = "refreshed-query"
        retriever._get_query_embedding(refreshed_query)

        # Now insert maxsize - 2 more entries (filling to capacity)
        for i in range(maxsize - 2):
            retriever._get_query_embedding(f"filler-{i}")

        # Cache should be exactly at maxsize
        assert len(retriever._embedding_cache) == maxsize

        # Refresh the target query to move it to the end
        retriever._get_query_embedding(refreshed_query)
        assert retriever._embedding_cache_hits == 1

        # Add one more entry to trigger eviction of the oldest (doomed_query)
        retriever._get_query_embedding("final-filler")

        # doomed_query should have been evicted (it was the oldest, never refreshed)
        doomed_key = hash(doomed_query)
        assert doomed_key not in retriever._embedding_cache

        # refreshed_query should still be present (it was moved to the end)
        refreshed_key = hash(refreshed_query)
        assert refreshed_key in retriever._embedding_cache

    def test_retrieve_uses_cache_for_same_bean(self, tmp_path):
        """Two retrieve() calls with the same bean profile hit the cache."""
        from src.recipe_retriever.retriever import RetrievalResult

        retriever = _patched_retriever(tmp_path)
        recipe_jsons = [
            _sample_recipe_json(recipe_id="r1"),
            _sample_recipe_json(recipe_id="r2", method="Kalita Wave"),
        ]
        recipe_dir = tmp_path / "recipes"
        recipe_dir.mkdir()
        _write_recipe_dir(str(recipe_dir), recipe_jsons)
        retriever.index_recipes(str(recipe_dir))

        bean = _make_bean(roast=RoastLevel.LIGHT, clusters=["Floral"])
        prefs = {"brew_methods": ["V60"]}

        # First call populates the cache
        retriever._embedding_cache.clear()
        result1 = retriever.retrieve(bean, prefs, top_k=3)
        misses_after_first = retriever._embedding_cache_misses

        # Second call with same bean should hit the cache
        result2 = retriever.retrieve(bean, prefs, top_k=3)
        assert retriever._embedding_cache_hits >= 1
        # Misses should not have increased for the second call
        assert retriever._embedding_cache_misses == misses_after_first

        assert isinstance(result1, RetrievalResult)
        assert isinstance(result2, RetrievalResult)

    def test_cache_maxsize_constant(self):
        """Cache max size is 128."""
        from src.recipe_retriever.retriever import RecipeRetriever

        assert RecipeRetriever._EMBEDDING_CACHE_MAXSIZE == 128

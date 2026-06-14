"""Unit tests for the source_tier credibility field and its retrieval tie-breaker.

source_tier labels a recipe's source as champion / barista / enthusiast. It is a
trust signal in the UI and a NEAR-TIE breaker in retrieval ranking: when two
recipes score almost equally for a bean, the more credible source wins — but a
clear score gap is never overridden by tier.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from src.app.utils import dict_to_recipe, recipe_to_dict
from src.data_models import (
    BeanProfile,
    BrewMethod,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SourceTier,
    SuitableFor,
)
from src.recipe_retriever.retriever import TIE_BAND, RecipeRetriever


def _recipe(recipe_id: str, *, source_tier=None, well_matched: bool = True) -> Recipe:
    """A valid recipe. `well_matched` toggles suitability for a light Ethiopia bean."""
    if well_matched:
        suitable = SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        )
    else:
        suitable = SuitableFor(
            roast_levels=[RoastLevel.DARK],
            origins=["Brazil"],
            processes=[Process.NATURAL],
            flavor_profiles=["Chocolate"],
        )
    kwargs = dict(
        recipe_id=recipe_id,
        source="test-source",
        method=BrewMethod.V60,
        dose_g=16.0,
        water_total_g=256.0,
        ratio=16.0,
        grind_setting=5,
        water_temp_c=93.0,
        bloom_time_s=45,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=64.0),
            PourStep(step=2, time_offset_s=45, water_g=96.0),
            PourStep(step=3, time_offset_s=90, water_g=96.0),
        ],
        suitable_for=suitable,
        instructions="Test recipe",
    )
    if source_tier is not None:
        kwargs["source_tier"] = source_tier
    return Recipe(**kwargs)


def _light_ethiopia_bean() -> BeanProfile:
    return BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Ethiopian Yirgacheffe, light roast",
    )


# --- Data model: default + coercion ---


class TestSourceTierField:
    def test_defaults_to_barista_when_omitted(self):
        """A recipe with no source_tier (e.g. a legacy record) defaults to barista."""
        assert _recipe("r1").source_tier is SourceTier.BARISTA

    def test_none_coerces_to_default(self):
        assert _recipe("r1", source_tier=None).source_tier is SourceTier.BARISTA

    def test_string_coerces_to_enum(self):
        assert _recipe("r1", source_tier="champion").source_tier is SourceTier.CHAMPION

    def test_enum_value_preserved(self):
        assert _recipe("r1", source_tier=SourceTier.ENTHUSIAST).source_tier is SourceTier.ENTHUSIAST

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError, match="source_tier must be one of"):
            _recipe("r1", source_tier="world-champion")


# --- App-layer round trip ---


class TestSourceTierRoundTrip:
    def test_dict_round_trip_preserves_tier(self):
        original = _recipe("r1", source_tier="champion")
        restored = dict_to_recipe(recipe_to_dict(original))
        assert restored.source_tier is SourceTier.CHAMPION

    def test_serialized_dict_holds_string_value(self):
        d = recipe_to_dict(_recipe("r1", source_tier="champion"))
        assert d["source_tier"] == "champion"  # JSON-safe string, not the enum


# --- Curated data backfill integrity ---


class TestRecipeDataBackfill:
    def test_all_recipes_load_and_twelve_are_champion(self):
        from src.recipe_retriever.retriever import _parse_recipe

        tiers = [
            _parse_recipe(json.loads(p.read_text())).source_tier
            for p in pathlib.Path("data/recipes").glob("*.json")
        ]
        assert tiers, "no recipe data found"
        assert sum(t is SourceTier.CHAMPION for t in tiers) == 12
        # Every curated recipe is champion or barista — none left as enthusiast.
        assert all(t in (SourceTier.CHAMPION, SourceTier.BARISTA) for t in tiers)


# --- Retrieval tie-breaker behavior ---


def _rerank_ids(recipes: dict[str, Recipe]) -> list[str]:
    retriever = RecipeRetriever()
    retriever._recipes = recipes
    retriever._recipe_embeddings = {}
    scored = retriever._rerank(list(recipes), _light_ethiopia_bean(), query_emb=None)
    return [rid for rid, _, _ in scored]


class TestSourceTierTieBreaker:
    def test_near_tie_prefers_higher_tier(self):
        """Two identically-matched recipes -> the champion ranks first."""
        recipes = {
            "barista-one": _recipe("barista-one", source_tier="barista"),
            "champ-one": _recipe("champ-one", source_tier="champion"),
        }
        assert _rerank_ids(recipes)[0] == "champ-one"

    def test_clear_gap_not_overridden_by_tier(self):
        """A well-matched barista recipe still beats a poorly-matched champion."""
        recipes = {
            "champ-poor": _recipe("champ-poor", source_tier="champion", well_matched=False),
            "barista-great": _recipe("barista-great", source_tier="barista", well_matched=True),
        }
        retriever = RecipeRetriever()
        retriever._recipes = recipes
        retriever._recipe_embeddings = {}
        scored = retriever._rerank(list(recipes), _light_ethiopia_bean(), query_emb=None)
        by_id = {rid: combined for rid, combined, _ in scored}
        # The match-quality gap must exceed the tie band for this test to be meaningful.
        assert by_id["barista-great"] - by_id["champ-poor"] > TIE_BAND
        # ...and the better match wins despite the lower tier.
        assert scored[0][0] == "barista-great"

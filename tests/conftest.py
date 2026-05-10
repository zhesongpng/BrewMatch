"""Shared fixtures for BrewMatch tests.

Provides factory fixtures for all core data models (PourStep, SuitableFor,
Recipe, BeanProfile) and generator-style helpers (VirtualUser, bean dict,
recipe params dict), plus a seeded RNG for deterministic tests.
"""

import random

import pytest

# tests/sdk/ contains standalone scripts, not pytest tests
collect_ignore = ["sdk"]

from src.data_models import (
    BeanProfile,
    BrewMethod,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)
from src.data_generator.generator import VirtualUser


# --- Seeded RNG ---


@pytest.fixture
def rng() -> random.Random:
    """Deterministic random.Random seeded with 42."""
    return random.Random(42)


# --- Data-model fixtures ---


@pytest.fixture
def make_pour():
    """Factory: creates a PourStep with sensible defaults."""
    def _make_pour(
        step: int = 1, time_offset_s: int = 0, water_g: float = 60.0
    ) -> PourStep:
        return PourStep(step=step, time_offset_s=time_offset_s, water_g=water_g)

    return _make_pour


@pytest.fixture
def make_suitable():
    """Factory: creates a SuitableFor with valid defaults."""
    def _make_suitable(
        roast_levels=None, origins=None, processes=None, flavor_profiles=None
    ) -> SuitableFor:
        return SuitableFor(
            roast_levels=(
                roast_levels
                if roast_levels is not None
                else [RoastLevel.LIGHT, RoastLevel.MEDIUM]
            ),
            origins=(
                origins if origins is not None else ["Ethiopia", "Colombia"]
            ),
            processes=(
                processes
                if processes is not None
                else [Process.WASHED, Process.NATURAL]
            ),
            flavor_profiles=(
                flavor_profiles
                if flavor_profiles is not None
                else ["Floral", "Citrus"]
            ),
        )

    return _make_suitable


@pytest.fixture
def make_recipe(make_suitable):
    """Factory: creates a Recipe with valid defaults.

    Accepts keyword overrides for any Recipe field. ``pours`` and
    ``suitable_for`` default to valid three-pour V60 values.
    """
    def _make_recipe(**overrides) -> Recipe:
        defaults = dict(
            recipe_id="hoffmann-v60-classic",
            source="James Hoffmann",
            method=BrewMethod.V60,
            dose_g=15.0,
            water_total_g=250.0,
            ratio=16.67,
            grind_setting=5,
            water_temp_c=93.0,
            bloom_time_s=45,
            total_time_s=210,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=50.0),
                PourStep(step=2, time_offset_s=45, water_g=100.0),
                PourStep(step=3, time_offset_s=90, water_g=100.0),
            ],
            suitable_for=make_suitable(),
            instructions="Bloom, then pour in two stages.",
        )
        defaults.update(overrides)
        return Recipe(**defaults)

    return _make_recipe


@pytest.fixture
def make_bean():
    """Factory: creates a BeanProfile with valid defaults."""
    def _make_bean(**overrides) -> BeanProfile:
        defaults = dict(
            origin_country="Ethiopia",
            process=Process.WASHED,
            roast_level=RoastLevel.LIGHT,
            flavor_clusters=["Floral", "Citrus"],
            source_text="Ethiopian Yirgacheffe, light roast, floral and citrus notes",
        )
        defaults.update(overrides)
        return BeanProfile(**defaults)

    return _make_bean


# --- Generator-style fixtures ---


@pytest.fixture
def make_user():
    """Factory: creates a VirtualUser with valid defaults."""
    def _make_user(
        roast: str = "light",
        clusters: list[str] | None = None,
        bias: float = 0.0,
    ) -> VirtualUser:
        return VirtualUser(
            user_id="test-user",
            roast_preference=roast,
            preferred_clusters=clusters or ["Citrus", "Berry"],
            rating_bias=bias,
            acidity_tolerance=0.0,
            body_preference=0.0,
            sweetness_preference=0.0,
            experience_level="intermediate",
        )

    return _make_user


@pytest.fixture
def make_bean_dict():
    """Factory: creates a bean dict (generator-style) with defaults."""
    def _make_bean_dict(
        roast: str = "light",
        process: str = "washed",
        clusters: list[str] | None = None,
    ) -> dict:
        return {
            "roast_level": roast,
            "process": process,
            "flavor_clusters": clusters or ["Citrus", "Berry"],
        }

    return _make_bean_dict


@pytest.fixture
def make_recipe_dict():
    """Factory: creates a recipe params dict with defaults."""
    def _make_recipe_dict(
        temp: float = 95.0,
        grind: int = 5,
        ratio: float = 16.0,
        dose: float = 16.0,
        total: int = 225,
    ) -> dict:
        return {
            "water_temp_c": temp,
            "grind_setting": grind,
            "ratio": ratio,
            "dose_g": dose,
            "total_time_s": total,
            "bloom_time_s": 30,
        }

    return _make_recipe_dict

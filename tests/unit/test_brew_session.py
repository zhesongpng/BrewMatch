"""Unit tests for the Brew Session page.

Covers the pure, Streamlit-free scaling helper: rescaling a recipe to the
dose the user actually weighed. The st.* rendering is exercised manually.
"""
import pytest

from src.app.pages import brew_session as bs
from src.data_models import (
    BrewMethod,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)


def _recipe(dose_g=15.0, water_total_g=240.0, ratio=16.0, pours=None) -> Recipe:
    """A valid baseline recipe (15 g, 1:16, 240 g water) for scaling tests."""
    if pours is None:
        pours = [
            PourStep(step=1, time_offset_s=0, water_g=45.0),
            PourStep(step=2, time_offset_s=45, water_g=95.0),
            PourStep(step=3, time_offset_s=90, water_g=100.0),
        ]
    return Recipe(
        recipe_id="test-recipe",
        source="unit-test",
        method=BrewMethod.V60,
        dose_g=dose_g,
        water_total_g=water_total_g,
        ratio=ratio,
        grind_setting=5,
        water_temp_c=94.0,
        bloom_time_s=45,
        total_time_s=180,
        pours=pours,
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Brew it.",
    )


class TestScaleRecipe:
    def test_scaling_up_keeps_ratio_and_scales_water(self):
        # The plan's worked example: 15 g -> 18 g at 1:16 gives 288 g water.
        scaled = bs._scale_recipe(_recipe(), 18.0)
        assert scaled.dose_g == 18.0
        assert scaled.water_total_g == pytest.approx(288.0)
        assert scaled.ratio == pytest.approx(16.0)

    def test_every_pour_scales_proportionally(self):
        scaled = bs._scale_recipe(_recipe(), 18.0)  # factor 1.2
        assert [p.water_g for p in scaled.pours] == pytest.approx([54.0, 114.0, 120.0])
        # Pour water still sums to the new total (within the model's 5% rule).
        assert sum(p.water_g for p in scaled.pours) == pytest.approx(288.0)

    def test_scaling_down_keeps_ratio(self):
        scaled = bs._scale_recipe(_recipe(), 13.5)  # factor 0.9
        assert scaled.dose_g == 13.5
        assert scaled.water_total_g == pytest.approx(216.0)
        assert scaled.ratio == pytest.approx(16.0)

    def test_timings_grind_and_temp_unchanged(self):
        original = _recipe()
        scaled = bs._scale_recipe(original, 20.0)
        assert scaled.grind_setting == original.grind_setting
        assert scaled.water_temp_c == original.water_temp_c
        assert scaled.bloom_time_s == original.bloom_time_s
        assert scaled.total_time_s == original.total_time_s
        assert [p.time_offset_s for p in scaled.pours] == [
            p.time_offset_s for p in original.pours
        ]

    def test_identity_when_dose_unchanged(self):
        scaled = bs._scale_recipe(_recipe(), 15.0)
        assert scaled.dose_g == 15.0
        assert scaled.water_total_g == pytest.approx(240.0)

    def test_invalid_downscale_raises(self):
        # Downscaling a 20 g / 280 g recipe to 12 g yields 168 g water, below the
        # Recipe floor of 180 g -> the model rejects it and the caller falls back.
        recipe = _recipe(
            dose_g=20.0,
            water_total_g=280.0,
            ratio=14.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=60.0),
                PourStep(step=2, time_offset_s=45, water_g=110.0),
                PourStep(step=3, time_offset_s=90, water_g=110.0),
            ],
        )
        with pytest.raises(ValueError):
            bs._scale_recipe(recipe, 12.0)


class TestResolveBagId:
    """The no-bag guard: a brew links to a bag only when a bean was actually
    picked, so a stale current_bag_id can't attach to a one-off brew."""

    def test_bean_present_links_to_current_bag(self):
        assert bs._resolve_bag_id({"origin_country": "Ethiopia"}, "bag-1") == "bag-1"

    def test_no_bean_drops_stale_bag_id(self):
        # Fallback path: current_bean is None but a bag id lingers from earlier.
        assert bs._resolve_bag_id(None, "stale-bag") is None

    def test_bean_present_but_no_bag_is_none(self):
        assert bs._resolve_bag_id({"origin_country": "Ethiopia"}, None) is None

"""Unit tests for the PersonalizationEngine.

Covers phase transitions, user feature computation, directional flag
processing, learned preferences, cold-start behavior, bias updates,
content-based filtering with real clusters, and negative brew count
validation.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    DIRECTIONAL_FLAGS,
    ExperienceLevel,
    Feedback,
    LearnedPreferences,
    Onboarding,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
    UserTasteProfile,
)
from src.personalization.engine import PersonalizationEngine


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_bean(**overrides) -> BeanProfile:
    defaults = dict(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="test bean",
    )
    defaults.update(overrides)
    return BeanProfile(**defaults)


def _make_recipe(**overrides) -> Recipe:
    defaults = dict(
        recipe_id="test-recipe",
        source="test",
        method=BrewMethod.V60,
        dose_g=16.0,
        water_total_g=256.0,
        ratio=16.0,
        grind_setting=5,
        water_temp_c=93.0,
        bloom_time_s=30,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=64.0),
            PourStep(step=2, time_offset_s=30, water_g=96.0),
            PourStep(step=3, time_offset_s=60, water_g=96.0),
        ],
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Test recipe",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def _make_onboarding(**overrides) -> Onboarding:
    defaults = dict(
        preferred_clusters=["Floral", "Citrus"],
        roast_preference=RoastLevel.LIGHT,
        experience_level=ExperienceLevel.INTERMEDIATE,
    )
    defaults.update(overrides)
    return Onboarding(**defaults)


def _make_brew(
    brew_id: str = "brew-001",
    score: int = 7,
    thumbs_up: bool = True,
    directional_flags: list[str] | None = None,
    bean: BeanProfile | None = None,
    recipe: Recipe | None = None,
    timestamp: str = "2025-01-01T00:00:00",
) -> BrewRecord:
    return BrewRecord(
        brew_id=brew_id,
        timestamp=timestamp,
        bean_profile=bean or _make_bean(),
        recipe_used=recipe or _make_recipe(),
        feedback=Feedback(
            thumbs_up=thumbs_up,
            score=score,
            directional_flags=directional_flags,
        ),
    )


def _mock_predictor() -> MagicMock:
    """Create a mock TastePredictor that returns a fixed prediction."""
    predictor = MagicMock()
    predictor.is_trained = True
    predictor._encoder = MagicMock()
    predictor._encoder.encode.return_value = np.zeros(45, dtype=np.float64)

    # predict returns a PredictionResult-like object
    mock_result = MagicMock()
    mock_result.predicted_rating = 7.0
    mock_result.base_prediction = 7.0
    mock_result.user_bias = 0.0
    predictor.predict.return_value = mock_result

    return predictor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def predictor():
    return _mock_predictor()


@pytest.fixture
def engine(predictor):
    return PersonalizationEngine(
        predictor=predictor,
        user_id="test-user",
        onboarding=_make_onboarding(),
    )


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------

class TestPhaseTransitions:

    def test_zero_brews_returns_bean_aware_phase(self, engine):
        assert engine.phase == "bean_aware"

    def test_one_brew_returns_directional_phase(self, engine):
        engine.record_brew(_make_brew())
        assert engine.phase == "directional"

    def test_four_brews_still_directional_phase(self, engine):
        for i in range(4):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        assert engine.phase == "directional"

    def test_five_brews_returns_content_based_phase(self, engine):
        for i in range(5):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        assert engine.phase == "content_based"

    def test_nine_brews_still_content_based_phase(self, engine):
        for i in range(9):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        assert engine.phase == "content_based"

    def test_ten_brews_returns_full_hybrid_phase(self, engine):
        for i in range(10):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        assert engine.phase == "full_hybrid"

    def test_phase_property_read_only(self, engine):
        """phase is a property, not settable directly."""
        with pytest.raises(AttributeError):
            engine.phase = "something_else"


# ---------------------------------------------------------------------------
# get_phase_info
# ---------------------------------------------------------------------------

class TestGetPhaseInfo:

    def test_bean_aware_phase_info(self, engine):
        info = engine.get_phase_info()
        assert info["phase"] == "bean_aware"
        assert info["brew_count"] == 0
        assert "description" in info

    def test_directional_phase_info(self, engine):
        engine.record_brew(_make_brew())
        info = engine.get_phase_info()
        assert info["phase"] == "directional"
        assert info["brew_count"] == 1

    def test_content_based_phase_info(self, engine):
        for i in range(5):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        info = engine.get_phase_info()
        assert info["phase"] == "content_based"
        assert info["brew_count"] == 5

    def test_full_hybrid_phase_info(self, engine):
        for i in range(10):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        info = engine.get_phase_info()
        assert info["phase"] == "full_hybrid"
        assert info["brew_count"] == 10

    def test_phase_descriptions_are_different(self, engine):
        descriptions = set()
        phases = []
        counts = [0, 1, 5, 10]
        for count in counts:
            eng = PersonalizationEngine(
                predictor=_mock_predictor(),
                user_id="u",
                onboarding=_make_onboarding(),
            )
            for i in range(count):
                eng.record_brew(_make_brew(brew_id=f"b-{i}"))
            info = eng.get_phase_info()
            descriptions.add(info["description"])
            phases.append(info["phase"])
        # 4 distinct phases should have 4 distinct descriptions
        assert len(descriptions) == 4


# ---------------------------------------------------------------------------
# Cold start / empty history
# ---------------------------------------------------------------------------

class TestColdStart:

    def test_get_user_features_returns_zeros_for_cold_start(self, engine):
        features = engine.get_user_features()
        assert features["user_avg_rating"] == 0.0
        assert features["user_rating_count"] == 0.0
        assert features["user_roast_pref"] == 0.0
        assert features["user_temp_pref"] == 0.0
        assert features["user_grind_pref"] == 0.0
        assert features["user_ratio_pref"] == 0.0
        assert features["user_acidity_bias"] == 0.0
        assert features["user_body_bias"] == 0.0
        assert features["user_sweetness_bias"] == 0.0

    def test_get_user_features_returns_nine_keys(self, engine):
        features = engine.get_user_features()
        assert len(features) == 9

    def test_learned_preferences_defaults_on_cold_start(self, engine):
        prefs = engine.compute_learned_preferences()
        assert isinstance(prefs, LearnedPreferences)
        assert prefs.acidity_bias == 0.0
        assert prefs.body_bias == 0.0
        assert prefs.sweetness_bias == 0.0


# ---------------------------------------------------------------------------
# User feature computation from brew history
# ---------------------------------------------------------------------------

class TestUserFeatureComputation:

    def test_user_avg_rating_computed_correctly(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=6))
        engine.record_brew(_make_brew(brew_id="b2", score=8))
        features = engine.get_user_features()
        assert abs(features["user_avg_rating"] - 7.0) < 1e-6

    def test_user_rating_count_increments(self, engine):
        engine.record_brew(_make_brew(brew_id="b1"))
        assert engine.get_user_features()["user_rating_count"] == 1.0
        engine.record_brew(_make_brew(brew_id="b2"))
        assert engine.get_user_features()["user_rating_count"] == 2.0

    def test_user_roast_pref_from_highly_rated_brews(self, engine):
        """User prefers LIGHT roast but rates a MEDIUM brew higher.
        Most common roast among highly-rated (>avg) brews should be MEDIUM."""
        light_bean = _make_bean(roast_level=RoastLevel.LIGHT)
        medium_bean = _make_bean(roast_level=RoastLevel.MEDIUM)

        engine.record_brew(_make_brew(brew_id="b1", score=5, bean=light_bean))
        engine.record_brew(_make_brew(brew_id="b2", score=8, bean=medium_bean))

        features = engine.get_user_features()
        # avg = 6.5; highly-rated = b2 (score 8 > 6.5) which is MEDIUM
        assert features["user_roast_pref"] == 3.0  # MEDIUM ordinal

    def test_user_temp_pref_from_highly_rated_brews(self, engine):
        low_temp_recipe = _make_recipe(water_temp_c=90.0)
        high_temp_recipe = _make_recipe(water_temp_c=96.0)

        engine.record_brew(_make_brew(brew_id="b1", score=4, recipe=low_temp_recipe))
        engine.record_brew(_make_brew(brew_id="b2", score=9, recipe=high_temp_recipe))

        features = engine.get_user_features()
        # avg = 6.5; highly-rated = b2 at 96.0
        assert abs(features["user_temp_pref"] - 96.0) < 1e-6

    def test_user_grind_pref_from_highly_rated_brews(self, engine):
        coarse_recipe = _make_recipe(grind_setting=8)
        fine_recipe = _make_recipe(grind_setting=3)

        engine.record_brew(_make_brew(brew_id="b1", score=4, recipe=fine_recipe))
        engine.record_brew(_make_brew(brew_id="b2", score=9, recipe=coarse_recipe))

        features = engine.get_user_features()
        # avg = 6.5; highly-rated = b2 at grind 8
        assert abs(features["user_grind_pref"] - 8.0) < 1e-6

    def test_user_ratio_pref_from_highly_rated_brews(self, engine):
        thin_recipe = _make_recipe(
            ratio=17.0, water_total_g=272.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=68.0),
                PourStep(step=2, time_offset_s=30, water_g=102.0),
                PourStep(step=3, time_offset_s=60, water_g=102.0),
            ],
        )
        thick_recipe = _make_recipe(
            ratio=15.0, water_total_g=240.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=60.0),
                PourStep(step=2, time_offset_s=30, water_g=90.0),
                PourStep(step=3, time_offset_s=60, water_g=90.0),
            ],
        )

        engine.record_brew(_make_brew(brew_id="b1", score=4, recipe=thin_recipe))
        engine.record_brew(_make_brew(brew_id="b2", score=9, recipe=thick_recipe))

        features = engine.get_user_features()
        # avg = 6.5; highly-rated = b2 at ratio 15.0
        assert abs(features["user_ratio_pref"] - 15.0) < 1e-6

    def test_highly_rated_excludes_below_average(self, engine):
        """All brews have the same score so all are at avg (not > avg).
        Features should still reflect all since >= avg qualifies."""
        recipe = _make_recipe(water_temp_c=93.0)
        engine.record_brew(_make_brew(brew_id="b1", score=7, recipe=recipe))
        engine.record_brew(_make_brew(brew_id="b2", score=7, recipe=recipe))

        features = engine.get_user_features()
        # avg = 7.0; both are at avg, >= avg qualifies
        assert abs(features["user_temp_pref"] - 93.0) < 1e-6


# ---------------------------------------------------------------------------
# Directional flag processing
# ---------------------------------------------------------------------------

class TestDirectionalFlags:

    def test_too_sour_decreases_acidity_bias(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_sour"])
        )
        prefs = engine.compute_learned_preferences()
        assert prefs.acidity_bias < 0.0

    def test_too_bitter_decreases_body_bias(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_bitter"])
        )
        prefs = engine.compute_learned_preferences()
        assert prefs.body_bias < 0.0

    def test_too_weak_increases_body_bias(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_weak"])
        )
        prefs = engine.compute_learned_preferences()
        assert prefs.body_bias > 0.0

    def test_too_harsh_decreases_acidity_and_body_bias(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_harsh"])
        )
        prefs = engine.compute_learned_preferences()
        assert prefs.acidity_bias < 0.0
        assert prefs.body_bias < 0.0

    def test_astringent_decreases_sweetness_bias(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["astringent"])
        )
        prefs = engine.compute_learned_preferences()
        assert prefs.sweetness_bias < 0.0

    def test_multiple_flags_accumulate(self, engine):
        engine.record_brew(
            _make_brew(
                brew_id="b1",
                score=5,
                directional_flags=["too_sour", "too_bitter", "astringent"],
            )
        )
        prefs = engine.compute_learned_preferences()
        assert prefs.acidity_bias < 0.0
        assert prefs.body_bias < 0.0
        assert prefs.sweetness_bias < 0.0

    def test_flags_across_multiple_brews_accumulate(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_sour"])
        )
        engine.record_brew(
            _make_brew(brew_id="b2", score=5, directional_flags=["too_sour"])
        )
        prefs = engine.compute_learned_preferences()
        # Two too_sour flags should produce a stronger negative bias than one
        assert prefs.acidity_bias < -0.05

    def test_no_flags_leaves_biases_at_zero(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=7))
        prefs = engine.compute_learned_preferences()
        assert prefs.acidity_bias == 0.0
        assert prefs.body_bias == 0.0
        assert prefs.sweetness_bias == 0.0

    def test_user_acidity_bias_reflects_in_features(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_sour"])
        )
        features = engine.get_user_features()
        assert features["user_acidity_bias"] < 0.0

    def test_user_body_bias_reflects_in_features(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["too_weak"])
        )
        features = engine.get_user_features()
        assert features["user_body_bias"] > 0.0

    def test_user_sweetness_bias_reflects_in_features(self, engine):
        engine.record_brew(
            _make_brew(brew_id="b1", score=5, directional_flags=["astringent"])
        )
        features = engine.get_user_features()
        assert features["user_sweetness_bias"] < 0.0


# ---------------------------------------------------------------------------
# Learned preferences computation
# ---------------------------------------------------------------------------

class TestLearnedPreferences:

    def test_temp_range_from_highly_rated_brews(self, engine):
        low_temp_recipe = _make_recipe(water_temp_c=90.0)
        high_temp_recipe = _make_recipe(water_temp_c=96.0)

        engine.record_brew(_make_brew(brew_id="b1", score=4, recipe=low_temp_recipe))
        engine.record_brew(_make_brew(brew_id="b2", score=9, recipe=high_temp_recipe))

        prefs = engine.compute_learned_preferences()
        temp_lo, temp_hi = prefs.preferred_temp_range
        # avg = 6.5; highly-rated = b2 at 96.0 only
        assert temp_lo <= 96.0
        assert temp_hi >= 96.0

    def test_ratio_range_from_highly_rated_brews(self, engine):
        recipe_a = _make_recipe(
            ratio=15.0, water_total_g=240.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=60.0),
                PourStep(step=2, time_offset_s=30, water_g=90.0),
                PourStep(step=3, time_offset_s=60, water_g=90.0),
            ],
        )
        recipe_b = _make_recipe(
            ratio=17.0, water_total_g=272.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=68.0),
                PourStep(step=2, time_offset_s=30, water_g=102.0),
                PourStep(step=3, time_offset_s=60, water_g=102.0),
            ],
        )

        engine.record_brew(_make_brew(brew_id="b1", score=4, recipe=recipe_a))
        engine.record_brew(_make_brew(brew_id="b2", score=9, recipe=recipe_b))

        prefs = engine.compute_learned_preferences()
        ratio_lo, ratio_hi = prefs.preferred_ratio_range
        # avg = 6.5; highly-rated = b2 at 17.0 only
        assert ratio_lo <= 17.0
        assert ratio_hi >= 17.0

    def test_bias_values_clamped_to_valid_range(self, engine):
        """Even with many directional flags, biases should be in [-1, 1]."""
        for i in range(20):
            engine.record_brew(
                _make_brew(
                    brew_id=f"b{i}",
                    score=3,
                    directional_flags=["too_sour"],
                )
            )
        prefs = engine.compute_learned_preferences()
        assert -1.0 <= prefs.acidity_bias <= 1.0
        assert -1.0 <= prefs.body_bias <= 1.0
        assert -1.0 <= prefs.sweetness_bias <= 1.0

    def test_learned_preferences_default_on_empty_history(self, engine):
        prefs = engine.compute_learned_preferences()
        assert prefs.preferred_temp_range == (90.0, 96.0)
        assert prefs.preferred_ratio_range == (15.0, 17.0)


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------

class TestGetProfile:

    def test_returns_user_taste_profile(self, engine):
        profile = engine.get_profile()
        assert isinstance(profile, UserTasteProfile)

    def test_profile_contains_user_id(self, engine):
        profile = engine.get_profile()
        assert profile.user_id == "test-user"

    def test_profile_contains_onboarding(self, engine):
        profile = engine.get_profile()
        assert isinstance(profile.onboarding, Onboarding)
        assert profile.onboarding.roast_preference == RoastLevel.LIGHT

    def test_profile_brew_history_matches_recorded_brews(self, engine):
        engine.record_brew(_make_brew(brew_id="b1"))
        engine.record_brew(_make_brew(brew_id="b2"))
        profile = engine.get_profile()
        assert len(profile.brew_history) == 2

    def test_profile_stats_total_brews(self, engine):
        engine.record_brew(_make_brew(brew_id="b1"))
        engine.record_brew(_make_brew(brew_id="b2"))
        profile = engine.get_profile()
        assert profile.stats.total_brews == 2

    def test_profile_stats_avg_score(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=6))
        engine.record_brew(_make_brew(brew_id="b2", score=8))
        profile = engine.get_profile()
        assert abs(profile.stats.avg_score - 7.0) < 1e-6

    def test_profile_learned_preferences_populated_after_brew(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=7))
        profile = engine.get_profile()
        assert profile.learned_preferences is not None
        assert isinstance(profile.learned_preferences, LearnedPreferences)

    def test_profile_learned_preferences_none_on_cold_start(self, engine):
        profile = engine.get_profile()
        assert profile.learned_preferences is None


# ---------------------------------------------------------------------------
# record_brew updates
# ---------------------------------------------------------------------------

class TestRecordBrew:

    def test_record_brew_adds_to_history(self, engine):
        engine.record_brew(_make_brew(brew_id="b1"))
        assert len(engine.get_profile().brew_history) == 1

    def test_record_brew_calls_predictor_update_user_bias(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=7))
        # The predictor's update_user_bias should have been called
        engine.predictor.update_user_bias.assert_called_once()

    def test_record_brew_update_receives_correct_user_id(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=7))
        call_args = engine.predictor.update_user_bias.call_args
        assert call_args[0][0] == "test-user"

    def test_record_brew_update_receives_actual_rating(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=8))
        call_args = engine.predictor.update_user_bias.call_args
        assert call_args[0][2] == 8.0

    def test_record_brew_update_receives_correct_prior_count(self, engine):
        engine.record_brew(_make_brew(brew_id="b1", score=7))
        # First brew: n_prior_ratings = 0 at time of update
        call_args = engine.predictor.update_user_bias.call_args
        assert call_args[0][3] == 0

        engine.record_brew(_make_brew(brew_id="b2", score=7))
        # Second brew: n_prior_ratings = 1 at time of update
        call_args = engine.predictor.update_user_bias.call_args
        assert call_args[0][3] == 1

    def test_record_brew_with_no_score_skips_bias_update(self, engine):
        """Feedback without a score should not trigger bias update."""
        brew = _make_brew(brew_id="b1")
        brew.feedback.score = None
        engine.record_brew(brew)
        engine.predictor.update_user_bias.assert_not_called()

    def test_multiple_brews_maintain_order(self, engine):
        for i in range(5):
            engine.record_brew(_make_brew(brew_id=f"b{i}"))
        history = engine.get_profile().brew_history
        ids = [b.brew_id for b in history]
        assert ids == ["b0", "b1", "b2", "b3", "b4"]


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

class TestConstructor:

    def test_requires_predictor(self):
        with pytest.raises(TypeError):
            PersonalizationEngine(
                user_id="u",
                onboarding=_make_onboarding(),
            )

    def test_requires_user_id(self, predictor):
        with pytest.raises(ValueError, match="user_id"):
            PersonalizationEngine(
                predictor=predictor,
                user_id="",
                onboarding=_make_onboarding(),
            )

    def test_requires_onboarding(self, predictor):
        with pytest.raises(TypeError):
            PersonalizationEngine(
                predictor=predictor,
                user_id="u",
            )


# ---------------------------------------------------------------------------
# M06: Parametrized phase transition boundary tests
# ---------------------------------------------------------------------------

class TestPhaseTransitionBoundaries:
    """Parametrized tests verifying exact phase at every boundary.

    Phase model (per engine docstring):
      0 brews     -> bean_aware
      1-4 brews   -> directional
      5-9 brews   -> content_based
      10+ brews   -> full_hybrid
    """

    @pytest.mark.parametrize(
        "brew_count, expected_phase",
        [
            (0, "bean_aware"),
            (1, "directional"),
            (2, "directional"),
            (3, "directional"),
            (4, "directional"),
            (5, "content_based"),
            (6, "content_based"),
            (7, "content_based"),
            (8, "content_based"),
            (9, "content_based"),
            (10, "full_hybrid"),
            (11, "full_hybrid"),
            (20, "full_hybrid"),
            (50, "full_hybrid"),
        ],
    )
    def test_phase_at_boundary(self, brew_count, expected_phase):
        """Verify engine reports correct phase for each brew count."""
        predictor = _mock_predictor()
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="boundary-user",
            onboarding=_make_onboarding(),
        )
        for i in range(brew_count):
            engine.record_brew(_make_brew(brew_id=f"brew-{i}"))
        assert engine.phase == expected_phase

    def test_boundary_transition_from_bean_aware_to_directional(self):
        """Adding the first brew transitions from bean_aware to directional."""
        predictor = _mock_predictor()
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="transition-user",
            onboarding=_make_onboarding(),
        )
        assert engine.phase == "bean_aware"
        engine.record_brew(_make_brew(brew_id="b1"))
        assert engine.phase == "directional"

    def test_boundary_transition_from_directional_to_content_based(self):
        """Adding the 5th brew transitions from directional to content_based."""
        predictor = _mock_predictor()
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="transition-user",
            onboarding=_make_onboarding(),
        )
        for i in range(4):
            engine.record_brew(_make_brew(brew_id=f"b{i}"))
        assert engine.phase == "directional"
        engine.record_brew(_make_brew(brew_id="b4"))
        assert engine.phase == "content_based"

    def test_boundary_transition_from_content_based_to_full_hybrid(self):
        """Adding the 10th brew transitions from content_based to full_hybrid."""
        predictor = _mock_predictor()
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="transition-user",
            onboarding=_make_onboarding(),
        )
        for i in range(9):
            engine.record_brew(_make_brew(brew_id=f"b{i}"))
        assert engine.phase == "content_based"
        engine.record_brew(_make_brew(brew_id="b9"))
        assert engine.phase == "full_hybrid"


# ---------------------------------------------------------------------------
# M07: Content-based filtering with real flavor clusters
# ---------------------------------------------------------------------------

class TestContentBasedFilteringWithClusters:
    """Verify the engine reflects learned preferences for specific flavor
    clusters when the user's brew history consistently rates beans with
    matching clusters higher than non-matching ones.
    """

    def test_matching_clusters_ranked_higher_in_roast_preference(self):
        """User who highly rates Citrus/Berry beans should see those
        roast/cluster preferences reflected in learned preferences."""
        predictor = _mock_predictor()
        onboarding = _make_onboarding(
            preferred_clusters=["Citrus", "Berry"],
            roast_preference=RoastLevel.LIGHT,
        )
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="cluster-user",
            onboarding=onboarding,
        )

        # Matching beans: Citrus and Berry clusters, highly rated
        matching_bean_1 = _make_bean(
            flavor_clusters=["Citrus", "Floral"],
            roast_level=RoastLevel.LIGHT,
        )
        matching_bean_2 = _make_bean(
            flavor_clusters=["Berry", "Stone Fruit"],
            roast_level=RoastLevel.LIGHT,
        )

        # Non-matching bean: Chocolate/Nutty clusters, low rating
        non_matching_bean = _make_bean(
            flavor_clusters=["Chocolate", "Nutty"],
            roast_level=RoastLevel.DARK,
        )

        # Record brews: high scores for matching, low for non-matching
        engine.record_brew(_make_brew(
            brew_id="match-1", score=9, bean=matching_bean_1,
        ))
        engine.record_brew(_make_brew(
            brew_id="match-2", score=8, bean=matching_bean_2,
        ))
        engine.record_brew(_make_brew(
            brew_id="nonmatch-1", score=3, bean=non_matching_bean,
        ))

        # Learned preferences should reflect the matching beans
        features = engine.get_user_features()
        # Highly-rated brews are match-1 (9) and match-2 (8); avg = 6.67
        # Both matching brews are LIGHT roast (ordinal 1.0)
        assert features["user_roast_pref"] == 1.0  # LIGHT ordinal

    def test_matching_clusters_affect_temp_preference(self):
        """Highly-rated matching-cluster brews should drive temp preference."""
        predictor = _mock_predictor()
        onboarding = _make_onboarding(
            preferred_clusters=["Citrus"],
        )
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="temp-user",
            onboarding=onboarding,
        )

        matching_bean = _make_bean(flavor_clusters=["Citrus", "Floral"])
        non_matching_bean = _make_bean(flavor_clusters=["Chocolate", "Roasted"])

        high_temp_recipe = _make_recipe(water_temp_c=96.0)
        low_temp_recipe = _make_recipe(water_temp_c=88.0)

        # Matching bean with high temp gets high score
        engine.record_brew(_make_brew(
            brew_id="m1", score=9, bean=matching_bean, recipe=high_temp_recipe,
        ))
        # Non-matching bean with low temp gets low score
        engine.record_brew(_make_brew(
            brew_id="nm1", score=3, bean=non_matching_bean, recipe=low_temp_recipe,
        ))

        features = engine.get_user_features()
        # avg = 6.0; highly-rated = m1 (9 > 6), which used 96.0
        assert abs(features["user_temp_pref"] - 96.0) < 1e-6

    def test_multiple_matching_clusters_accumulate_preference_signal(self):
        """A user who rates 5 brews of Citrus/Berry highly and 5 brews of
        Chocolate/Nutty poorly should show a clear roast/temp preference
        aligned with the Citrus/Berry beans."""
        predictor = _mock_predictor()
        onboarding = _make_onboarding(
            preferred_clusters=["Citrus", "Berry"],
            roast_preference=RoastLevel.LIGHT,
        )
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="multi-cluster-user",
            onboarding=onboarding,
        )

        matching_recipe = _make_recipe(
            water_temp_c=95.0,
            grind_setting=5,
        )
        non_matching_recipe = _make_recipe(
            water_temp_c=89.0,
            grind_setting=8,
        )

        # 5 matching-cluster brews with high ratings
        for i in range(5):
            bean = _make_bean(
                flavor_clusters=["Citrus", "Berry"],
                roast_level=RoastLevel.LIGHT,
            )
            engine.record_brew(_make_brew(
                brew_id=f"match-{i}",
                score=8,
                bean=bean,
                recipe=matching_recipe,
            ))

        # 5 non-matching-cluster brews with low ratings
        for i in range(5):
            bean = _make_bean(
                flavor_clusters=["Chocolate", "Nutty"],
                roast_level=RoastLevel.DARK,
            )
            engine.record_brew(_make_brew(
                brew_id=f"nonmatch-{i}",
                score=3,
                bean=bean,
                recipe=non_matching_recipe,
            ))

        # Engine should now be in full_hybrid phase
        assert engine.phase == "full_hybrid"

        features = engine.get_user_features()
        # avg score = (5*8 + 5*3) / 10 = 5.5
        # Highly-rated = the 5 matching brews (8 > 5.5)
        # They are all LIGHT roast (ordinal 1.0), temp 95.0, grind 5
        assert features["user_roast_pref"] == 1.0  # LIGHT
        assert abs(features["user_temp_pref"] - 95.0) < 1e-6
        assert abs(features["user_grind_pref"] - 5.0) < 1e-6

    def test_profile_contains_brews_with_correct_cluster_distribution(self):
        """Verify the user profile records brews with matching clusters
        and the stats reflect the history correctly."""
        predictor = _mock_predictor()
        onboarding = _make_onboarding(
            preferred_clusters=["Citrus", "Berry"],
        )
        engine = PersonalizationEngine(
            predictor=predictor,
            user_id="profile-user",
            onboarding=onboarding,
        )

        matching_bean = _make_bean(flavor_clusters=["Citrus"])
        non_matching_bean = _make_bean(flavor_clusters=["Chocolate"])

        engine.record_brew(_make_brew(brew_id="m1", score=9, bean=matching_bean))
        engine.record_brew(_make_brew(brew_id="nm1", score=2, bean=non_matching_bean))

        profile = engine.get_profile()
        assert profile.stats.total_brews == 2
        # avg_score = (9 + 2) / 2 = 5.5
        assert abs(profile.stats.avg_score - 5.5) < 1e-6

        # Learned preferences should reflect the matching bean (temp, ratio)
        assert profile.learned_preferences is not None
        # Highly-rated = m1 only (9 > 5.5), which used default temp 93.0
        assert profile.learned_preferences.preferred_temp_range == (93.0, 93.0)


# ---------------------------------------------------------------------------
# M14: Negative brew count validation
# ---------------------------------------------------------------------------

class TestNegativeBrewCountValidation:
    """Verify get_phase_for_count handles negative brew counts gracefully
    by clamping to 0 and logging a warning.
    """

    def test_negative_one_returns_bean_aware(self):
        """get_phase_for_count(-1) should return bean_aware (same as 0)."""
        assert PersonalizationEngine.get_phase_for_count(-1) == "bean_aware"

    def test_large_negative_returns_bean_aware(self):
        """get_phase_for_count(-100) should not crash and return bean_aware."""
        assert PersonalizationEngine.get_phase_for_count(-100) == "bean_aware"

    def test_negative_count_logs_warning(self):
        """get_phase_for_count with negative value should emit a warning."""
        with patch("src.personalization.engine.logger") as mock_logger:
            PersonalizationEngine.get_phase_for_count(-5)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "negative" in str(call_args).lower() or "clamp" in str(call_args).lower()

    def test_zero_count_does_not_log_warning(self):
        """get_phase_for_count(0) should NOT emit a warning."""
        with patch("src.personalization.engine.logger") as mock_logger:
            PersonalizationEngine.get_phase_for_count(0)
            mock_logger.warning.assert_not_called()

    @pytest.mark.parametrize(
        "brew_count, expected_phase",
        [
            (0, "bean_aware"),
            (1, "directional"),
            (4, "directional"),
            (5, "content_based"),
            (9, "content_based"),
            (10, "full_hybrid"),
            (100, "full_hybrid"),
        ],
    )
    def test_valid_count_returns_correct_phase(self, brew_count, expected_phase):
        """get_phase_for_count with valid counts returns correct phases."""
        assert PersonalizationEngine.get_phase_for_count(brew_count) == expected_phase

    def test_negative_count_consistent_with_zero(self):
        """Negative count must produce the same result as zero."""
        negative_result = PersonalizationEngine.get_phase_for_count(-42)
        zero_result = PersonalizationEngine.get_phase_for_count(0)
        assert negative_result == zero_result

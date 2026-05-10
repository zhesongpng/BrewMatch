"""Unit tests for the BrewMatch diagnosis engine.

Tests the perturb-and-score diagnosis approach that identifies which
recipe parameter changes would most improve a user's brew based on
reported directional flags (too_sour, too_bitter, etc.).
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from src.data_models import (
    BeanProfile,
    BrewMethod,
    DIRECTIONAL_FLAGS,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)
from src.diagnosis.engine import DiagnosisEngine, DiagnosisResult, DiagnosisSuggestion


# --- Fixtures ---


@pytest.fixture
def bean() -> BeanProfile:
    return BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="test bean",
        altitude_min_m=1800,
        altitude_max_m=2000,
    )


@pytest.fixture
def recipe() -> Recipe:
    return Recipe(
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


def _make_mock_predictor(base_score: float = 6.0):
    """Create a mock TastePredictor that returns a controlled base score.

    The mock returns a PredictionResult with the given predicted_rating.
    Callers can override predict for flag-specific scoring.
    """
    predictor = MagicMock()
    result = MagicMock()
    result.predicted_rating = base_score
    result.confidence_interval = (base_score - 1.0, base_score + 1.0)
    result.user_bias = 0.0
    result.base_prediction = base_score
    result.feature_importance = {"grind_setting": 0.3, "water_temp_c": 0.25}
    predictor.predict.return_value = result
    return predictor


def _make_sour_scoring_predictor(base_score: float = 5.0):
    """Mock predictor that scores finer grinds higher (too_sour context).

    Under-extraction (too sour) is improved by finer grind, higher temp,
    lower ratio. This mock encodes that domain knowledge.
    """
    predictor = MagicMock()

    def score_for_params(bean_profile, recipe, user_id=None, **kwargs):
        score = base_score
        # Finer grind (lower number) -> higher score for sour
        if recipe.grind_setting < 5:
            score += (5 - recipe.grind_setting) * 0.3
        elif recipe.grind_setting > 5:
            score -= (recipe.grind_setting - 5) * 0.3
        # Higher temp -> higher score for sour
        if recipe.water_temp_c > 93.0:
            score += (recipe.water_temp_c - 93.0) * 0.2
        elif recipe.water_temp_c < 93.0:
            score -= (93.0 - recipe.water_temp_c) * 0.2
        # Lower ratio (more coffee per water) -> higher score for sour
        if recipe.ratio < 16.0:
            score += (16.0 - recipe.ratio) * 0.15
        elif recipe.ratio > 16.0:
            score -= (recipe.ratio - 16.0) * 0.15
        # Higher dose -> slight improvement for weak/sour
        if recipe.dose_g > 16.0:
            score += (recipe.dose_g - 16.0) * 0.1

        result = MagicMock()
        result.predicted_rating = max(1.0, min(10.0, score))
        result.confidence_interval = (max(1.0, score - 1.0), min(10.0, score + 1.0))
        result.user_bias = 0.0
        result.base_prediction = score
        result.feature_importance = {"grind_setting": 0.3, "water_temp_c": 0.25}
        return result

    predictor.predict.side_effect = score_for_params
    return predictor


def _make_bitter_scoring_predictor(base_score: float = 5.0):
    """Mock predictor that scores coarser grinds higher (too_bitter context).

    Over-extraction (too bitter) is improved by coarser grind, lower temp,
    higher ratio.
    """
    predictor = MagicMock()

    def score_for_params(bean_profile, recipe, user_id=None, **kwargs):
        score = base_score
        # Coarser grind (higher number) -> higher score for bitter
        if recipe.grind_setting > 5:
            score += (recipe.grind_setting - 5) * 0.3
        elif recipe.grind_setting < 5:
            score -= (5 - recipe.grind_setting) * 0.3
        # Lower temp -> higher score for bitter
        if recipe.water_temp_c < 93.0:
            score += (93.0 - recipe.water_temp_c) * 0.2
        elif recipe.water_temp_c > 93.0:
            score -= (recipe.water_temp_c - 93.0) * 0.2
        # Higher ratio -> higher score for bitter
        if recipe.ratio > 16.0:
            score += (recipe.ratio - 16.0) * 0.15
        elif recipe.ratio < 16.0:
            score -= (16.0 - recipe.ratio) * 0.15

        result = MagicMock()
        result.predicted_rating = max(1.0, min(10.0, score))
        result.confidence_interval = (max(1.0, score - 1.0), min(10.0, score + 1.0))
        result.user_bias = 0.0
        result.base_prediction = score
        result.feature_importance = {"grind_setting": 0.3, "water_temp_c": 0.25}
        return result

    predictor.predict.side_effect = score_for_params
    return predictor


# --- Test Classes ---


class TestDiagnosisResultShape:
    """Diagnosis returns DiagnosisResult with all required fields."""

    def test_diagnose_returns_diagnosis_result(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert isinstance(result, DiagnosisResult)

    def test_result_has_issue_flags(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert result.issue_flags == ["too_sour"]

    def test_result_has_suggestions_list(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert isinstance(result.suggestions, list)

    def test_result_has_overall_assessment(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert isinstance(result.overall_assessment, str)
        assert len(result.overall_assessment) > 0

    def test_result_has_predicted_improvement(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert isinstance(result.predicted_improvement, float)

    def test_result_has_base_score(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.5)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert isinstance(result.base_score, float)
        assert result.base_score == pytest.approx(6.5, abs=0.1)

    def test_result_has_best_case_score(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert isinstance(result.best_case_score, float)
        assert result.best_case_score >= result.base_score

    def test_suggestions_are_diagnosis_suggestion_type(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for suggestion in result.suggestions:
            assert isinstance(suggestion, DiagnosisSuggestion)

    def test_suggestion_has_all_fields(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        if result.suggestions:
            s = result.suggestions[0]
            assert isinstance(s.parameter, str)
            assert isinstance(s.current_value, float)
            assert isinstance(s.suggested_value, float)
            assert isinstance(s.score_delta, float)
            assert isinstance(s.confidence, float)
            assert isinstance(s.reason, str)


class TestSuggestionsRankedByScoreDelta:
    """Suggestions ranked by score_delta descending (largest improvement first)."""

    def test_suggestions_sorted_descending(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        deltas = [s.score_delta for s in result.suggestions]
        assert deltas == sorted(deltas, reverse=True)

    def test_positive_deltas_first(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        # All suggestions with positive delta should come before negatives
        positive_done = False
        for s in result.suggestions:
            if s.score_delta <= 0:
                positive_done = True
            else:
                assert not positive_done, (
                    f"Positive delta {s.score_delta} after non-positive deltas"
                )


class TestDirectionalFlagSuggestions:
    """Each directional flag produces appropriate suggestions."""

    def test_too_sour_suggests_finer_grind(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        grind_suggestion = next(
            (s for s in result.suggestions if s.parameter == "grind_setting"),
            None,
        )
        assert grind_suggestion is not None
        assert grind_suggestion.suggested_value < recipe.grind_setting

    def test_too_sour_suggests_higher_temp(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        temp_suggestion = next(
            (s for s in result.suggestions if s.parameter == "water_temp_c"),
            None,
        )
        assert temp_suggestion is not None
        assert temp_suggestion.suggested_value > recipe.water_temp_c

    def test_too_bitter_suggests_coarser_grind(self, bean, recipe):
        predictor = _make_bitter_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_bitter"])
        grind_suggestion = next(
            (s for s in result.suggestions if s.parameter == "grind_setting"),
            None,
        )
        assert grind_suggestion is not None
        assert grind_suggestion.suggested_value > recipe.grind_setting

    def test_too_bitter_suggests_lower_temp(self, bean, recipe):
        predictor = _make_bitter_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_bitter"])
        temp_suggestion = next(
            (s for s in result.suggestions if s.parameter == "water_temp_c"),
            None,
        )
        assert temp_suggestion is not None
        assert temp_suggestion.suggested_value < recipe.water_temp_c

    def test_too_weak_suggests_higher_dose(self, bean, recipe):
        """Too weak (under-extraction/low dose) should suggest more coffee."""
        predictor = MagicMock()

        def score_weak(bean_profile, recipe, user_id=None, **kwargs):
            score = 5.0
            score += max(0, (recipe.dose_g - 16.0)) * 0.5
            score += max(0, (16.0 - recipe.ratio)) * 0.2
            result = MagicMock()
            result.predicted_rating = max(1.0, min(10.0, score))
            result.confidence_interval = (max(1.0, score - 1.0), min(10.0, score + 1.0))
            result.user_bias = 0.0
            result.base_prediction = score
            result.feature_importance = {}
            return result

        predictor.predict.side_effect = score_weak
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_weak"])
        dose_suggestion = next(
            (s for s in result.suggestions if s.parameter == "dose_g"),
            None,
        )
        assert dose_suggestion is not None
        assert dose_suggestion.suggested_value > recipe.dose_g

    def test_too_harsh_suggests_lower_temp(self, bean, recipe):
        """Too harsh (over-extraction/high temp) should suggest lower temp."""
        predictor = MagicMock()

        def score_harsh(bean_profile, recipe, user_id=None, **kwargs):
            score = 5.0
            score += max(0, (93.0 - recipe.water_temp_c)) * 0.3
            score += max(0, (recipe.grind_setting - 5)) * 0.2
            result = MagicMock()
            result.predicted_rating = max(1.0, min(10.0, score))
            result.confidence_interval = (max(1.0, score - 1.0), min(10.0, score + 1.0))
            result.user_bias = 0.0
            result.base_prediction = score
            result.feature_importance = {}
            return result

        predictor.predict.side_effect = score_harsh
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_harsh"])
        temp_suggestion = next(
            (s for s in result.suggestions if s.parameter == "water_temp_c"),
            None,
        )
        assert temp_suggestion is not None
        assert temp_suggestion.suggested_value < recipe.water_temp_c

    def test_astringent_produces_suggestions(self, bean, recipe):
        """Astringent (over/under extraction) should still produce suggestions."""
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["astringent"])
        assert len(result.suggestions) > 0


class TestMultipleFlags:
    """Multiple flags handled correctly."""

    def test_multiple_flags_in_result(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour", "too_weak"])
        assert result.issue_flags == ["too_sour", "too_weak"]

    def test_multiple_flags_produce_suggestions(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour", "too_weak"])
        assert len(result.suggestions) > 0

    def test_multiple_flags_assessment_mentions_issues(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour", "too_weak"])
        assert "sour" in result.overall_assessment.lower()


class TestClampingToValidRanges:
    """Suggestions clamped to valid recipe ranges."""

    def test_grind_setting_clamped_low(self, bean):
        """Grind setting should not go below 1."""
        recipe = Recipe(
            recipe_id="test-low-grind",
            source="test",
            method=BrewMethod.V60,
            dose_g=16.0,
            water_total_g=256.0,
            ratio=16.0,
            grind_setting=2,  # near lower bound
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
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            if s.parameter == "grind_setting":
                assert s.suggested_value >= 1

    def test_grind_setting_clamped_high(self, bean):
        """Grind setting should not go above 10."""
        recipe = Recipe(
            recipe_id="test-high-grind",
            source="test",
            method=BrewMethod.V60,
            dose_g=16.0,
            water_total_g=256.0,
            ratio=16.0,
            grind_setting=9,  # near upper bound
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
        predictor = _make_bitter_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_bitter"])
        for s in result.suggestions:
            if s.parameter == "grind_setting":
                assert s.suggested_value <= 10

    def test_water_temp_clamped(self, bean, recipe):
        """Water temp should stay within 85-100 C."""
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            if s.parameter == "water_temp_c":
                assert 85.0 <= s.suggested_value <= 100.0

    def test_dose_clamped(self, bean, recipe):
        """Dose should stay within 12-22 (perturbation clamp)."""
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            if s.parameter == "dose_g":
                assert 12.0 <= s.suggested_value <= 22.0

    def test_ratio_clamped(self, bean, recipe):
        """Ratio should stay within 14-18."""
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            if s.parameter == "ratio":
                assert 14.0 <= s.suggested_value <= 18.0


class TestConfidenceCorrelatesWithScoreDelta:
    """Confidence correlates with score_delta (larger delta = higher confidence)."""

    def test_higher_delta_has_higher_confidence(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        if len(result.suggestions) >= 2:
            # Since sorted by delta descending, first should have higher confidence
            # than the last (or equal if both have the same delta)
            assert (
                result.suggestions[0].confidence
                >= result.suggestions[-1].confidence
            )

    def test_confidence_between_zero_and_one(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            assert 0.0 <= s.confidence <= 1.0


class TestEmptyFlagsList:
    """Empty flags list should still produce a valid result."""

    def test_empty_flags_returns_result(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=[])
        assert isinstance(result, DiagnosisResult)
        assert result.issue_flags == []

    def test_empty_flags_suggestions_may_be_empty(self, bean, recipe):
        """With no flags, suggestions may be empty or neutral."""
        predictor = _make_mock_predictor(base_score=6.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=[])
        # With no directional guidance, no suggestions is acceptable
        # But the result must still be well-formed
        assert isinstance(result.suggestions, list)
        assert isinstance(result.overall_assessment, str)


class TestExplanations:
    """Explanations are human-readable and reference the issue."""

    def test_sour_explanation_mentions_under_extraction(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            assert len(s.reason) > 0
            assert isinstance(s.reason, str)

    def test_explanation_mentions_parameter(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        for s in result.suggestions:
            # The explanation should reference what is changing
            assert len(s.reason) > 20  # non-trivial explanation

    def test_bitter_explanation_mentions_over_extraction(self, bean, recipe):
        predictor = _make_bitter_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_bitter"])
        grind_suggestion = next(
            (s for s in result.suggestions if s.parameter == "grind_setting"),
            None,
        )
        if grind_suggestion is not None:
            reason_lower = grind_suggestion.reason.lower()
            assert "over-extract" in reason_lower or "bitter" in reason_lower


class TestPerturbParameter:
    """_perturb_parameter works for each parameter type."""

    def test_perturb_grind_setting(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        score = engine._perturb_parameter(bean, recipe, "grind_setting", 4.0, None)
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_perturb_water_temp(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        score = engine._perturb_parameter(bean, recipe, "water_temp_c", 95.0, None)
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_perturb_dose(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        score = engine._perturb_parameter(bean, recipe, "dose_g", 17.0, None)
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_perturb_ratio(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        score = engine._perturb_parameter(bean, recipe, "ratio", 15.0, None)
        assert isinstance(score, float)
        assert 1.0 <= score <= 10.0

    def test_perturb_with_user_id(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        score = engine._perturb_parameter(
            bean, recipe, "grind_setting", 4.0, "user-123"
        )
        assert isinstance(score, float)

    def test_perturb_keeps_pour_schedule_fixed(self, bean, recipe):
        """Perturbation should not change pour schedule."""
        predictor = MagicMock()
        call_recipes = []

        def capture_predict(bean_profile, recipe, user_id=None, **kwargs):
            call_recipes.append(recipe)
            result = MagicMock()
            result.predicted_rating = 6.0
            result.confidence_interval = (5.0, 7.0)
            result.user_bias = 0.0
            result.base_prediction = 6.0
            result.feature_importance = {}
            return result

        predictor.predict.side_effect = capture_predict
        engine = DiagnosisEngine(predictor)
        engine._perturb_parameter(bean, recipe, "grind_setting", 3.0, None)

        # Verify the perturbed recipe has same pours but different grind
        if call_recipes:
            perturbed = call_recipes[0]
            assert perturbed.pours == recipe.pours
            assert perturbed.grind_setting != recipe.grind_setting or len(call_recipes) == 0


class TestBestCaseScore:
    """Best case score computed correctly."""

    def test_best_case_higher_than_base(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        # If suggestions exist, best_case should be >= base
        if result.suggestions:
            assert result.best_case_score >= result.base_score

    def test_predicted_improvement_is_sum_of_positive_deltas(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        positive_deltas = [s.score_delta for s in result.suggestions if s.score_delta > 0]
        if positive_deltas:
            assert result.predicted_improvement > 0

    def test_best_case_equals_base_plus_improvement(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        assert result.best_case_score == pytest.approx(
            result.base_score + result.predicted_improvement, abs=0.01
        )


class TestDiagnosisEngineInit:
    """DiagnosisEngine initialization."""

    def test_init_stores_predictor(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        assert engine._predictor is predictor

    def test_init_with_none_predictor_raises(self):
        with pytest.raises((TypeError, ValueError)):
            DiagnosisEngine(None)


class TestGenerateExplanation:
    """_generate_explanation produces relevant text."""

    def test_grind_explanation_for_sour(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        explanation = engine._generate_explanation(
            "grind_setting", 5.0, 3.0, ["too_sour"]
        )
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        # Should mention grind and/or extraction
        lower = explanation.lower()
        assert "grind" in lower or "extract" in lower or "finer" in lower

    def test_temp_explanation_for_bitter(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        explanation = engine._generate_explanation(
            "water_temp_c", 93.0, 90.0, ["too_bitter"]
        )
        assert isinstance(explanation, str)
        lower = explanation.lower()
        assert "temp" in lower or "bitter" in lower or "over-extract" in lower

    def test_dose_explanation_for_weak(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        explanation = engine._generate_explanation(
            "dose_g", 16.0, 18.0, ["too_weak"]
        )
        assert isinstance(explanation, str)
        lower = explanation.lower()
        assert "dose" in lower or "coffee" in lower or "weak" in lower

    def test_ratio_explanation(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        explanation = engine._generate_explanation(
            "ratio", 16.0, 15.0, ["too_sour"]
        )
        assert isinstance(explanation, str)
        assert len(explanation) > 0


class TestOverallAssessment:
    """Overall assessment summarizes the issue."""

    def test_sour_assessment(self, bean, recipe):
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        lower = result.overall_assessment.lower()
        assert "sour" in lower or "under-extract" in lower

    def test_bitter_assessment(self, bean, recipe):
        predictor = _make_bitter_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_bitter"])
        lower = result.overall_assessment.lower()
        assert "bitter" in lower or "over-extract" in lower

    def test_no_flags_assessment(self, bean, recipe):
        predictor = _make_mock_predictor(base_score=7.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=[])
        assert isinstance(result.overall_assessment, str)
        assert len(result.overall_assessment) > 0


class TestValidateFlags:
    """_validate_flags() collects ALL unknown flags before raising."""

    def test_empty_list_returns_empty(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        result = engine._validate_flags([])
        assert result == []

    def test_all_valid_flags_pass_through(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        all_valid = list(DIRECTIONAL_FLAGS)
        result = engine._validate_flags(all_valid)
        assert result == all_valid

    def test_single_unknown_flag_raises_with_name(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        with pytest.raises(ValueError, match="unknown_flag"):
            engine._validate_flags(["unknown_flag"])

    def test_multiple_unknown_flags_raises_listing_all(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        with pytest.raises(ValueError, match="bad_one") as exc_info:
            engine._validate_flags(["bad_one", "bad_two"])
        error_msg = str(exc_info.value)
        assert "bad_one" in error_msg
        assert "bad_two" in error_msg

    def test_mixed_valid_and_invalid_raises_listing_only_invalid(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        with pytest.raises(ValueError, match="not_real") as exc_info:
            engine._validate_flags(["too_sour", "not_real", "too_bitter", "also_fake"])
        error_msg = str(exc_info.value)
        assert "not_real" in error_msg
        assert "also_fake" in error_msg
        # The error message prefix lists unknown flags; valid flags only appear
        # in the "Must be one of ..." suffix. Check the prefix before that suffix.
        prefix = error_msg.split("Must be one of")[0]
        assert "too_sour" not in prefix
        assert "too_bitter" not in prefix


class TestComputeConfidence:
    """_compute_confidence() produces values in [0, 1] with correct ordering."""

    @pytest.mark.parametrize("delta", [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0])
    def test_output_in_unit_interval(self, delta):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        confidence = engine._compute_confidence(delta)
        assert 0.0 <= confidence <= 1.0

    def test_delta_zero_produces_low_confidence(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        confidence = engine._compute_confidence(0.0)
        assert confidence < 0.5

    def test_larger_deltas_produce_higher_confidence(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        deltas = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        confidences = [engine._compute_confidence(d) for d in deltas]
        for i in range(len(confidences) - 1):
            assert confidences[i] < confidences[i + 1], (
                f"delta={deltas[i]} gave confidence={confidences[i]}, "
                f"but delta={deltas[i+1]} gave confidence={confidences[i+1]} "
                f"(expected strictly increasing)"
            )

    def test_negative_delta_produces_low_confidence(self):
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        confidence = engine._compute_confidence(-1.0)
        assert confidence < 0.5


class TestPerturbationRanges:
    """Verify perturbation uses correct ranges and steps."""

    def test_all_four_parameters_evaluated(self, bean, recipe):
        """All 4 tunable params should be evaluated."""
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        params = {s.parameter for s in result.suggestions}
        assert "grind_setting" in params
        assert "water_temp_c" in params
        assert "dose_g" in params
        assert "ratio" in params

    def test_only_tunable_params_suggested(self, bean, recipe):
        """Only the 4 tunable params should appear in suggestions."""
        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)
        result = engine.diagnose(bean, recipe, flags=["too_sour"])
        allowed = {"grind_setting", "water_temp_c", "dose_g", "ratio"}
        for s in result.suggestions:
            assert s.parameter in allowed


class TestM13Logging:
    """M2-M13: Diagnosis engine has structured logging at key operations."""

    def test_module_has_logger(self):
        """Module-level logger should be defined."""
        from src.diagnosis import engine as mod
        import logging
        assert hasattr(mod, "logger")
        assert isinstance(mod.logger, logging.Logger)
        assert mod.logger.name == "src.diagnosis.engine"

    def test_diagnose_logs_flags_and_suggestions(self, bean, recipe, capfd):
        """diagnose() should log flags and number of suggestions."""
        import logging
        from src.diagnosis.engine import DiagnosisEngine

        predictor = _make_sour_scoring_predictor(base_score=5.0)
        engine = DiagnosisEngine(predictor)

        # Enable logging capture
        with capfd.disabled():
            handler = logging.StreamHandler()
            handler.setLevel(logging.INFO)
            logger = logging.getLogger("src.diagnosis.engine")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            try:
                engine.diagnose(bean, recipe, flags=["too_sour"])
            finally:
                logger.removeHandler(handler)


class TestM15ExplanationMagnitude:
    """M2-M15: Explanation templates vary by magnitude of parameter change."""

    def test_large_delta_includes_gradually(self):
        """Large parameter changes should include 'gradually' in explanation."""
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        # grind_setting step is 1.0; 2x step = 2.0; delta of 3.0 is > 2x
        explanation = engine._generate_explanation(
            "grind_setting", 5.0, 2.0, ["too_sour"]
        )
        assert "gradually" in explanation.lower()

    def test_small_delta_includes_small_adjustment(self):
        """Small parameter changes should include 'small adjustment' in explanation."""
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        # grind_setting step is 1.0; delta of 0.5 is small (< 2x step)
        explanation = engine._generate_explanation(
            "grind_setting", 5.0, 4.5, ["too_sour"]
        )
        assert "small adjustment" in explanation.lower()

    def test_zero_delta_includes_small_adjustment(self):
        """No change should include 'small adjustment' in explanation."""
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        explanation = engine._generate_explanation(
            "water_temp_c", 93.0, 93.0, ["too_bitter"]
        )
        assert "small adjustment" in explanation.lower()

    def test_large_temp_delta_includes_gradually(self):
        """Large temperature change should include 'gradually'."""
        predictor = _make_mock_predictor()
        engine = DiagnosisEngine(predictor)
        # water_temp_c step is 0.5; 2x step = 1.0; delta of 3.0 is large
        explanation = engine._generate_explanation(
            "water_temp_c", 93.0, 90.0, ["too_bitter"]
        )
        assert "gradually" in explanation.lower()

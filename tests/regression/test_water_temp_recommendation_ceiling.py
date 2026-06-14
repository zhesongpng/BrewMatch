"""Regression: BrewMatch must never *recommend* a water temperature above 98°C.

A logged brew may record up to 100°C (the data-model storage envelope), but the
two recommendation paths — the recipe optimizer and the troubleshooting/diagnosis
engine — are capped at a 98°C ceiling. Before this fix both paths could prescribe
up to 100°C: the brief said 96°C, the validation allowed 100°C, and the optimizer
search band / diagnosis clamp used 100°C (journal 0031).

These tests push each path toward the hottest possible recommendation and assert
the 98°C ceiling holds end-to-end.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from src.data_models import (
    BeanProfile,
    BrewMethod,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)
from src.diagnosis.engine import DiagnosisEngine
from src.recipe_optimizer.optimizer import RecipeOptimizer

RECOMMENDATION_CEILING_C = 98.0


def _recipe(water_temp_c: float) -> Recipe:
    """Valid V60 recipe at the requested temperature (dose*ratio == pour sum)."""
    return Recipe(
        recipe_id="test-recipe",
        source="test",
        method=BrewMethod.V60,
        dose_g=16.0,
        water_total_g=256.0,
        ratio=16.0,
        grind_setting=5,
        water_temp_c=water_temp_c,
        bloom_time_s=45,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=64.0),
            PourStep(step=2, time_offset_s=45, water_g=96.0),
            PourStep(step=3, time_offset_s=90, water_g=96.0),
        ],
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Test recipe",
    )


def _bean() -> BeanProfile:
    return BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Ethiopian Yirgacheffe, light roast",
    )


def _flat_predictor(score: float = 7.0) -> MagicMock:
    """Optimizer predictor returning a fixed score for any encoded recipe."""
    predictor = MagicMock()
    predictor.is_trained = True
    encoder = MagicMock()
    encoder.encode.return_value = np.zeros(45, dtype=np.float64)
    predictor._encoder = encoder
    predictor.encode_features = encoder.encode
    predictor.predict_batch.side_effect = lambda feats, user_ids=None: np.full(
        feats.shape[0], score, dtype=np.float64
    )
    return predictor


def _hotter_is_better_predictor(base_score: float = 5.0) -> MagicMock:
    """Diagnosis predictor that rewards ever-higher temperature without bound.

    This is the adversarial case: left unclamped, the engine would chase the
    temperature all the way to the storage ceiling (100°C).
    """
    predictor = MagicMock()

    def score_for_params(bean_profile, recipe, user_id=None, **kwargs):
        score = base_score + (recipe.water_temp_c - 93.0) * 0.2
        result = MagicMock()
        result.predicted_rating = max(1.0, min(10.0, score))
        result.confidence_interval = (max(1.0, score - 1.0), min(10.0, score + 1.0))
        result.user_bias = 0.0
        result.base_prediction = score
        result.feature_importance = {"water_temp_c": 0.25, "grind_setting": 0.3}
        return result

    predictor.predict.side_effect = score_for_params
    return predictor


@pytest.mark.regression
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_optimizer_never_recommends_above_98c(seed: int):
    """Optimizer must not prescribe >98°C even when the brewed base was 100°C."""
    opt = RecipeOptimizer(_flat_predictor(), n_trials=40, seed=seed)
    result = opt.optimize(_bean(), _recipe(water_temp_c=100.0))
    assert result.optimized_recipe.water_temp_c <= RECOMMENDATION_CEILING_C


@pytest.mark.regression
def test_diagnosis_never_prescribes_above_98c():
    """Diagnosis must clamp temperature suggestions at 98°C, not the 100°C envelope."""
    engine = DiagnosisEngine(_hotter_is_better_predictor())
    # Already hot at 97°C and reporting too_sour — the engine wants it hotter still.
    result = engine.diagnose(_bean(), _recipe(water_temp_c=97.0), flags=["too_sour"])
    temp_suggestions = [
        s for s in result.suggestions if s.parameter == "water_temp_c"
    ]
    for suggestion in temp_suggestions:
        assert suggestion.suggested_value <= RECOMMENDATION_CEILING_C

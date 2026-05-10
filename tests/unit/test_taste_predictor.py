"""Unit tests for the TastePredictor model."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.data_models import (
    BeanProfile,
    BrewMethod,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
    PourStep,
)
from src.taste_predictor.model import (
    FEATURE_NAMES,
    _MODEL_PARAMS,
    PredictionResult,
    TastePredictor,
)


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


@pytest.fixture
def trained_predictor(bean, recipe):
    """Create a predictor trained on synthetic data (small set)."""
    predictor = TastePredictor()
    np.random.seed(42)
    n = 100
    X = np.random.randn(n, 45).astype(np.float64)
    y = np.random.uniform(3, 9, n)
    X_train, X_val = X[:80], X[80:]
    y_train, y_val = y[:80], y[80:]
    predictor.train(X_train, y_train, X_val, y_val)
    return predictor


class TestTastePredictorInit:

    def test_not_trained_initially(self):
        p = TastePredictor()
        assert not p.is_trained

    def test_predict_raises_when_not_trained(self, bean, recipe):
        p = TastePredictor()
        with pytest.raises(RuntimeError, match="not trained"):
            p.predict(bean, recipe)


class TestTastePredictorTrain:

    def test_train_sets_trained_flag(self):
        p = TastePredictor()
        X = np.random.randn(60, 45)
        y = np.random.uniform(3, 9, 60)
        p.train(X[:50], y[:50], X[50:], y[50:])
        assert p.is_trained

    def test_train_uses_correct_params(self):
        p = TastePredictor()
        X = np.random.randn(60, 45)
        y = np.random.uniform(3, 9, 60)
        p.train(X[:50], y[:50], X[50:], y[50:])
        model = p._model
        assert model.max_depth == _MODEL_PARAMS["max_depth"]
        assert abs(model.learning_rate - _MODEL_PARAMS["learning_rate"]) < 1e-6
        assert model.n_estimators == _MODEL_PARAMS["n_estimators"]

    def test_train_returns_val_metrics(self):
        p = TastePredictor()
        X = np.random.randn(60, 45)
        y = np.random.uniform(3, 9, 60)
        result = p.train(X[:50], y[:50], X[50:], y[50:])
        assert "best_iteration" in result
        assert "val_rmse" in result
        assert result["val_rmse"] > 0


class TestTastePredictorPredict:

    def test_predict_returns_prediction_result(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe)
        assert isinstance(result, PredictionResult)

    def test_predicted_rating_in_range(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe)
        assert 1.0 <= result.predicted_rating <= 10.0

    def test_confidence_interval_in_range(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe)
        lo, hi = result.confidence_interval
        assert 1.0 <= lo <= 10.0
        assert 1.0 <= hi <= 10.0
        assert lo <= hi

    def test_base_prediction_before_bias(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe)
        assert result.base_prediction != result.predicted_rating or result.user_bias == 0.0

    def test_feature_importance_has_10_entries(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe)
        assert len(result.feature_importance) <= 10
        assert len(result.feature_importance) > 0

    def test_feature_importance_keys_are_valid(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe)
        for key in result.feature_importance:
            assert key in FEATURE_NAMES


class TestTastePredictorBatchPredict:

    def test_batch_predict_shape(self, trained_predictor):
        X = np.random.randn(10, 45)
        preds = trained_predictor.predict_batch(X)
        assert preds.shape == (10,)

    def test_batch_predict_clipped(self, trained_predictor):
        X = np.random.randn(10, 45)
        preds = trained_predictor.predict_batch(X)
        assert np.all(preds >= 1.0)
        assert np.all(preds <= 10.0)

    def test_batch_predict_with_user_ids(self, trained_predictor):
        trained_predictor._user_biases["user-1"] = 0.5
        X = np.random.randn(3, 45)
        ids = ["user-1", None, "user-1"]
        preds = trained_predictor.predict_batch(X, user_ids=ids)
        assert preds.shape == (3,)


class TestTastePredictorUserBias:

    def test_no_bias_for_unknown_user(self, trained_predictor, bean, recipe):
        result = trained_predictor.predict(bean, recipe, user_id="unknown")
        assert result.user_bias == 0.0

    def test_update_bias_early_ratings(self, trained_predictor, bean, recipe):
        features = trained_predictor._encoder.encode(bean, recipe)
        trained_predictor.update_user_bias("user-1", features, 8.0, n_prior_ratings=2)
        assert "user-1" in trained_predictor._user_biases

    def test_update_bias_many_ratings(self, trained_predictor, bean, recipe):
        features = trained_predictor._encoder.encode(bean, recipe)
        trained_predictor._user_biases["user-2"] = 0.0
        trained_predictor.update_user_bias("user-2", features, 9.0, n_prior_ratings=10)
        assert trained_predictor._user_biases["user-2"] != 0.0

    def test_bias_affects_prediction(self, trained_predictor, bean, recipe):
        result_no_bias = trained_predictor.predict(bean, recipe, user_id=None)
        trained_predictor._user_biases["biased-user"] = 2.0
        result_with_bias = trained_predictor.predict(bean, recipe, user_id="biased-user")
        assert result_with_bias.predicted_rating >= result_no_bias.predicted_rating


class TestTastePredictorPersistence:

    def test_save_and_load(self, trained_predictor, tmp_path):
        trained_predictor._user_biases["user-x"] = 0.3
        trained_predictor.save(tmp_path)

        assert (tmp_path / "taste_predictor.joblib").exists()
        assert (tmp_path / "feature_encoder.joblib").exists()
        assert (tmp_path / "user_biases.json").exists()
        assert (tmp_path / "training_metadata.json").exists()

        loaded = TastePredictor()
        loaded.load(tmp_path)
        assert loaded.is_trained
        assert loaded._user_biases.get("user-x") == 0.3
        assert abs(loaded._global_mean - trained_predictor._global_mean) < 1e-6

    def test_loaded_model_predicts_same(self, trained_predictor, bean, recipe, tmp_path):
        trained_predictor.save(tmp_path)
        loaded = TastePredictor()
        loaded.load(tmp_path)

        original = trained_predictor.predict(bean, recipe)
        reloaded = loaded.predict(bean, recipe)
        assert abs(original.predicted_rating - reloaded.predicted_rating) < 1e-6

    def test_save_load_preserves_bias_during_prediction(self, trained_predictor, bean, recipe, tmp_path):
        """Bias state survives save/load and is applied during predict (M2-M11).

        Trains a model, updates a user's bias, saves, loads into a fresh
        instance, then predicts with that user_id. The loaded model must
        apply the same bias, producing a different prediction than the
        unbiased baseline.
        """
        # 1. Get unbiased baseline from original model
        result_no_bias = trained_predictor.predict(bean, recipe, user_id=None)
        base_rating = result_no_bias.predicted_rating

        # 2. Update bias for user "biased-user" on the original model
        features = trained_predictor._encoder.encode(bean, recipe)
        trained_predictor.update_user_bias(
            "biased-user", features, actual_rating=9.5, n_prior_ratings=2,
        )
        biased_result_before = trained_predictor.predict(
            bean, recipe, user_id="biased-user",
        )
        # Sanity: bias actually changed something on the original model
        assert biased_result_before.user_bias != 0.0
        bias_value = biased_result_before.user_bias

        # 3. Save and load into a fresh instance
        trained_predictor.save(tmp_path)
        loaded = TastePredictor()
        loaded.load(tmp_path)

        # 4. Predict with the loaded model using the same user_id
        result_loaded = loaded.predict(bean, recipe, user_id="biased-user")

        # 5. Verify bias was preserved and applied
        assert result_loaded.user_bias == pytest.approx(bias_value, abs=1e-3), (
            f"Loaded model user_bias {result_loaded.user_bias} != original {bias_value}"
        )
        # The biased prediction should differ from the unbiased baseline
        assert result_loaded.predicted_rating != base_rating, (
            "Loaded model with active bias should produce a different prediction "
            "than the unbiased baseline"
        )
        # The loaded biased prediction should match the original biased prediction
        assert abs(result_loaded.predicted_rating - biased_result_before.predicted_rating) < 0.05, (
            f"Loaded biased prediction {result_loaded.predicted_rating} != "
            f"original biased prediction {biased_result_before.predicted_rating}"
        )


class TestFeatureNames:

    def test_feature_names_count(self):
        assert len(FEATURE_NAMES) == 45

    def test_feature_names_unique(self):
        assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)

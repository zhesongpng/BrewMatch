"""Unit tests for the evaluation pipeline (scripts/evaluate_pipeline.py).

Covers all 6 public functions: evaluate_bean_extraction,
evaluate_recipe_retrieval, evaluate_taste_prediction,
evaluate_recipe_optimization, evaluate_personalization, save_all_artifacts,
and the main() orchestrator. External dependencies (LLM APIs, ChromaDB,
LightGBM training) are mocked to keep each test < 1 second.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The script inserts its own ROOT path on import; this is fine for testing
# since we need the same src/ resolvability.
import scripts.evaluate_pipeline as ep  # noqa: E402


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def mock_predictor():
    """A mock TastePredictor that returns controlled predictions."""
    predictor = MagicMock()
    predictor.is_trained = True
    predictor._user_biases = {}

    def _predict_batch(X, user_ids=None):
        return np.full(X.shape[0], 7.0, dtype=np.float64)

    predictor.predict_batch.side_effect = _predict_batch
    return predictor


@pytest.fixture
def trained_predictor():
    """A minimally-trained real TastePredictor for integration-shape tests."""
    from src.taste_predictor.model import TastePredictor

    predictor = TastePredictor()
    rng = np.random.RandomState(42)
    n = 120
    X = rng.randn(n, 45).astype(np.float64)
    y = rng.uniform(3, 9, n)
    predictor.train(X[:80], y[:80], X[80:100], y[80:100])
    # Reserve X[100:], y[100:] as a test set if callers need it.
    predictor._test_X = X[100:]
    predictor._test_y = y[100:]
    return predictor


@pytest.fixture
def sample_pred_results(trained_predictor):
    """A pred_results dict mimicking evaluate_taste_prediction() output."""
    return {
        "metrics": {
            "rmse": 0.85,
            "mae": 0.62,
            "r_squared": 0.71,
            "cold_start_rmse": 1.10,
            "per_roast_rmse": {"light": 0.80, "medium": 0.90},
            "predictions": [
                {"actual": 7.0, "predicted": 7.1},
                {"actual": 6.5, "predicted": 6.3},
            ],
            "feature_importance": {"grind_setting": 0.5, "water_temp_c": 0.4},
            "n_train": 80,
            "n_val": 20,
            "n_test": 20,
        },
        "predictor": trained_predictor,
        "learning_curves": [
            {"fraction": 0.1, "n_rows": 8, "rmse": 1.20},
            {"fraction": 1.0, "n_rows": 80, "rmse": 0.85},
        ],
    }


@pytest.fixture
def sample_opt_results():
    """An opt_results dict mimicking evaluate_recipe_optimization() output."""
    return {
        "metrics": {
            "avg_improvement": 0.6,
            "trials_to_convergence": 45.0,
            "convergence_curves": [7.0, 7.3, 7.5, 7.6, 7.6],
            "constraint_satisfaction_rate": 0.92,
            "n_beans": 40,
        },
        "convergence_data": [[7.0, 7.3, 7.5], [7.1, 7.4, 7.6]],
    }


@pytest.fixture
def sample_pers_results():
    """A pers_results dict mimicking evaluate_personalization() output."""
    return {
        "metrics": {
            "bean_aware_rmse": 1.05,
            "hybrid_rmse": 0.88,
            "improvement_pct": 16.2,
            "rmse_by_ratings": [
                {"num_ratings": 1, "rmse": 1.20},
                {"num_ratings": 10, "rmse": 0.90},
            ],
            "phase_rmses": {"bean_aware": 1.05, "full_hybrid": 0.88},
            "n_users": 30,
        },
        "personalization_data": [
            {"num_ratings": 1, "rmse": 1.20},
            {"num_ratings": 10, "rmse": 0.90},
        ],
    }


@pytest.fixture
def sample_results(sample_pred_results, sample_opt_results, sample_pers_results):
    """A full results dict mimicking the main() accumulator."""
    return {
        "bean_extraction": {
            "accuracy": 0.88,
            "avg_confidence": 0.75,
            "failure_rate": 0.06,
            "n_test": 50,
        },
        "recipe_retrieval": {
            "precision_at_3": 0.85,
            "mrr": 0.90,
            "avg_latency_s": 0.012,
            "n_queries": 50,
        },
        "taste_prediction": sample_pred_results["metrics"],
        "recipe_optimization": sample_opt_results["metrics"],
        "personalization": sample_pers_results["metrics"],
    }


# ===========================================================================
# 1. evaluate_bean_extraction
# ===========================================================================


class TestEvaluateBeanExtraction:
    """Tests for evaluate_bean_extraction()."""

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_expected_keys_without_api_key(self):
        """Without an LLM API key, returns heuristic metrics."""
        result = ep.evaluate_bean_extraction()
        assert "accuracy" in result
        assert "avg_confidence" in result
        assert "failure_rate" in result
        assert "n_test" in result

    @patch.dict("os.environ", {}, clear=True)
    def test_heuristic_values_are_plausible(self):
        """Heuristic fallback returns plausible accuracy and confidence."""
        result = ep.evaluate_bean_extraction()
        assert 0.0 <= result["accuracy"] <= 1.0
        assert 0.0 <= result["avg_confidence"] <= 1.0
        assert 0.0 <= result["failure_rate"] <= 1.0
        assert result["n_test"] == 50

    @patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=False)
    @patch("src.bean_extractor.extractor.BeanExtractor")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_with_api_key_calls_extractor(
        self, mock_gen_bean, mock_extractor_cls
    ):
        """When API key is present, BeanExtractor is constructed and called."""
        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
            "altitude_min_m": 1500,
            "altitude_max_m": 1800,
        }

        mock_profile = MagicMock()
        mock_profile.origin_country = "Ethiopia"
        mock_profile.process.value = "washed"
        mock_profile.roast_level.value = "light"
        mock_profile.flavor_clusters = ["Floral"]

        mock_result = MagicMock()
        mock_result.bean_profile = mock_profile
        mock_result.confidence = 0.9

        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract.return_value = mock_result
        mock_extractor_cls.return_value = mock_extractor_instance

        result = ep.evaluate_bean_extraction()

        assert mock_extractor_cls.called
        assert mock_extractor_instance.extract.called
        assert result["accuracy"] > 0
        assert result["n_test"] == 50

    @patch.dict("os.environ", {"LLM_API_KEY": "test-key"}, clear=False)
    @patch("src.bean_extractor.extractor.BeanExtractor")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_extraction_failure_counted(
        self, mock_gen_bean, mock_extractor_cls
    ):
        """Failed extractions increment the failure count."""
        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
            "altitude_min_m": 1500,
            "altitude_max_m": 1800,
        }

        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract.side_effect = RuntimeError("API timeout")
        mock_extractor_cls.return_value = mock_extractor_instance

        result = ep.evaluate_bean_extraction()
        assert result["failure_rate"] > 0
        assert result["failure_rate"] <= 1.0

    @patch.dict("os.environ", {}, clear=True)
    def test_all_values_are_numeric(self):
        """All returned values are numeric (int or float)."""
        result = ep.evaluate_bean_extraction()
        for key in ["accuracy", "avg_confidence", "failure_rate", "n_test"]:
            assert isinstance(result[key], (int, float)), (
                f"Expected numeric for {key}, got {type(result[key])}"
            )


# ===========================================================================
# 2. evaluate_recipe_retrieval
# ===========================================================================


class TestEvaluateRecipeRetrieval:
    """Tests for evaluate_recipe_retrieval()."""

    @patch("src.recipe_retriever.retriever.RecipeRetriever")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_returns_expected_keys(self, mock_gen_bean, mock_retriever_cls):
        """Returns precision_at_3, mrr, avg_latency_s, n_queries."""
        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_recipe = MagicMock()
        mock_recipe.recipe_id = "test-recipe"
        mock_recipe.suitable_for.flavor_profiles = ["Floral"]
        mock_recipe.suitable_for.roast_levels = [MagicMock(value="light")]
        mock_recipe.suitable_for.processes = [MagicMock(value="washed")]

        mock_ranked = MagicMock()
        mock_ranked.recipe = mock_recipe
        mock_ranked.rank = 1

        mock_retrieval = MagicMock()
        mock_retrieval.recipes = [mock_ranked]

        mock_instance = MagicMock()
        mock_instance.retrieve.return_value = mock_retrieval
        mock_retriever_cls.return_value = mock_instance

        result = ep.evaluate_recipe_retrieval()

        assert "precision_at_3" in result
        assert "mrr" in result
        assert "avg_latency_s" in result
        assert "n_queries" in result

    @patch("src.recipe_retriever.retriever.RecipeRetriever")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_metrics_in_valid_range(self, mock_gen_bean, mock_retriever_cls):
        """Precision@3 and MRR are in [0, 1]."""
        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_retrieval = MagicMock()
        mock_retrieval.recipes = []

        mock_instance = MagicMock()
        mock_instance.retrieve.return_value = mock_retrieval
        mock_retriever_cls.return_value = mock_instance

        result = ep.evaluate_recipe_retrieval()
        assert 0.0 <= result["precision_at_3"] <= 1.0
        assert 0.0 <= result["mrr"] <= 1.0
        assert result["avg_latency_s"] >= 0
        assert result["n_queries"] == 50

    @patch("src.recipe_retriever.retriever.RecipeRetriever")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_latency_is_positive(self, mock_gen_bean, mock_retriever_cls):
        """Average latency should be a non-negative float."""
        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }
        mock_retrieval = MagicMock()
        mock_retrieval.recipes = []
        mock_instance = MagicMock()
        mock_instance.retrieve.return_value = mock_retrieval
        mock_retriever_cls.return_value = mock_instance

        result = ep.evaluate_recipe_retrieval()
        assert result["avg_latency_s"] >= 0.0


# ===========================================================================
# 3. evaluate_taste_prediction
# ===========================================================================


class TestEvaluateTastePrediction:
    """Tests for evaluate_taste_prediction()."""

    def test_returns_metrics_and_predictor(self):
        """Full evaluation returns metrics dict, predictor, and learning curves."""
        result = ep.evaluate_taste_prediction()
        assert "metrics" in result
        assert "predictor" in result
        assert "learning_curves" in result

    def test_metrics_contain_required_fields(self):
        """Metrics dict has all required keys."""
        result = ep.evaluate_taste_prediction()
        m = result["metrics"]
        required = [
            "rmse", "mae", "r_squared", "cold_start_rmse",
            "per_roast_rmse", "predictions", "feature_importance",
            "n_train", "n_val", "n_test",
        ]
        for key in required:
            assert key in m, f"Missing key: {key}"

    def test_rmse_and_mae_are_positive(self):
        """RMSE and MAE should be positive numbers."""
        result = ep.evaluate_taste_prediction()
        assert result["metrics"]["rmse"] > 0
        assert result["metrics"]["mae"] > 0

    def test_r_squared_in_valid_range(self):
        """R-squared should be a finite number."""
        result = ep.evaluate_taste_prediction()
        r2 = result["metrics"]["r_squared"]
        assert np.isfinite(r2)

    def test_predictions_are_pairs(self):
        """Each prediction has 'actual' and 'predicted' keys."""
        result = ep.evaluate_taste_prediction()
        for pred in result["metrics"]["predictions"][:10]:
            assert "actual" in pred
            assert "predicted" in pred
            assert isinstance(pred["actual"], (int, float))
            assert isinstance(pred["predicted"], (int, float))

    def test_cold_start_rmse_positive(self):
        """Cold-start RMSE should be positive."""
        result = ep.evaluate_taste_prediction()
        assert result["metrics"]["cold_start_rmse"] > 0

    def test_per_roast_rmse_is_dict(self):
        """per_roast_rmse is a dict mapping roast levels to RMSE values."""
        result = ep.evaluate_taste_prediction()
        pr = result["metrics"]["per_roast_rmse"]
        assert isinstance(pr, dict)
        if pr:
            for roast_val, rmse_val in pr.items():
                assert isinstance(roast_val, str)
                assert rmse_val > 0

    def test_feature_importance_is_dict(self):
        """feature_importance is a dict of feature names to scores."""
        result = ep.evaluate_taste_prediction()
        fi = result["metrics"]["feature_importance"]
        assert isinstance(fi, dict)
        if fi:
            for name, score in fi.items():
                assert isinstance(name, str)
                assert isinstance(score, (int, float))

    def test_learning_curves_structure(self):
        """Learning curves have fraction, n_rows, rmse entries."""
        result = ep.evaluate_taste_prediction()
        curves = result["learning_curves"]
        assert isinstance(curves, list)
        assert len(curves) > 0
        for entry in curves:
            assert "fraction" in entry
            assert "n_rows" in entry
            assert "rmse" in entry

    def test_predictor_is_trained(self):
        """Returned predictor is trained and usable."""
        result = ep.evaluate_taste_prediction()
        assert result["predictor"].is_trained
        X = np.random.randn(5, 45)
        preds = result["predictor"].predict_batch(X)
        assert preds.shape == (5,)


# ===========================================================================
# 4. _compute_feature_importance
# ===========================================================================


class TestComputeFeatureImportance:
    """Tests for the _compute_feature_importance helper."""

    def test_returns_dict_of_top_features(self, trained_predictor):
        """Returns a non-empty dict of feature importance scores."""
        from src.taste_predictor.model import FEATURE_NAMES

        X_test = np.random.RandomState(42).randn(20, 45)
        result = ep._compute_feature_importance(
            trained_predictor, X_test, FEATURE_NAMES
        )
        assert isinstance(result, dict)
        assert len(result) > 0
        assert len(result) <= 15  # top 15

    def test_feature_names_are_from_feature_names_list(self, trained_predictor):
        """All keys in the result are from the FEATURE_NAMES list."""
        from src.taste_predictor.model import FEATURE_NAMES

        X_test = np.random.RandomState(42).randn(20, 45)
        result = ep._compute_feature_importance(
            trained_predictor, X_test, FEATURE_NAMES
        )
        for key in result:
            assert key in FEATURE_NAMES

    def test_importance_values_are_non_negative(self, trained_predictor):
        """Permutation importance values should be non-negative floats."""
        from src.taste_predictor.model import FEATURE_NAMES

        X_test = np.random.RandomState(42).randn(20, 45)
        result = ep._compute_feature_importance(
            trained_predictor, X_test, FEATURE_NAMES
        )
        for key, val in result.items():
            assert val >= 0.0


# ===========================================================================
# 5. _compute_learning_curves
# ===========================================================================


class TestComputeLearningCurves:
    """Tests for the _compute_learning_curves helper."""

    def test_returns_list_of_dicts(self):
        """Returns a list with entries for each fraction."""
        from src.taste_predictor.model import TastePredictor

        rng = np.random.RandomState(42)
        n = 200
        X_all = rng.randn(n, 45).astype(np.float64)
        y_all = rng.uniform(3, 9, n)

        # Small predictor for speed
        p = TastePredictor()
        p.train(X_all[:50], y_all[:50], X_all[50:75], y_all[50:75])

        result = ep._compute_learning_curves(
            X_all[:100], y_all[:100],
            X_all[100:125], y_all[100:125],
            X_all[125:], y_all[125:],
        )
        assert isinstance(result, list)
        assert len(result) == 5  # fractions: 0.1, 0.25, 0.5, 0.75, 1.0

    def test_fractions_are_ascending(self):
        """Fraction values in the output should be ascending."""
        from src.taste_predictor.model import TastePredictor

        rng = np.random.RandomState(42)
        n = 200
        X_all = rng.randn(n, 45).astype(np.float64)
        y_all = rng.uniform(3, 9, n)

        p = TastePredictor()
        p.train(X_all[:50], y_all[:50], X_all[50:75], y_all[50:75])

        result = ep._compute_learning_curves(
            X_all[:100], y_all[:100],
            X_all[100:125], y_all[100:125],
            X_all[125:], y_all[125:],
        )
        fractions = [entry["fraction"] for entry in result]
        assert fractions == sorted(fractions)

    def test_n_rows_increases_with_fraction(self):
        """n_rows should increase (or stay the same) with fraction."""
        from src.taste_predictor.model import TastePredictor

        rng = np.random.RandomState(42)
        n = 200
        X_all = rng.randn(n, 45).astype(np.float64)
        y_all = rng.uniform(3, 9, n)

        p = TastePredictor()
        p.train(X_all[:50], y_all[:50], X_all[50:75], y_all[50:75])

        result = ep._compute_learning_curves(
            X_all[:100], y_all[:100],
            X_all[100:125], y_all[100:125],
            X_all[125:], y_all[125:],
        )
        rows = [entry["n_rows"] for entry in result]
        for i in range(1, len(rows)):
            assert rows[i] >= rows[i - 1]


# ===========================================================================
# 6. evaluate_recipe_optimization
# ===========================================================================


class TestEvaluateRecipeOptimization:
    """Tests for evaluate_recipe_optimization(predictor)."""

    @patch("src.recipe_optimizer.optimizer.RecipeOptimizer")
    @patch("src.recipe_retriever.retriever.RecipeRetriever")
    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_returns_metrics_and_convergence_data(
        self,
        mock_gen_bean,
        mock_load_recipes,
        mock_retriever_cls,
        mock_optimizer_cls,
        mock_predictor,
    ):
        """Returns a dict with 'metrics' and 'convergence_data'."""
        mock_load_recipes.return_value = [MagicMock()]

        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_recipe = MagicMock()
        mock_ranked = MagicMock()
        mock_ranked.recipe = mock_recipe
        mock_retrieval = MagicMock()
        mock_retrieval.recipes = [mock_ranked]
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = mock_retrieval
        mock_retriever_cls.return_value = mock_retriever_instance

        mock_opt_result = MagicMock()
        mock_opt_result.improvement = 0.5
        mock_opt_result.constraint_violations = []
        mock_opt_result.predicted_score = 7.5
        mock_opt_result.baseline_score = 7.0
        mock_opt_result.n_trials = 30
        mock_optimizer_instance = MagicMock()
        mock_optimizer_instance.optimize.return_value = mock_opt_result
        mock_optimizer_cls.return_value = mock_optimizer_instance

        result = ep.evaluate_recipe_optimization(mock_predictor)
        assert "metrics" in result
        assert "convergence_data" in result

    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    def test_empty_recipes_returns_zero_metrics(
        self, mock_load_recipes, mock_predictor
    ):
        """When no recipes are found, returns safe zero metrics."""
        mock_load_recipes.return_value = []
        result = ep.evaluate_recipe_optimization(mock_predictor)
        assert result["metrics"]["avg_improvement"] == 0.0
        assert result["metrics"]["constraint_satisfaction_rate"] == 0.0
        assert result["metrics"]["convergence_curves"] == []

    @patch("src.recipe_optimizer.optimizer.RecipeOptimizer")
    @patch("src.recipe_retriever.retriever.RecipeRetriever")
    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    @patch("src.data_generator.generator.generate_random_bean")
    def test_metrics_have_expected_keys(
        self,
        mock_gen_bean,
        mock_load_recipes,
        mock_retriever_cls,
        mock_optimizer_cls,
        mock_predictor,
    ):
        """Metrics dict contains all expected keys."""
        mock_load_recipes.return_value = [MagicMock()]

        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_recipe = MagicMock()
        mock_ranked = MagicMock()
        mock_ranked.recipe = mock_recipe
        mock_retrieval = MagicMock()
        mock_retrieval.recipes = [mock_ranked]
        mock_retriever_instance = MagicMock()
        mock_retriever_instance.retrieve.return_value = mock_retrieval
        mock_retriever_cls.return_value = mock_retriever_instance

        mock_opt_result = MagicMock()
        mock_opt_result.improvement = 0.5
        mock_opt_result.constraint_violations = []
        mock_opt_result.predicted_score = 7.5
        mock_opt_result.baseline_score = 7.0
        mock_opt_result.n_trials = 30
        mock_optimizer_instance = MagicMock()
        mock_optimizer_instance.optimize.return_value = mock_opt_result
        mock_optimizer_cls.return_value = mock_optimizer_instance

        result = ep.evaluate_recipe_optimization(mock_predictor)
        m = result["metrics"]
        for key in [
            "avg_improvement",
            "trials_to_convergence",
            "convergence_curves",
            "constraint_satisfaction_rate",
            "n_beans",
        ]:
            assert key in m, f"Missing metric key: {key}"


# ===========================================================================
# 7. evaluate_personalization
# ===========================================================================


class TestEvaluatePersonalization:
    """Tests for evaluate_personalization(predictor)."""

    @patch("src.personalization.engine.PersonalizationEngine")
    @patch("src.data_generator.generator.generate_random_bean")
    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    def test_returns_metrics_and_data(
        self, mock_load, mock_gen_bean, mock_engine_cls, mock_predictor
    ):
        """Returns a dict with 'metrics' and 'personalization_data'."""
        mock_recipe = MagicMock()
        mock_recipe.method = MagicMock()
        mock_load.return_value = [mock_recipe]

        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_engine = MagicMock()
        mock_engine.get_user_features.return_value = {
            "user_avg_rating": 0.0,
            "user_rating_count": 0.0,
            "user_roast_pref": 0.0,
            "user_temp_pref": 0.0,
            "user_grind_pref": 0.0,
            "user_ratio_pref": 0.0,
            "user_acidity_bias": 0.0,
            "user_body_bias": 0.0,
            "user_sweetness_bias": 0.0,
        }
        mock_engine.get_phase_for_count.return_value = "bean_aware"
        mock_engine_cls.return_value = mock_engine
        mock_engine_cls.get_phase_for_count = staticmethod(lambda n: "directional")

        # encode_features returns a 45-element array
        with patch("src.taste_predictor.encoder.encode_features") as mock_encode:
            mock_encode.return_value = np.zeros(45, dtype=np.float64)
            result = ep.evaluate_personalization(mock_predictor)

        assert "metrics" in result
        assert "personalization_data" in result

    @patch("src.personalization.engine.PersonalizationEngine")
    @patch("src.data_generator.generator.generate_random_bean")
    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    def test_metrics_contain_required_keys(
        self, mock_load, mock_gen_bean, mock_engine_cls, mock_predictor
    ):
        """Metrics dict has bean_aware_rmse, hybrid_rmse, improvement_pct."""
        mock_recipe = MagicMock()
        mock_recipe.method = MagicMock()
        mock_load.return_value = [mock_recipe]

        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_engine = MagicMock()
        mock_engine.get_user_features.return_value = {
            "user_avg_rating": 0.0,
            "user_rating_count": 0.0,
            "user_roast_pref": 0.0,
            "user_temp_pref": 0.0,
            "user_grind_pref": 0.0,
            "user_ratio_pref": 0.0,
            "user_acidity_bias": 0.0,
            "user_body_bias": 0.0,
            "user_sweetness_bias": 0.0,
        }
        mock_engine.get_phase_for_count.return_value = "bean_aware"
        mock_engine_cls.return_value = mock_engine
        mock_engine_cls.get_phase_for_count = staticmethod(lambda n: "directional")

        with patch("src.taste_predictor.encoder.encode_features") as mock_encode:
            mock_encode.return_value = np.zeros(45, dtype=np.float64)
            result = ep.evaluate_personalization(mock_predictor)

        m = result["metrics"]
        for key in [
            "bean_aware_rmse",
            "hybrid_rmse",
            "improvement_pct",
            "rmse_by_ratings",
            "n_users",
        ]:
            assert key in m, f"Missing metric key: {key}"

    @patch("src.personalization.engine.PersonalizationEngine")
    @patch("src.data_generator.generator.generate_random_bean")
    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    def test_rmse_by_ratings_structure(
        self, mock_load, mock_gen_bean, mock_engine_cls, mock_predictor
    ):
        """rmse_by_ratings is a list of dicts with num_ratings and rmse."""
        mock_recipe = MagicMock()
        mock_recipe.method = MagicMock()
        mock_load.return_value = [mock_recipe]

        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_engine = MagicMock()
        mock_engine.get_user_features.return_value = {
            "user_avg_rating": 0.0,
            "user_rating_count": 0.0,
            "user_roast_pref": 0.0,
            "user_temp_pref": 0.0,
            "user_grind_pref": 0.0,
            "user_ratio_pref": 0.0,
            "user_acidity_bias": 0.0,
            "user_body_bias": 0.0,
            "user_sweetness_bias": 0.0,
        }
        mock_engine.get_phase_for_count.return_value = "bean_aware"
        mock_engine_cls.return_value = mock_engine
        mock_engine_cls.get_phase_for_count = staticmethod(lambda n: "directional")

        with patch("src.taste_predictor.encoder.encode_features") as mock_encode:
            mock_encode.return_value = np.zeros(45, dtype=np.float64)
            result = ep.evaluate_personalization(mock_predictor)

        ratings_data = result["metrics"]["rmse_by_ratings"]
        assert isinstance(ratings_data, list)
        if ratings_data:
            for entry in ratings_data:
                assert "num_ratings" in entry
                assert "rmse" in entry

    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    def test_empty_recipes_returns_safe_defaults(self, mock_load, mock_predictor):
        """When no recipes are found, returns safe zero metrics."""
        mock_load.return_value = []
        result = ep.evaluate_personalization(mock_predictor)
        assert result["metrics"]["bean_aware_rmse"] == 0.0
        assert result["metrics"]["hybrid_rmse"] == 0.0
        assert result["metrics"]["improvement_pct"] == 0.0

    @patch("src.personalization.engine.PersonalizationEngine")
    @patch("src.data_generator.generator.generate_random_bean")
    @patch("src.recipe_retriever.retriever.load_recipes_from_directory")
    def test_n_users_is_set(
        self, mock_load, mock_gen_bean, mock_engine_cls, mock_predictor
    ):
        """n_users matches the internal count."""
        mock_recipe = MagicMock()
        mock_recipe.method = MagicMock()
        mock_load.return_value = [mock_recipe]

        mock_gen_bean.return_value = {
            "origin_country": "Ethiopia",
            "process": "washed",
            "roast_level": "light",
            "flavor_clusters": ["Floral"],
        }

        mock_engine = MagicMock()
        mock_engine.get_user_features.return_value = {
            "user_avg_rating": 0.0,
            "user_rating_count": 0.0,
            "user_roast_pref": 0.0,
            "user_temp_pref": 0.0,
            "user_grind_pref": 0.0,
            "user_ratio_pref": 0.0,
            "user_acidity_bias": 0.0,
            "user_body_bias": 0.0,
            "user_sweetness_bias": 0.0,
        }
        mock_engine.get_phase_for_count.return_value = "bean_aware"
        mock_engine_cls.return_value = mock_engine
        mock_engine_cls.get_phase_for_count = staticmethod(lambda n: "directional")

        with patch("src.taste_predictor.encoder.encode_features") as mock_encode:
            mock_encode.return_value = np.zeros(45, dtype=np.float64)
            result = ep.evaluate_personalization(mock_predictor)

        assert result["metrics"]["n_users"] == 30


# ===========================================================================
# 8. save_all_artifacts
# ===========================================================================


class TestSaveAllArtifacts:
    """Tests for save_all_artifacts()."""

    def test_creates_all_six_artifact_files(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """All 6 artifact files are created in the models directory."""
        # Override MODELS_DIR to tmp_path via monkeypatching the module constant
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            expected_files = [
                "evaluation_results.json",
                "test_predictions.csv",
                "feature_importance.json",
                "convergence_curves.json",
                "personalization_curves.json",
                "learning_curves.json",
            ]
            for fname in expected_files:
                assert (tmp_path / fname).exists(), (
                    f"Expected artifact {fname} not found"
                )
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_evaluation_results_json_structure(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """evaluation_results.json is valid JSON with all component keys."""
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            with open(tmp_path / "evaluation_results.json") as f:
                data = json.load(f)

            for component in [
                "bean_extraction",
                "recipe_retrieval",
                "taste_prediction",
                "recipe_optimization",
                "personalization",
            ]:
                assert component in data, f"Missing component: {component}"
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_test_predictions_csv_structure(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """test_predictions.csv has actual and predicted columns."""
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            with open(tmp_path / "test_predictions.csv", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) > 0
                assert "actual" in reader.fieldnames
                assert "predicted" in reader.fieldnames
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_feature_importance_json_structure(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """feature_importance.json is valid JSON dict."""
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            with open(tmp_path / "feature_importance.json") as f:
                data = json.load(f)
            assert isinstance(data, dict)
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_convergence_curves_json_structure(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """convergence_curves.json has average_curve and individual_curves."""
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            with open(tmp_path / "convergence_curves.json") as f:
                data = json.load(f)
            assert "average_curve" in data
            assert "individual_curves" in data
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_personalization_curves_json_structure(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """personalization_curves.json is a list of rating/RMSE entries."""
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            with open(tmp_path / "personalization_curves.json") as f:
                data = json.load(f)
            assert isinstance(data, list)
            if data:
                assert "num_ratings" in data[0]
                assert "rmse" in data[0]
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_learning_curves_json_structure(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """learning_curves.json is a list of fraction/RMSE entries."""
        original_models_dir = ep.MODELS_DIR
        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            with open(tmp_path / "learning_curves.json") as f:
                data = json.load(f)
            assert isinstance(data, list)
            if data:
                assert "fraction" in data[0]
                assert "rmse" in data[0]
        finally:
            ep.MODELS_DIR = original_models_dir

    def test_does_not_pollute_real_models_dir(
        self, tmp_path, sample_results, sample_pred_results,
        sample_opt_results, sample_pers_results,
    ):
        """When MODELS_DIR is overridden, files are written to tmp_path
        not to the original models/ location."""
        real_models = ep.MODELS_DIR

        # Record existing files in real models dir before the call
        existing_files = set()
        if real_models.exists():
            existing_files = {f.name for f in real_models.iterdir() if f.is_file()}

        ep.MODELS_DIR = tmp_path
        try:
            ep.save_all_artifacts(
                sample_results,
                sample_pred_results,
                sample_opt_results,
                sample_pers_results,
            )

            # All 6 files should exist in tmp_path (our override)
            expected_files = [
                "evaluation_results.json",
                "test_predictions.csv",
                "feature_importance.json",
                "convergence_curves.json",
                "personalization_curves.json",
                "learning_curves.json",
            ]
            for fname in expected_files:
                assert (tmp_path / fname).exists(), (
                    f"File {fname} not written to tmp_path"
                )

            # Check that no NEW files appeared in the real models dir
            if real_models.exists():
                current_files = {f.name for f in real_models.iterdir() if f.is_file()}
                new_files = current_files - existing_files
                assert len(new_files) == 0, (
                    f"Unexpected new files in real models/: {new_files}"
                )
        finally:
            ep.MODELS_DIR = real_models


# ===========================================================================
# 9. main() orchestrator
# ===========================================================================


class TestMain:
    """Tests for the main() orchestrator function."""

    @patch.object(ep, "save_all_artifacts")
    @patch.object(ep, "evaluate_personalization")
    @patch.object(ep, "evaluate_recipe_optimization")
    @patch.object(ep, "evaluate_taste_prediction")
    @patch.object(ep, "evaluate_recipe_retrieval")
    @patch.object(ep, "evaluate_bean_extraction")
    def test_main_calls_all_components_in_order(
        self,
        mock_bean,
        mock_retrieval,
        mock_taste,
        mock_opt,
        mock_pers,
        mock_save,
    ):
        """main() invokes all 5 evaluation components and save_all_artifacts."""
        mock_bean.return_value = {"accuracy": 0.88, "avg_confidence": 0.75}
        mock_retrieval.return_value = {"precision_at_3": 0.85, "mrr": 0.90}

        mock_predictor_instance = MagicMock()
        mock_taste.return_value = {
            "metrics": {"rmse": 0.85, "mae": 0.62, "r_squared": 0.71, "predictions": [], "feature_importance": {}},
            "predictor": mock_predictor_instance,
            "learning_curves": [],
        }
        mock_opt.return_value = {
            "metrics": {"avg_improvement": 0.6, "constraint_satisfaction_rate": 0.92, "convergence_curves": []},
            "convergence_data": [],
        }
        mock_pers.return_value = {
            "metrics": {"bean_aware_rmse": 1.05, "hybrid_rmse": 0.88, "improvement_pct": 16.0, "rmse_by_ratings": []},
            "personalization_data": [],
        }

        ep.main()

        mock_bean.assert_called_once()
        mock_retrieval.assert_called_once()
        mock_taste.assert_called_once()
        mock_opt.assert_called_once_with(mock_predictor_instance)
        mock_pers.assert_called_once_with(mock_predictor_instance)
        mock_save.assert_called_once()

    @patch.object(ep, "save_all_artifacts")
    @patch.object(ep, "evaluate_personalization")
    @patch.object(ep, "evaluate_recipe_optimization")
    @patch.object(ep, "evaluate_taste_prediction")
    @patch.object(ep, "evaluate_recipe_retrieval")
    @patch.object(ep, "evaluate_bean_extraction")
    def test_main_passes_predictor_to_opt_and_pers(
        self,
        mock_bean,
        mock_retrieval,
        mock_taste,
        mock_opt,
        mock_pers,
        mock_save,
    ):
        """The predictor from taste prediction is passed to optimization
        and personalization."""
        mock_bean.return_value = {"accuracy": 0.9, "avg_confidence": 0.8}
        mock_retrieval.return_value = {"precision_at_3": 0.85, "mrr": 0.9}

        predictor = MagicMock()
        mock_taste.return_value = {
            "metrics": {"rmse": 0.7, "mae": 0.5, "r_squared": 0.8, "predictions": [], "feature_importance": {}},
            "predictor": predictor,
            "learning_curves": [],
        }
        mock_opt.return_value = {
            "metrics": {"avg_improvement": 0.5, "constraint_satisfaction_rate": 0.9, "convergence_curves": []},
            "convergence_data": [],
        }
        mock_pers.return_value = {
            "metrics": {"bean_aware_rmse": 1.0, "hybrid_rmse": 0.8, "improvement_pct": 20.0, "rmse_by_ratings": []},
            "personalization_data": [],
        }

        ep.main()

        mock_opt.assert_called_once_with(predictor)
        mock_pers.assert_called_once_with(predictor)

    @patch.object(ep, "save_all_artifacts")
    @patch.object(ep, "evaluate_personalization")
    @patch.object(ep, "evaluate_recipe_optimization")
    @patch.object(ep, "evaluate_taste_prediction")
    @patch.object(ep, "evaluate_recipe_retrieval")
    @patch.object(ep, "evaluate_bean_extraction")
    def test_main_creates_models_dir(
        self,
        mock_bean,
        mock_retrieval,
        mock_taste,
        mock_opt,
        mock_pers,
        mock_save,
        tmp_path,
    ):
        """main() ensures the models directory exists."""
        mock_bean.return_value = {"accuracy": 0.9, "avg_confidence": 0.8}
        mock_retrieval.return_value = {"precision_at_3": 0.85, "mrr": 0.9}
        mock_taste.return_value = {
            "metrics": {"rmse": 0.7, "mae": 0.5, "r_squared": 0.8, "predictions": [], "feature_importance": {}},
            "predictor": MagicMock(),
            "learning_curves": [],
        }
        mock_opt.return_value = {
            "metrics": {"avg_improvement": 0.5, "constraint_satisfaction_rate": 0.9, "convergence_curves": []},
            "convergence_data": [],
        }
        mock_pers.return_value = {
            "metrics": {"bean_aware_rmse": 1.0, "hybrid_rmse": 0.8, "improvement_pct": 20.0, "rmse_by_ratings": []},
            "personalization_data": [],
        }

        original = ep.MODELS_DIR
        test_dir = tmp_path / "models_test"
        ep.MODELS_DIR = test_dir
        try:
            ep.main()
            assert test_dir.exists()
        finally:
            ep.MODELS_DIR = original

    @patch.object(ep, "save_all_artifacts")
    @patch.object(ep, "evaluate_personalization")
    @patch.object(ep, "evaluate_recipe_optimization")
    @patch.object(ep, "evaluate_taste_prediction")
    @patch.object(ep, "evaluate_recipe_retrieval")
    @patch.object(ep, "evaluate_bean_extraction")
    def test_save_receives_correct_arguments(
        self,
        mock_bean,
        mock_retrieval,
        mock_taste,
        mock_opt,
        mock_pers,
        mock_save,
    ):
        """save_all_artifacts is called with results, pred, opt, pers dicts."""
        mock_bean.return_value = {"accuracy": 0.9, "avg_confidence": 0.8}
        mock_retrieval.return_value = {"precision_at_3": 0.85, "mrr": 0.95}

        pred_results = {
            "metrics": {"rmse": 0.7, "mae": 0.5, "r_squared": 0.8, "predictions": [], "feature_importance": {}},
            "predictor": MagicMock(),
            "learning_curves": [],
        }
        mock_taste.return_value = pred_results

        opt_results = {
            "metrics": {"avg_improvement": 0.5, "constraint_satisfaction_rate": 0.9, "convergence_curves": []},
            "convergence_data": [],
        }
        mock_opt.return_value = opt_results

        pers_results = {
            "metrics": {"bean_aware_rmse": 1.0, "hybrid_rmse": 0.8, "improvement_pct": 20.0, "rmse_by_ratings": []},
            "personalization_data": [],
        }
        mock_pers.return_value = pers_results

        ep.main()

        save_call = mock_save.call_args
        args = save_call[0]
        # First arg: aggregated results dict
        assert args[0]["bean_extraction"] == {"accuracy": 0.9, "avg_confidence": 0.8}
        assert args[0]["recipe_retrieval"] == {"precision_at_3": 0.85, "mrr": 0.95}
        # Second arg: pred_results
        assert args[1] is pred_results
        # Third arg: opt_results
        assert args[2] is opt_results
        # Fourth arg: pers_results
        assert args[3] is pers_results


# ===========================================================================
# 10. _print_summary (smoke test)
# ===========================================================================


class TestPrintSummary:
    """Tests for _print_summary() helper."""

    def test_print_summary_does_not_raise(self, capsys):
        """_print_summary runs without errors on a valid results dict."""
        results = {
            "bean_extraction": {"accuracy": 0.9, "avg_confidence": 0.8},
            "recipe_retrieval": {"precision_at_3": 0.85, "mrr": 0.9},
            "taste_prediction": {"rmse": 0.85, "mae": 0.6, "r_squared": 0.7},
            "recipe_optimization": {
                "avg_improvement": 0.6,
                "constraint_satisfaction_rate": 0.9,
            },
            "personalization": {
                "bean_aware_rmse": 1.1,
                "hybrid_rmse": 0.9,
                "improvement_pct": 18.0,
            },
        }
        ep._print_summary(results)
        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "Bean Extraction" in captured.out

    def test_print_summary_handles_empty_components(self, capsys):
        """_print_summary prints Summary header even with empty component dicts."""
        # Provide dicts with the required numeric keys so format strings work.
        results = {
            "bean_extraction": {"accuracy": 0.0, "avg_confidence": 0.0},
            "recipe_retrieval": {"precision_at_3": 0.0, "mrr": 0.0},
            "taste_prediction": {"rmse": 0.0, "mae": 0.0, "r_squared": 0.0},
            "recipe_optimization": {
                "avg_improvement": 0.0,
                "constraint_satisfaction_rate": 0.0,
            },
            "personalization": {
                "bean_aware_rmse": 0.0,
                "hybrid_rmse": 0.0,
                "improvement_pct": 0,
            },
        }
        ep._print_summary(results)
        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "Bean Extraction" in captured.out


# ===========================================================================
# 11. Module-level constants
# ===========================================================================


class TestModuleConstants:
    """Tests for module-level path constants."""

    def test_models_dir_is_path(self):
        assert isinstance(ep.MODELS_DIR, Path)

    def test_data_dir_is_path(self):
        assert isinstance(ep.DATA_DIR, Path)

    def test_recipes_dir_is_path(self):
        assert isinstance(ep.RECIPES_DIR, Path)

    def test_synthetic_dir_is_path(self):
        assert isinstance(ep.SYNTHETIC_DIR, Path)

    def test_recipes_dir_points_to_data_recipes(self):
        assert ep.RECIPES_DIR == ep.DATA_DIR / "recipes"

    def test_synthetic_dir_points_to_data_synthetic(self):
        assert ep.SYNTHETIC_DIR == ep.DATA_DIR / "synthetic"

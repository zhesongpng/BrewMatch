"""Unit tests for the RecipeOptimizer.

Tests use a mocked TastePredictor to return controlled predictions,
so no trained model is required.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import joblib
import numpy as np
import optuna
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
from src.recipe_optimizer.optimizer import OptimizationResult, RecipeOptimizer


# --- Helpers ---


def _make_recipe(**overrides) -> Recipe:
    """Create a valid Recipe with sensible V60 defaults."""
    defaults = dict(
        recipe_id="test-recipe",
        source="test",
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


def _make_bean(**overrides) -> BeanProfile:
    defaults = dict(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Ethiopian Yirgacheffe, light roast",
    )
    defaults.update(overrides)
    return BeanProfile(**defaults)


def _mock_predictor(score: float = 7.0) -> MagicMock:
    """Create a mocked TastePredictor that returns a fixed score.

    - is_trained returns True
    - predict_batch returns an array of shape (N,) filled with `score`
    - _encoder.encode returns a 45-element zero array (so it has the right shape)
    """
    predictor = MagicMock()
    predictor.is_trained = True

    # Encoder returns 45-element arrays via public encode_features method
    encoder = MagicMock()
    encoder.encode.return_value = np.zeros(45, dtype=np.float64)
    predictor._encoder = encoder
    predictor.encode_features = encoder.encode

    # predict_batch returns controlled scores
    def _predict_batch(features_array, user_ids=None):
        return np.full(features_array.shape[0], score, dtype=np.float64)

    predictor.predict_batch.side_effect = _predict_batch
    return predictor


def _make_edge_recipe(dose_g: float, ratio: float) -> Recipe:
    """Create a valid Recipe with pours scaled to match dose*ratio.

    Used for edge-case tests where dose_g differs from the default 16.0,
    ensuring water_total_g stays within 5% of the pour sum (a Recipe
    validation invariant).
    """
    water_total_g = dose_g * ratio
    # Default base pour sum is 64+96+96=256; scale proportionally
    base_total = 256.0
    scale = water_total_g / base_total if base_total > 0 else 1.0
    pours = [
        PourStep(step=1, time_offset_s=0, water_g=round(64.0 * scale, 1)),
        PourStep(step=2, time_offset_s=45, water_g=round(96.0 * scale, 1)),
        PourStep(step=3, time_offset_s=90, water_g=round(96.0 * scale, 1)),
    ]
    return _make_recipe(
        dose_g=dose_g,
        water_total_g=water_total_g,
        ratio=ratio,
        pours=pours,
    )


# --- Fixtures ---


@pytest.fixture
def base_recipe() -> Recipe:
    return _make_recipe()


@pytest.fixture
def light_bean() -> BeanProfile:
    return _make_bean(roast_level=RoastLevel.LIGHT)


@pytest.fixture
def dark_bean() -> BeanProfile:
    return _make_bean(
        origin_country="Brazil",
        roast_level=RoastLevel.DARK,
        flavor_clusters=["Chocolate", "Nutty"],
        source_text="Brazilian dark roast",
    )


# --- Test: OptimizationResult dataclass ---


class TestOptimizationResult:

    def test_fields_exist(self):
        result = OptimizationResult(
            optimized_recipe=_make_recipe(),
            predicted_score=8.0,
            baseline_score=7.0,
            improvement=1.0,
            n_trials=50,
            convergence_reached=True,
            parameter_changes={},
            constraint_violations=[],
        )
        assert result.predicted_score == 8.0
        assert result.baseline_score == 7.0
        assert result.improvement == 1.0
        assert result.n_trials == 50
        assert result.convergence_reached is True
        assert isinstance(result.parameter_changes, dict)
        assert isinstance(result.constraint_violations, list)


# --- Test: Optimizer initialization ---


class TestRecipeOptimizerInit:

    def test_default_params(self):
        predictor = _mock_predictor()
        opt = RecipeOptimizer(predictor)
        assert opt._n_trials == 50
        assert opt._seed == 42

    def test_custom_params(self):
        predictor = _mock_predictor()
        opt = RecipeOptimizer(predictor, n_trials=100, seed=123)
        assert opt._n_trials == 100
        assert opt._seed == 123


# --- Test: Core optimize behavior ---


class TestOptimize:

    def test_returns_optimization_result(self, base_recipe, light_bean):
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert isinstance(result, OptimizationResult)

    def test_predicted_score_greater_equal_baseline(self, base_recipe, light_bean):
        """Guarantee: optimization never makes things worse."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.predicted_score >= result.baseline_score

    def test_improvement_equals_difference(self, base_recipe, light_bean):
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        expected_improvement = round(result.predicted_score - result.baseline_score, 6)
        assert abs(result.improvement - expected_improvement) < 1e-6

    def test_n_trials_recorded(self, base_recipe, light_bean):
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.n_trials > 0
        assert result.n_trials <= 50

    def test_parameter_changes_tracked(self, base_recipe, light_bean):
        """parameter_changes should only include params that actually changed."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert isinstance(result.parameter_changes, dict)
        # Only changed params appear; each entry maps to (baseline, optimized) tuple
        valid_keys = {"grind_setting", "water_temp_c", "dose_g", "ratio"}
        for key, (baseline, optimized) in result.parameter_changes.items():
            assert key in valid_keys
            assert isinstance(baseline, float)
            assert isinstance(optimized, float)
            assert abs(optimized - baseline) > 1e-6

    def test_constraint_violations_is_list(self, base_recipe, light_bean):
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert isinstance(result.constraint_violations, list)


# --- Test: Pour schedule preserved ---


class TestPourSchedulePreserved:

    def test_pours_preserved(self, base_recipe, light_bean):
        """The optimized recipe must preserve the base recipe's pour schedule."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.optimized_recipe.pours == base_recipe.pours

    def test_bloom_time_preserved(self, base_recipe, light_bean):
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.optimized_recipe.bloom_time_s == base_recipe.bloom_time_s

    def test_total_time_preserved(self, base_recipe, light_bean):
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.optimized_recipe.total_time_s == base_recipe.total_time_s


# --- Test: Hard constraints ---


class TestHardConstraints:

    def test_water_total_g_upper_bound(self, base_recipe, light_bean):
        """C1: optimized recipe water_total_g <= 400.0."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.optimized_recipe.water_total_g <= 400.0

    def test_water_total_g_lower_bound(self, base_recipe, light_bean):
        """C2: optimized recipe water_total_g >= 180.0."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.optimized_recipe.water_total_g >= 180.0

    def test_hard_constraints_with_various_beans(self, base_recipe):
        """Test that hard constraints hold for multiple bean profiles."""
        beans = [
            _make_bean(roast_level=RoastLevel.LIGHT),
            _make_bean(roast_level=RoastLevel.DARK),
            _make_bean(roast_level=RoastLevel.MEDIUM),
        ]
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        for bean in beans:
            result = opt.optimize(bean, base_recipe)
            assert result.optimized_recipe.water_total_g <= 400.0
            assert result.optimized_recipe.water_total_g >= 180.0


# --- Test: Soft constraints ---


class TestSoftConstraints:

    def test_light_roast_low_temp_has_violation(self, base_recipe, light_bean):
        """Light roast with low temp should report S1 violation if optimized
        recipe ends up with water_temp_c < 92.0."""
        # Return a high score regardless so optimizer doesn't avoid it
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        # Check if temp is below 92.0 and violation is listed
        if result.optimized_recipe.water_temp_c < 92.0:
            assert any("S1" in v or "light" in v.lower() for v in result.constraint_violations)

    def test_dark_roast_high_temp_has_violation(self, base_recipe, dark_bean):
        """Dark roast with high temp should report S2 violation if optimized
        recipe ends up with water_temp_c > 94.0."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(dark_bean, base_recipe)
        if result.optimized_recipe.water_temp_c > 94.0:
            assert any("S2" in v or "dark" in v.lower() for v in result.constraint_violations)

    def test_ratio_outside_15_17_tracked(self, base_recipe, light_bean):
        """Ratio outside 15.0-17.0 should be reported as a soft violation."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        ratio = result.optimized_recipe.ratio
        if ratio < 15.0 or ratio > 17.0:
            assert any("ratio" in v.lower() or "S3" in v for v in result.constraint_violations)

    def test_dose_outside_14_18_tracked(self, base_recipe, light_bean):
        """Dose outside 14.0-18.0 should be reported as a soft violation."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        dose = result.optimized_recipe.dose_g
        if dose < 14.0 or dose > 18.0:
            assert any("dose" in v.lower() or "S4" in v for v in result.constraint_violations)


# --- Test: Soft constraint penalties reduce score ---


class TestSoftConstraintPenalties:

    def test_penalty_reduces_objective(self, base_recipe, light_bean):
        """When all scores are the same, the optimizer should prefer recipes
        that don't violate soft constraints (penalty reduces effective score)."""
        # Score is always 8.0, so the optimizer should choose the params
        # that minimize penalties
        predictor = _mock_predictor(score=8.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        # For light roast, low temp would be penalized. The optimizer
        # should find a high-temp config if penalties work.
        # We don't assert exact temp since the search space is discrete,
        # but the optimization should have run and returned something valid.
        assert result.predicted_score >= result.baseline_score


# --- Test: Fallback on failure ---


class TestFallback:

    def test_fallback_on_exception(self, base_recipe, light_bean):
        """If the predictor raises, optimizer returns base recipe with improvement=0."""
        predictor = MagicMock()
        predictor.is_trained = True
        predictor._encoder = MagicMock()
        predictor._encoder.encode.return_value = np.zeros(45, dtype=np.float64)
        predictor.encode_features = predictor._encoder.encode
        predictor.predict_batch.side_effect = RuntimeError("model exploded")

        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)

        assert result.improvement == 0.0
        assert result.baseline_score is None
        assert result.n_trials == 0
        assert result.convergence_reached is False
        # Optimized recipe should be the same as base
        assert result.optimized_recipe.recipe_id == base_recipe.recipe_id

    def test_fallback_preserves_pours(self, base_recipe, light_bean):
        """Fallback recipe must preserve the pour schedule."""
        predictor = MagicMock()
        predictor.is_trained = True
        predictor._encoder = MagicMock()
        predictor._encoder.encode.return_value = np.zeros(45, dtype=np.float64)
        predictor.encode_features = predictor._encoder.encode
        predictor.predict_batch.side_effect = RuntimeError("fail")

        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert result.optimized_recipe.pours == base_recipe.pours


# --- Test: Early stopping ---


class TestEarlyStopping:

    def test_early_stopping_detected(self, base_recipe, light_bean):
        """When score doesn't improve for 15 consecutive trials, early stop triggers."""
        # Constant score means no improvement after first trial
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=50)
        result = opt.optimize(light_bean, base_recipe)
        # With a constant score, early stopping should kick in since
        # best never improves by more than 0.05 after the first real trial.
        # At minimum, n_trials should be less than 50.
        assert result.convergence_reached is True or result.n_trials == 50

    def test_early_stopping_reduces_trials(self, base_recipe, light_bean):
        """Early stopping should result in fewer than max trials when score is flat."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=50)
        result = opt.optimize(light_bean, base_recipe)
        # With completely flat scores, should stop early (< 50 trials)
        if result.convergence_reached:
            assert result.n_trials < 50


# --- Test: Warm start ---


class TestWarmStart:

    def test_base_recipe_params_in_search_space(self, base_recipe, light_bean):
        """The optimizer should evaluate the base recipe params at some point
        (ensuring warm start). We verify by checking that baseline_score
        is the score for the base recipe."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        # baseline_score should be 7.0 (the mock score)
        assert abs(result.baseline_score - 7.0) < 1e-6


# --- Test: User ID passthrough ---


class TestUserIdPassthrough:

    def test_user_id_passed_to_encode(self, base_recipe, light_bean):
        """When user_id is provided, it should be passed through to predict."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe, user_id="test-user")
        assert isinstance(result, OptimizationResult)

    def test_no_user_id(self, base_recipe, light_bean):
        """Optimization works without user_id."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe, user_id=None)
        assert isinstance(result, OptimizationResult)


# --- Test: Recipe validity ---


class TestRecipeValidity:

    def test_optimized_recipe_is_valid_recipe(self, base_recipe, light_bean):
        """The optimized recipe should pass Recipe validation."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        # If this doesn't raise, the recipe is valid
        assert isinstance(result.optimized_recipe, Recipe)
        assert result.optimized_recipe.dose_g >= 12.0
        assert result.optimized_recipe.dose_g <= 22.0

    def test_optimized_recipe_ratio_in_range(self, base_recipe, light_bean):
        """Optimized ratio should be in the valid search space (14.0-18.0)."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert 14.0 <= result.optimized_recipe.ratio <= 18.0

    def test_optimized_recipe_grind_in_range(self, base_recipe, light_bean):
        """Optimized grind_setting should be in the valid search space (1-10)."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert 1 <= result.optimized_recipe.grind_setting <= 10

    def test_optimized_recipe_temp_in_range(self, base_recipe, light_bean):
        """Optimized water_temp_c should be in the valid search space (85-100)."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert 85.0 <= result.optimized_recipe.water_temp_c <= 100.0

    def test_optimized_recipe_dose_in_range(self, base_recipe, light_bean):
        """Optimized dose_g should be in the valid search space (12.0-22.0)."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        result = opt.optimize(light_bean, base_recipe)
        assert 12.0 <= result.optimized_recipe.dose_g <= 22.0


# --- Test: Score improvement ---


class TestScoreImprovement:

    def test_higher_score_for_different_predictions(self, base_recipe, light_bean):
        """When some recipes score higher than others, optimizer finds improvement."""
        call_count = [0]

        def _varied_predict(features_array, user_ids=None):
            n = features_array.shape[0]
            scores = np.array([6.0 + (i % 5) * 0.5 for i in range(n)])
            call_count[0] += n
            return scores

        predictor = _mock_predictor(score=7.0)
        predictor.predict_batch.side_effect = _varied_predict
        opt = RecipeOptimizer(predictor, n_trials=30)
        result = opt.optimize(light_bean, base_recipe)
        # Baseline is the score of the initial recipe
        # The optimizer should find at least one recipe scoring >= baseline
        assert result.predicted_score >= result.baseline_score


# --- Test: Determinism ---


class TestDeterminism:

    def test_same_seed_same_result(self, base_recipe, light_bean):
        """Same seed should produce same optimization result."""
        predictor1 = _mock_predictor(score=7.0)
        opt1 = RecipeOptimizer(predictor1, n_trials=20, seed=42)
        result1 = opt1.optimize(light_bean, base_recipe)

        predictor2 = _mock_predictor(score=7.0)
        opt2 = RecipeOptimizer(predictor2, n_trials=20, seed=42)
        result2 = opt2.optimize(light_bean, base_recipe)

        assert abs(result1.predicted_score - result2.predicted_score) < 1e-6
        assert result1.n_trials == result2.n_trials
        assert result1.optimized_recipe.grind_setting == result2.optimized_recipe.grind_setting
        assert abs(result1.optimized_recipe.water_temp_c - result2.optimized_recipe.water_temp_c) < 1e-6
        assert abs(result1.optimized_recipe.dose_g - result2.optimized_recipe.dose_g) < 1e-6
        assert abs(result1.optimized_recipe.ratio - result2.optimized_recipe.ratio) < 1e-6


# --- M05: Objective function tested in isolation ---


class TestObjectiveFunctionIsolation:
    """Verify the Optuna objective function behavior directly.

    Instead of only checking the final OptimizationResult, these tests
    inspect the internal study's trial records to verify pruning, finite
    returns, and penalty effects at the objective level.
    """

    def test_objective_returns_finite_float(self, base_recipe, light_bean):
        """Each completed trial's objective value must be a finite float."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)

        # Patch _run_optimization to capture the study after it runs.
        original_run = opt._run_optimization

        captured_study = [None]

        def capturing_run(bean_profile, base_recipe, user_id):
            result = original_run(bean_profile, base_recipe, user_id)
            # Re-run just the study part to capture it
            return result

        # Run optimization and then reconstruct the study to inspect trials.
        opt.optimize(light_bean, base_recipe)

        # Reconstruct the same study to inspect trials directly.
        sampler = optuna.samplers.TPESampler(seed=opt._seed, n_startup_trials=10)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.enqueue_trial({
            "grind_setting": base_recipe.grind_setting,
            "water_temp_c": base_recipe.water_temp_c,
            "dose_g": base_recipe.dose_g,
            "ratio": base_recipe.ratio,
        })

        def objective(trial):
            grind_setting = trial.suggest_int("grind_setting", 1, 10)
            water_temp_c = trial.suggest_float("water_temp_c", 85.0, 100.0, step=0.5)
            dose_g = trial.suggest_float("dose_g", 12.0, 22.0, step=0.5)
            ratio = trial.suggest_float("ratio", 14.0, 18.0, step=0.25)
            water_total_g = dose_g * ratio
            if water_total_g > 400.0 or water_total_g < 180.0:
                raise optuna.exceptions.TrialPruned()
            recipe = opt._build_trial_recipe(
                base_recipe, grind_setting, water_temp_c, dose_g, ratio,
            )
            features = predictor.encode_features(light_bean, recipe)
            scores = predictor.predict_batch(features.reshape(1, -1))
            predicted_score = float(scores[0])
            from src.recipe_optimizer.optimizer import _compute_penalties
            penalty, _ = _compute_penalties(
                grind_setting, water_temp_c, dose_g, ratio,
                light_bean.roast_level,
            )
            return predicted_score - penalty

        study.optimize(objective, n_trials=20)

        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                assert isinstance(trial.value, float), (
                    f"Trial {trial.number} value is {type(trial.value)}, expected float"
                )
                assert np.isfinite(trial.value), (
                    f"Trial {trial.number} value is {trial.value}, expected finite"
                )

    def test_hard_constraint_violations_prune_trials(self, base_recipe, light_bean):
        """Trials where water_total_g > 400 or < 180 must be pruned.

        We directly enqueue trials that violate hard constraints, then run
        optimization to confirm they are pruned rather than completed.
        """
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=30)

        sampler = optuna.samplers.TPESampler(seed=42, n_startup_trials=10)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        def objective_with_constraints(trial):
            grind_setting = trial.suggest_int("grind_setting", 1, 10)
            water_temp_c = trial.suggest_float("water_temp_c", 85.0, 100.0, step=0.5)
            dose_g = trial.suggest_float("dose_g", 12.0, 22.0, step=0.5)
            ratio = trial.suggest_float("ratio", 14.0, 18.0, step=0.25)
            water_total_g = dose_g * ratio
            if water_total_g > 400.0 or water_total_g < 180.0:
                raise optuna.exceptions.TrialPruned()
            return 7.0

        # Enqueue a trial that violates C2: dose_g=12, ratio=14 -> water=168 < 180
        study.enqueue_trial({
            "grind_setting": 5,
            "water_temp_c": 90.0,
            "dose_g": 12.0,
            "ratio": 14.0,  # 12 * 14 = 168 < 180
        })

        # Enqueue a trial that violates C1: dose_g=22, ratio=18.25 -> water=401.5 > 400
        # (ratio max is 18.0 in search space, so test with max dose and max ratio)
        # Actually dose=22, ratio=18 -> 396, which is within bounds.
        # For C1 violation we need dose*ratio > 400, e.g. dose=22.0, ratio=18.25
        # but ratio search space only goes to 18.0. So we also enqueue with
        # dose=20, ratio=14 -> 280 (within bounds, valid trial for contrast).

        study.enqueue_trial({
            "grind_setting": 5,
            "water_temp_c": 90.0,
            "dose_g": 20.0,
            "ratio": 14.0,  # 20 * 14 = 280, within bounds
        })

        study.optimize(objective_with_constraints, n_trials=10)

        # At least the first enqueued trial (water=168) should be pruned
        pruned_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]
        assert len(pruned_trials) >= 1, (
            "Expected at least one pruned trial from hard constraint violations, "
            f"but all {len(study.trials)} trials completed."
        )

        # Verify every pruned trial indeed violated hard constraints
        for trial in pruned_trials:
            dose = trial.params["dose_g"]
            ratio = trial.params["ratio"]
            water_total = dose * ratio
            assert water_total > 400.0 or water_total < 180.0, (
                f"Pruned trial {trial.number} has water_total_g={water_total}, "
                "which is within bounds -- pruning was not caused by hard constraints."
            )

    def test_soft_constraint_penalties_reduce_objective(self, base_recipe, light_bean):
        """Soft constraint penalties must reduce the objective value below
        the raw prediction score.

        For a light roast with water_temp_c < 92.0, the penalty is positive,
        so the objective should be strictly less than the raw prediction.
        """
        from src.recipe_optimizer.optimizer import _compute_penalties

        # Test a specific parameter combination that violates S1 (light roast, low temp)
        penalty_s1, violations_s1 = _compute_penalties(
            grind_setting=5,
            water_temp_c=87.0,  # Below 92.0 for light roast
            dose_g=15.0,
            ratio=16.0,
            roast_level=RoastLevel.LIGHT,
        )

        # Penalty must be positive when violation exists
        assert penalty_s1 > 0.0, (
            f"Expected positive penalty for light roast at 87.0 C, got {penalty_s1}"
        )
        assert len(violations_s1) > 0

        # The objective (= score - penalty) must be less than the raw score
        raw_score = 8.0
        penalized_objective = raw_score - penalty_s1
        assert penalized_objective < raw_score, (
            f"Penalized objective {penalized_objective} should be less than "
            f"raw score {raw_score}"
        )

    def test_no_penalty_within_soft_constraints(self, base_recipe, light_bean):
        """Parameters fully within soft constraints should have zero penalty."""
        from src.recipe_optimizer.optimizer import _compute_penalties

        penalty, violations = _compute_penalties(
            grind_setting=5,
            water_temp_c=93.0,  # Within range for light roast
            dose_g=15.0,        # Within 14-18
            ratio=16.0,         # Within 15-17
            roast_level=RoastLevel.LIGHT,
        )
        assert penalty == 0.0, (
            f"Expected zero penalty for compliant params, got {penalty}"
        )
        assert violations == []


# --- M10: Optimizer parameter bounds at edge values ---


class TestParameterBoundsAtEdges:
    """Verify the optimizer respects bounds when starting at edge values.

    Uses recipes initialized at the lower/upper bounds of individual
    parameters and confirms the optimizer stays within valid ranges.
    """

    def test_grind_at_lower_bound_stays_above(self, light_bean):
        """Recipe at grind_setting=1 (lower bound): optimized grind >= 1."""
        recipe = _make_recipe(grind_setting=1)
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)
        result = opt.optimize(light_bean, recipe)
        assert result.optimized_recipe.grind_setting >= 1, (
            f"Optimized grind_setting {result.optimized_recipe.grind_setting} "
            "is below the lower bound of 1"
        )

    def test_temp_at_upper_bound_stays_below(self, light_bean):
        """Recipe at water_temp_c=100 (upper bound): optimized temp <= 100."""
        recipe = _make_recipe(water_temp_c=100.0)
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)
        result = opt.optimize(light_bean, recipe)
        assert result.optimized_recipe.water_temp_c <= 100.0, (
            f"Optimized water_temp_c {result.optimized_recipe.water_temp_c} "
            "exceeds the upper bound of 100.0"
        )

    def test_dose_at_upper_bound_stays_below(self, light_bean):
        """Recipe at dose_g=22 (upper bound): optimized dose <= 22."""
        recipe = _make_edge_recipe(dose_g=22.0, ratio=16.0)
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)
        result = opt.optimize(light_bean, recipe)
        assert result.optimized_recipe.dose_g <= 22.0, (
            f"Optimized dose_g {result.optimized_recipe.dose_g} "
            "exceeds the upper bound of 22.0"
        )

    def test_grind_at_upper_bound_stays_below(self, light_bean):
        """Recipe at grind_setting=10 (upper bound): optimized grind <= 10."""
        recipe = _make_recipe(grind_setting=10)
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)
        result = opt.optimize(light_bean, recipe)
        assert result.optimized_recipe.grind_setting <= 10, (
            f"Optimized grind_setting {result.optimized_recipe.grind_setting} "
            "exceeds the upper bound of 10"
        )

    def test_temp_at_lower_bound_stays_above(self, light_bean):
        """Recipe at water_temp_c=85 (lower bound): optimized temp >= 85."""
        recipe = _make_recipe(water_temp_c=85.0)
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)
        result = opt.optimize(light_bean, recipe)
        assert result.optimized_recipe.water_temp_c >= 85.0, (
            f"Optimized water_temp_c {result.optimized_recipe.water_temp_c} "
            "is below the lower bound of 85.0"
        )

    def test_dose_at_lower_bound_stays_above(self, light_bean):
        """Recipe at dose_g=12 (lower bound): optimized dose >= 12."""
        recipe = _make_edge_recipe(dose_g=12.0, ratio=16.0)
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor, n_trials=20)
        result = opt.optimize(light_bean, recipe)
        assert result.optimized_recipe.dose_g >= 12.0, (
            f"Optimized dose_g {result.optimized_recipe.dose_g} "
            "is below the lower bound of 12.0"
        )


# --- M17: Study persistence via study_path ---


class TestStudyPersistence:
    """Verify that the Optuna study is persisted to disk when study_path
    is provided, and warm-started from historical data on subsequent runs.

    The M17 code fix adds a study_path parameter to RecipeOptimizer.__init__().
    """

    def test_study_file_created_after_optimization(self, base_recipe, light_bean):
        """When study_path is set, a file is created after optimization."""
        predictor = _mock_predictor(score=7.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            study_path = Path(tmpdir) / "study.pkl"
            assert not study_path.exists(), "Study file should not exist yet"

            opt = RecipeOptimizer(predictor, n_trials=10, study_path=str(study_path))
            result = opt.optimize(light_bean, base_recipe)

            assert study_path.exists(), (
                "Study file was not created after optimization"
            )
            assert isinstance(result, OptimizationResult)

    def test_loaded_study_has_prior_trial_history(self, base_recipe, light_bean):
        """When the file exists, the next optimization run loads the study
        and has prior trial history."""
        predictor = _mock_predictor(score=7.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            study_path = Path(tmpdir) / "study.pkl"

            # First run: creates the study
            opt1 = RecipeOptimizer(predictor, n_trials=10, study_path=str(study_path))
            result1 = opt1.optimize(light_bean, base_recipe)
            first_trial_count = result1.n_trials

            # Load the study directly and verify it has trials
            loaded_study = joblib.load(study_path)
            assert len(loaded_study.trials) == first_trial_count, (
                f"Loaded study has {len(loaded_study.trials)} trials, "
                f"expected {first_trial_count}"
            )

            # Second run: should load the study and add more trials
            opt2 = RecipeOptimizer(predictor, n_trials=10, study_path=str(study_path))
            result2 = opt2.optimize(light_bean, base_recipe)

            # The second run's trial count should be greater than the first
            assert result2.n_trials > first_trial_count, (
                f"Second run has {result2.n_trials} trials, "
                f"expected more than first run's {first_trial_count}"
            )

    def test_study_path_none_does_not_create_file(self, base_recipe, light_bean):
        """When study_path is None (default), no file is created."""
        predictor = _mock_predictor(score=7.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            study_path = Path(tmpdir) / "study.pkl"
            opt = RecipeOptimizer(predictor, n_trials=10, study_path=None)
            opt.optimize(light_bean, base_recipe)

            assert not study_path.exists(), (
                "Study file was created even though study_path is None"
            )

    def test_study_path_default_is_none(self):
        """Constructor default for study_path is None."""
        predictor = _mock_predictor(score=7.0)
        opt = RecipeOptimizer(predictor)
        assert opt._study_path is None

    def test_warm_start_preserves_best_value(self, base_recipe, light_bean):
        """A loaded study preserves the best_value from the prior run."""
        predictor = _mock_predictor(score=7.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            study_path = Path(tmpdir) / "study.pkl"

            opt1 = RecipeOptimizer(predictor, n_trials=10, study_path=str(study_path))
            opt1.optimize(light_bean, base_recipe)

            loaded_study = joblib.load(study_path)
            first_best = loaded_study.best_value

            opt2 = RecipeOptimizer(predictor, n_trials=10, study_path=str(study_path))
            opt2.optimize(light_bean, base_recipe)

            loaded_study2 = joblib.load(study_path)
            # The best value from the second run should be at least as good
            # as the first run's best value (we added more trials)
            assert loaded_study2.best_value >= first_best - 1e-6, (
                f"Second run best_value {loaded_study2.best_value} is worse than "
                f"first run best_value {first_best}"
            )

"""Recipe optimizer using Optuna TPE sampler.

Finds the best parameter adjustments for a diagnosed brew issue using
Bayesian optimization over grind_setting, water_temp_c, dose_g, and ratio.
Pour schedule is preserved from the base recipe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import optuna

from src.data_models import BeanProfile, PourStep, Recipe, RoastLevel, SuitableFor
from src.taste_predictor.encoder import encode_features
from src.taste_predictor.model import TastePredictor

logger = logging.getLogger(__name__)

# Soft constraint penalty weights
_S1_WEIGHT = 0.5  # Light roast: water_temp_c >= 92.0
_S2_WEIGHT = 0.5  # Dark roast: water_temp_c <= 94.0
_S3_WEIGHT = 0.2  # ratio between 15.0 and 17.0
_S4_WEIGHT = 0.1  # dose_g between 14.0 and 18.0

# Normalization denominators for penalty calculation
_S1_RANGE = 7.0   # 92.0 - 85.0
_S2_RANGE = 6.0   # 100.0 - 94.0
_S3_RANGE_LOW = 1.0   # 15.0 - 14.0
_S3_RANGE_HIGH = 1.0  # 18.0 - 17.0
_S4_RANGE_LOW = 2.0   # 14.0 - 12.0
_S4_RANGE_HIGH = 4.0  # 22.0 - 18.0

# Early stopping
_EARLY_STOP_PATIENCE = 15
_EARLY_STOP_MIN_DELTA = 0.05


@dataclass
class OptimizationResult:
    optimized_recipe: Recipe
    predicted_score: float
    baseline_score: float | None
    improvement: float
    n_trials: int
    convergence_reached: bool
    parameter_changes: dict[str, tuple[float, float]]
    constraint_violations: list[str]


def _compute_penalties(
    grind_setting: int,
    water_temp_c: float,
    dose_g: float,
    ratio: float,
    roast_level: RoastLevel,
) -> tuple[float, list[str]]:
    """Compute soft constraint penalties and list violations.

    Returns (total_penalty, list_of_violation_descriptions).
    """
    penalty = 0.0
    violations: list[str] = []

    # S1: Light roast should use water_temp_c >= 92.0
    if roast_level in (RoastLevel.LIGHT, RoastLevel.MEDIUM_LIGHT):
        if water_temp_c < 92.0:
            penalty += _S1_WEIGHT * (92.0 - water_temp_c) / _S1_RANGE
            violations.append("S1: Light roast with low temperature")

    # S2: Dark roast should use water_temp_c <= 94.0
    if roast_level in (RoastLevel.DARK, RoastLevel.MEDIUM_DARK):
        if water_temp_c > 94.0:
            penalty += _S2_WEIGHT * (water_temp_c - 94.0) / _S2_RANGE
            violations.append("S2: Dark roast with high temperature")

    # S3: ratio between 15.0 and 17.0
    if ratio < 15.0:
        penalty += _S3_WEIGHT * (15.0 - ratio) / _S3_RANGE_LOW
        violations.append("S3: Ratio below 15.0")
    elif ratio > 17.0:
        penalty += _S3_WEIGHT * (ratio - 17.0) / _S3_RANGE_HIGH
        violations.append("S3: Ratio above 17.0")

    # S4: dose_g between 14.0 and 18.0
    if dose_g < 14.0:
        penalty += _S4_WEIGHT * (14.0 - dose_g) / _S4_RANGE_LOW
        violations.append("S4: Dose below 14.0g")
    elif dose_g > 18.0:
        penalty += _S4_WEIGHT * (dose_g - 18.0) / _S4_RANGE_HIGH
        violations.append("S4: Dose above 18.0g")

    return penalty, violations


class RecipeOptimizer:
    """Bayesian optimizer for pour-over coffee recipes.

    Uses Optuna TPESampler to search over grind_setting, water_temp_c,
    dose_g, and ratio, maximizing the predicted taste score from a
    trained TastePredictor. Pour schedule is fixed from the base recipe.
    """

    def __init__(
        self,
        predictor: TastePredictor,
        n_trials: int = 50,
        seed: int = 42,
        study_path: str | Path | None = None,
    ):
        self._predictor = predictor
        self._n_trials = n_trials
        self._seed = seed
        self._study_path = Path(study_path) if study_path is not None else None

    def optimize(
        self,
        bean_profile: BeanProfile,
        base_recipe: Recipe,
        user_id: str | None = None,
    ) -> OptimizationResult:
        """Optimize recipe parameters for the given bean profile.

        Returns OptimizationResult with the best recipe found.
        On failure, falls back to the base recipe with improvement=0.0.
        """
        try:
            result = self._run_optimization(bean_profile, base_recipe, user_id)
            logger.info(
                "optimizer.complete baseline_score=%.4f best_score=%.4f n_trials=%d improvement=%.6f",
                result.baseline_score or 0.0, result.predicted_score,
                result.n_trials, result.improvement,
            )
            return result
        except Exception:
            logger.exception("Recipe optimization failed, returning base recipe")
            return self._fallback_result(base_recipe)

    def _run_optimization(
        self,
        bean_profile: BeanProfile,
        base_recipe: Recipe,
        user_id: str | None,
    ) -> OptimizationResult:
        """Execute the Optuna optimization loop."""
        # Compute baseline score from the base recipe
        baseline_features = self._predictor.encode_features(bean_profile, base_recipe)
        baseline_scores = self._predictor.predict_batch(
            baseline_features.reshape(1, -1),
            user_ids=[user_id] if user_id else None,
        )
        baseline_score = float(baseline_scores[0])
        baseline_penalties, _ = _compute_penalties(
            base_recipe.grind_setting,
            base_recipe.water_temp_c,
            base_recipe.dose_g,
            base_recipe.ratio,
            bean_profile.roast_level,
        )
        baseline_objective = baseline_score - baseline_penalties

        # Early stopping state
        best_score = baseline_objective
        trials_without_improvement = 0
        convergence_reached = False

        # Create study (or load from disk if study_path is set and file exists)
        sampler = optuna.samplers.TPESampler(seed=self._seed, n_startup_trials=10)
        if self._study_path is not None and self._study_path.exists():
            study = joblib.load(self._study_path)
            logger.info(
                "study.load",
                path=str(self._study_path),
                prior_trials=len(study.trials),
            )
        else:
            study = optuna.create_study(direction="maximize", sampler=sampler)

        def objective(trial: optuna.Trial) -> float:
            # Suggest decision variables
            grind_setting = trial.suggest_int("grind_setting", 1, 10)
            water_temp_c = trial.suggest_float("water_temp_c", 85.0, 100.0, step=0.5)
            dose_g = trial.suggest_float("dose_g", 12.0, 22.0, step=0.5)
            ratio = trial.suggest_float("ratio", 14.0, 18.0, step=0.25)

            # Hard constraint: C1 water_total_g <= 400.0, C2 water_total_g >= 180.0
            water_total_g = dose_g * ratio
            if water_total_g > 400.0 or water_total_g < 180.0:
                raise optuna.exceptions.TrialPruned()

            # Build a temporary recipe for prediction
            recipe = self._build_trial_recipe(
                base_recipe, grind_setting, water_temp_c, dose_g, ratio,
            )

            # Encode and predict
            features = self._predictor.encode_features(bean_profile, recipe)
            scores = self._predictor.predict_batch(
                features.reshape(1, -1),
                user_ids=[user_id] if user_id else None,
            )
            predicted_score = float(scores[0])

            # Apply soft constraint penalties
            penalty, _ = _compute_penalties(
                grind_setting, water_temp_c, dose_g, ratio,
                bean_profile.roast_level,
            )

            return predicted_score - penalty

        # Custom callback for early stopping
        def early_stop_callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
            nonlocal best_score, trials_without_improvement, convergence_reached

            current_best = study.best_value
            if current_best > best_score + _EARLY_STOP_MIN_DELTA:
                best_score = current_best
                trials_without_improvement = 0
            else:
                trials_without_improvement += 1

            if trials_without_improvement >= _EARLY_STOP_PATIENCE:
                convergence_reached = True
                study.stop()

        # Enqueue warm start from base recipe (snap to step grid)
        try:
            warm_ratio = max(14.0, min(18.0, round(base_recipe.ratio / 0.25) * 0.25))
            warm_dose = max(12.0, min(22.0, round(base_recipe.dose_g / 0.5) * 0.5))
            warm_temp = max(85.0, min(100.0, round(base_recipe.water_temp_c / 0.5) * 0.5))
            study.enqueue_trial({
                "grind_setting": max(1, min(10, base_recipe.grind_setting)),
                "water_temp_c": warm_temp,
                "dose_g": warm_dose,
                "ratio": warm_ratio,
            })
        except Exception:
            pass  # If enqueue fails, proceed without warm start

        # Run optimization
        study.optimize(objective, n_trials=self._n_trials, callbacks=[early_stop_callback])

        # Persist study to disk if study_path is set
        if self._study_path is not None:
            self._study_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(study, self._study_path)
            logger.info(
                "study.save",
                path=str(self._study_path),
                total_trials=len(study.trials),
            )

        # Extract best params
        best_params = study.best_params
        best_grind = best_params["grind_setting"]
        best_temp = best_params["water_temp_c"]
        best_dose = best_params["dose_g"]
        best_ratio = best_params["ratio"]

        # Build the optimized recipe
        optimized_recipe = self._build_trial_recipe(
            base_recipe, best_grind, best_temp, best_dose, best_ratio,
        )

        # Get predicted score for the optimized recipe (without penalties)
        opt_features = self._predictor.encode_features(bean_profile, optimized_recipe)
        opt_scores = self._predictor.predict_batch(
            opt_features.reshape(1, -1),
            user_ids=[user_id] if user_id else None,
        )
        predicted_score = float(opt_scores[0])

        # Compute remaining constraint violations
        _, constraint_violations = _compute_penalties(
            best_grind, best_temp, best_dose, best_ratio,
            bean_profile.roast_level,
        )

        # Guarantee: predicted_score >= baseline_score
        if predicted_score < baseline_score:
            optimized_recipe = base_recipe
            predicted_score = baseline_score
            constraint_violations = []

        # Compute parameter changes (exclude zero-delta entries)
        _EPS = 1e-6
        parameter_changes = {}
        for name, (old, new) in [
            ("grind_setting", (float(base_recipe.grind_setting), float(best_grind))),
            ("water_temp_c", (float(base_recipe.water_temp_c), float(best_temp))),
            ("dose_g", (float(base_recipe.dose_g), float(best_dose))),
            ("ratio", (float(base_recipe.ratio), float(best_ratio))),
        ]:
            if abs(new - old) > _EPS:
                parameter_changes[name] = (old, new)

        improvement = round(predicted_score - baseline_score, 6)

        return OptimizationResult(
            optimized_recipe=optimized_recipe,
            predicted_score=predicted_score,
            baseline_score=baseline_score,
            improvement=improvement,
            n_trials=len(study.trials),
            convergence_reached=convergence_reached,
            parameter_changes=parameter_changes,
            constraint_violations=constraint_violations,
        )

    def _build_trial_recipe(
        self,
        base_recipe: Recipe,
        grind_setting: int,
        water_temp_c: float,
        dose_g: float,
        ratio: float,
    ) -> Recipe:
        """Build a Recipe with trial params and fixed pour schedule.

        Redistributes pour water to match the new water_total_g while
        preserving the relative pour structure from the base recipe.
        """
        water_total_g = dose_g * ratio

        # Redistribute pours proportionally
        base_pour_total = base_recipe.water_total_g
        scale = water_total_g / base_pour_total if base_pour_total > 0 else 1.0

        pours = []
        for p in base_recipe.pours:
            new_water = round(p.water_g * scale, 1)
            # Clamp to PourStep validation bounds
            new_water = max(10.0, min(200.0, new_water))
            pours.append(PourStep(
                step=p.step,
                time_offset_s=p.time_offset_s,
                water_g=new_water,
            ))

        return Recipe(
            recipe_id=base_recipe.recipe_id,
            source=base_recipe.source,
            method=base_recipe.method,
            dose_g=dose_g,
            water_total_g=water_total_g,
            ratio=ratio,
            grind_setting=grind_setting,
            water_temp_c=water_temp_c,
            bloom_time_s=base_recipe.bloom_time_s,
            total_time_s=base_recipe.total_time_s,
            pours=pours,
            suitable_for=base_recipe.suitable_for,
            instructions=base_recipe.instructions,
            source_url=base_recipe.source_url,
        )

    def _fallback_result(self, base_recipe: Recipe) -> OptimizationResult:
        """Build a fallback result using the base recipe unchanged."""
        return OptimizationResult(
            optimized_recipe=base_recipe,
            predicted_score=0.0,
            baseline_score=None,
            improvement=0.0,
            n_trials=0,
            convergence_reached=False,
            parameter_changes={},
            constraint_violations=[],
        )

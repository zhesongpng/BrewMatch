"""Diagnosis engine for BrewMatch pour-over coffee troubleshooting.

Uses perturb-and-score to identify which parameter changes would most
improve a user's brew based on reported directional flags (too_sour,
too_bitter, etc.). Generates ranked, actionable suggestions with
human-readable explanations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Optional

logger = logging.getLogger(__name__)

from src.data_models import (
    BeanProfile,
    DIRECTIONAL_FLAGS,
    Recipe,
)
from src.taste_predictor.model import TastePredictor


# --- Valid parameter ranges for clamping ---
PARAM_RANGES: dict[str, tuple[float, float]] = {
    "grind_setting": (1.0, 10.0),
    "water_temp_c": (85.0, 98.0),  # recommendation ceiling (storage allows 100C)
    "dose_g": (12.0, 22.0),
    "ratio": (14.0, 18.0),
}

# --- Perturbation configs: range offset and step ---
PERTURBATION_CONFIG: dict[str, tuple[float, float]] = {
    # (max offset from current, step size)
    "grind_setting": (3.0, 1.0),
    "water_temp_c": (5.0, 0.5),
    "dose_g": (4.0, 0.5),
    "ratio": (2.0, 0.25),
}

# --- Expected direction per (param, flag) based on coffee science ---
# "increase" = template says raise the value; "decrease" = template says lower it
_EXPECTED_DIRECTION: dict[tuple[str, str], str] = {
    ("water_temp_c", "too_sour"): "increase",
    ("water_temp_c", "too_bitter"): "decrease",
    ("water_temp_c", "too_weak"): "increase",
    ("water_temp_c", "too_harsh"): "decrease",
    ("water_temp_c", "astringent"): "decrease",
    ("grind_setting", "too_sour"): "decrease",   # finer = lower number
    ("grind_setting", "too_bitter"): "increase",  # coarser = higher number
    ("grind_setting", "too_weak"): "decrease",
    ("grind_setting", "too_harsh"): "increase",
    ("dose_g", "too_sour"): "increase",
    ("dose_g", "too_bitter"): "decrease",
    ("dose_g", "too_weak"): "increase",
    ("ratio", "too_weak"): "decrease",            # lower ratio = more concentrated
    ("ratio", "too_sour"): "decrease",
    ("ratio", "too_bitter"): "increase",
}

# --- Directional flag knowledge ---
FLAG_ROOT_CAUSES: dict[str, str] = {
    "too_sour": "under-extraction",
    "too_bitter": "over-extraction",
    "too_weak": "under-extraction or low dose",
    "too_harsh": "over-extraction or high temperature",
    "astringent": "uneven extraction",
}

FLAG_ASSESSMENT: dict[str, str] = {
    "too_sour": "Your brew tastes sour, which typically indicates under-extraction. "
                "The coffee compounds haven't fully dissolved into the water.",
    "too_bitter": "Your brew tastes bitter, which typically indicates over-extraction. "
                  "Too many compounds (including harsh ones) have been dissolved.",
    "too_weak": "Your brew tastes weak, suggesting insufficient coffee solubles "
                "in the cup. This could be from too little coffee or under-extraction.",
    "too_harsh": "Your brew tastes harsh, which often comes from over-extraction "
                 "or water that is too hot, pulling out astringent compounds.",
    "astringent": "Your brew has an astringent, drying mouthfeel. This can come from "
                  "both over- and under-extraction, often related to grind consistency "
                  "and water temperature.",
}

# --- Explanation templates keyed by (param, flag) ---
# Each template describes WHY the parameter change helps for the given issue.
EXPLANATION_TEMPLATES: dict[str, dict[str, str]] = {
    "grind_setting": {
        "too_sour": (
            "Too sour typically means under-extraction. A finer grind "
            "increases the surface area of the coffee particles, allowing "
            "more flavor compounds to dissolve into the water."
        ),
        "too_bitter": (
            "Too bitter typically means over-extraction. A coarser grind "
            "reduces the surface area, slowing extraction and preventing "
            "harsh compounds from dissolving."
        ),
        "too_weak": (
            "A weak brew can benefit from a finer grind, which increases "
            "extraction and produces a more concentrated cup."
        ),
        "too_harsh": (
            "Harshness can come from over-extraction. A coarser grind "
            "slows extraction and reduces the harsh, astringent compounds."
        ),
        "astringent": (
            "Astringency often relates to grind consistency. Adjusting "
            "the grind setting can help achieve a more even extraction."
        ),
        "default": (
            "Adjusting the grind setting changes the extraction rate, "
            "which directly affects the balance of flavors in the cup."
        ),
    },
    "water_temp_c": {
        "too_sour": (
            "Higher water temperature increases extraction, pulling more "
            "of the sweet and complex flavor compounds that balance sourness."
        ),
        "too_bitter": (
            "Lower water temperature reduces extraction, preventing the "
            "harsh, bitter compounds from dissolving out of the coffee."
        ),
        "too_weak": (
            "Higher water temperature can increase extraction strength, "
            "producing a more full-bodied cup."
        ),
        "too_harsh": (
            "Harshness is often caused by water that is too hot. Lowering "
            "the temperature reduces the extraction of astringent compounds."
        ),
        "astringent": (
            "Astringency can be tamed by adjusting water temperature to "
            "find the right extraction balance."
        ),
        "default": (
            "Water temperature directly controls how quickly flavor "
            "compounds dissolve from the coffee grounds."
        ),
    },
    "dose_g": {
        "too_sour": (
            "Increasing the dose (more coffee) provides more material "
            "for extraction, which can help balance sourness."
        ),
        "too_bitter": (
            "If the dose is too high, it can contribute to over-extraction. "
            "A small reduction may help balance the brew."
        ),
        "too_weak": (
            "Increasing the dose gives you more coffee per unit of water, "
            "producing a stronger, more flavorful cup."
        ),
        "too_harsh": (
            "Adjusting the dose can help balance the ratio of coffee to "
            "water, reducing harshness from over-concentration."
        ),
        "astringent": (
            "Adjusting the dose can help balance overall extraction and "
            "reduce astringent mouthfeel."
        ),
        "default": (
            "The dose (amount of coffee) directly affects the strength "
            "and concentration of the brew."
        ),
    },
    "ratio": {
        "too_sour": (
            "A lower ratio (more coffee relative to water) increases "
            "extraction concentration, which can counteract sourness."
        ),
        "too_bitter": (
            "A higher ratio (more water relative to coffee) dilutes the "
            "brew slightly, which can reduce perceived bitterness."
        ),
        "too_weak": (
            "A lower ratio means more coffee per unit of water, producing "
            "a stronger, more concentrated cup."
        ),
        "too_harsh": (
            "Adjusting the ratio can help balance the overall extraction "
            "and reduce harshness in the cup."
        ),
        "astringent": (
            "The brew ratio affects overall extraction balance. Adjusting "
            "it can help reduce astringent dryness."
        ),
        "default": (
            "The brew ratio (water to coffee) is one of the most "
            "impactful parameters for overall extraction balance."
        ),
    },
}


@dataclass
class DiagnosisSuggestion:
    """A single actionable suggestion for improving a brew."""

    parameter: str           # e.g. "grind_setting"
    current_value: float     # Current value
    suggested_value: float   # Suggested value
    score_delta: float       # Predicted improvement
    confidence: float        # Confidence in this suggestion (0-1)
    reason: str              # Human-readable explanation


@dataclass
class DiagnosisResult:
    """Complete diagnosis result with ranked suggestions."""

    issue_flags: list[str]                         # Reported issues
    suggestions: list[DiagnosisSuggestion]          # Ranked suggestions (best first)
    overall_assessment: str                         # Summary of what's wrong
    predicted_improvement: float                    # Sum of score deltas from top suggestions
    base_score: float                              # Current predicted score
    best_case_score: float                         # Predicted score if all suggestions applied


class DiagnosisEngine:
    """Diagnoses brew issues via perturb-and-score analysis.

    For each reported directional flag, perturbs recipe parameters one
    at a time and scores each perturbation with the taste predictor.
    Returns ranked suggestions showing which parameter changes produce
    the largest improvement.
    """

    def __init__(self, predictor: TastePredictor):
        if predictor is None:
            raise ValueError(
                "DiagnosisEngine requires a TastePredictor instance, got None"
            )
        self._predictor = predictor

    def diagnose(
        self,
        bean_profile: BeanProfile,
        recipe: Recipe,
        flags: list[str],
        user_id: str | None = None,
    ) -> DiagnosisResult:
        """Diagnose brew issues and suggest parameter changes.

        Args:
            bean_profile: The bean used in the brew.
            recipe: The recipe used for the brew.
            flags: List of directional flags (e.g. ["too_sour", "too_weak"]).
            user_id: Optional user ID for personalization bias.

        Returns:
            DiagnosisResult with ranked suggestions and assessment.
        """
        # Validate flags
        validated_flags = self._validate_flags(flags)
        logger.info("diagnosis.start flags=%s n_flags=%d", flags, len(flags))

        # Get the base score for the current recipe
        base_prediction = self._predictor.predict(bean_profile, recipe, user_id=user_id)
        base_score = base_prediction.predicted_rating

        if not validated_flags:
            return DiagnosisResult(
                issue_flags=[],
                suggestions=[],
                overall_assessment="No issues reported. Your brew parameters look good.",
                predicted_improvement=0.0,
                base_score=base_score,
                best_case_score=base_score,
            )

        # Find the best perturbation for each parameter
        suggestions: list[DiagnosisSuggestion] = []
        for param_name in PERTURBATION_CONFIG:
            best_value, best_score = self._find_best_perturbation(
                bean_profile, recipe, param_name, user_id
            )
            score_delta = best_score - base_score

            # Compute confidence based on normalized score delta
            # Larger improvement = higher confidence
            confidence = self._compute_confidence(score_delta)

            reason = self._generate_explanation(
                param_name,
                self._get_current_value(recipe, param_name),
                best_value,
                validated_flags,
            )

            suggestions.append(DiagnosisSuggestion(
                parameter=param_name,
                current_value=self._get_current_value(recipe, param_name),
                suggested_value=best_value,
                score_delta=round(score_delta, 3),
                confidence=round(confidence, 3),
                reason=reason,
            ))

        # Rank by score_delta descending (largest improvement first)
        suggestions.sort(key=lambda s: s.score_delta, reverse=True)

        # Compute aggregate metrics from positive-delta suggestions
        positive_deltas = [s.score_delta for s in suggestions if s.score_delta > 0]
        predicted_improvement = round(float(sum(positive_deltas)), 3)

        overall_assessment = self._generate_assessment(validated_flags)

        logger.info(
            "diagnosis.complete n_suggestions=%d predicted_improvement=%.3f base_score=%.1f",
            len(suggestions), predicted_improvement, base_score,
        )

        return DiagnosisResult(
            issue_flags=validated_flags,
            suggestions=suggestions,
            overall_assessment=overall_assessment,
            predicted_improvement=predicted_improvement,
            base_score=base_score,
            best_case_score=round(base_score + predicted_improvement, 3),
        )

    def _perturb_parameter(
        self,
        bean_profile: BeanProfile,
        recipe: Recipe,
        param_name: str,
        value: float,
        user_id: str | None,
    ) -> float:
        """Score a perturbed recipe. Returns predicted rating."""
        perturbed_recipe = self._apply_perturbation(recipe, param_name, value)
        result = self._predictor.predict(bean_profile, perturbed_recipe, user_id=user_id)
        return result.predicted_rating

    def _generate_explanation(
        self,
        param_name: str,
        current: float,
        suggested: float,
        flags: list[str],
    ) -> str:
        """Generate human-readable explanation for a suggestion."""
        delta = suggested - current
        is_neutral = abs(delta) < 1e-6

        # If the model suggests no change, use a neutral message
        if is_neutral:
            return "The current setting looks reasonable for this parameter."

        # Check if the model's direction matches coffee-science expectations
        direction_mismatch = False
        for flag in flags:
            expected = _EXPECTED_DIRECTION.get((param_name, flag))
            if expected is None:
                continue
            actual = "increase" if delta > 0 else "decrease"
            if actual != expected:
                direction_mismatch = True
                break

        # When direction contradicts coffee science, use a model-based explanation
        if direction_mismatch:
            param_display = param_name.replace("_", " ")
            direction_word = "increasing" if delta > 0 else "decreasing"
            return (
                f"Based on your bean profile and brewing history, {direction_word} "
                f"the {param_display} is predicted to improve your next cup. "
                f"The model found this adjustment works better than the typical "
                f"recommendation for this issue."
            )

        # Direction matches — use the coffee-science explanation template
        templates = EXPLANATION_TEMPLATES.get(param_name, {})
        template = None
        for flag in flags:
            if flag in templates:
                template = templates[flag]
                break

        if template is None:
            template = templates.get("default", "Adjusting this parameter may improve your brew.")

        # Append magnitude note
        step = PERTURBATION_CONFIG.get(param_name, (1.0, 1.0))[1]
        if abs(delta) > 2 * step:
            template += " Consider making this change gradually over multiple brews."
        else:
            template += " This is a small adjustment that should be safe to try."

        return template

    def _validate_flags(self, flags: list[str]) -> list[str]:
        """Validate directional flags, collecting all unknowns before raising."""
        if not flags:
            return []
        valid = []
        unknown = []
        for flag in flags:
            if flag in DIRECTIONAL_FLAGS:
                valid.append(flag)
            else:
                unknown.append(flag)
        if unknown:
            raise ValueError(
                f"Unknown directional flag(s): {', '.join(repr(f) for f in unknown)}. "
                f"Must be one of {DIRECTIONAL_FLAGS}"
            )
        return valid

    def _get_current_value(self, recipe: Recipe, param_name: str) -> float:
        """Get the current value of a parameter from a recipe."""
        return float(getattr(recipe, param_name))

    def _find_best_perturbation(
        self,
        bean_profile: BeanProfile,
        recipe: Recipe,
        param_name: str,
        user_id: str | None,
    ) -> tuple[float, float]:
        """Find the perturbation value that maximizes the predicted score.

        Returns (best_value, best_score).
        """
        current = self._get_current_value(recipe, param_name)
        max_offset, step = PERTURBATION_CONFIG[param_name]
        lo, hi = PARAM_RANGES[param_name]

        # Generate all candidate values within range
        candidates: list[float] = []
        offset = -max_offset
        while offset <= max_offset + 1e-9:
            val = current + offset
            clamped = max(lo, min(hi, val))
            if clamped not in candidates:
                candidates.append(clamped)
            offset += step

        # Always include the current value to ensure we don't suggest
        # a change that is worse
        if current not in candidates:
            candidates.append(current)

        # Score each candidate and track the best
        best_value = current
        best_score = self._perturb_parameter(bean_profile, recipe, param_name, current, user_id)

        for candidate in candidates:
            if abs(candidate - current) < 1e-9:
                continue  # Already scored current
            score = self._perturb_parameter(bean_profile, recipe, param_name, candidate, user_id)
            if score > best_score:
                best_score = score
                best_value = candidate

        return best_value, best_score

    def _apply_perturbation(
        self, recipe: Recipe, param_name: str, value: float
    ) -> Recipe:
        """Create a new recipe with one parameter changed.

        Keeps pour schedule timing fixed. Only changes the specified tunable
        parameter. When dose_g or ratio changes, adjusts water_total_g and
        pour volumes proportionally so the recipe passes validation.
        """
        updates: dict[str, object] = {}

        if param_name == "dose_g":
            # Keep water_total_g fixed, adjust ratio to match
            new_dose = value
            new_ratio = round(recipe.water_total_g / new_dose, 2)
            # Clamp ratio to valid range; if it falls outside, adjust
            # water_total_g to keep ratio in range
            new_ratio = max(14.0, min(18.0, new_ratio))
            new_water = round(new_dose * new_ratio, 1)
            # Clamp water_total_g to valid range
            new_water = max(180.0, min(600.0, new_water))
            # Recompute ratio from clamped water
            new_ratio = round(new_water / new_dose, 2)
            updates["dose_g"] = new_dose
            updates["ratio"] = new_ratio
            updates["water_total_g"] = new_water
            # Scale pours proportionally
            if recipe.water_total_g > 0:
                scale = new_water / recipe.water_total_g
                updates["pours"] = [
                    replace(p, water_g=max(10.0, min(200.0, round(p.water_g * scale, 1))))
                    for p in recipe.pours
                ]

        elif param_name == "ratio":
            new_ratio = value
            new_water = round(recipe.dose_g * new_ratio, 1)
            new_water = max(180.0, min(600.0, new_water))
            # Recompute ratio from clamped water
            new_ratio = round(new_water / recipe.dose_g, 2)
            updates["ratio"] = new_ratio
            updates["water_total_g"] = new_water
            # Scale pours proportionally
            if recipe.water_total_g > 0:
                scale = new_water / recipe.water_total_g
                updates["pours"] = [
                    replace(p, water_g=max(10.0, min(200.0, round(p.water_g * scale, 1))))
                    for p in recipe.pours
                ]

        else:
            # grind_setting, water_temp_c: simple scalar change
            updates[param_name] = type(getattr(recipe, param_name))(value)

        return replace(recipe, **updates)

    def _compute_confidence(self, score_delta: float) -> float:
        """Compute confidence in a suggestion based on score delta.

        Larger deltas produce higher confidence. The scale is normalized
        so that a delta of 1.0 (one full rating point improvement) gives
        confidence of ~0.8, and deltas below 0.1 give low confidence.
        """
        if score_delta <= 0:
            return 0.0
        # Sigmoid-like normalization: confidence grows with delta
        # but saturates near 1.0
        # At delta=0.5 -> ~0.62, delta=1.0 -> ~0.80, delta=2.0 -> ~0.93
        confidence = score_delta / (score_delta + 0.25)
        return min(1.0, confidence)

    def _generate_assessment(self, flags: list[str]) -> str:
        """Generate overall assessment text from the reported flags."""
        if not flags:
            return "No issues reported. Your brew parameters look good."

        parts: list[str] = []
        for flag in flags:
            assessment = FLAG_ASSESSMENT.get(flag, "")
            if assessment:
                parts.append(assessment)

        if len(parts) == 0:
            return "Issues reported with your brew. See suggestions below for improvements."
        if len(parts) == 1:
            return parts[0]
        # Multiple flags: join with context
        return " ".join(parts)

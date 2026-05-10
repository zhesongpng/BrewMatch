"""Personalization engine for BrewMatch.

Tracks user brewing history, extracts learned preferences from directional
flags and ratings, and computes user features for the taste predictor model.

Phase model (per taste-prediction.md Section 4.2):
  - bean_aware  (0 brews):   global model only, no user features
  - directional (1-4 brews): global model + linear bias from directional flags
  - content_based (5-9):     model with full user features populated
  - full_hybrid (10+):       full model + collaborative filtering signals
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Optional

from src.data_models import (
    BeanProfile,
    BrewRecord,
    LearnedPreferences,
    Onboarding,
    Recipe,
    RoastLevel,
    UserStats,
    UserTasteProfile,
)
from src.taste_predictor.encoder import ROAST_ORDINAL

logger = logging.getLogger(__name__)

# Per-flag bias step size (applied once per occurrence).
_FLAG_BIAS_STEP = 0.1

# Mapping of directional flags to bias deltas.
_DIRECTIONAL_FLAG_EFFECTS: dict[str, dict[str, float]] = {
    "too_sour":   {"acidity_bias": -_FLAG_BIAS_STEP},
    "too_bitter": {"body_bias":    -_FLAG_BIAS_STEP},
    "too_weak":   {"body_bias":    +_FLAG_BIAS_STEP},
    "too_harsh":  {"acidity_bias": -_FLAG_BIAS_STEP,
                   "body_bias":    -_FLAG_BIAS_STEP},
    "astringent": {"sweetness_bias": -_FLAG_BIAS_STEP},
}

# Phase descriptions for get_phase_info.
_PHASE_DESCRIPTIONS: dict[str, str] = {
    "bean_aware": "Global model only; no personalisation data yet.",
    "directional": "Early personalisation using directional flags from your feedback.",
    "content_based": "Personalised predictions using your brewing history.",
    "full_hybrid": "Full personalisation with collaborative filtering signals.",
}


class PersonalizationEngine:
    """Tracks brewing history and computes per-user features and preferences.

    Parameters
    ----------
    predictor : TastePredictor
        The trained taste prediction model (used for bias updates).
    user_id : str
        Unique identifier for the user (must be non-empty).
    onboarding : Onboarding
        The user's onboarding preferences (clusters, roast, experience).
    """

    def __init__(
        self,
        predictor,
        user_id: str,
        onboarding: Onboarding,
    ) -> None:
        if not user_id:
            raise ValueError("user_id is required and must be non-empty")
        self._predictor = predictor
        self._user_id = user_id
        self._onboarding = onboarding
        self._brew_history: list[BrewRecord] = []

        # Accumulated directional-flag biases (clamped to [-1, 1]).
        self._acidity_bias: float = 0.0
        self._body_bias: float = 0.0
        self._sweetness_bias: float = 0.0

    @property
    def predictor(self):
        """The underlying TastePredictor (read-only access for testing)."""
        return self._predictor

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def phase(self) -> str:
        """Return the current personalisation phase name."""
        n = len(self._brew_history)
        if n == 0:
            return "bean_aware"
        if n <= 4:
            return "directional"
        if n <= 9:
            return "content_based"
        return "full_hybrid"

    @staticmethod
    def get_phase_for_count(brew_count: int) -> str:
        """Return the personalisation phase name for a given brew count.

        Validates the input: negative counts are clamped to 0 with a
        warning, since negative brew counts are nonsensical and typically
        indicate a caller bug.

        Parameters
        ----------
        brew_count : int
            Number of brews the user has recorded.

        Returns
        -------
        str
            Phase name: ``bean_aware``, ``directional``, ``content_based``,
            or ``full_hybrid``.
        """
        if brew_count < 0:
            logger.warning(
                "get_phase_for_count received negative brew_count=%d; "
                "clamping to 0. Caller should investigate.",
                brew_count,
            )
            brew_count = 0
        if brew_count == 0:
            return "bean_aware"
        if brew_count <= 4:
            return "directional"
        if brew_count <= 9:
            return "content_based"
        return "full_hybrid"

    def record_brew(self, brew: BrewRecord) -> None:
        """Record a brew event and update internal preferences.

        Appends the brew to history, processes directional flags to update
        bias values, and (when a numeric score exists) calls the predictor
        to update the per-user bias layer.
        """
        old_phase = self.phase
        self._brew_history.append(brew)
        self._process_directional_flags(brew)

        if brew.feedback.score is not None:
            self._update_predictor_bias(brew)

        new_phase = self.phase
        if new_phase != old_phase:
            logger.info(
                "personalization.phase_transition user_id=%s old_phase=%s new_phase=%s total_brews=%d",
                self._user_id, old_phase, new_phase, len(self._brew_history),
            )

    def get_user_features(self) -> dict[str, float]:
        """Return the 9 user features as a dict for the feature encoder.

        All values are 0.0 for cold-start users (no brews).
        """
        n = len(self._brew_history)
        if n == 0:
            return self._empty_user_features()

        ratings = [
            b.feedback.score
            for b in self._brew_history
            if b.feedback.score is not None
        ]
        avg_rating = _safe_mean(ratings)
        highly_rated = [
            b for b in self._brew_history
            if b.feedback.score is not None and b.feedback.score >= avg_rating
        ]

        return {
            "user_avg_rating": avg_rating,
            "user_rating_count": float(n),
            "user_roast_pref": self._roast_preference(highly_rated),
            "user_temp_pref": _mean_recipe_field(highly_rated, "water_temp_c"),
            "user_grind_pref": _mean_recipe_field(highly_rated, "grind_setting"),
            "user_ratio_pref": _mean_recipe_field(highly_rated, "ratio"),
            "user_acidity_bias": self._acidity_bias,
            "user_body_bias": self._body_bias,
            "user_sweetness_bias": self._sweetness_bias,
        }

    def get_profile(self) -> UserTasteProfile:
        """Return the current user taste profile."""
        ratings = [
            b.feedback.score
            for b in self._brew_history
            if b.feedback.score is not None
        ]

        learned = (
            self.compute_learned_preferences()
            if self._brew_history
            else None
        )

        return UserTasteProfile(
            user_id=self._user_id,
            onboarding=self._onboarding,
            brew_history=list(self._brew_history),
            learned_preferences=learned,
            stats=UserStats(
                total_brews=len(self._brew_history),
                avg_score=_safe_mean(ratings) if ratings else 0.0,
            ),
        )

    def get_phase_info(self) -> dict:
        """Return phase name, brew count, and human-readable description."""
        return {
            "phase": self.phase,
            "brew_count": len(self._brew_history),
            "description": _PHASE_DESCRIPTIONS[self.phase],
        }

    def compute_learned_preferences(self) -> LearnedPreferences:
        """Compute learned preferences from brew history.

        Returns default LearnedPreferences when there is no history.
        Otherwise derives preferred temp/ratio ranges from highly-rated
        brews and incorporates accumulated directional-flag biases.
        """
        if not self._brew_history:
            return LearnedPreferences()

        ratings = [
            b.feedback.score
            for b in self._brew_history
            if b.feedback.score is not None
        ]
        avg_rating = _safe_mean(ratings)
        highly_rated = [
            b for b in self._brew_history
            if b.feedback.score is not None and b.feedback.score >= avg_rating
        ]

        if highly_rated:
            temps = [b.recipe_used.water_temp_c for b in highly_rated]
            ratios = [b.recipe_used.ratio for b in highly_rated]
            temp_range = (min(temps), max(temps))
            ratio_range = (min(ratios), max(ratios))
        else:
            temp_range = (90.0, 96.0)
            ratio_range = (15.0, 17.0)

        prefs = LearnedPreferences(
            acidity_bias=_clamp(self._acidity_bias, -1.0, 1.0),
            body_bias=_clamp(self._body_bias, -1.0, 1.0),
            sweetness_bias=_clamp(self._sweetness_bias, -1.0, 1.0),
            preferred_temp_range=temp_range,
            preferred_ratio_range=ratio_range,
        )

        logger.info(
            "personalization.compute_preferences user_id=%s temp_range=%s ratio_range=%s total_brews=%d",
            self._user_id, temp_range, ratio_range, len(self._brew_history),
        )

        return prefs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_user_features() -> dict[str, float]:
        return {
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

    def _process_directional_flags(self, brew: BrewRecord) -> None:
        flags = brew.feedback.directional_flags or []
        for flag in flags:
            effects = _DIRECTIONAL_FLAG_EFFECTS.get(flag)
            if effects is None:
                continue
            if "acidity_bias" in effects:
                self._acidity_bias = max(-1.0, min(1.0, self._acidity_bias + effects["acidity_bias"]))
            if "body_bias" in effects:
                self._body_bias = max(-1.0, min(1.0, self._body_bias + effects["body_bias"]))
            if "sweetness_bias" in effects:
                self._sweetness_bias = max(-1.0, min(1.0, self._sweetness_bias + effects["sweetness_bias"]))

    def _update_predictor_bias(self, brew: BrewRecord) -> None:
        """Call predictor.update_user_bias with the current prior count."""
        if not self._predictor.is_trained:
            return

        features = self._predictor.encode_features(
            brew.bean_profile, brew.recipe_used
        )
        # n_prior_ratings is the count *before* this brew (already appended).
        n_prior = len(self._brew_history) - 1
        self._predictor.update_user_bias(
            self._user_id, features, float(brew.feedback.score), n_prior
        )

    def _roast_preference(self, highly_rated: list[BrewRecord]) -> float:
        """Most common roast level ordinal among highly-rated brews."""
        if not highly_rated:
            return 0.0
        roast_counts: Counter[RoastLevel] = Counter()
        for b in highly_rated:
            roast_counts[b.bean_profile.roast_level] += 1
        most_common = roast_counts.most_common(1)[0][0]
        return ROAST_ORDINAL.get(most_common, 3.0)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _safe_mean(values: list[int | float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _mean_recipe_field(brews: list[BrewRecord], field: str) -> float:
    if not brews:
        return 0.0
    total = sum(getattr(b.recipe_used, field) for b in brews)
    return total / len(brews)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))

"""Feature encoder for BrewMatch taste prediction model.

Produces a 45-element numpy float array from a BeanProfile, Recipe, and
optional user preference features. Column ordering is fixed to match
training data expectations.
"""

from __future__ import annotations

import numpy as np

from src.data_models import (
    FLAVOR_CLUSTERS,
    BeanProfile,
    Process,
    Recipe,
    RoastLevel,
)

# --- Constants ---

# Top 20 origin countries mapped to integers 1-20; everything else maps to 0.
ORIGIN_MAP: dict[str, int] = {
    "Ethiopia": 1,
    "Colombia": 2,
    "Brazil": 3,
    "Kenya": 4,
    "Guatemala": 5,
    "Costa Rica": 6,
    "Honduras": 7,
    "Panama": 8,
    "Nicaragua": 9,
    "El Salvador": 10,
    "Peru": 11,
    "Bolivia": 12,
    "Ecuador": 13,
    "Rwanda": 14,
    "Burundi": 15,
    "Tanzania": 16,
    "Uganda": 17,
    "Indonesia": 18,
    "India": 19,
    "Vietnam": 20,
}

# Roast level ordinal mapping: light=1 through dark=5, unknown=3 (midpoint).
ROAST_ORDINAL: dict[RoastLevel, float] = {
    RoastLevel.LIGHT: 1.0,
    RoastLevel.MEDIUM_LIGHT: 2.0,
    RoastLevel.MEDIUM: 3.0,
    RoastLevel.MEDIUM_DARK: 4.0,
    RoastLevel.DARK: 5.0,
    RoastLevel.UNKNOWN: 3.0,
}

# Process enum to one-hot column index.
# Indices: washed=1, natural=2, honey=3, anaerobic=4, other=5
_PROCESS_ONEHOT: dict[Process, int] = {
    Process.WASHED: 1,
    Process.NATURAL: 2,
    Process.HONEY: 3,
    Process.ANAEROBIC: 4,
    # WET_HULLED and UNKNOWN both map to "other" (index 5)
    Process.WET_HULLED: 5,
    Process.UNKNOWN: 5,
}

# Flavor cluster name to column offset (0-indexed from cluster start at idx 7).
_CLUSTER_OFFSET: dict[str, int] = {
    name: i for i, name in enumerate(FLAVOR_CLUSTERS)
}


def _encode_origin(country: str) -> float:
    """Label-encode origin country. Top 20 map to 1-20; others map to 0."""
    return float(ORIGIN_MAP.get(country, 0))


def _encode_process(process: Process) -> list[float]:
    """One-hot encode process into 5 columns [washed, natural, honey, anaerobic, other]."""
    result = [0.0, 0.0, 0.0, 0.0, 0.0]
    idx = _PROCESS_ONEHOT.get(process)
    if idx is not None:
        result[idx - 1] = 1.0
    return result


def _encode_roast(roast_level: RoastLevel) -> float:
    """Ordinal encode roast level."""
    return ROAST_ORDINAL.get(roast_level, 3.0)


def _encode_clusters(flavor_clusters: list[str]) -> list[float]:
    """Multi-hot encode flavor clusters into 15 binary columns.

    Returns Balanced=1 only when the input list is empty (cold-start default).
    """
    result = [0.0] * len(FLAVOR_CLUSTERS)
    if not flavor_clusters:
        # Default: Balanced
        result[_CLUSTER_OFFSET["Balanced"]] = 1.0
        return result
    for cluster in flavor_clusters:
        offset = _CLUSTER_OFFSET.get(cluster)
        if offset is not None:
            result[offset] = 1.0
    return result


def _encode_altitude(bean: BeanProfile) -> float:
    """Return altitude_min_m, or 0.0 if missing."""
    if bean.altitude_min_m is not None:
        return float(bean.altitude_min_m)
    return 0.0


def encode_features(
    bean_profile: BeanProfile,
    recipe: Recipe,
    user_avg_rating: float = 0.0,
    user_rating_count: int = 0,
    user_roast_pref: float = 3.0,
    user_temp_pref: float = 0.0,
    user_grind_pref: float = 0.0,
    user_ratio_pref: float = 0.0,
    user_acidity_bias: float = 0.0,
    user_body_bias: float = 0.0,
    user_sweetness_bias: float = 0.0,
) -> np.ndarray:
    """Encode bean, recipe, and user features into a 45-element float array.

    Column ordering (0-indexed):
      Bean features (0-22):
        [0]  origin_encoded       label encoding (top 20 = 1-20, other = 0)
        [1]  process_washed       one-hot
        [2]  process_natural      one-hot
        [3]  process_honey        one-hot
        [4]  process_anaerobic    one-hot
        [5]  process_other        one-hot (wet-hulled + unknown)
        [6]  roast_ordinal        ordinal 1-5, unknown=3
        [7-21]  15 flavor cluster binaries
        [22] altitude_mean        (min+max)/2 or 0.0

      Recipe features (23-29):
        [23] dose_g
        [24] ratio
        [25] grind_setting
        [26] water_temp_c
        [27] bloom_time_s
        [28] total_time_s
        [29] pour_count

      User features (30-38):
        [30] user_avg_rating
        [31] user_rating_count
        [32] user_roast_pref
        [33] user_temp_pref
        [34] user_grind_pref
        [35] user_ratio_pref
        [36] user_acidity_bias
        [37] user_body_bias
        [38] user_sweetness_bias

      Interaction features (39-44):
        [39] roast_x_temp       roast_ordinal * water_temp_c
        [40] grind_x_time       grind_setting * total_time_s
        [41] grind_x_temp       grind_setting * water_temp_c
        [42] ratio_x_dose       ratio * dose_g
        [43] roast_x_grind      roast_ordinal * grind_setting
        [44] cluster_count      sum of 15 cluster binaries
    """
    features: list[float] = []

    # --- Bean features (indices 0-22) ---
    features.append(_encode_origin(bean_profile.origin_country))          # [0]
    features.extend(_encode_process(bean_profile.process))                # [1-5]
    roast_ordinal = _encode_roast(bean_profile.roast_level)
    features.append(roast_ordinal)                                        # [6]
    cluster_bins = _encode_clusters(bean_profile.flavor_clusters)
    features.extend(cluster_bins)                                         # [7-21]
    features.append(_encode_altitude(bean_profile))                       # [22]

    # --- Recipe features (indices 23-29) ---
    features.append(float(recipe.dose_g))                                 # [23]
    features.append(float(recipe.ratio))                                  # [24]
    features.append(float(recipe.grind_setting))                          # [25]
    features.append(float(recipe.water_temp_c))                           # [26]
    features.append(float(recipe.bloom_time_s))                           # [27]
    features.append(float(recipe.total_time_s))                           # [28]
    features.append(float(len(recipe.pours)))                             # [29]

    # --- User features (indices 30-38) ---
    features.append(float(user_avg_rating))                               # [30]
    features.append(float(user_rating_count))                             # [31]
    features.append(float(user_roast_pref))                               # [32]
    features.append(float(user_temp_pref))                                # [33]
    features.append(float(user_grind_pref))                               # [34]
    features.append(float(user_ratio_pref))                               # [35]
    features.append(float(user_acidity_bias))                             # [36]
    features.append(float(user_body_bias))                                # [37]
    features.append(float(user_sweetness_bias))                           # [38]

    # --- Interaction features (indices 39-44) ---
    features.append(roast_ordinal * float(recipe.water_temp_c))           # [39]
    features.append(float(recipe.grind_setting) * float(recipe.total_time_s))  # [40]
    features.append(float(recipe.grind_setting) * float(recipe.water_temp_c))  # [41]
    features.append(float(recipe.ratio) * float(recipe.dose_g))          # [42]
    features.append(roast_ordinal * float(recipe.grind_setting))          # [43]
    features.append(float(sum(cluster_bins)))                             # [44]

    return np.array(features, dtype=np.float64)


class FeatureEncoder:
    """Stateless feature encoder wrapping origin label mapping.

    Can be serialized (the mapping is a class constant). Delegates to
    the module-level ``encode_features`` function.
    """

    ORIGIN_MAP: dict[str, int] = ORIGIN_MAP.copy()
    ROAST_ORDINAL: dict[RoastLevel, float] = ROAST_ORDINAL.copy()

    def encode(
        self,
        bean_profile: BeanProfile,
        recipe: Recipe,
        **user_kwargs: float,
    ) -> np.ndarray:
        """Encode features with optional user preference overrides.

        Accepts the same keyword arguments as ``encode_features``:
        user_avg_rating, user_rating_count, user_roast_pref,
        user_temp_pref, user_grind_pref, user_ratio_pref,
        user_acidity_bias, user_body_bias, user_sweetness_bias.
        """
        return encode_features(bean_profile, recipe, **user_kwargs)

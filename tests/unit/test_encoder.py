"""Unit tests for the feature encoder.

Covers: output shape, column ordering, origin encoding, process one-hot,
roast ordinal, flavor cluster multi-hot, cold-start user defaults,
interaction features, altitude mean, default cluster fallback,
single-pour edge case, FeatureEncoder class wrapper.
"""

import numpy as np
import pytest

from src.data_models import (
    FLAVOR_CLUSTERS,
    BeanProfile,
    BrewMethod,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)
from src.taste_predictor.encoder import (
    ORIGIN_MAP,
    ROAST_ORDINAL,
    FeatureEncoder,
    _encode_clusters,
    encode_features,
)


# --- Helpers ---


def _make_recipe(**overrides) -> Recipe:
    """Create a valid Recipe with sensible defaults for testing.

    When callers override dose, ratio, or water_total_g, they must keep the
    constraint ratio == water_total_g / dose_g (within 0.1) and pours sum
    within 5% of water_total_g.
    """
    defaults = dict(
        recipe_id="test-recipe",
        source="Test Source",
        method=BrewMethod.V60,
        dose_g=15.0,
        water_total_g=250.0,
        ratio=16.67,
        grind_setting=5,
        water_temp_c=93.0,
        bloom_time_s=45,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=50.0),
            PourStep(step=2, time_offset_s=45, water_g=100.0),
            PourStep(step=3, time_offset_s=90, water_g=100.0),
        ],
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Test instructions",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def _make_bean(**overrides) -> BeanProfile:
    """Create a valid BeanProfile with sensible defaults for testing."""
    defaults = dict(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Test bean source text",
    )
    defaults.update(overrides)
    return BeanProfile(**defaults)


# --- Test: Output shape ---


class TestOutputShape:
    """Encoder always produces a (45,) float64 array."""

    def test_default_produces_45_elements(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe())
        assert vec.shape == (45,)

    def test_with_user_features_produces_45_elements(self, make_bean, make_recipe):
        vec = encode_features(
            make_bean(),
            make_recipe(),
            user_avg_rating=7.5,
            user_rating_count=12,
            user_roast_pref=2.0,
        )
        assert vec.shape == (45,)

    def test_cold_start_user_produces_45_elements(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe())
        assert vec.shape == (45,)

    def test_output_dtype_is_float64(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe())
        assert vec.dtype == np.float64


# --- Test: Column ordering ---


class TestColumnOrdering:
    """Verify specific column indices match the spec."""

    def test_origin_at_index_0(self, make_recipe):
        bean = _make_bean(origin_country="Colombia")
        vec = encode_features(bean, make_recipe())
        # Colombia maps to 2
        assert vec[0] == 2.0

    def test_process_onehot_at_indices_1_through_5(self, make_recipe):
        bean = _make_bean(process=Process.NATURAL)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 0.0  # washed
        assert vec[2] == 1.0  # natural
        assert vec[3] == 0.0  # honey
        assert vec[4] == 0.0  # anaerobic
        assert vec[5] == 0.0  # other

    def test_roast_ordinal_at_index_6(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.MEDIUM_DARK)
        vec = encode_features(bean, make_recipe())
        assert vec[6] == 4.0

    def test_clusters_at_indices_7_through_21(self, make_recipe):
        # Use a bean with exactly "Berry" cluster
        bean = _make_bean(flavor_clusters=["Berry"])
        vec = encode_features(bean, make_recipe())
        # Berry is the 2nd cluster (index 1 within the cluster block)
        assert vec[7] == 0.0   # Floral
        assert vec[8] == 1.0   # Berry
        assert vec[9] == 0.0   # Citrus

    def test_altitude_min_m_at_index_22(self, make_recipe):
        bean = _make_bean(altitude_min_m=1500, altitude_max_m=1900)
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 1500.0

    def test_dose_at_index_23(self, make_bean):
        # Recipe validates ratio == water_total_g / dose_g within 0.1,
        # and pours sum within 5% of water_total_g. Override consistently.
        recipe = _make_recipe(
            dose_g=18.0,
            water_total_g=300.0,
            ratio=16.67,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=60.0),
                PourStep(step=2, time_offset_s=45, water_g=120.0),
                PourStep(step=3, time_offset_s=90, water_g=120.0),
            ],
        )
        vec = encode_features(make_bean(), recipe)
        assert vec[23] == 18.0

    def test_ratio_at_index_24(self, make_bean):
        recipe = _make_recipe()
        vec = encode_features(make_bean(), recipe)
        assert vec[24] == pytest.approx(16.67)

    def test_grind_at_index_25(self, make_bean):
        recipe = _make_recipe(grind_setting=7)
        vec = encode_features(make_bean(), recipe)
        assert vec[25] == 7.0

    def test_water_temp_at_index_26(self, make_bean):
        recipe = _make_recipe(water_temp_c=96.0)
        vec = encode_features(make_bean(), recipe)
        assert vec[26] == 96.0

    def test_bloom_time_at_index_27(self, make_bean):
        recipe = _make_recipe(bloom_time_s=30)
        vec = encode_features(make_bean(), recipe)
        assert vec[27] == 30.0

    def test_total_time_at_index_28(self, make_bean):
        recipe = _make_recipe(total_time_s=240)
        vec = encode_features(make_bean(), recipe)
        assert vec[28] == 240.0

    def test_pour_count_at_index_29(self, make_bean):
        recipe = _make_recipe()
        vec = encode_features(make_bean(), recipe)
        assert vec[29] == 3.0  # 3 pours in default recipe

    def test_user_avg_rating_at_index_30(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_avg_rating=6.5)
        assert vec[30] == 6.5

    def test_user_rating_count_at_index_31(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_rating_count=42)
        assert vec[31] == 42.0

    def test_user_roast_pref_at_index_32(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_roast_pref=4.0)
        assert vec[32] == 4.0

    def test_user_temp_pref_at_index_33(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_temp_pref=92.0)
        assert vec[33] == 92.0

    def test_user_grind_pref_at_index_34(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_grind_pref=6.0)
        assert vec[34] == 6.0

    def test_user_ratio_pref_at_index_35(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_ratio_pref=15.5)
        assert vec[35] == 15.5

    def test_user_acidity_bias_at_index_36(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_acidity_bias=0.7)
        assert vec[36] == pytest.approx(0.7)

    def test_user_body_bias_at_index_37(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_body_bias=-0.4)
        assert vec[37] == pytest.approx(-0.4)

    def test_user_sweetness_bias_at_index_38(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe(), user_sweetness_bias=0.2)
        assert vec[38] == pytest.approx(0.2)

    def test_roast_x_temp_at_index_39(self, make_bean, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.DARK)
        recipe = make_recipe(water_temp_c=90.0)
        vec = encode_features(bean, recipe)
        np.testing.assert_array_almost_equal(
            np.array([vec[39]]), np.array([5.0 * 90.0])
        )

    def test_grind_x_time_at_index_40(self, make_bean, make_recipe):
        recipe = make_recipe(grind_setting=4, total_time_s=200)
        vec = encode_features(make_bean(), recipe)
        np.testing.assert_array_almost_equal(
            np.array([vec[40]]), np.array([4.0 * 200.0])
        )

    def test_grind_x_temp_at_index_41(self, make_bean, make_recipe):
        recipe = make_recipe(grind_setting=6, water_temp_c=95.0)
        vec = encode_features(make_bean(), recipe)
        np.testing.assert_array_almost_equal(
            np.array([vec[41]]), np.array([6.0 * 95.0])
        )

    def test_ratio_x_dose_at_index_42(self, make_bean):
        # Keep ratio, dose, water_total_g consistent for Recipe validation.
        recipe = _make_recipe(
            dose_g=16.0,
            water_total_g=256.0,
            ratio=16.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=51.0),
                PourStep(step=2, time_offset_s=45, water_g=102.0),
                PourStep(step=3, time_offset_s=90, water_g=103.0),
            ],
        )
        vec = encode_features(make_bean(), recipe)
        np.testing.assert_array_almost_equal(
            np.array([vec[42]]), np.array([16.0 * 16.0])
        )

    def test_roast_x_grind_at_index_43(self, make_bean, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.MEDIUM)  # ordinal=3
        recipe = make_recipe(grind_setting=7)
        vec = encode_features(bean, recipe)
        np.testing.assert_array_almost_equal(
            np.array([vec[43]]), np.array([3.0 * 7.0])
        )

    def test_cluster_count_at_index_44(self, make_bean, make_recipe):
        bean = _make_bean(flavor_clusters=["Floral", "Berry", "Chocolate"])
        vec = encode_features(bean, make_recipe())
        assert vec[44] == 3.0


# --- Test: Origin encoding ---


class TestOriginEncoding:
    """Label encoding for top-20 countries, others map to 0."""

    def test_ethiopia_maps_to_1(self, make_recipe):
        bean = _make_bean(origin_country="Ethiopia")
        assert encode_features(bean, make_recipe())[0] == 1.0

    def test_colombia_maps_to_2(self, make_recipe):
        bean = _make_bean(origin_country="Colombia")
        assert encode_features(bean, make_recipe())[0] == 2.0

    def test_brazil_maps_to_3(self, make_recipe):
        bean = _make_bean(origin_country="Brazil")
        assert encode_features(bean, make_recipe())[0] == 3.0

    def test_vietnam_maps_to_20(self, make_recipe):
        bean = _make_bean(origin_country="Vietnam")
        assert encode_features(bean, make_recipe())[0] == 20.0

    def test_unknown_country_maps_to_0(self, make_recipe):
        bean = _make_bean(origin_country="Antarctica")
        assert encode_features(bean, make_recipe())[0] == 0.0

    def test_all_top20_countries_mapped(self):
        """Verify all 20 countries in the spec have entries in ORIGIN_MAP."""
        expected_countries = [
            "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala",
            "Costa Rica", "Honduras", "Panama", "Nicaragua", "El Salvador",
            "Peru", "Bolivia", "Ecuador", "Rwanda", "Burundi",
            "Tanzania", "Uganda", "Indonesia", "India", "Vietnam",
        ]
        for country in expected_countries:
            assert country in ORIGIN_MAP, f"Missing country: {country}"

    def test_origin_map_values_1_through_20(self):
        """All ORIGIN_MAP values are 1-20."""
        values = set(ORIGIN_MAP.values())
        assert values == set(range(1, 21))


# --- Test: Process one-hot ---


class TestProcessOneHot:
    """Exactly one hot for known process, all zeros for unknown."""

    def test_washed(self, make_recipe):
        bean = _make_bean(process=Process.WASHED)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 1.0  # washed
        assert vec[2] == 0.0
        assert vec[3] == 0.0
        assert vec[4] == 0.0
        assert vec[5] == 0.0

    def test_natural(self, make_recipe):
        bean = _make_bean(process=Process.NATURAL)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 0.0
        assert vec[2] == 1.0  # natural
        assert vec[3] == 0.0
        assert vec[4] == 0.0
        assert vec[5] == 0.0

    def test_honey(self, make_recipe):
        bean = _make_bean(process=Process.HONEY)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 0.0
        assert vec[2] == 0.0
        assert vec[3] == 1.0  # honey
        assert vec[4] == 0.0
        assert vec[5] == 0.0

    def test_anaerobic(self, make_recipe):
        bean = _make_bean(process=Process.ANAEROBIC)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 0.0
        assert vec[2] == 0.0
        assert vec[3] == 0.0
        assert vec[4] == 1.0  # anaerobic
        assert vec[5] == 0.0

    def test_wet_hulled_maps_to_other(self, make_recipe):
        bean = _make_bean(process=Process.WET_HULLED)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 0.0
        assert vec[2] == 0.0
        assert vec[3] == 0.0
        assert vec[4] == 0.0
        assert vec[5] == 1.0  # other

    def test_unknown_maps_to_other(self, make_recipe):
        bean = _make_bean(process=Process.UNKNOWN)
        vec = encode_features(bean, make_recipe())
        assert vec[1] == 0.0
        assert vec[2] == 0.0
        assert vec[3] == 0.0
        assert vec[4] == 0.0
        assert vec[5] == 1.0  # other

    def test_exactly_one_hot_for_known_process(self, make_recipe):
        """For any known process, exactly one of indices 1-5 is 1.0."""
        known = [Process.WASHED, Process.NATURAL, Process.HONEY,
                 Process.ANAEROBIC, Process.WET_HULLED, Process.UNKNOWN]
        for proc in known:
            bean = _make_bean(process=proc)
            vec = encode_features(bean, make_recipe())
            onehot_slice = vec[1:6]
            assert onehot_slice.sum() == 1.0, (
                f"Process {proc.value}: expected exactly 1 hot, got {onehot_slice}"
            )


# --- Test: Roast ordinal ---


class TestRoastOrdinal:
    """Light=1 through Dark=5, Unknown=3."""

    def test_light_is_1(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.LIGHT)
        assert encode_features(bean, make_recipe())[6] == 1.0

    def test_medium_light_is_2(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.MEDIUM_LIGHT)
        assert encode_features(bean, make_recipe())[6] == 2.0

    def test_medium_is_3(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.MEDIUM)
        assert encode_features(bean, make_recipe())[6] == 3.0

    def test_medium_dark_is_4(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.MEDIUM_DARK)
        assert encode_features(bean, make_recipe())[6] == 4.0

    def test_dark_is_5(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.DARK)
        assert encode_features(bean, make_recipe())[6] == 5.0

    def test_unknown_is_3(self, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.UNKNOWN)
        assert encode_features(bean, make_recipe())[6] == 3.0


# --- Test: Flavor cluster multi-hot ---


class TestFlavorClusters:
    """Multi-hot encoding for the 15 flavor clusters in FLAVOR_CLUSTERS order."""

    def test_single_cluster(self, make_recipe):
        bean = _make_bean(flavor_clusters=["Chocolate"])
        vec = encode_features(bean, make_recipe())
        # Chocolate is index 6 within FLAVOR_CLUSTERS -> offset 7+6=13
        assert vec[7 + 6] == 1.0  # Chocolate
        assert vec[7:22].sum() == 1.0  # exactly one hot

    def test_multiple_clusters(self, make_recipe):
        bean = _make_bean(flavor_clusters=["Floral", "Citrus", "Nutty"])
        vec = encode_features(bean, make_recipe())
        # Floral=0, Citrus=2, Nutty=7 within FLAVOR_CLUSTERS
        assert vec[7 + 0] == 1.0  # Floral
        assert vec[7 + 2] == 1.0  # Citrus
        assert vec[7 + 7] == 1.0  # Nutty
        assert vec[7:22].sum() == 3.0

    def test_all_15_clusters(self, make_recipe):
        bean = _make_bean(flavor_clusters=list(FLAVOR_CLUSTERS))
        vec = encode_features(bean, make_recipe())
        assert vec[7:22].sum() == 15.0
        for i in range(15):
            assert vec[7 + i] == 1.0

    def test_cluster_order_matches_flavor_clusters_constant(self, make_recipe):
        """Each cluster appears at the correct offset in the feature vector."""
        for i, cluster_name in enumerate(FLAVOR_CLUSTERS):
            bean = _make_bean(flavor_clusters=[cluster_name])
            vec = encode_features(bean, make_recipe())
            assert vec[7 + i] == 1.0, (
                f"Cluster '{cluster_name}' expected at index {7 + i}, got {vec[7 + i]}"
            )

    def test_empty_clusters_defaults_to_balanced(self):
        """_encode_clusters([]) returns Balanced=1 as the cold-start default."""
        result = _encode_clusters([])
        balanced_index = FLAVOR_CLUSTERS.index("Balanced")
        assert result[balanced_index] == 1.0
        assert sum(result) == 1.0

    def test_nonempty_clusters_does_not_default_to_balanced(self):
        """When clusters are explicitly provided, Balanced is NOT auto-added."""
        result = _encode_clusters(["Floral"])
        assert result[0] == 1.0  # Floral
        assert result[FLAVOR_CLUSTERS.index("Balanced")] == 0.0  # Balanced not auto-set


# --- Test: Cold-start user ---


class TestColdStartUser:
    """Cold-start users have all user features = 0.0 (default values)."""

    def test_all_user_features_zero_by_default(self, make_bean, make_recipe):
        vec = encode_features(make_bean(), make_recipe())
        # user features at indices 30-38
        user_slice = vec[30:39]
        expected = np.array([0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        # Note: user_roast_pref defaults to 3.0 (medium midpoint)
        np.testing.assert_array_almost_equal(user_slice, expected)

    def test_explicit_user_features(self, make_bean, make_recipe):
        vec = encode_features(
            make_bean(),
            make_recipe(),
            user_avg_rating=7.0,
            user_rating_count=10,
            user_roast_pref=1.0,
            user_temp_pref=93.0,
            user_grind_pref=5.0,
            user_ratio_pref=16.0,
            user_acidity_bias=0.5,
            user_body_bias=-0.3,
            user_sweetness_bias=0.8,
        )
        expected_user = np.array([
            7.0,   # [30] user_avg_rating
            10.0,  # [31] user_rating_count
            1.0,   # [32] user_roast_pref
            93.0,  # [33] user_temp_pref
            5.0,   # [34] user_grind_pref
            16.0,  # [35] user_ratio_pref
            0.5,   # [36] user_acidity_bias
            -0.3,  # [37] user_body_bias
            0.8,   # [38] user_sweetness_bias
        ])
        np.testing.assert_array_almost_equal(vec[30:39], expected_user)


# --- Test: Interaction features ---


class TestInteractionFeatures:
    """Interaction features computed from bean + recipe values."""

    def test_roast_x_temp(self, make_bean, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.DARK)
        recipe = make_recipe(water_temp_c=90.0)
        vec = encode_features(bean, recipe)
        # dark=5, temp=90 => 5*90=450
        assert vec[39] == pytest.approx(5.0 * 90.0)

    def test_grind_x_time(self, make_bean, make_recipe):
        recipe = make_recipe(grind_setting=4, total_time_s=200)
        vec = encode_features(make_bean(), recipe)
        assert vec[40] == pytest.approx(4.0 * 200.0)

    def test_grind_x_temp(self, make_bean, make_recipe):
        recipe = make_recipe(grind_setting=6, water_temp_c=95.0)
        vec = encode_features(make_bean(), recipe)
        assert vec[41] == pytest.approx(6.0 * 95.0)

    def test_ratio_x_dose(self, make_bean):
        # Keep ratio, dose, water_total_g consistent for Recipe validation.
        recipe = _make_recipe(
            dose_g=16.0,
            water_total_g=256.0,
            ratio=16.0,
            pours=[
                PourStep(step=1, time_offset_s=0, water_g=51.0),
                PourStep(step=2, time_offset_s=45, water_g=102.0),
                PourStep(step=3, time_offset_s=90, water_g=103.0),
            ],
        )
        vec = encode_features(make_bean(), recipe)
        assert vec[42] == pytest.approx(16.0 * 16.0)

    def test_roast_x_grind(self, make_bean, make_recipe):
        bean = _make_bean(roast_level=RoastLevel.MEDIUM)  # ordinal=3
        recipe = make_recipe(grind_setting=7)
        vec = encode_features(bean, recipe)
        assert vec[43] == pytest.approx(3.0 * 7.0)

    def test_cluster_count(self, make_bean, make_recipe):
        bean = _make_bean(flavor_clusters=["Floral", "Berry", "Chocolate"])
        vec = encode_features(bean, make_recipe())
        assert vec[44] == 3.0

    def test_cluster_count_all_15(self, make_bean, make_recipe):
        bean = _make_bean(flavor_clusters=list(FLAVOR_CLUSTERS))
        vec = encode_features(bean, make_recipe())
        assert vec[44] == 15.0

    def test_cluster_count_single(self, make_bean, make_recipe):
        bean = _make_bean(flavor_clusters=["Balanced"])
        vec = encode_features(bean, make_recipe())
        assert vec[44] == 1.0


# --- Test: Altitude mean ---


class TestAltitudeMin:
    """Altitude uses altitude_min_m directly, or 0.0 if missing."""

    def test_both_altitudes_present(self, make_recipe):
        bean = _make_bean(altitude_min_m=1000, altitude_max_m=2000)
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 1000.0

    def test_both_altitudes_same(self, make_recipe):
        bean = _make_bean(altitude_min_m=1800, altitude_max_m=1800)
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 1800.0

    def test_no_altitudes(self, make_recipe):
        bean = _make_bean()  # no altitude fields
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 0.0

    def test_only_min_altitude(self, make_recipe):
        bean = _make_bean(altitude_min_m=1500)
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 1500.0

    def test_only_max_altitude_returns_zero(self, make_recipe):
        bean = _make_bean(altitude_max_m=2000)
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 0.0


# --- Test: Default cluster (Balanced) ---


class TestDefaultCluster:
    """When flavor clusters would be empty, default to Balanced=1."""

    def test_balanced_is_last_cluster_index(self, make_recipe):
        """Balanced is the 15th cluster at index 7+14=21."""
        bean = _make_bean(flavor_clusters=["Balanced"])
        vec = encode_features(bean, make_recipe())
        assert vec[21] == 1.0
        assert vec[7:22].sum() == 1.0


# --- Test: FeatureEncoder class ---


class TestFeatureEncoder:
    """FeatureEncoder wraps encode_features with class-level constants."""

    def test_encode_delegates_to_function(self, make_bean, make_recipe):
        encoder = FeatureEncoder()
        vec = encoder.encode(make_bean(), make_recipe())
        assert vec.shape == (45,)

    def test_encode_passes_user_kwargs(self, make_bean, make_recipe):
        encoder = FeatureEncoder()
        vec = encoder.encode(
            make_bean(), make_recipe(),
            user_avg_rating=8.0,
            user_rating_count=5,
        )
        assert vec[30] == 8.0
        assert vec[31] == 5.0

    def test_encode_passes_all_user_kwargs(self, make_bean, make_recipe):
        """All 9 user preference kwargs are forwarded correctly."""
        encoder = FeatureEncoder()
        vec = encoder.encode(
            make_bean(), make_recipe(),
            user_avg_rating=6.0,
            user_rating_count=3,
            user_roast_pref=2.0,
            user_temp_pref=94.0,
            user_grind_pref=4.0,
            user_ratio_pref=15.0,
            user_acidity_bias=-0.5,
            user_body_bias=0.3,
            user_sweetness_bias=0.1,
        )
        expected_user = np.array([
            6.0, 3.0, 2.0, 94.0, 4.0, 15.0, -0.5, 0.3, 0.1,
        ])
        np.testing.assert_array_almost_equal(vec[30:39], expected_user)

    def test_origin_map_class_attribute(self):
        encoder = FeatureEncoder()
        assert encoder.ORIGIN_MAP["Ethiopia"] == 1
        assert encoder.ORIGIN_MAP["Vietnam"] == 20
        assert len(encoder.ORIGIN_MAP) == 20

    def test_roast_ordinal_class_attribute(self):
        encoder = FeatureEncoder()
        assert encoder.ROAST_ORDINAL[RoastLevel.LIGHT] == 1.0
        assert encoder.ROAST_ORDINAL[RoastLevel.DARK] == 5.0
        assert encoder.ROAST_ORDINAL[RoastLevel.UNKNOWN] == 3.0


# --- Test: Edge cases ---


class TestEdgeCases:
    """Edge-case scenarios: single pour, missing altitude, unknown origin."""

    def test_single_pour_recipe(self, make_bean):
        """Recipe with exactly 1 pour should produce pour_count=1."""
        # PourStep validates water_g 10-200, so use a small single-pour recipe.
        recipe = _make_recipe(
            dose_g=12.0,
            water_total_g=192.0,
            ratio=16.0,
            pours=[PourStep(step=1, time_offset_s=0, water_g=192.0)],
            total_time_s=150,
        )
        vec = encode_features(make_bean(), recipe)
        assert vec[29] == 1.0  # pour_count
        assert vec.shape == (45,)

    def test_single_pour_interaction_features(self, make_bean):
        """Interaction features computed correctly for single-pour recipe."""
        recipe = _make_recipe(
            dose_g=12.0,
            water_total_g=192.0,
            ratio=16.0,
            pours=[PourStep(step=1, time_offset_s=0, water_g=192.0)],
            total_time_s=150,
            grind_setting=3,
            water_temp_c=88.0,
        )
        bean = _make_bean(roast_level=RoastLevel.MEDIUM)  # ordinal=3
        vec = encode_features(bean, recipe)

        roast = vec[6]
        temp = vec[26]
        grind = vec[25]
        time_s = vec[28]
        ratio = vec[24]
        dose = vec[23]

        np.testing.assert_array_almost_equal(
            vec[39:45],
            np.array([
                roast * temp,      # [39] roast_x_temp
                grind * time_s,    # [40] grind_x_time
                grind * temp,      # [41] grind_x_temp
                ratio * dose,      # [42] ratio_x_dose
                roast * grind,     # [43] roast_x_grind
                vec[7:22].sum(),   # [44] cluster_count
            ]),
        )

    def test_missing_altitude_returns_zero(self, make_recipe):
        """Bean with no altitude fields encodes altitude_mean as 0.0."""
        bean = _make_bean()
        assert bean.altitude_min_m is None
        assert bean.altitude_max_m is None
        vec = encode_features(bean, make_recipe())
        assert vec[22] == 0.0

    def test_unknown_origin_returns_zero(self, make_recipe):
        """Bean with a non-top-20 country encodes origin as 0."""
        bean = _make_bean(origin_country="Mars")
        vec = encode_features(bean, make_recipe())
        assert vec[0] == 0.0

    def test_unknown_roast_uses_midpoint(self, make_recipe):
        """Unknown roast level defaults to ordinal 3 (medium midpoint)."""
        bean = _make_bean(roast_level=RoastLevel.UNKNOWN)
        vec = encode_features(bean, make_recipe())
        assert vec[6] == 3.0


# --- Test: End-to-end consistency ---


class TestEndToEnd:
    """Verify the full pipeline produces consistent results."""

    def test_deterministic_output(self, make_bean, make_recipe):
        """Same inputs always produce same output."""
        bean = make_bean()
        recipe = make_recipe()
        vec1 = encode_features(bean, recipe)
        vec2 = encode_features(bean, recipe)
        np.testing.assert_array_equal(vec1, vec2)

    def test_different_beans_produce_different_vectors(self, make_recipe):
        bean_a = _make_bean(origin_country="Ethiopia", roast_level=RoastLevel.LIGHT)
        bean_b = _make_bean(origin_country="Brazil", roast_level=RoastLevel.DARK)
        vec_a = encode_features(bean_a, make_recipe())
        vec_b = encode_features(bean_b, make_recipe())
        assert not np.array_equal(vec_a, vec_b)

    def test_interaction_features_consistent_with_base_features(self, make_bean, make_recipe):
        """Interaction features must be exactly derivable from base features."""
        bean = make_bean()
        recipe = make_recipe()
        vec = encode_features(bean, recipe)

        roast = vec[6]
        temp = vec[26]
        grind = vec[25]
        time_s = vec[28]
        ratio = vec[24]
        dose = vec[23]
        cluster_count = vec[44]

        expected_interactions = np.array([
            roast * temp,
            grind * time_s,
            grind * temp,
            ratio * dose,
            roast * grind,
            vec[7:22].sum(),
        ])
        np.testing.assert_array_almost_equal(vec[39:45], expected_interactions)

    def test_full_vector_reconstructed_from_parts(self, make_bean, make_recipe):
        """The 45-element vector equals the concatenation of its four segments."""
        bean = make_bean()
        recipe = make_recipe()
        vec = encode_features(bean, recipe)

        bean_features = vec[0:23]
        recipe_features = vec[23:30]
        user_features = vec[30:39]
        interaction_features = vec[39:45]

        full = np.concatenate([bean_features, recipe_features, user_features, interaction_features])
        np.testing.assert_array_almost_equal(vec, full)
        assert len(full) == 45


# --- Test: Missing-field defaults (M2-M04) ---


class TestMissingFieldDefaults:
    """Verify default values applied when optional bean fields are absent.

    BeanProfile requires origin_country, process, roast_level,
    flavor_clusters, and source_text. The optional fields are
    altitude_min_m, altitude_max_m, variety, origin_region,
    flavor_notes, and extraction_confidence.

    When the encoder encounters absent/unknown values, it must apply
    sensible defaults: unknown origin maps to 0, unknown process maps
    to the "other" one-hot, unknown roast maps to ordinal 3 (midpoint),
    missing altitude maps to 0.0.
    """

    def test_minimal_bean_all_defaults_correct(self, make_recipe):
        """BeanProfile with only required fields: verify every default.

        Uses an unrecognized country (not in top 20), Process.UNKNOWN,
        RoastLevel.UNKNOWN, a single trivial cluster, and no altitude.
        """
        bean = BeanProfile(
            origin_country="Atlantis",        # not in top 20 -> origin = 0
            process=Process.UNKNOWN,           # maps to "other" one-hot
            roast_level=RoastLevel.UNKNOWN,    # ordinal midpoint = 3
            flavor_clusters=["Balanced"],      # single valid cluster
            source_text="minimal test bean",
            # altitude_min_m, altitude_max_m, variety, origin_region all None
        )
        recipe = make_recipe()
        vec = encode_features(bean, recipe)

        # [0] origin: unrecognized country -> 0
        assert vec[0] == 0.0

        # [1-5] process one-hot: UNKNOWN -> index 5 (other) = 1, rest = 0
        assert vec[1] == 0.0  # washed
        assert vec[2] == 0.0  # natural
        assert vec[3] == 0.0  # honey
        assert vec[4] == 0.0  # anaerobic
        assert vec[5] == 1.0  # other

        # [6] roast ordinal: UNKNOWN -> 3.0
        assert vec[6] == 3.0

        # [7-21] flavor clusters: only "Balanced" set
        # Balanced is at index 14 within FLAVOR_CLUSTERS -> vec index 7+14=21
        balanced_offset = FLAVOR_CLUSTERS.index("Balanced")
        assert vec[7 + balanced_offset] == 1.0
        assert vec[7:22].sum() == 1.0  # exactly one cluster

        # [22] altitude: both None -> 0.0
        assert vec[22] == 0.0

        # [23-29] recipe features: unaffected by bean, should match recipe values
        assert vec[23] == recipe.dose_g
        assert vec[25] == float(recipe.grind_setting)

        # [30-38] user features: all defaults (cold-start)
        user_slice = vec[30:39]
        expected_user = np.array([0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(user_slice, expected_user)

        # [39] roast_x_temp: 3.0 * water_temp_c
        assert vec[39] == pytest.approx(3.0 * recipe.water_temp_c)

        # [40] grind_x_time
        assert vec[40] == pytest.approx(float(recipe.grind_setting) * float(recipe.total_time_s))

        # [41] grind_x_temp
        assert vec[41] == pytest.approx(float(recipe.grind_setting) * float(recipe.water_temp_c))

        # [42] ratio_x_dose
        assert vec[42] == pytest.approx(float(recipe.ratio) * float(recipe.dose_g))

        # [43] roast_x_grind: 3.0 * grind_setting
        assert vec[43] == pytest.approx(3.0 * float(recipe.grind_setting))

        # [44] cluster_count: 1 (Balanced only)
        assert vec[44] == 1.0

        # Overall shape still valid
        assert vec.shape == (45,)
        assert vec.dtype == np.float64

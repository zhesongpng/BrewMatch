"""Tests for data_generator.generator — alignment, scoring, rating, beans, progression."""

import random
from datetime import datetime

import pytest

from src.data_generator.generator import (
    CLUSTER_NOTE_MAP,
    FLAVOR_CLUSTERS,
    ORIGINS,
    ORIGIN_REGIONS,
    PROCESSES,
    ROAST_LEVELS,
    VARIETIES,
    Expert,
    VirtualUser,
    _biased_recipe,
    compute_grind_time_alignment,
    compute_preference_alignment,
    compute_process_grind_alignment,
    compute_roast_temp_alignment,
    expert_rating,
    extraction_quality_score,
    generate_brew_history,
    generate_demo_alex,
    generate_directional_flags,
    generate_experts,
    generate_random_bean,
    generate_rating,
    generate_recipe_params,
    generate_user,
    is_overextracted,
    is_underextracted,
)


# --- Helpers ---

def _rng(seed=42):
    return random.Random(seed)


def _bean(roast="light", process="washed", clusters=None):
    return {
        "roast_level": roast,
        "process": process,
        "flavor_clusters": clusters or ["Citrus", "Berry"],
    }


def _recipe(temp=95.0, grind=5, ratio=16.0, dose=16.0, total=225):
    return {
        "water_temp_c": temp,
        "grind_setting": grind,
        "ratio": ratio,
        "dose_g": dose,
        "total_time_s": total,
        "bloom_time_s": 30,
    }


def _user(roast="light", clusters=None, bias=0.0):
    return VirtualUser(
        user_id="test-user",
        roast_preference=roast,
        preferred_clusters=clusters or ["Citrus", "Berry"],
        rating_bias=bias,
        acidity_tolerance=0.0,
        body_preference=0.0,
        sweetness_preference=0.0,
        experience_level="intermediate",
    )


# =====================================================================
# compute_roast_temp_alignment
# =====================================================================

class TestRoastTempAlignment:
    def test_light_roast_in_range(self):
        assert compute_roast_temp_alignment("light", 95.0) == 1.0

    def test_light_roast_optimal_boundary(self):
        assert compute_roast_temp_alignment("light", 92.0) == 1.0
        assert compute_roast_temp_alignment("light", 98.0) == 1.0

    def test_light_roast_below_range(self):
        score = compute_roast_temp_alignment("light", 88.0)
        assert 0.0 < score < 1.0

    def test_light_roast_above_range(self):
        score = compute_roast_temp_alignment("light", 100.0)
        assert 0.0 <= score < 1.0

    def test_dark_roast_in_range(self):
        assert compute_roast_temp_alignment("dark", 91.0) == 1.0

    def test_dark_roast_optimal_boundary(self):
        assert compute_roast_temp_alignment("dark", 89.0) == 1.0
        assert compute_roast_temp_alignment("dark", 94.0) == 1.0

    def test_dark_roast_above_range(self):
        score = compute_roast_temp_alignment("dark", 97.0)
        assert 0.0 <= score < 1.0

    def test_dark_roast_below_range(self):
        score = compute_roast_temp_alignment("dark", 85.0)
        assert 0.0 <= score < 1.0

    def test_medium_roast_in_range(self):
        assert compute_roast_temp_alignment("medium", 93.0) == 1.0

    def test_medium_roast_center(self):
        assert compute_roast_temp_alignment("medium", 93.0) == 1.0

    def test_medium_roast_out_of_range(self):
        score = compute_roast_temp_alignment("medium", 85.0)
        assert 0.0 <= score < 1.0

    def test_never_negative(self):
        for roast in ROAST_LEVELS:
            assert compute_roast_temp_alignment(roast, 80.0) >= 0.0
            assert compute_roast_temp_alignment(roast, 105.0) >= 0.0


# =====================================================================
# compute_grind_time_alignment
# =====================================================================

class TestGrindTimeAlignment:
    def test_fine_grind_optimal(self):
        assert compute_grind_time_alignment(2, 180) == 1.0

    def test_fine_grind_boundary(self):
        assert compute_grind_time_alignment(3, 150) == 1.0
        assert compute_grind_time_alignment(3, 210) == 1.0

    def test_coarse_grind_optimal(self):
        assert compute_grind_time_alignment(8, 280) == 1.0

    def test_coarse_grind_boundary(self):
        assert compute_grind_time_alignment(7, 240) == 1.0
        assert compute_grind_time_alignment(7, 330) == 1.0

    def test_medium_grind_optimal(self):
        assert compute_grind_time_alignment(5, 225) == 1.0

    def test_medium_grind_boundary(self):
        assert compute_grind_time_alignment(5, 180) == 1.0
        assert compute_grind_time_alignment(5, 270) == 1.0

    def test_mismatch_fine_long(self):
        score = compute_grind_time_alignment(2, 300)
        assert score < 1.0

    def test_mismatch_coarse_short(self):
        score = compute_grind_time_alignment(8, 150)
        assert score < 1.0

    def test_never_negative(self):
        for grind in range(1, 11):
            for total in [100, 120, 150, 200, 250, 300, 360, 400]:
                assert compute_grind_time_alignment(grind, total) >= 0.0


# =====================================================================
# compute_process_grind_alignment
# =====================================================================

class TestProcessGrindAlignment:
    def test_natural_optimal(self):
        assert compute_process_grind_alignment("natural", 6) == 1.0

    def test_natural_boundary(self):
        assert compute_process_grind_alignment("natural", 5) == 1.0
        assert compute_process_grind_alignment("natural", 8) == 1.0

    def test_natural_too_fine(self):
        score = compute_process_grind_alignment("natural", 2)
        assert 0.0 <= score < 1.0

    def test_washed_optimal(self):
        assert compute_process_grind_alignment("washed", 4) == 1.0

    def test_washed_boundary(self):
        assert compute_process_grind_alignment("washed", 3) == 1.0
        assert compute_process_grind_alignment("washed", 6) == 1.0

    def test_other_process(self):
        assert compute_process_grind_alignment("honey", 5) == 0.7
        assert compute_process_grind_alignment("anaerobic", 5) == 0.7


# =====================================================================
# extraction_quality_score
# =====================================================================

class TestExtractionQualityScore:
    def test_well_aligned(self):
        bean = _bean(roast="light")
        recipe = _recipe(temp=95.0, grind=5, ratio=16.0, dose=16.0, total=225)
        score = extraction_quality_score(bean, recipe)
        assert 0.5 < score <= 1.0

    def test_poor_alignment(self):
        bean = _bean(roast="dark")
        recipe = _recipe(temp=99.0, grind=2, ratio=14.0, dose=20.0, total=300)
        score = extraction_quality_score(bean, recipe)
        assert score < 0.9

    def test_bounded_0_to_1(self):
        rng = _rng(99)
        for _ in range(100):
            bean = generate_random_bean(rng)
            recipe = generate_recipe_params(rng)
            score = extraction_quality_score(bean, recipe)
            assert 0.0 <= score <= 1.0


# =====================================================================
# compute_preference_alignment
# =====================================================================

class TestPreferenceAlignment:
    def test_exact_roast_match(self):
        user = _user(roast="light")
        bean = _bean(roast="light")
        alignment = compute_preference_alignment(user, bean)
        assert alignment >= 1.0  # roast match + possible cluster match

    def test_roast_mismatch(self):
        user = _user(roast="light")
        bean = _bean(roast="dark")
        alignment = compute_preference_alignment(user, bean)
        assert alignment < 1.0

    def test_cluster_match(self):
        user = _user(clusters=["Berry", "Citrus"])
        bean = _bean(clusters=["Berry", "Floral"])
        alignment = compute_preference_alignment(user, bean)
        assert alignment > 0.0  # at least the Berry match

    def test_no_match(self):
        user = _user(roast="light", clusters=["Berry"])
        bean = _bean(roast="dark", clusters=["Chocolate"])
        alignment = compute_preference_alignment(user, bean)
        assert alignment < 0.0

    def test_bounded(self):
        user = _user(roast="light", clusters=["Citrus"])
        bean = _bean(roast="dark", clusters=["Chocolate", "Nutty", "Roasted"])
        alignment = compute_preference_alignment(user, bean)
        assert -2.0 <= alignment <= 3.0


# =====================================================================
# generate_rating
# =====================================================================

class TestGenerateRating:
    def test_returns_int_1_to_10(self):
        rng = _rng()
        user = _user()
        bean = _bean()
        for q in [0.0, 0.3, 0.5, 0.8, 1.0]:
            rating = generate_rating(q, user, bean, rng=rng)
            assert 1 <= rating <= 10
            assert isinstance(rating, int)

    def test_higher_quality_higher_rating(self):
        rng = _rng()
        user = _user(bias=0.0)
        bean = _bean()
        low_ratings = [generate_rating(0.2, user, bean, noise_std=0.01, rng=_rng(i)) for i in range(20)]
        high_ratings = [generate_rating(0.9, user, bean, noise_std=0.01, rng=_rng(i)) for i in range(20)]
        assert sum(high_ratings) / len(high_ratings) > sum(low_ratings) / len(low_ratings)

    def test_deterministic_with_seed(self):
        user = _user()
        bean = _bean()
        r1 = generate_rating(0.7, user, bean, rng=_rng(42))
        r2 = generate_rating(0.7, user, bean, rng=_rng(42))
        assert r1 == r2

    def test_clipped_to_1(self):
        rng = _rng(42)
        user = _user(bias=-5.0)
        bean = _bean()
        rating = generate_rating(0.0, user, bean, noise_std=0.0, rng=rng)
        assert rating >= 1

    def test_clipped_to_10(self):
        rng = _rng(42)
        user = _user(bias=5.0)
        bean = _bean()
        rating = generate_rating(1.0, user, bean, noise_std=0.0, rng=rng)
        assert rating <= 10


# =====================================================================
# is_underextracted / is_overextracted
# =====================================================================

class TestExtractionDiagnosis:
    def test_underextracted_low_temp(self):
        bean = _bean(roast="light")
        recipe = _recipe(temp=89.0)
        assert is_underextracted(bean, recipe)

    def test_underextracted_coarse_grind_short_time(self):
        bean = _bean()
        recipe = _recipe(grind=8, total=180)
        assert is_underextracted(bean, recipe)

    def test_underextracted_high_ratio(self):
        bean = _bean()
        recipe = _recipe(ratio=18.0)
        assert is_underextracted(bean, recipe)

    def test_not_underextracted(self):
        bean = _bean(roast="medium")
        recipe = _recipe(temp=93.0, grind=5, ratio=16.0, total=225)
        assert not is_underextracted(bean, recipe)

    def test_overextracted_high_temp(self):
        bean = _bean(roast="dark")
        recipe = _recipe(temp=97.0)
        assert is_overextracted(bean, recipe)

    def test_overextracted_fine_grind_long_time(self):
        bean = _bean()
        recipe = _recipe(grind=2, total=280)
        assert is_overextracted(bean, recipe)

    def test_overextracted_low_ratio(self):
        bean = _bean()
        recipe = _recipe(ratio=14.0)
        assert is_overextracted(bean, recipe)

    def test_not_overextracted(self):
        bean = _bean(roast="medium")
        recipe = _recipe(temp=93.0, grind=5, ratio=16.0, total=225)
        assert not is_overextracted(bean, recipe)


# =====================================================================
# generate_directional_flags
# =====================================================================

class TestDirectionalFlags:
    def test_high_rating_no_flags(self):
        bean = _bean()
        recipe = _recipe()
        flags = generate_directional_flags(bean, recipe, 8)
        assert flags == []

    def test_low_rating_underextracted(self):
        rng = _rng()
        bean = _bean(roast="light")
        recipe = _recipe(temp=88.0)
        # With random, just check it doesn't crash and returns a list
        flags = generate_directional_flags(bean, recipe, 3)
        assert isinstance(flags, list)
        for f in flags:
            assert f in ("too_sour", "too_bitter", "too_weak", "too_harsh", "astringent")


# =====================================================================
# generate_random_bean
# =====================================================================

class TestGenerateRandomBean:
    def test_valid_origin(self):
        bean = generate_random_bean(_rng())
        assert bean["origin_country"] in ORIGINS

    def test_valid_process(self):
        bean = generate_random_bean(_rng())
        assert bean["process"] in PROCESSES

    def test_valid_roast(self):
        bean = generate_random_bean(_rng())
        assert bean["roast_level"] in ROAST_LEVELS

    def test_valid_clusters(self):
        bean = generate_random_bean(_rng())
        for c in bean["flavor_clusters"]:
            assert c in FLAVOR_CLUSTERS

    def test_notes_derived_from_clusters(self):
        """Every flavor note must come from one of the bean's cluster note pools."""
        bean = generate_random_bean(_rng())
        valid_notes = set()
        for cluster in bean["flavor_clusters"]:
            valid_notes.update(CLUSTER_NOTE_MAP.get(cluster, []))
        for note in bean["flavor_notes"]:
            assert note in valid_notes, f"Note '{note}' not from any cluster in {bean['flavor_clusters']}"

    def test_altitude_none_or_positive(self):
        for _ in range(50):
            bean = generate_random_bean(_rng())
            if bean["altitude_min_m"] is not None:
                assert bean["altitude_min_m"] >= 0

    def test_region_valid_for_origin(self):
        for _ in range(50):
            bean = generate_random_bean(_rng())
            if bean["origin_region"] is not None:
                regions = ORIGIN_REGIONS.get(bean["origin_country"], [])
                assert bean["origin_region"] in regions

    def test_deterministic(self):
        b1 = generate_random_bean(_rng(42))
        b2 = generate_random_bean(_rng(42))
        assert b1 == b2

    def test_cluster_note_map_covers_all_clusters(self):
        for cluster in FLAVOR_CLUSTERS:
            assert cluster in CLUSTER_NOTE_MAP, f"Missing cluster in CLUSTER_NOTE_MAP: {cluster}"
            assert len(CLUSTER_NOTE_MAP[cluster]) >= 2


# =====================================================================
# generate_recipe_params
# =====================================================================

class TestGenerateRecipeParams:
    def test_valid_ranges(self):
        rng = _rng()
        for _ in range(50):
            recipe = generate_recipe_params(rng)
            assert 12.0 <= recipe["dose_g"] <= 35.0
            assert 14.0 <= recipe["ratio"] <= 18.0
            assert 1 <= recipe["grind_setting"] <= 10
            assert 85.0 <= recipe["water_temp_c"] <= 100.0
            assert 15 <= recipe["bloom_time_s"] <= 90
            assert 120 <= recipe["total_time_s"] <= 360
            assert 1 <= recipe["pour_count"] <= 6


# =====================================================================
# generate_user
# =====================================================================

class TestGenerateUser:
    def test_valid_user(self):
        user = generate_user("test-001", _rng())
        assert user.user_id == "test-001"
        assert user.roast_preference in ROAST_LEVELS
        assert user.experience_level in ("beginner", "intermediate", "advanced")
        assert 2 <= len(user.preferred_clusters) <= 4

    def test_bias_range(self):
        for i in range(50):
            user = generate_user(f"u-{i}", _rng(i))
            assert -1.0 <= user.acidity_tolerance <= 1.0
            assert -1.0 <= user.body_preference <= 1.0
            assert -1.0 <= user.sweetness_preference <= 1.0


# =====================================================================
# _biased_recipe
# =====================================================================

class TestBiasedRecipe:
    def test_zero_tightness_returns_random(self):
        rng = _rng(42)
        bean = _bean()
        user = _user(roast="light")
        r1 = _biased_recipe(rng, bean, user, 0.0)
        r2 = generate_recipe_params(_rng(42), bean)
        assert r1 == r2

    def test_high_tightness_converges(self):
        rng = _rng(100)
        bean = _bean()
        user = _user(roast="light")
        recipes = [_biased_recipe(_rng(i), bean, user, 0.8) for i in range(50)]
        temps = [r["water_temp_c"] for r in recipes]
        assert min(temps) >= 85.0
        assert max(temps) <= 100.0
        # With tightness=0.8, temps should cluster in light roast optimal range
        avg_temp = sum(temps) / len(temps)
        assert 90.0 <= avg_temp <= 99.0


# =====================================================================
# generate_brew_history
# =====================================================================

class TestBrewHistory:
    def test_correct_number_of_brews(self):
        user = _user()
        brews = generate_brew_history(user, 10, _rng(), datetime(2026, 1, 1))
        assert len(brews) == 10

    def test_zero_brews(self):
        user = _user()
        brews = generate_brew_history(user, 0, _rng(), datetime(2026, 1, 1))
        assert brews == []

    def test_timestamps_monotonic(self):
        user = _user()
        brews = generate_brew_history(user, 30, _rng(), datetime(2026, 1, 1))
        timestamps = [b["timestamp"] for b in brews]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1], f"Timestamps not monotonic at index {i}"

    def test_ratings_in_range(self):
        user = _user()
        brews = generate_brew_history(user, 20, _rng(), datetime(2026, 1, 1))
        for brew in brews:
            assert 1 <= brew["rating"] <= 10

    def test_user_id_propagated(self):
        user = _user()
        brews = generate_brew_history(user, 5, _rng(), datetime(2026, 1, 1))
        for brew in brews:
            assert brew["user_id"] == user.user_id

    def test_learning_progression_ratings_trend(self):
        """Late brews should generally rate higher than early brews for a consistent user."""
        rng = _rng(42)
        user = _user(roast="light", clusters=["Citrus", "Floral"], bias=0.3)
        brews = generate_brew_history(user, 25, rng, datetime(2026, 1, 1))
        early = [b["rating"] for b in brews[:5]]
        late = [b["rating"] for b in brews[15:]]
        # Late average should be >= early average (allowing noise)
        assert sum(late) / len(late) >= sum(early) / len(early) - 0.5


# =====================================================================
# generate_demo_alex
# =====================================================================

class TestDemoAlex:
    def test_structure(self):
        alex = generate_demo_alex(_rng())
        assert alex["user_id"] == "demo-alex-001"
        assert alex["experience_level"] == "intermediate"
        assert alex["roast_preference"] == "light"
        assert len(alex["brew_history"]) == 15

    def test_last_5_ratings_high(self):
        alex = generate_demo_alex(_rng())
        for brew in alex["brew_history"][10:]:
            assert brew["rating"] >= 7

    def test_timestamps_monotonic(self):
        alex = generate_demo_alex(_rng())
        timestamps = [b["timestamp"] for b in alex["brew_history"]]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1]


# =====================================================================
# generate_experts
# =====================================================================

class TestGenerateExperts:
    def test_five_experts(self):
        experts = generate_experts()
        assert len(experts) == 5

    def test_expert_fields(self):
        experts = generate_experts()
        for exp in experts:
            assert isinstance(exp, Expert)
            assert exp.expert_id
            assert exp.specialty
            assert -1.0 <= exp.rating_bias <= 1.0
            assert exp.noise_std > 0


# =====================================================================
# expert_rating
# =====================================================================

class TestExpertRating:
    def test_returns_int_1_to_10(self):
        expert = generate_experts()[0]
        bean = _bean()
        rating = expert_rating(0.7, expert, bean)
        assert 1 <= rating <= 10
        assert isinstance(rating, int)

    def test_higher_quality_higher_rating(self):
        expert = generate_experts()[0]
        bean = _bean()
        low = [expert_rating(0.1, expert, bean) for _ in range(10)]
        high = [expert_rating(0.9, expert, bean) for _ in range(10)]
        assert sum(high) / len(high) > sum(low) / len(low)

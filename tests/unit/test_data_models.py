import pytest

from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    ExperienceLevel,
    Feedback,
    LearnedPreferences,
    Onboarding,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
    UserTasteProfile,
    create_user_id,
    DIRECTIONAL_FLAGS,
    FLAVOR_CLUSTERS,
)


# --- Helpers ---

def _make_pour(step: int = 1, time_offset_s: int = 0, water_g: float = 60.0) -> PourStep:
    return PourStep(step=step, time_offset_s=time_offset_s, water_g=water_g)


def _make_suitable(
    roast_levels=None, origins=None, processes=None, flavor_profiles=None
) -> SuitableFor:
    return SuitableFor(
        roast_levels=roast_levels if roast_levels is not None else [RoastLevel.LIGHT, RoastLevel.MEDIUM],
        origins=origins if origins is not None else ["Ethiopia", "Colombia"],
        processes=processes if processes is not None else [Process.WASHED, Process.NATURAL],
        flavor_profiles=flavor_profiles if flavor_profiles is not None else ["Floral", "Citrus"],
    )


def _make_recipe(**overrides) -> Recipe:
    defaults = dict(
        recipe_id="hoffmann-v60-classic",
        source="James Hoffmann",
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
        suitable_for=_make_suitable(),
        instructions="Bloom, then pour in two stages.",
    )
    defaults.update(overrides)
    return Recipe(**defaults)


def _make_bean(**overrides) -> BeanProfile:
    defaults = dict(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Ethiopian Yirgacheffe, light roast, floral and citrus notes",
    )
    defaults.update(overrides)
    return BeanProfile(**defaults)


# --- PourStep Tests ---

class TestPourStep:
    def test_valid_pour(self):
        p = _make_pour()
        assert p.step == 1
        assert p.water_g == 60.0

    def test_step_must_be_positive(self):
        with pytest.raises(ValueError, match="1-indexed"):
            _make_pour(step=0)

    def test_first_pour_must_be_zero_offset(self):
        with pytest.raises(ValueError, match="time_offset_s=0"):
            _make_pour(step=1, time_offset_s=10)

    def test_water_too_small(self):
        with pytest.raises(ValueError, match="10.0-200.0"):
            _make_pour(water_g=5.0)

    def test_water_too_large(self):
        with pytest.raises(ValueError, match="10.0-200.0"):
            _make_pour(water_g=250.0)


# --- SuitableFor Tests ---

class TestSuitableFor:
    def test_valid(self):
        s = _make_suitable()
        assert len(s.roast_levels) == 2

    def test_empty_roast_levels(self):
        with pytest.raises(ValueError, match="roast_levels"):
            _make_suitable(roast_levels=[])

    def test_empty_origins(self):
        with pytest.raises(ValueError, match="origins"):
            _make_suitable(origins=[])

    def test_empty_processes(self):
        with pytest.raises(ValueError, match="processes"):
            _make_suitable(processes=[])

    def test_empty_flavor_profiles(self):
        with pytest.raises(ValueError, match="flavor_profiles"):
            _make_suitable(flavor_profiles=[])

    def test_unknown_flavor_profile(self):
        with pytest.raises(ValueError, match="Unknown flavor profile"):
            _make_suitable(flavor_profiles=["Fake"])


# --- Recipe Tests ---

class TestRecipe:
    def test_valid_recipe(self):
        r = _make_recipe()
        assert r.recipe_id == "hoffmann-v60-classic"
        assert r.method == BrewMethod.V60

    def test_invalid_recipe_id(self):
        with pytest.raises(ValueError, match="kebab-case"):
            _make_recipe(recipe_id="")

    def test_dose_too_low(self):
        with pytest.raises(ValueError, match="12.0-35.0"):
            _make_recipe(dose_g=10.0)

    def test_dose_too_high(self):
        with pytest.raises(ValueError, match="12.0-35.0"):
            _make_recipe(dose_g=40.0)

    def test_water_total_too_low(self):
        with pytest.raises(ValueError, match="180.0-600.0"):
            _make_recipe(water_total_g=150.0)

    def test_water_total_too_high(self):
        with pytest.raises(ValueError, match="180.0-600.0"):
            _make_recipe(water_total_g=700.0)

    def test_ratio_out_of_range(self):
        with pytest.raises(ValueError, match="14.0-18.0"):
            _make_recipe(ratio=10.0)

    def test_grind_out_of_range(self):
        with pytest.raises(ValueError, match="1-10"):
            _make_recipe(grind_setting=11)

    def test_temp_too_low(self):
        with pytest.raises(ValueError, match="85.0-100.0"):
            _make_recipe(water_temp_c=80.0)

    def test_temp_too_high(self):
        with pytest.raises(ValueError, match="85.0-100.0"):
            _make_recipe(water_temp_c=105.0)

    def test_bloom_time_too_short(self):
        with pytest.raises(ValueError, match="15-90"):
            _make_recipe(bloom_time_s=10)

    def test_total_time_too_short(self):
        with pytest.raises(ValueError, match="120-360"):
            _make_recipe(total_time_s=60)

    def test_total_time_too_long(self):
        with pytest.raises(ValueError, match="120-360"):
            _make_recipe(total_time_s=400)

    def test_water_pours_mismatch(self):
        bad_pours = [PourStep(step=1, time_offset_s=0, water_g=30.0)]
        with pytest.raises(ValueError, match="within 5%"):
            _make_recipe(pours=bad_pours, water_total_g=250.0)

    def test_ratio_dose_mismatch(self):
        # ratio=15.0 is in range (14-18) but 250/15=16.67 != 15.0
        with pytest.raises(ValueError, match="ratio"):
            _make_recipe(ratio=15.0)

    def test_total_time_vs_last_pour(self):
        # last pour at 120s, total_time_s=130 < 120+30
        bad_pours = [
            PourStep(step=1, time_offset_s=0, water_g=50.0),
            PourStep(step=2, time_offset_s=45, water_g=100.0),
            PourStep(step=3, time_offset_s=120, water_g=100.0),
        ]
        with pytest.raises(ValueError, match="last pour offset"):
            _make_recipe(pours=bad_pours, total_time_s=140)

    def test_too_many_pours(self):
        pours = [PourStep(step=i+1, time_offset_s=i*30, water_g=40.0) for i in range(7)]
        with pytest.raises(ValueError, match="1-6 pours"):
            _make_recipe(pours=pours, water_total_g=280.0, total_time_s=250)

    def test_empty_instructions(self):
        with pytest.raises(ValueError, match="non-empty"):
            _make_recipe(instructions="")

    def test_source_url_optional(self):
        r = _make_recipe(source_url="https://example.com")
        assert r.source_url == "https://example.com"


# --- BeanProfile Tests ---

class TestBeanProfile:
    def test_valid_bean(self):
        b = _make_bean()
        assert b.origin_country == "Ethiopia"
        assert b.process == Process.WASHED

    def test_missing_origin_country(self):
        with pytest.raises(ValueError, match="origin_country"):
            _make_bean(origin_country="")

    def test_missing_source_text(self):
        with pytest.raises(ValueError, match="source_text"):
            _make_bean(source_text="")

    def test_empty_flavor_clusters(self):
        with pytest.raises(ValueError, match="at least 1"):
            _make_bean(flavor_clusters=[])

    def test_unknown_flavor_cluster(self):
        with pytest.raises(ValueError, match="Unknown flavor cluster"):
            _make_bean(flavor_clusters=["Fake"])

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError, match="0.0-1.0"):
            _make_bean(extraction_confidence=1.5)

    def test_altitude_min_negative(self):
        with pytest.raises(ValueError, match=">= 0"):
            _make_bean(altitude_min_m=-100)

    def test_altitude_min_gt_max(self):
        with pytest.raises(ValueError, match=">"):
            _make_bean(altitude_min_m=2000, altitude_max_m=1000)

    def test_optional_fields(self):
        b = _make_bean(
            origin_region="Yirgacheffe",
            flavor_notes=["jasmine", "lemon"],
            variety="Gesha",
            altitude_min_m=1800,
            altitude_max_m=2200,
            extraction_confidence=0.85,
        )
        assert b.origin_region == "Yirgacheffe"
        assert b.extraction_confidence == 0.85


# --- Feedback Tests ---

class TestFeedback:
    def test_valid_thumbs_up(self):
        f = Feedback(thumbs_up=True)
        assert f.thumbs_up is True

    def test_valid_with_score(self):
        f = Feedback(thumbs_up=False, score=7)
        assert f.score == 7

    def test_score_too_low(self):
        with pytest.raises(ValueError, match="1-10"):
            Feedback(thumbs_up=True, score=0)

    def test_score_too_high(self):
        with pytest.raises(ValueError, match="1-10"):
            Feedback(thumbs_up=True, score=11)

    def test_valid_directional_flags(self):
        f = Feedback(thumbs_up=False, directional_flags=["too_sour", "too_weak"])
        assert len(f.directional_flags) == 2

    def test_invalid_directional_flag(self):
        with pytest.raises(ValueError, match="Unknown directional flag"):
            Feedback(thumbs_up=True, directional_flags=["too_salty"])

    def test_all_valid_flags(self):
        for flag in DIRECTIONAL_FLAGS:
            f = Feedback(thumbs_up=True, directional_flags=[flag])
            assert flag in f.directional_flags


# --- BrewRecord Tests ---

class TestBrewRecord:
    def test_valid_brew_record(self):
        r = _make_recipe()
        b = _make_bean()
        f = Feedback(thumbs_up=True, score=8)
        br = BrewRecord(brew_id="abc-123", timestamp="2026-05-09T10:00:00Z",
                        bean_profile=b, recipe_used=r, feedback=f)
        assert br.brew_id == "abc-123"

    def test_missing_brew_id(self):
        with pytest.raises(ValueError, match="brew_id"):
            BrewRecord(
                brew_id="", timestamp="2026-05-09T10:00:00Z",
                bean_profile=_make_bean(), recipe_used=_make_recipe(),
                feedback=Feedback(thumbs_up=True),
            )


# --- LearnedPreferences Tests ---

class TestLearnedPreferences:
    def test_defaults(self):
        lp = LearnedPreferences()
        assert lp.acidity_bias == 0.0
        assert lp.preferred_temp_range == (90.0, 96.0)

    def test_bias_out_of_range(self):
        with pytest.raises(ValueError, match="-1.0 to 1.0"):
            LearnedPreferences(acidity_bias=2.0)

    def test_custom_ranges(self):
        lp = LearnedPreferences(
            acidity_bias=-0.3, body_bias=0.5, sweetness_bias=0.8,
            preferred_temp_range=(88.0, 94.0),
            preferred_ratio_range=(14.5, 16.5),
        )
        assert lp.acidity_bias == -0.3


# --- Onboarding Tests ---

class TestOnboarding:
    def test_valid(self):
        o = Onboarding(
            preferred_clusters=["Floral", "Citrus"],
            roast_preference=RoastLevel.LIGHT,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert len(o.preferred_clusters) == 2

    def test_too_many_clusters(self):
        with pytest.raises(ValueError, match="1-5"):
            Onboarding(
                preferred_clusters=list(FLAVOR_CLUSTERS[:6]),
                roast_preference=RoastLevel.LIGHT,
                experience_level=ExperienceLevel.BEGINNER,
            )

    def test_empty_clusters(self):
        with pytest.raises(ValueError, match="1-5"):
            Onboarding(
                preferred_clusters=[],
                roast_preference=RoastLevel.LIGHT,
                experience_level=ExperienceLevel.BEGINNER,
            )

    def test_unknown_cluster(self):
        with pytest.raises(ValueError, match="Unknown cluster"):
            Onboarding(
                preferred_clusters=["Fake"],
                roast_preference=RoastLevel.LIGHT,
                experience_level=ExperienceLevel.BEGINNER,
            )


# --- UserTasteProfile Tests ---

class TestUserTasteProfile:
    def test_valid_profile(self):
        uid = create_user_id()
        o = Onboarding(
            preferred_clusters=["Berry", "Chocolate"],
            roast_preference=RoastLevel.MEDIUM,
            experience_level=ExperienceLevel.ADVANCED,
        )
        p = UserTasteProfile(user_id=uid, onboarding=o)
        assert p.user_id == uid
        assert p.stats.total_brews == 0

    def test_missing_user_id(self):
        with pytest.raises(ValueError, match="user_id"):
            UserTasteProfile(
                user_id="",
                onboarding=Onboarding(
                    preferred_clusters=["Floral"],
                    roast_preference=RoastLevel.LIGHT,
                    experience_level=ExperienceLevel.BEGINNER,
                ),
            )

    def test_with_brew_history(self):
        p = UserTasteProfile(
            user_id=create_user_id(),
            onboarding=Onboarding(
                preferred_clusters=["Floral"],
                roast_preference=RoastLevel.LIGHT,
                experience_level=ExperienceLevel.BEGINNER,
            ),
            brew_history=[
                BrewRecord(
                    brew_id="b1", timestamp="2026-05-09T10:00:00Z",
                    bean_profile=_make_bean(), recipe_used=_make_recipe(),
                    feedback=Feedback(thumbs_up=True, score=8),
                ),
            ],
        )
        assert len(p.brew_history) == 1


# --- Flavor Clusters & Flags Constants ---

class TestConstants:
    def test_flavor_clusters_count(self):
        assert len(FLAVOR_CLUSTERS) == 15

    def test_directional_flags_count(self):
        assert len(DIRECTIONAL_FLAGS) == 5

    def test_brew_methods(self):
        assert {m.value for m in BrewMethod} == {"V60", "Kalita Wave", "Origami"}

    def test_roast_levels(self):
        assert len(RoastLevel) == 6

    def test_processes(self):
        assert len(Process) == 6

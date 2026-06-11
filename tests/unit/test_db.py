"""Tests for the SQLite persistence layer (src.app.db)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from src.app.db import (
    count_brews,
    delete_user_data,
    get_connection,
    get_user_stats,
    init_db,
    load_brew_history,
    load_user,
    save_brew,
    save_user,
    update_preferences,
)
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
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def conn():
    """Provide an in-memory SQLite connection with tables initialised."""
    c = get_connection(":memory:")
    init_db(c)
    yield c
    c.close()


@pytest.fixture()
def onboarding():
    return Onboarding(
        preferred_clusters=["Citrus", "Berry"],
        roast_preference=RoastLevel.LIGHT,
        experience_level=ExperienceLevel.INTERMEDIATE,
    )


@pytest.fixture()
def make_recipe_db(make_suitable):
    """Factory that builds a Recipe suitable for DB round-trips."""
    def _make(**overrides):
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
            suitable_for=make_suitable(),
            instructions="Bloom, then pour in two stages.",
        )
        defaults.update(overrides)
        return Recipe(**defaults)

    return _make


@pytest.fixture()
def make_bean_db():
    """Factory that builds a BeanProfile suitable for DB round-trips."""
    def _make(**overrides):
        defaults = dict(
            origin_country="Ethiopia",
            process=Process.WASHED,
            roast_level=RoastLevel.LIGHT,
            flavor_clusters=["Floral", "Citrus"],
            source_text="Ethiopian Yirgacheffe",
        )
        defaults.update(overrides)
        return BeanProfile(**defaults)

    return _make


def _brew_record(brew_id: str, bean: BeanProfile, recipe: Recipe) -> BrewRecord:
    return BrewRecord(
        brew_id=brew_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        bean_profile=bean,
        recipe_used=recipe,
        feedback=Feedback(thumbs_up=True, score=8, directional_flags=["too_sour"]),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_init_db_creates_tables(self, conn):
        """init_db should create users and brew_history tables."""
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [row["name"] for row in tables]
        assert "users" in table_names
        assert "brew_history" in table_names

    def test_init_db_idempotent(self, conn):
        """Calling init_db twice must not raise."""
        init_db(conn)  # second call -- should succeed silently


class TestUserRoundTrip:
    def test_save_and_load_user(self, conn, onboarding):
        """save_user followed by load_user returns matching data."""
        save_user(conn, "user-1", onboarding)
        loaded = load_user(conn, "user-1")

        assert loaded is not None
        assert loaded["user_id"] == "user-1"
        assert isinstance(loaded["onboarding"], Onboarding)
        assert loaded["onboarding"].preferred_clusters == ["Citrus", "Berry"]
        assert loaded["onboarding"].roast_preference == RoastLevel.LIGHT
        assert loaded["onboarding"].experience_level == ExperienceLevel.INTERMEDIATE
        assert loaded["preferences"] is None

    def test_load_nonexistent_user_returns_none(self, conn):
        assert load_user(conn, "no-such-user") is None

    def test_save_user_upsert(self, conn, onboarding):
        """Saving the same user_id twice should replace the row."""
        save_user(conn, "user-1", onboarding)
        updated_onboarding = Onboarding(
            preferred_clusters=["Chocolate"],
            roast_preference=RoastLevel.MEDIUM,
            experience_level=ExperienceLevel.ADVANCED,
        )
        save_user(conn, "user-1", updated_onboarding)
        loaded = load_user(conn, "user-1")
        assert loaded["onboarding"].preferred_clusters == ["Chocolate"]
        assert loaded["onboarding"].roast_preference == RoastLevel.MEDIUM

    def test_update_preferences(self, conn, onboarding):
        save_user(conn, "user-1", onboarding)
        prefs = LearnedPreferences(
            acidity_bias=0.3,
            body_bias=-0.2,
            sweetness_bias=0.5,
            preferred_temp_range=(92.0, 96.0),
            preferred_ratio_range=(15.5, 16.5),
        )
        update_preferences(conn, "user-1", prefs)
        loaded = load_user(conn, "user-1")
        assert loaded["preferences"] is not None
        assert isinstance(loaded["preferences"], LearnedPreferences)
        assert loaded["preferences"].acidity_bias == 0.3
        assert loaded["preferences"].preferred_temp_range == (92.0, 96.0)


class TestBrewRoundTrip:
    def test_save_and_load_brew(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db()
        brew = _brew_record("brew-001", bean, recipe)
        save_brew(conn, "user-1", brew)

        history = load_brew_history(conn, "user-1")
        assert len(history) == 1
        entry = history[0]
        assert entry["brew_id"] == "brew-001"
        assert isinstance(entry["bean_profile"], BeanProfile)
        assert entry["bean_profile"].origin_country == "Ethiopia"
        assert entry["bean_profile"].process == Process.WASHED
        assert isinstance(entry["recipe_used"], Recipe)
        assert entry["recipe_used"].method == BrewMethod.V60
        assert len(entry["recipe_used"].pours) == 3
        assert isinstance(entry["feedback"], Feedback)
        assert entry["feedback"].thumbs_up is True
        assert entry["feedback"].score == 8
        assert entry["feedback"].directional_flags == ["too_sour"]

    def test_load_brew_history_ordered_by_timestamp(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        """Most recent brews should come first."""
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db()
        for i in range(5):
            brew = _brew_record(f"brew-{i:03d}", bean, recipe)
            save_brew(conn, "user-1", brew)

        history = load_brew_history(conn, "user-1")
        assert len(history) == 5
        # Timestamps are generated in-order; DESC means last-saved is first.
        # Since ISO 8601 sorts lexicographically for same-timezone, this holds.
        timestamps = [h["timestamp"] for h in history]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_load_brew_history_respects_limit(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db()
        for i in range(10):
            save_brew(conn, "user-1", _brew_record(f"brew-{i:03d}", bean, recipe))

        history = load_brew_history(conn, "user-1", limit=3)
        assert len(history) == 3

    def test_load_brew_history_empty(self, conn, onboarding):
        save_user(conn, "user-1", onboarding)
        assert load_brew_history(conn, "user-1") == []


class TestGetUserStats:
    @pytest.mark.regression
    def test_stats_computation(self, conn, onboarding, make_recipe_db, make_bean_db):
        """get_user_stats should compute total_brews, avg_score, favorites."""
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean1 = make_bean_db(origin_country="Ethiopia", flavor_clusters=["Floral", "Citrus"])
        bean2 = make_bean_db(origin_country="Colombia", flavor_clusters=["Chocolate", "Nutty"])

        # brew 1: score 8
        brew1 = BrewRecord(
            brew_id="b1",
            timestamp=datetime.now(timezone.utc).isoformat(),
            bean_profile=bean1,
            recipe_used=recipe,
            feedback=Feedback(thumbs_up=True, score=8),
        )
        save_brew(conn, "user-1", brew1)

        # brew 2: score 6
        brew2 = BrewRecord(
            brew_id="b2",
            timestamp=datetime.now(timezone.utc).isoformat(),
            bean_profile=bean2,
            recipe_used=recipe,
            feedback=Feedback(thumbs_up=False, score=6),
        )
        save_brew(conn, "user-1", brew2)

        stats = get_user_stats(conn, "user-1")
        assert stats["total_brews"] == 2
        assert stats["avg_score"] == 7.0
        # Both origins appear once; ordering is by count DESC.
        assert len(stats["favorite_origins"]) >= 1
        assert "favorite_clusters" in stats

    def test_stats_empty_history(self, conn, onboarding):
        save_user(conn, "user-1", onboarding)
        stats = get_user_stats(conn, "user-1")
        assert stats["total_brews"] == 0
        assert stats["avg_score"] == 0.0
        assert stats["favorite_origins"] == []
        assert stats["favorite_clusters"] == []


class TestCountBrews:
    def test_count_brews_empty(self, conn, onboarding):
        save_user(conn, "user-1", onboarding)
        assert count_brews(conn, "user-1") == 0

    def test_count_brews_counts_all_saved(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db()
        for i in range(7):
            save_brew(conn, "user-1", _brew_record(f"b{i}", bean, recipe))
        assert count_brews(conn, "user-1") == 7

    def test_count_brews_is_per_user(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        save_user(conn, "user-1", onboarding)
        save_user(conn, "user-2", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db()
        save_brew(conn, "user-1", _brew_record("b1", bean, recipe))
        assert count_brews(conn, "user-2") == 0


class TestDeleteUserData:
    @pytest.mark.regression
    def test_delete_user_data_removes_everything(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db()
        save_brew(conn, "user-1", _brew_record("b1", bean, recipe))

        delete_user_data(conn, "user-1")

        assert load_user(conn, "user-1") is None
        assert load_brew_history(conn, "user-1") == []

    def test_delete_nonexistent_user_is_safe(self, conn):
        """Deleting a user that doesn't exist must not raise."""
        delete_user_data(conn, "ghost-user")


class TestInMemoryMode:
    def test_memory_db_works(self):
        """get_connection(':memory:') produces a working DB."""
        conn = get_connection(":memory:")
        init_db(conn)
        onboarding = Onboarding(
            preferred_clusters=["Berry"],
            roast_preference=RoastLevel.MEDIUM,
            experience_level=ExperienceLevel.BEGINNER,
        )
        save_user(conn, "demo-user", onboarding)
        loaded = load_user(conn, "demo-user")
        assert loaded is not None
        assert loaded["user_id"] == "demo-user"
        conn.close()


class TestParameterizedQueries:
    @pytest.mark.regression
    def test_no_sql_injection_in_user_id(self, conn, onboarding):
        """Malicious user_id strings must not break queries or inject SQL."""
        malicious_id = "'; DROP TABLE users; --"
        save_user(conn, malicious_id, onboarding)
        loaded = load_user(conn, malicious_id)
        assert loaded is not None
        assert loaded["user_id"] == malicious_id

        # Verify tables still exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [row["name"] for row in tables]
        assert "users" in table_names
        assert "brew_history" in table_names

    def test_no_sql_injection_in_bean_origin(
        self, conn, onboarding, make_recipe_db, make_bean_db
    ):
        save_user(conn, "user-1", onboarding)
        recipe = make_recipe_db()
        bean = make_bean_db(
            origin_country="'; DROP TABLE brew_history; --"
        )
        brew = _brew_record("b-evil", bean, recipe)
        save_brew(conn, "user-1", brew)

        history = load_brew_history(conn, "user-1")
        assert len(history) == 1
        assert history[0]["bean_profile"].origin_country == "'; DROP TABLE brew_history; --"

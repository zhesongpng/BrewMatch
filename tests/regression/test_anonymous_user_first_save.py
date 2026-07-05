"""Regression: an anonymous device user can save a bag/brew on first use.

Bags and brews carry a foreign key to ``users(user_id)``. Anonymous on-device
users (``device-*`` ids) never pass through onboarding or registration, so no
``users`` row exists for them. On PostgreSQL (Supabase, production) the foreign
key is enforced and the first save failed with a 500:

    insert or update on table "coffee_bags" violates foreign key constraint
    "coffee_bags_user_id_fkey"

SQLite leaves foreign keys OFF by default, which is why the unit suite never
caught this. These tests enable ``PRAGMA foreign_keys=ON`` to mimic PostgreSQL,
proving both (a) the bug reproduces without the fix and (b) ``ensure_user_exists``
closes it for the bag and brew write paths.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from src.app.db import (
    create_bag,
    ensure_user_exists,
    get_connection,
    init_db,
    list_active_bags,
    load_brew_history,
    save_brew,
)
from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    CoffeeBag,
    Feedback,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
    create_bag_id,
)

DEVICE_USER = "device-anon-first-save"


@pytest.fixture()
def fk_conn():
    """In-memory SQLite with foreign keys ON, mimicking PostgreSQL."""
    c = get_connection(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    init_db(c)
    yield c
    c.close()


def _make_bean() -> BeanProfile:
    return BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="manual entry",
    )


def _make_bag(bag_id: str) -> CoffeeBag:
    return CoffeeBag(
        bag_id=bag_id,
        roaster="Diag Roaster",
        name="Diag Test Bag",
        bean_profile=_make_bean(),
        bag_size_g=250.0,
        date_opened=datetime.now(timezone.utc).date().isoformat(),
        active=True,
    )


def _make_brew(brew_id: str) -> BrewRecord:
    recipe = Recipe(
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
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Bloom, then pour.",
    )
    return BrewRecord(
        brew_id=brew_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        bean_profile=_make_bean(),
        recipe_used=recipe,
        feedback=Feedback(thumbs_up=True, score=8, directional_flags=[]),
    )


@pytest.mark.regression
def test_bag_save_without_user_row_violates_fk(fk_conn):
    """Guard: the bug reproduces — a bag for a user with no row is rejected."""
    with pytest.raises(sqlite3.IntegrityError):
        create_bag(fk_conn, DEVICE_USER, _make_bag(create_bag_id()))
    fk_conn.rollback()


@pytest.mark.regression
def test_ensure_user_exists_lets_anon_user_save_bag(fk_conn):
    """The fix: after ensure_user_exists, the first bag save succeeds."""
    ensure_user_exists(fk_conn, DEVICE_USER)
    create_bag(fk_conn, DEVICE_USER, _make_bag("bag-anon-1"))

    bags = list_active_bags(fk_conn, DEVICE_USER)
    assert [b.bag_id for b in bags] == ["bag-anon-1"]


@pytest.mark.regression
def test_ensure_user_exists_lets_anon_user_save_brew(fk_conn):
    """Same fix covers the sibling brew-save path (same foreign key)."""
    ensure_user_exists(fk_conn, DEVICE_USER)
    save_brew(fk_conn, DEVICE_USER, _make_brew("brew-anon-1"))

    brews = load_brew_history(fk_conn, DEVICE_USER)
    assert [b["brew_id"] for b in brews] == ["brew-anon-1"]


@pytest.mark.regression
def test_ensure_user_exists_is_idempotent(fk_conn):
    """Calling it twice must not error or duplicate the user row."""
    ensure_user_exists(fk_conn, DEVICE_USER)
    ensure_user_exists(fk_conn, DEVICE_USER)

    rows = fk_conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE user_id = ?", (DEVICE_USER,)
    ).fetchone()
    assert rows["n"] == 1

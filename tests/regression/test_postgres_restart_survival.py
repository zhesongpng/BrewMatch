"""Regression: data survives an app restart on the permanent PostgreSQL backend.

Phase 1 (Goal A / item A4 + C2) made the live app store everything in a
permanent PostgreSQL database (Supabase) so it stops forgetting accounts and
brew history when Streamlit restarts the process. This test is the recorded
proof of that promise.

A Streamlit restart wipes the app's *in-process* state — open connections and
the module-level "schema already initialised" flag — but leaves the external
PostgreSQL database untouched. This test reproduces exactly that:

1.  WRITE through a fresh connection: register an account, complete onboarding,
    save a coffee bag, and log a brew. Commit and close the connection.
2.  SIMULATE THE RESTART: reset the module-level ``_db_initialized`` flag so the
    next connection re-runs startup from scratch, exactly as a restarted process
    would. The PostgreSQL server keeps running with the data on disk.
3.  RECONNECT from scratch and assert the account, onboarding, coffee bag, brew
    history, and brew count are all still there and unchanged.

The database is a **disposable, real PostgreSQL** spun up by ``pgserver`` (it
bundles its own Postgres binary) — never the production Supabase database, so
the test is safe to run on every change and leaves nothing behind. SQLite-on-disk
would survive a restart trivially, which would prove nothing about the hosted
setup; the whole risk lives in the PostgreSQL path, so the test exercises that
path through the app's own ``db.py`` code (``DATABASE_URL`` → ``get_connection``).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

pgserver = pytest.importorskip(
    "pgserver",
    reason="pgserver not installed — restart-survival proof needs an embedded "
    "PostgreSQL (pip install -e '.[dev]')",
)

from src.data_models import (  # noqa: E402
    BeanProfile,
    BrewMethod,
    BrewRecord,
    CoffeeBag,
    ExperienceLevel,
    Feedback,
    Onboarding,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)

TEST_EMAIL = "restart-survivor@brewmatch.test"
TEST_DISPLAY_NAME = "Restart Survivor"
TEST_PASSWORD_HASH = "bcrypt$placeholder-hash-not-verified-here"


# ---------------------------------------------------------------------------
# Disposable real PostgreSQL (bundled by pgserver — no Docker, no system install)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pg_database_url(tmp_path_factory):
    """Spin up a disposable PostgreSQL, point the app at it, tear it down after.

    Sets ``DATABASE_URL`` so the app's ``db.py`` routes through its PostgreSQL
    code path (``active_backend() == 'postgres'``). The server and all its data
    are destroyed when the module's tests finish.
    """
    data_dir = tmp_path_factory.mktemp("pg-restart-survival")
    server = pgserver.get_server(str(data_dir))
    prior_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = server.get_uri()
    try:
        yield os.environ["DATABASE_URL"]
    finally:
        if prior_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prior_url
        server.cleanup()


def _onboarding() -> Onboarding:
    return Onboarding(
        preferred_clusters=["Citrus", "Berry"],
        roast_preference=RoastLevel.LIGHT,
        experience_level=ExperienceLevel.INTERMEDIATE,
    )


def _bean() -> BeanProfile:
    return BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Ethiopian Yirgacheffe",
    )


def _recipe() -> Recipe:
    return Recipe(
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
            PourStep(step=2, time_offset_s=45, water_g=200.0),
        ],
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Bloom, then pour.",
    )


def _brew(brew_id: str, bag_id: str) -> BrewRecord:
    return BrewRecord(
        brew_id=brew_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        bean_profile=_bean(),
        recipe_used=_recipe(),
        feedback=Feedback(thumbs_up=True, score=8),
        bag_id=bag_id,
        actual_dose_g=15.0,
    )


@pytest.mark.regression
@pytest.mark.integration
def test_account_and_history_survive_restart(pg_database_url):
    """Account + onboarding + bag + brews persist across a simulated restart."""
    # Import here so the module-level DATABASE_URL is already set by the fixture.
    import src.app.db as db

    assert db.active_backend() == "postgres", (
        "test must exercise the real PostgreSQL path, not SQLite"
    )

    # --- Phase 1: WRITE through a fresh connection, then close it -----------
    conn = db.get_connection()
    assert db._is_pg(conn), "expected a PostgreSQL connection"
    db.init_db(conn)

    user_id = db.register_user(conn, TEST_EMAIL, TEST_DISPLAY_NAME, TEST_PASSWORD_HASH)
    db.update_onboarding(conn, user_id, _onboarding(), drippers=[BrewMethod.V60])

    bag = CoffeeBag(
        bag_id="bag-1",
        roaster="Test Roaster",
        name="Yirgacheffe",
        bean_profile=_bean(),
        bag_size_g=250.0,
        date_opened=datetime.now(timezone.utc).date().isoformat(),
        active=True,
    )
    db.create_bag(conn, user_id, bag)

    for i in range(3):
        db.save_brew(conn, user_id, _brew(f"brew-{i}", bag_id="bag-1"))

    conn.commit()
    conn.close()

    # --- Phase 2: SIMULATE THE RESTART -------------------------------------
    # A restarted process loses in-memory state. The only in-process state in
    # db.py is the "schema already initialised" flag; reset it so the next
    # connection re-runs startup exactly as a cold process would. The external
    # PostgreSQL server keeps running with the data persisted.
    db._db_initialized = False

    # --- Phase 3: RECONNECT and prove everything is still there -------------
    fresh = db.get_connection()
    assert db._is_pg(fresh), "expected a fresh PostgreSQL connection after restart"

    # Account is reachable by login lookup, with the right identity.
    auth = db.authenticate_user(fresh, TEST_EMAIL)
    assert auth is not None, "account did not survive the restart"
    assert auth["user_id"] == user_id
    assert auth["password_hash"] == TEST_PASSWORD_HASH

    # Onboarding + drippers survived.
    loaded = db.load_user(fresh, user_id)
    assert loaded is not None
    assert loaded["display_name"] == TEST_DISPLAY_NAME
    assert loaded["onboarding"].preferred_clusters == ["Citrus", "Berry"]
    assert loaded["onboarding"].roast_preference == RoastLevel.LIGHT
    assert loaded["drippers"] == [BrewMethod.V60]

    # Saved coffee bag survived.
    bags = db.list_active_bags(fresh, user_id)
    assert len(bags) == 1
    assert bags[0].bag_id == "bag-1"
    assert bags[0].name == "Yirgacheffe"

    # Brew history survived — count and contents both intact.
    assert db.count_brews(fresh, user_id) == 3
    history = db.load_brew_history(fresh, user_id)
    assert len(history) == 3
    assert {h["brew_id"] for h in history} == {"brew-0", "brew-1", "brew-2"}
    assert all(h["actual_dose_g"] == 15.0 for h in history)
    assert all(h["bag_id"] == "bag-1" for h in history)
    # The bag's running-total (grams used) is derived from the saved brews.
    assert db.grams_used_for_bag(fresh, user_id, "bag-1") == pytest.approx(45.0)

    # --- Cleanup so the test is idempotent ---------------------------------
    db.delete_user_data(fresh, user_id)
    fresh.close()

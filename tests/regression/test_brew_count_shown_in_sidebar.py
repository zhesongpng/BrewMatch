"""Regression: the sidebar must honestly show how many brews it learned from.

Phase 1 B3: the sidebar already showed the personalization *phase* name, but
not the brew count it was derived from. Users couldn't see *how much* the app
had learned. The fix stores the brew count in session state
(``personalization_brews``) every time the phase is recomputed, so the sidebar
can render "Learned from N brews".

These tests call ``apply_personalization_phase`` against a fresh, cold-start
session and assert the brew count is stored alongside the phase, matching the
brews actually saved in the database.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.app.db import get_connection, init_db, save_brew, save_user
from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    ExperienceLevel,
    Feedback,
    Onboarding,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)


def _onboarding() -> Onboarding:
    return Onboarding(
        preferred_clusters=["Citrus", "Berry"],
        roast_preference=RoastLevel.LIGHT,
        experience_level=ExperienceLevel.INTERMEDIATE,
    )


def _brew(brew_id: str) -> BrewRecord:
    bean = BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus"],
        source_text="Ethiopian Yirgacheffe",
    )
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
    return BrewRecord(
        brew_id=brew_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        bean_profile=bean,
        recipe_used=recipe,
        feedback=Feedback(thumbs_up=True, score=8),
    )


def _fresh_login_session():
    """Simulate session state right after re-login: count at zero default."""
    from src.app.pages import auth

    class _SS(dict):
        """dict that also supports attribute access, like st.session_state."""

        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

        def __setattr__(self, name, value):
            self[name] = value

    ss = _SS()
    ss["personalization_phase"] = "cold_start"  # init_session_state default
    ss["personalization_brews"] = 0  # init_session_state default
    auth.st.session_state = ss
    return auth, ss


@pytest.mark.regression
class TestBrewCountShownInSidebar:
    """apply_personalization_phase must store the brew count for the sidebar."""

    def _conn(self):
        c = get_connection(":memory:")
        init_db(c)
        save_user(c, "user-1", _onboarding())
        return c

    def test_no_brews_stores_zero_count(self):
        conn = self._conn()
        auth, ss = _fresh_login_session()

        auth.apply_personalization_phase(conn, "user-1")

        assert ss["personalization_brews"] == 0
        conn.close()

    def test_count_matches_saved_brews(self):
        conn = self._conn()
        for i in range(7):
            save_brew(conn, "user-1", _brew(f"b{i}"))

        auth, ss = _fresh_login_session()
        auth.apply_personalization_phase(conn, "user-1")

        assert ss["personalization_brews"] == 7, (
            "sidebar brew count was not recomputed from saved brews — the "
            "'learned from N brews' indicator would show a stale number"
        )
        conn.close()

    def test_count_and_phase_stay_consistent(self):
        conn = self._conn()
        for i in range(12):
            save_brew(conn, "user-1", _brew(f"b{i}"))

        auth, ss = _fresh_login_session()
        auth.apply_personalization_phase(conn, "user-1")

        # 12 brews -> full_hybrid phase AND a count of 12, shown together.
        assert ss["personalization_brews"] == 12
        assert ss["personalization_phase"] == "full_hybrid"
        conn.close()

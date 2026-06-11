"""Regression: personalization phase must survive re-login.

Bug found in the Phase 1 learning-loop work: after a user logged out and
logged back in, the sidebar "Phase" reset to the cold-start default even when
the user had a full brew history. The login path loaded onboarding + drippers
but never recomputed the personalization phase from the user's saved brews, so
``personalization_phase`` stayed at its ``init_session_state`` default.

The fix derives the phase from the saved brew count on every app entry point
(login, cookie session-restore, onboarding) via
``src.app.pages.auth.apply_personalization_phase``. These tests call that
helper against a fresh, cold-start session and assert the phase is recomputed
from the brews actually in the database.
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
    """Simulate session state right after re-login: phase at cold-start default."""
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
    auth.st.session_state = ss
    return auth, ss


@pytest.mark.regression
class TestPhasePersistsOnLogin:
    """apply_personalization_phase must recompute phase from saved brews."""

    def _conn(self):
        c = get_connection(":memory:")
        init_db(c)
        save_user(c, "user-1", _onboarding())
        return c

    def test_no_brews_resolves_to_bean_aware(self):
        conn = self._conn()
        auth, ss = _fresh_login_session()

        auth.apply_personalization_phase(conn, "user-1")

        assert ss["personalization_phase"] == "bean_aware"
        conn.close()

    def test_history_recomputes_phase_not_cold_start(self):
        """The actual bug: 7 saved brews must show as content_based, not cold-start."""
        conn = self._conn()
        for i in range(7):
            save_brew(conn, "user-1", _brew(f"b{i}"))

        auth, ss = _fresh_login_session()
        assert ss["personalization_phase"] == "cold_start"  # pre-condition

        auth.apply_personalization_phase(conn, "user-1")

        assert ss["personalization_phase"] == "content_based", (
            "phase was not recomputed from saved brews on login — the "
            "cold-start-after-login bug has regressed"
        )
        conn.close()

    def test_full_history_resolves_to_full_hybrid(self):
        conn = self._conn()
        for i in range(12):
            save_brew(conn, "user-1", _brew(f"b{i}"))

        auth, ss = _fresh_login_session()
        auth.apply_personalization_phase(conn, "user-1")

        assert ss["personalization_phase"] == "full_hybrid"
        conn.close()

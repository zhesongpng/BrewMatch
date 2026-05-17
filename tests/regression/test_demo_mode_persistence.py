"""Regression tests for demo / Streamlit-Cloud in-memory mode.

Two bugs were found during the Milestone 5 demo walkthrough:

1. Shared-cache in-memory SQLite is destroyed when its last connection
   closes. The app opens and closes connections serially with no overlap,
   so the database was wiped between every operation — the demo account
   was never created and registrations never persisted on Streamlit Cloud.
   Fixed by holding one process-lifetime keep-alive connection per
   in-memory URI in ``src.app.db``.

2. The demo seed never set Alex's drippers, so the showcase account's
   profile/recommend pages displayed no equipment even though Alex's 15
   brews span V60, Kalita Wave, and Origami.

3. The evaluation dashboard read ``models/`` via a bare relative path.
   Streamlit Cloud runs the app from a temp directory, so the dashboard
   resolved no data and showed "Not yet evaluated" for every metric.

4. The sentence-transformers embedding model fails to load on Streamlit
   Cloud with "Cannot copy out of meta tensor; no data!". This left the
   retriever with recipes loaded but no search index, and retrieval
   hard-failed with "Could not retrieve recipes". Retrieval must degrade
   to BM25-only keyword search when the embedding model is unavailable.

5. The optimization comparison showed grind on the bare 1-10 scale while
   the recipe card showed grinder-specific clicks — confusingly
   inconsistent. Both must use the same grinder-aware formatting.
"""

from __future__ import annotations

import os

import pytest

from src.app.db import (
    authenticate_user,
    get_connection,
    init_db,
    load_user,
    register_user,
)
from src.data_models import BrewMethod


@pytest.mark.regression
class TestInMemoryKeepAlive:
    """In-memory shared-cache DB must survive connection close cycles."""

    def test_data_survives_connection_close_cycle(self):
        uri = "file:regr_keepalive_a?mode=memory&cache=shared"

        c1 = get_connection(uri)
        init_db(c1)
        uid = register_user(c1, "keepalive@x.com", "K", "hash")
        c1.close()  # last transient connection closes — pre-fix this wiped the DB

        c2 = get_connection(uri)
        row = authenticate_user(c2, "keepalive@x.com")
        c2.close()

        assert row is not None, (
            "in-memory DB was wiped when the last transient connection "
            "closed — keep-alive connection is not holding it open"
        )
        assert row["user_id"] == uid

    def test_registration_then_separate_read_persists(self):
        uri = "file:regr_keepalive_b?mode=memory&cache=shared"

        c1 = get_connection(uri)
        init_db(c1)
        uid = register_user(c1, "persist@x.com", "P", "hash")
        c1.close()

        c2 = get_connection(uri)
        loaded = load_user(c2, uid)
        c2.close()

        assert loaded is not None
        assert loaded["user_id"] == uid


@pytest.mark.regression
class TestDemoAccountDrippers:
    """The seeded demo account must own all three pour-over drippers."""

    def test_seed_demo_data_for_user_sets_drippers(self):
        from scripts.seed_demo import seed_demo_data_for_user

        uri = "file:regr_demo_drippers?mode=memory&cache=shared"
        conn = get_connection(uri)
        init_db(conn)
        uid = register_user(conn, "demo-regr@x.com", "Demo", "hash")
        seed_demo_data_for_user(conn, uid)

        loaded = load_user(conn, uid)
        conn.close()

        assert loaded is not None
        assert loaded["drippers"] is not None, (
            "demo account has no drippers — profile/recommend pages "
            "would show no equipment for the showcase account"
        )
        assert set(loaded["drippers"]) == {
            BrewMethod.V60,
            BrewMethod.KALITA_WAVE,
            BrewMethod.ORIGAMI,
        }


@pytest.mark.regression
class TestEvaluationDashboardPathResolution:
    """Eval dashboard must resolve models/ from repo root, not the CWD."""

    def test_eval_path_is_absolute_and_cwd_independent(self):
        from src.app.pages.evaluation import _EVALUATION_PATH, _MODELS_DIR

        assert _EVALUATION_PATH.is_absolute(), (
            "evaluation path is relative — resolves against the CWD, which "
            "is a temp dir on Streamlit Cloud, so the dashboard shows no data"
        )
        assert _MODELS_DIR.name == "models"

    def test_eval_data_loads_from_foreign_cwd(self, tmp_path):
        from src.app.pages.evaluation import _load_evaluation_data

        original = os.getcwd()
        try:
            os.chdir(tmp_path)  # simulate Streamlit Cloud's temp working dir
            data = _load_evaluation_data()
        finally:
            os.chdir(original)

        assert data is not None, (
            "evaluation dashboard returned no data when run from a foreign "
            "CWD — path resolution regressed to relative"
        )
        assert "taste_prediction" in data


@pytest.mark.regression
class TestRetrievalDegradesWithoutEmbeddingModel:
    """Recipe retrieval must fall back to BM25 if the embedding model fails."""

    def test_index_and_retrieve_survive_model_failure(self):
        from src.data_models import BeanProfile, Process, RoastLevel
        from src.recipe_retriever.retriever import RecipeRetriever

        r = RecipeRetriever(chroma_persist_dir=None)

        # Reproduce the exact Streamlit Cloud failure.
        def _meta_tensor_failure(*args, **kwargs):
            raise RuntimeError("Cannot copy out of meta tensor; no data!")

        r._get_model = _meta_tensor_failure

        # Indexing must NOT raise and MUST still build the BM25 index.
        r.index_recipes("data/recipes")
        assert r._recipes, "recipes failed to load"
        assert r._bm25 is not None, (
            "BM25 index was not built — a model failure during dense "
            "indexing skipped the sparse index (non-atomic indexing)"
        )

        # Retrieval must return recipes via BM25, not raise RuntimeError.
        bean = BeanProfile(
            origin_country="Ethiopia",
            process=Process.WASHED,
            roast_level=RoastLevel.LIGHT,
            flavor_clusters=["Floral", "Citrus"],
            source_text="jasmine lemon blueberry",
        )
        result = r.retrieve(
            bean,
            {"brew_methods": ["V60", "Kalita Wave", "Origami"]},
            top_k=3,
        )
        assert result.recipes, (
            "retrieval hard-failed with the embedding model unavailable — "
            "BM25-only degradation is not working"
        )


@pytest.mark.regression
class TestGrindDisplayConsistency:
    """Optimization grind display must match the recipe card (grinder-aware)."""

    def _set_grinder(self, grinder_id):
        import streamlit as st
        from src.app.pages import recommend
        from src.data_models import (
            ExperienceLevel,
            Onboarding,
            RoastLevel,
        )

        class _SS(dict):
            pass

        ss = _SS()
        if grinder_id is not None:
            ss["onboarding"] = Onboarding(
                preferred_clusters=["Berry"],
                roast_preference=RoastLevel.LIGHT,
                experience_level=ExperienceLevel.INTERMEDIATE,
                grinder_id=grinder_id,
            )
        recommend.st.session_state = ss
        return recommend

    def test_grinder_clicks_shown_when_configured(self):
        recommend = self._set_grinder("comandante-c40")
        out = recommend._format_grind(5)
        assert "Comandante C40" in out and "clicks" in out, (
            "grind display dropped grinder-specific clicks — optimization "
            "would show a bare /10 inconsistent with the recipe card"
        )
        assert "(5/10)" in out  # scale kept as secondary reference

    def test_continuous_optimizer_value_rounded_to_step(self):
        recommend = self._set_grinder("comandante-c40")
        # Optimizer emits continuous values; must round to a whole step
        # so the grinder mapping (keyed to whole steps) resolves.
        assert recommend._format_grind(7.3).startswith(
            recommend._format_grind(7).split(" ")[0]
        )
        assert "(7/10)" in recommend._format_grind(7.3)

    def test_falls_back_to_scale_without_grinder(self):
        recommend = self._set_grinder(None)
        out = recommend._format_grind(5)
        assert "(5/10)" in out
        assert "clicks" not in out and "—" not in out, (
            "no grinder configured — must fall back to the 1-10 scale "
            "rather than show an empty grind field"
        )

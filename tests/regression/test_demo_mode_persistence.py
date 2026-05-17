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

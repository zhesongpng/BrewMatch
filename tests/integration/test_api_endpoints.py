"""End-to-end tests for the Phase 2 Brain API (api/main.py).

Exercises every endpoint through FastAPI's TestClient against an isolated
local SQLite database. NEVER touches production Supabase: DATABASE_URL is
forced empty before import so the db layer resolves to SQLite, and the file
lives in a per-test temp directory.

Guards the three bugs the 2026-06-25 red team caught:
  1. save_brew omitted the required Feedback.thumbs_up field (422 every call)
  2. /learn called predictor.train(brew_records) — wrong signature; the
     predictor is a global model, never retrained per user
  3. CORS allow_credentials=True + allow_origins="*" (browser-rejected combo)
"""
import os
import tempfile

import pytest

# Force SQLite BEFORE importing the app: load_dotenv(override=False) inside
# api.main must not clobber an empty DATABASE_URL with the production URL.
os.environ["DATABASE_URL"] = ""
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from fastapi.testclient import TestClient  # noqa: E402

import src.app.db as db  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """A TestClient whose db layer points at a throwaway SQLite file.

    Module-scoped because the lifespan loads heavy ML models (~seconds);
    loading once per module keeps the suite fast.
    """
    tmpdir = tempfile.mkdtemp()
    tmpdb = os.path.join(tmpdir, "test_api.db")
    db.get_db_path = lambda: tmpdb
    assert db.active_backend() == "sqlite", "test must not hit production"
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bean():
    return {
        "origin_country": "Ethiopia",
        "process": "washed",
        "roast_level": "light",
        "flavor_clusters": ["Floral", "Citrus"],
        "source_text": "test bean",
    }


@pytest.fixture
def recipe(client, bean):
    r = client.post("/recommend", json={"bean": bean, "top_k": 1})
    assert r.status_code == 200
    recipes = r.json()["recipes"]
    assert recipes, "retriever returned no recipes"
    return recipes[0]["recipe"]


def test_health_reports_all_components_ready(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["retriever_ready"] is True
    assert body["predictor_trained"] is True


def test_recommend_returns_ranked_recipes(client, bean):
    r = client.post("/recommend", json={"bean": bean, "preferences": {"brew_methods": ["V60"]}, "top_k": 3})
    assert r.status_code == 200
    recipes = r.json()["recipes"]
    assert len(recipes) > 0
    assert "recipe" in recipes[0]
    assert "predicted_score" in recipes[0]


def test_recommend_rejects_malformed_bean(client):
    r = client.post("/recommend", json={"bean": {"process": "not_a_process"}, "top_k": 1})
    assert r.status_code == 422


def test_diagnose_ml_path_returns_suggestions(client, bean, recipe):
    r = client.post("/diagnose", json={"bean": bean, "recipe": recipe, "flags": ["too_sour"], "user_id": "u1"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] in ("ml", "rule_based")
    assert "suggestions" in body


def test_diagnose_no_flags_short_circuits(client, bean, recipe):
    r = client.post("/diagnose", json={"bean": bean, "recipe": recipe, "flags": []})
    assert r.status_code == 200
    assert r.json()["mode"] == "no_flags"


def test_save_and_load_brew_round_trip(client, bean, recipe):
    """Regression: save_brew must supply Feedback.thumbs_up."""
    brew = {
        "brew_id": "rt-brew-rt1",
        "timestamp": "2026-06-25T10:00:00+00:00",
        "bean": bean,
        "recipe": recipe,
        "feedback": {"score": 5, "directional_flags": ["too_sour"], "notes": "n"},
        "actual_dose_g": 15.0,
    }
    r = client.post("/brews/rtuser", json=brew)
    assert r.status_code == 200, r.text
    assert r.json()["saved"] is True

    r = client.get("/brews/rtuser")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_save_brew_missing_id_returns_422(client, bean, recipe):
    r = client.post("/brews/rtuser", json={"bean": bean, "recipe": recipe, "feedback": {"thumbs_up": True}})
    assert r.status_code == 422


def test_learn_reports_phase_without_retraining(client, bean, recipe):
    """Regression: /learn must NOT call predictor.train(); it counts brews."""
    user = "learnuser"
    for i in range(6):
        brew = {
            "brew_id": f"ln-{i}",
            "timestamp": "2026-06-25T10:00:00+00:00",
            "bean": bean,
            "recipe": recipe,
            "feedback": {"thumbs_up": True, "score": 8, "directional_flags": [], "notes": ""},
        }
        assert client.post(f"/brews/{user}", json=brew).status_code == 200

    r = client.post(f"/learn/{user}")
    assert r.status_code == 200
    body = r.json()
    assert body["brew_count"] == 6
    assert body["phase"] == "content_based"
    # The endpoint must not advertise a retraining side effect.
    assert "retrained" not in body


def test_learn_accepts_get(client):
    r = client.get("/learn/nobody")
    assert r.status_code == 200
    assert r.json()["phase"] == "bean_aware"


def test_cors_allows_cross_origin_without_credentials():
    """Regression: wildcard origin must not be paired with credentials."""
    from api.main import app as fastapi_app

    cors = next(
        (m for m in fastapi_app.user_middleware if "CORSMiddleware" in str(m.cls)),
        None,
    )
    assert cors is not None
    # allow_credentials must be False while origins is "*".
    assert cors.kwargs.get("allow_credentials") is False

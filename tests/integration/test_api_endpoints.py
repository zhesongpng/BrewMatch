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
    # The "schema created" flag is a process-global keyed on one DB (correct in
    # production). Reset it so the lazy schema-init fires for THIS module's DB
    # even when another test module already initialised against a different file.
    db._db_initialized = False
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


def test_grinders_returns_catalog(client):
    r = client.get("/grinders")
    assert r.status_code == 200
    grinders = r.json()["grinders"]
    # The catalog ships 9 grinders (6 hand, 3 electric).
    assert len(grinders) == 9
    assert {g["type"] for g in grinders} == {"hand", "electric"}

    # Each grinder maps all 10 generic steps to a dial value, keyed by string.
    for g in grinders:
        assert set(g["mapping"].keys()) == {str(i) for i in range(1, 11)}
        assert {"id", "brand", "model", "scale"} <= g.keys()

    # Spot-check a known mapping so a future catalog edit can't silently drift.
    by_id = {g["id"]: g for g in grinders}
    assert by_id["kingrinder-k6"]["mapping"]["7"] == 74
    assert by_id["kingrinder-k6"]["scale"] == "clicks"


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


def test_brews_response_has_history_display_fields(client, bean, recipe):
    """The web History screen reads specific fields off each saved brew. Lock
    them so a backend rename can't silently blank the screen."""
    brew = {
        "brew_id": "hist-fields-1",
        "timestamp": "2026-06-26T08:30:00+00:00",
        "bean": bean,
        "recipe": recipe,
        "feedback": {
            "thumbs_up": True,
            "score": 8,
            "directional_flags": ["too_sour"],
            "notes": "bright",
        },
        "actual_dose_g": 15.0,
    }
    assert client.post("/brews/histuser", json=brew).status_code == 200

    items = client.get("/brews/histuser").json()["brews"]
    item = next(b for b in items if b["brew_id"] == "hist-fields-1")
    # Fields HistoryFlow.tsx / LogBrew round-trip depend on:
    assert item["timestamp"] == "2026-06-26T08:30:00+00:00"
    assert item["recipe"]["method"] and item["recipe"]["source"]
    assert item["bean"]["origin_country"]
    fb = item["feedback"]
    assert fb["thumbs_up"] is True
    assert fb["score"] == 8
    assert fb["directional_flags"] == ["too_sour"]
    assert fb["notes"] == "bright"


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


def _bag_body(**overrides):
    """A valid POST /bags body; override any field per test."""
    body = {
        "roaster": "Onyx",
        "name": "Ethiopia Guji",
        "bag_size_g": 250,
        "origin_country": "Ethiopia",
        "process": "washed",
        "roast_level": "light",
        "flavor_clusters": ["Floral", "Citrus"],
        "region": "Guji",
        "variety": "Heirloom",
        "altitude_min_m": 1800,
        "altitude_max_m": 2000,
    }
    body.update(overrides)
    return body


def test_create_and_list_bag_round_trip(client):
    user = "baguser1"
    created = client.post(f"/bags/{user}", json=_bag_body())
    assert created.status_code == 200, created.text
    bag = created.json()
    assert bag["roaster"] == "Onyx"
    assert bag["name"] == "Ethiopia Guji"
    assert bag["bean"]["origin_country"] == "Ethiopia"
    # Brand-new 250 g bag at a 15 g nominal dose → ~16 brews, nothing used yet.
    assert bag["grams_used"] == 0.0
    assert bag["brews_left"] == 16
    assert bag["bag_id"]

    listed = client.get(f"/bags/{user}").json()
    assert listed["count"] == 1
    assert listed["bags"][0]["bag_id"] == bag["bag_id"]


def test_create_bag_rejects_missing_roaster(client):
    r = client.post("/bags/baguser-bad", json=_bag_body(roaster=""))
    assert r.status_code == 422


def test_create_bag_rejects_bad_process(client):
    r = client.post("/bags/baguser-bad", json=_bag_body(process="not_a_process"))
    assert r.status_code == 422


def test_brews_left_decrements_when_brew_logged_against_bag(client, bean, recipe):
    """A brew that records bag_id + dose must reduce the bag's running-low count."""
    user = "baguser2"
    bag = client.post(f"/bags/{user}", json=_bag_body(bag_size_g=100)).json()
    # 100 g bag → 6 brews at a 15 g nominal dose, before any brew.
    assert bag["brews_left"] == 6

    brew = {
        "brew_id": "bag-brew-1",
        "timestamp": "2026-06-28T09:00:00+00:00",
        "bean": bean,
        "recipe": recipe,
        "feedback": {"thumbs_up": True, "score": 8},
        "bag_id": bag["bag_id"],
        "actual_dose_g": 30.0,
    }
    assert client.post(f"/brews/{user}", json=brew).status_code == 200

    after = client.get(f"/bags/{user}").json()["bags"][0]
    assert after["grams_used"] == 30.0
    # (100 - 30) // 15 = 4 brews left.
    assert after["brews_left"] == 4


def test_finish_bag_removes_it_from_active_list(client):
    user = "baguser3"
    bag = client.post(f"/bags/{user}", json=_bag_body()).json()
    assert client.get(f"/bags/{user}").json()["count"] == 1

    r = client.post(f"/bags/{user}/{bag['bag_id']}/finish")
    assert r.status_code == 200
    assert r.json()["finished"] is True

    assert client.get(f"/bags/{user}").json()["count"] == 0


def test_bags_are_scoped_per_user(client):
    """A bag saved by one user must not appear in another user's list."""
    client.post("/bags/owner-a", json=_bag_body(name="A's coffee"))
    assert client.get("/bags/owner-b").json()["count"] == 0


def test_stats_empty_user_returns_zeroes(client):
    body = client.get("/stats/nobody-stats").json()
    assert body["total_brews"] == 0
    assert body["avg_score"] == 0.0
    assert body["favorite_origins"] == []
    assert body["favorite_clusters"] == []


def test_stats_reflect_logged_brews(client, bean, recipe):
    """The Profile screen reads these fields; lock the shape + aggregation."""
    user = "stats-user"
    for i in range(3):
        brew = {
            "brew_id": f"st-{i}",
            "timestamp": "2026-06-28T10:00:00+00:00",
            "bean": bean,  # Ethiopia / Floral+Citrus
            "recipe": recipe,
            "feedback": {"thumbs_up": True, "score": 8},
        }
        assert client.post(f"/brews/{user}", json=brew).status_code == 200

    s = client.get(f"/stats/{user}").json()
    assert s["total_brews"] == 3
    assert s["avg_score"] == 8.0
    assert "Ethiopia" in s["favorite_origins"]
    assert "Floral" in s["favorite_clusters"]


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

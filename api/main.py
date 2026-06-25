"""BrewMatch Brain API — FastAPI service wrapping the Python ML brain.

Exposes the recommendation, diagnosis, brew-logging, and personalization
functions as HTTP endpoints so the React front-end can call them over the
internet.  The Supabase database is accessed via DATABASE_URL exactly as
the Streamlit app does — no schema or data changes required.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Ensure repo root is importable so `from src.*` works on Render.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Suppress CUDA / tokenizer noise on CPU-only Render instances.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Application state — heavy models initialised once at startup.
# ---------------------------------------------------------------------------

_state: dict[str, Any] = {
    "retriever": None,
    "predictor": None,
    "diagnosis_engine": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy ML models once at process start."""
    _load_models()
    yield


def _load_models() -> None:
    """Initialise retriever, predictor, and diagnosis engine."""
    data_dir = _REPO_ROOT / "data"

    # --- Taste predictor ---
    try:
        from src.taste_predictor.model import TastePredictor
        predictor = TastePredictor()
        try:
            predictor.load()
            logger.info("brain.startup: predictor loaded (trained=%s)", predictor.is_trained)
        except FileNotFoundError:
            logger.warning("brain.startup: no saved predictor — running untrained")
        _state["predictor"] = predictor
    except Exception as exc:
        logger.error("brain.startup: predictor init failed: %s", exc)

    # --- Recipe retriever (chromadb + sentence-transformers) ---
    try:
        from src.recipe_retriever.retriever import RecipeRetriever
        retriever = RecipeRetriever(
            chroma_persist_dir=str(data_dir / "chroma"),
        )
        retriever.index_recipes(str(data_dir / "recipes"))
        _state["retriever"] = retriever
        logger.info("brain.startup: retriever ready")
    except Exception as exc:
        logger.error("brain.startup: retriever init failed: %s", exc)

    # --- Diagnosis engine (only when predictor is trained) ---
    predictor = _state.get("predictor")
    if predictor is not None and predictor.is_trained:
        try:
            from src.diagnosis.engine import DiagnosisEngine
            _state["diagnosis_engine"] = DiagnosisEngine(predictor)
            logger.info("brain.startup: diagnosis engine ready")
        except Exception as exc:
            logger.error("brain.startup: diagnosis engine failed: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BrewMatch Brain API",
    description="ML recommendation and diagnosis service for BrewMatch",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened once the Vercel domain is known
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """A3 — proves the brain is online and answers from real data."""
    retriever = _state.get("retriever")
    predictor = _state.get("predictor")
    return {
        "status": "ok",
        "retriever_ready": retriever is not None,
        "predictor_trained": predictor is not None and predictor.is_trained,
        "diagnosis_engine_ready": _state.get("diagnosis_engine") is not None,
    }


# ---------------------------------------------------------------------------
# Recommend
# ---------------------------------------------------------------------------

@app.post("/recommend")
def recommend(body: dict):
    """Return ranked recipe recommendations for a bean profile.

    Request body:
        bean      : dict  — BeanProfile fields (origin_country, process, roast_level, …)
        preferences: dict  — optional; keys: brew_methods (list[str]), experience_level (str)
        top_k     : int   — how many recipes to return (default 3)
    """
    retriever = _state.get("retriever")
    if retriever is None:
        raise HTTPException(503, "Retriever not ready — brain is still starting up")

    from src.app.utils import dict_to_bean_profile, recipe_to_dict

    try:
        bean_profile = dict_to_bean_profile(body.get("bean", {}))
    except Exception as exc:
        raise HTTPException(422, f"Invalid bean profile: {exc}") from exc

    preferences = body.get("preferences", {"brew_methods": ["V60"]})
    top_k = int(body.get("top_k", 3))

    try:
        result = retriever.retrieve(bean_profile, preferences, top_k=top_k)
    except Exception as exc:
        logger.exception("recommend: retrieval failed")
        raise HTTPException(500, f"Retrieval failed: {exc}") from exc

    predictor = _state.get("predictor")
    recipes_out = []
    for ranked in result.recipes:
        recipe_dict = recipe_to_dict(ranked.recipe)
        predicted_score = None
        if predictor is not None and predictor.is_trained:
            try:
                pred = predictor.predict(bean_profile, ranked.recipe)
                predicted_score = round(pred.predicted_rating, 2)
            except Exception:
                pass
        recipes_out.append({
            "recipe": recipe_dict,
            "rank": ranked.rank,
            "score": ranked.score,
            "predicted_score": predicted_score,
        })

    return {"recipes": recipes_out, "total_candidates": result.total_candidates}


# ---------------------------------------------------------------------------
# Diagnose
# ---------------------------------------------------------------------------

# Rule-based fallback (mirrors diagnosis/engine rule table).
_RULE_DIAGNOSIS: dict[str, dict] = {
    "too_sour": {
        "cause": "Under-extraction",
        "assessment": "Sourness suggests under-extraction — the coffee compounds haven't fully dissolved.",
        "suggestions": [
            {"parameter": "grind_setting", "direction": "finer", "reason": "Increases surface area for better extraction."},
            {"parameter": "water_temp_c",  "direction": "higher (+1-2 °C)", "reason": "Dissolves more flavour compounds."},
            {"parameter": "total_time_s",  "direction": "longer (+15-30 s)", "reason": "Allows more contact time."},
        ],
    },
    "too_bitter": {
        "cause": "Over-extraction",
        "assessment": "Bitterness suggests over-extraction — too many harsh compounds have dissolved.",
        "suggestions": [
            {"parameter": "grind_setting", "direction": "coarser", "reason": "Reduces surface area to slow extraction."},
            {"parameter": "water_temp_c",  "direction": "lower (-1-2 °C)", "reason": "Prevents harsh compounds from dissolving."},
            {"parameter": "total_time_s",  "direction": "shorter (-15-30 s)", "reason": "Limits contact time."},
        ],
    },
    "too_weak": {
        "cause": "Under-extraction or low dose",
        "assessment": "Weak coffee may indicate under-extraction or too little coffee relative to water.",
        "suggestions": [
            {"parameter": "grind_setting", "direction": "finer", "reason": "Increases extraction strength."},
            {"parameter": "dose_g",        "direction": "increase (+0.5-1 g)", "reason": "More coffee means more solubles."},
            {"parameter": "ratio",         "direction": "lower (e.g. 1:15)", "reason": "More concentrated brew."},
        ],
    },
    "too_harsh": {
        "cause": "Channeling or over-extraction",
        "assessment": "Harshness can indicate channeling or over-extraction.",
        "suggestions": [
            {"parameter": "grind_setting", "direction": "coarser", "reason": "Slows extraction of harsh compounds."},
            {"parameter": "water_temp_c",  "direction": "lower (-1-2 °C)", "reason": "Reduces astringent compound extraction."},
        ],
    },
    "astringent": {
        "cause": "Over-extraction",
        "assessment": "Astringency often indicates over-extraction.",
        "suggestions": [
            {"parameter": "grind_setting", "direction": "coarser", "reason": "Slows overall extraction."},
            {"parameter": "water_temp_c",  "direction": "lower (-1-2 °C)", "reason": "Prevents over-dissolving."},
            {"parameter": "total_time_s",  "direction": "shorter (-15-30 s)", "reason": "Limits extraction of astringent compounds."},
        ],
    },
}


@app.post("/diagnose")
def diagnose(body: dict):
    """Diagnose brew issues from directional flags.

    Request body:
        bean   : dict       — BeanProfile fields
        recipe : dict       — Recipe fields
        flags  : list[str]  — e.g. ["too_sour", "too_bitter"]
        user_id: str | None — used by ML engine when available
    """
    from src.app.utils import dict_to_bean_profile, dict_to_recipe

    flags: list[str] = body.get("flags", [])
    if not flags:
        return {"mode": "no_flags", "suggestions": [], "assessments": []}

    # Try ML engine first.
    diagnosis_engine = _state.get("diagnosis_engine")
    if diagnosis_engine is not None:
        try:
            bean = dict_to_bean_profile(body.get("bean", {}))
            recipe = dict_to_recipe(body.get("recipe", {}))
            user_id = body.get("user_id")
            result = diagnosis_engine.diagnose(bean, recipe, flags, user_id=user_id)
            suggestions = [
                {
                    "parameter": s.parameter,
                    "current_value": s.current_value,
                    "suggested_value": s.suggested_value,
                    "reason": s.reason,
                    "confidence": s.confidence,
                }
                for s in result.suggestions
            ]
            return {
                "mode": "ml",
                "overall_assessment": result.overall_assessment,
                "suggestions": suggestions,
            }
        except Exception:
            logger.warning("diagnose: ML engine failed, using rule-based fallback", exc_info=True)

    # Rule-based fallback.
    assessments = []
    seen_params: set[str] = set()
    suggestions = []
    for flag in flags:
        rule = _RULE_DIAGNOSIS.get(flag)
        if rule is None:
            continue
        assessments.append({"flag": flag, "cause": rule["cause"], "assessment": rule["assessment"]})
        for s in rule["suggestions"]:
            if s["parameter"] not in seen_params:
                seen_params.add(s["parameter"])
                suggestions.append(s)

    return {"mode": "rule_based", "assessments": assessments, "suggestions": suggestions}


# ---------------------------------------------------------------------------
# Brews
# ---------------------------------------------------------------------------

@app.post("/brews/{user_id}")
def save_brew(user_id: str, body: dict):
    """Save a brew record for a user.

    Request body mirrors the BrewRecord dataclass fields:
        brew_id   : str
        timestamp : str  (ISO 8601)
        bean      : dict
        recipe    : dict
        feedback  : dict  — {score, directional_flags, notes}
        bag_id    : str | None
        actual_dose_g: float | None
    """
    from src.app.utils import dict_to_bean_profile, dict_to_recipe
    from src.app.db import get_db, save_brew as db_save_brew, ensure_schema
    from src.data_models import BrewRecord, Feedback

    try:
        bean = dict_to_bean_profile(body.get("bean", {}))
        recipe = dict_to_recipe(body.get("recipe", {}))
        fb_raw = body.get("feedback", {})
        feedback = Feedback(
            score=fb_raw.get("score"),
            directional_flags=fb_raw.get("directional_flags", []),
            notes=fb_raw.get("notes", ""),
        )
        brew = BrewRecord(
            brew_id=body["brew_id"],
            timestamp=body["timestamp"],
            bean_profile=bean,
            recipe_used=recipe,
            feedback=feedback,
            bag_id=body.get("bag_id"),
            actual_dose_g=body.get("actual_dose_g"),
        )
    except Exception as exc:
        raise HTTPException(422, f"Invalid brew record: {exc}") from exc

    try:
        with get_db() as conn:
            ensure_schema(conn)
            db_save_brew(conn, user_id, brew)
    except Exception as exc:
        logger.exception("save_brew: DB write failed")
        raise HTTPException(500, f"Failed to save brew: {exc}") from exc

    logger.info("save_brew: user=%s brew=%s", user_id, brew.brew_id)
    return {"saved": True, "brew_id": brew.brew_id}


@app.get("/brews/{user_id}")
def get_brews(user_id: str, limit: int = 50):
    """Return recent brews for a user, newest first."""
    from src.app.db import get_db, load_brew_history, ensure_schema
    from src.app.utils import bean_to_dict, recipe_to_dict
    from dataclasses import asdict

    try:
        with get_db() as conn:
            ensure_schema(conn)
            history = load_brew_history(conn, user_id, limit=limit)
    except Exception as exc:
        logger.exception("get_brews: DB read failed")
        raise HTTPException(500, f"Failed to load brews: {exc}") from exc

    out = []
    for record in history:
        out.append({
            "brew_id": record["brew_id"],
            "timestamp": record["timestamp"],
            "bean": bean_to_dict(record["bean_profile"]),
            "recipe": recipe_to_dict(record["recipe_used"]),
            "feedback": asdict(record["feedback"]),
            "bag_id": record.get("bag_id"),
            "actual_dose_g": record.get("actual_dose_g"),
        })

    return {"brews": out, "count": len(out)}


# ---------------------------------------------------------------------------
# Learn — re-train predictor from a user's brew history
# ---------------------------------------------------------------------------

@app.post("/learn/{user_id}")
def learn(user_id: str):
    """Re-train the taste predictor from a user's brew history.

    Returns the user's updated personalization phase and brew count.
    """
    predictor = _state.get("predictor")
    if predictor is None:
        raise HTTPException(503, "Predictor not initialised")

    from src.app.db import get_db, load_brew_history, count_brews, ensure_schema
    from src.app.utils import dict_to_bean_profile, dict_to_recipe
    from src.personalization.engine import PersonalizationEngine

    try:
        with get_db() as conn:
            ensure_schema(conn)
            brew_count = count_brews(conn, user_id)
            history = load_brew_history(conn, user_id, limit=200)
    except Exception as exc:
        logger.exception("learn: DB read failed")
        raise HTTPException(500, f"DB read failed: {exc}") from exc

    if not history:
        return {"phase": "bean_aware", "brew_count": 0, "retrained": False}

    # Convert DB rows back to BrewRecord objects for the PersonalizationEngine.
    from src.data_models import BrewRecord
    brew_records = []
    for record in history:
        try:
            brew_records.append(BrewRecord(
                brew_id=record["brew_id"],
                timestamp=record["timestamp"],
                bean_profile=record["bean_profile"],
                recipe_used=record["recipe_used"],
                feedback=record["feedback"],
                bag_id=record.get("bag_id"),
                actual_dose_g=record.get("actual_dose_g"),
            ))
        except Exception:
            pass

    # Train predictor on full history.
    retrained = False
    if len(brew_records) >= 5:
        try:
            predictor.train(brew_records)
            predictor.save()
            retrained = True
            # Refresh diagnosis engine with freshly trained predictor.
            from src.diagnosis.engine import DiagnosisEngine
            _state["diagnosis_engine"] = DiagnosisEngine(predictor)
            logger.info("learn: retrained predictor for user=%s brews=%d", user_id, brew_count)
        except Exception as exc:
            logger.warning("learn: training failed: %s", exc)

    # Compute personalization phase.
    if brew_count == 0:
        phase = "bean_aware"
    elif brew_count < 5:
        phase = "directional"
    elif brew_count < 10:
        phase = "content_based"
    else:
        phase = "full_hybrid"

    return {"phase": phase, "brew_count": brew_count, "retrained": retrained}

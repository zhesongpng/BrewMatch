"""BrewMatch — Coffee Troubleshooting Tool.

Diagnosis-first pour-over app: get a recipe, brew, report what went wrong,
get a specific fix. Gets better with every brew.
"""
import logging
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `from src.*` works on Streamlit Cloud.
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Force CPU-only for torch/sentence-transformers on cloud environments.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import streamlit as st

logger = logging.getLogger(__name__)

_PUBLIC_PAGES = {"landing", "auth", "demo"}


def init_session_state():
    """Initialize all session state keys per specs/user-interface.md Section 6.1."""
    defaults = {
        "user_id": None,
        "current_bean": None,
        "current_recipes": None,
        "selected_recipe": None,
        "optimized_params": None,
        "personalization_phase": "cold_start",
        "demo_mode": os.environ.get("BREWMATCH_DEMO_MODE", "false").lower() == "true",
        "page": "landing",
        "models_loaded": False,
        "predictor": None,
        "encoder": None,
        "retriever": None,
        "personalization_engine": None,
        "diagnosis_engine": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def init_cookie_manager():
    """Initialize the cookie manager for session persistence."""
    if "cookie_manager" not in st.session_state:
        try:
            from streamlit_cookies_manager import CookieManager

            st.session_state.cookie_manager = CookieManager(prefix="brewmatch_")
        except Exception:
            logger.debug("Cookie manager unavailable", exc_info=True)


def restore_session():
    """Restore user session from cookie if available."""
    if st.session_state.get("user_id"):
        return

    cm = st.session_state.get("cookie_manager")
    if cm is None:
        return

    try:
        if not cm.ready():
            return
    except Exception:
        return

    try:
        token = cm.get("session_token")
    except Exception:
        return

    if not token:
        return

    try:
        from src.app.auth import restore_session as auth_restore
        from src.app.db import get_db, load_user

        with get_db() as conn:
            user_id = auth_restore(conn, token)

        if not user_id:
            return

        with get_db() as conn:
            user = load_user(conn, user_id)

        if user:
            st.session_state.user_id = user_id
            if user.get("onboarding"):
                st.session_state.onboarding = user["onboarding"]
            if user.get("drippers"):
                st.session_state.drippers = user["drippers"]
    except Exception:
        logger.debug("Session restore failed", exc_info=True)


def load_models():
    """Load ML models on startup. Set session_state.models_loaded = True on success."""
    if st.session_state.models_loaded:
        return

    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent.parent

    try:
        from src.taste_predictor.encoder import FeatureEncoder
        from src.taste_predictor.model import TastePredictor

        # Load predictor
        predictor = TastePredictor()
        try:
            predictor.load()
            st.session_state.predictor = predictor
        except FileNotFoundError:
            logger.warning("Model file not found — predictor will run untrained")
            st.session_state.predictor = predictor
        except Exception as exc:
            logger.error("Failed to load predictor: %s", exc)
            st.session_state.predictor = predictor

        # FeatureEncoder is stateless, just instantiate
        st.session_state.encoder = FeatureEncoder()

        # Initialize retriever (loads recipes + ChromaDB)
        try:
            from src.recipe_retriever.retriever import RecipeRetriever

            retriever = RecipeRetriever(
                chroma_persist_dir=str(repo_root / "data" / "chroma"),
            )
            try:
                retriever.index_recipes(str(repo_root / "data" / "recipes"))
            except FileNotFoundError:
                logger.warning("Recipe directory not found — retriever has no recipes")
            except Exception as idx_exc:
                logger.warning("Failed to index recipes: %s", idx_exc)
            st.session_state.retriever = retriever
        except Exception as exc:
            logger.error("Failed to initialize retriever: %s", exc)

        # Initialize diagnosis engine
        if predictor.is_trained:
            from src.diagnosis.engine import DiagnosisEngine

            st.session_state.diagnosis_engine = DiagnosisEngine(predictor)

        st.session_state.models_loaded = True
        logger.info("Models loaded successfully")
    except Exception as exc:
        logger.error("Failed to load models: %s", exc)
        st.session_state.models_loaded = False


def _handle_sidebar_logout():
    """Handle logout from the sidebar."""
    from src.app.auth import logout as auth_logout
    from src.app.db import get_db

    cm = st.session_state.get("cookie_manager")
    token = None
    if cm is not None:
        try:
            token = cm.get("session_token")
            cm.delete("session_token")
        except Exception:
            pass

    if token:
        with get_db() as conn:
            auth_logout(conn, token)

    for key in ["user_id", "onboarding", "drippers", "personalization_phase"]:
        st.session_state.pop(key, None)

    st.session_state.page = "landing"
    st.rerun()


def render_sidebar():
    """Render sidebar with navigation and user info."""
    with st.sidebar:
        st.markdown("### :coffee: BrewMatch")
        st.markdown("---")

        # Navigation
        if st.button("Home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

        st.caption("Brew")
        if st.button("Describe Beans", use_container_width=True):
            st.session_state.page = "bean_input"
            st.rerun()
        if st.button("Recipes", use_container_width=True):
            st.session_state.page = "recommend"
            st.rerun()
        if st.button("Brew Session", use_container_width=True):
            st.session_state.page = "brew_session"
            st.rerun()

        st.markdown("---")
        st.caption("Insights")
        if st.button("History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()
        if st.button("Diagnosis", use_container_width=True):
            st.session_state.page = "diagnosis"
            st.rerun()

        st.markdown("---")
        st.caption("More")
        if st.button("Demo Mode", use_container_width=True):
            st.session_state.demo_mode = True
            st.session_state.page = "demo"
            st.rerun()
        if st.button("Evaluation", use_container_width=True):
            st.session_state.page = "evaluation"
            st.rerun()

        # User info section
        st.markdown("---")
        if st.session_state.user_id:
            phase = st.session_state.personalization_phase or "cold_start"
            phase_label = phase.replace("_", " ").title()
            st.markdown(f"**Phase:** {phase_label}")
            if st.button("Profile", use_container_width=True):
                st.session_state.page = "profile"
                st.rerun()
            if st.button("Sign Out", use_container_width=True):
                _handle_sidebar_logout()
        else:
            if st.button("Sign In", use_container_width=True):
                st.session_state.page = "auth"
                st.rerun()

        if st.session_state.demo_mode:
            st.markdown("---")
            st.markdown(":orange[Demonstration Mode]")


_DEMO_EMAIL = "demo@brewmatch.com"
_DEMO_PASSWORD = "brewmatch"
_DEMO_DISPLAY_NAME = "Alex (Demo)"


def _ensure_demo_account():
    """Create the demo account and seed Alex's data if it doesn't exist. Idempotent."""
    try:
        from src.app.auth import hash_password
        from src.app.db import authenticate_user, get_connection, register_user

        conn = get_connection()
        existing = authenticate_user(conn, _DEMO_EMAIL)
        if existing is not None:
            conn.close()
            return

        pw_hash = hash_password(_DEMO_PASSWORD)
        user_id = register_user(conn, _DEMO_EMAIL, _DEMO_DISPLAY_NAME, pw_hash)

        # Seed Alex's onboarding, preferences, and brew history
        try:
            from scripts.seed_demo import seed_demo_data_for_user

            seed_demo_data_for_user(conn, user_id)
        except Exception:
            logger.debug("Could not seed demo data for %s", user_id, exc_info=True)

        conn.close()
        logger.info("Demo account created: %s (user_id=%s)", _DEMO_EMAIL, user_id)
    except Exception:
        logger.debug("Could not create demo account", exc_info=True)


def main():
    st.set_page_config(
        page_title="BrewMatch",
        page_icon="☕",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()
    init_cookie_manager()
    restore_session()
    load_models()

    # Initialize DB schema once at startup.
    try:
        from src.app.db import get_connection, init_db

        conn = get_connection()
        init_db(conn)
        conn.close()
    except Exception as exc:
        logger.error("Failed to initialize database: %s", exc)

    # Ensure the demo account exists.
    _ensure_demo_account()

    render_sidebar()

    # Auth gate: redirect to auth if not logged in and not on a public page.
    page = st.session_state.get("page", "landing")
    if page not in _PUBLIC_PAGES and not st.session_state.get("user_id"):
        st.session_state.page = "auth"
        st.rerun()

    # Page routing
    page_map = {
        "landing": "src.app.pages.landing",
        "auth": "src.app.pages.auth",
        "onboarding": "src.app.pages.onboarding",
        "bean_input": "src.app.pages.bean_input",
        "recommend": "src.app.pages.recommend",
        "brew_session": "src.app.pages.brew_session",
        "history": "src.app.pages.history",
        "diagnosis": "src.app.pages.diagnosis",
        "demo": "src.app.pages.demo",
        "evaluation": "src.app.pages.evaluation",
        "profile": "src.app.pages.profile",
    }

    module_name = page_map.get(page, "src.app.pages.landing")
    try:
        import importlib

        page_module = importlib.import_module(module_name)
        page_module.render()
    except Exception as exc:
        st.error("Something went wrong. Please try refreshing the page.")
        logger.exception("Page render failed for %s", page)


if __name__ == "__main__":
    main()

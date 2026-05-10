"""BrewMatch — Coffee Troubleshooting Tool.

Diagnosis-first pour-over app: get a recipe, brew, report what went wrong,
get a specific fix. Gets better with every brew.
"""
import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)


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


def load_models():
    """Load ML models on startup. Set session_state.models_loaded = True on success."""
    if st.session_state.models_loaded:
        return

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
                chroma_persist_dir="data/chroma",
            )
            try:
                retriever.index_recipes("data/recipes")
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


def render_sidebar():
    """Render sidebar with navigation and user info."""
    with st.sidebar:
        st.markdown("### BrewMatch")
        st.markdown("---")

        # Navigation
        if st.button("Home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

        st.markdown("**New Brew**")
        if st.button("Bean Input", use_container_width=True):
            st.session_state.page = "bean_input"
            st.rerun()
        if st.button("Recommend", use_container_width=True):
            st.session_state.page = "recommend"
            st.rerun()
        if st.button("Brew", use_container_width=True):
            st.session_state.page = "brew_session"
            st.rerun()

        st.markdown("---")
        if st.button("History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()
        if st.button("Diagnosis", use_container_width=True):
            st.session_state.page = "diagnosis"
            st.rerun()

        st.markdown("---")
        if st.button("Demo Mode", use_container_width=True):
            st.session_state.demo_mode = True
            st.session_state.page = "demo"
            st.rerun()
        if st.button("Evaluation", use_container_width=True):
            st.session_state.page = "evaluation"
            st.rerun()

        # User info section
        st.markdown("---")
        st.markdown("**User Info**")
        if st.session_state.user_id:
            phase = st.session_state.personalization_phase or "cold_start"
            st.markdown(f"Phase: {phase.replace('_', ' ').title()}")
        else:
            st.markdown("Not signed in")

        if st.session_state.demo_mode:
            st.markdown("---")
            st.markdown(":orange[Demonstration Mode]")


def main():
    st.set_page_config(
        page_title="BrewMatch",
        page_icon="☕",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()
    load_models()

    # Initialize DB schema once at startup.
    try:
        from src.app.db import get_connection, init_db

        conn = get_connection()
        init_db(conn)
        conn.close()
    except Exception as exc:
        logger.error("Failed to initialize database: %s", exc)
    render_sidebar()

    # Page routing
    page = st.session_state.get("page", "landing")

    page_map = {
        "landing": "src.app.pages.landing",
        "onboarding": "src.app.pages.onboarding",
        "bean_input": "src.app.pages.bean_input",
        "recommend": "src.app.pages.recommend",
        "brew_session": "src.app.pages.brew_session",
        "history": "src.app.pages.history",
        "diagnosis": "src.app.pages.diagnosis",
        "demo": "src.app.pages.demo",
        "evaluation": "src.app.pages.evaluation",
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

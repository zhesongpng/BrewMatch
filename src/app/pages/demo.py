"""Page: Demo Mode. See specs/user-interface.md Section 4.8.

Pre-seeded 'Alex' user for live demonstration of the BrewMatch diagnosis
workflow. Alex is an intermediate pour-over enthusiast with learned
preferences that the personalization engine can surface.
"""
import logging
import os

import streamlit as st

logger = logging.getLogger(__name__)

from src.data_models import (
    ExperienceLevel,
    LearnedPreferences,
    Onboarding,
    RoastLevel,
)

# ---------------------------------------------------------------------------
# Alex's static profile
# ---------------------------------------------------------------------------

ALEX_USER_ID = "alex-demo"

ALEX_ONBOARDING = Onboarding(
    preferred_clusters=["Berry", "Citrus", "Floral"],
    roast_preference=RoastLevel.LIGHT,
    experience_level=ExperienceLevel.INTERMEDIATE,
)

ALEX_PREFERENCES = LearnedPreferences(
    acidity_bias=0.3,
    body_bias=-0.1,
    sweetness_bias=0.2,
    preferred_temp_range=(91.0, 95.0),
    preferred_ratio_range=(15.0, 16.5),
)

# Summary stats shown on the intro card (representative demo data).
ALEX_DEMO_STATS = {
    "total_brews": 15,
    "avg_rating": 7.2,
    "personalization_phase": "Full Hybrid",
}


def _clear_demo_session():
    """Remove all Alex-related keys from session state."""
    keys_to_remove = [
        "user_id",
        "onboarding",
        "current_bean",
        "current_recipes",
        "selected_recipe",
        "optimized_params",
        "personalization_phase",
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)


def _render_profile_chart():
    """Render a horizontal bar chart of Alex's learned preference biases."""
    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        st.info("Install altair and pandas to see preference charts.")
        return

    data = pd.DataFrame({
        "Bias": ["Acidity", "Body", "Sweetness"],
        "Value": [
            ALEX_PREFERENCES.acidity_bias,
            ALEX_PREFERENCES.body_bias,
            ALEX_PREFERENCES.sweetness_bias,
        ],
    })

    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            y=alt.Y("Bias:N", sort=["Acidity", "Body", "Sweetness"]),
            x=alt.X("Value:Q", scale=alt.Scale(domain=[-1, 1]), title="Bias (-1 to +1)"),
            color=alt.condition(
                alt.datum.Value > 0,
                alt.value("#2196F3"),
                alt.value("#FF7043"),
            ),
        )
        .properties(title="Learned Taste Biases", width=400, height=150)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_taste_journey(brew_history):
    """Render a line chart of rating vs brew number."""
    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        st.info("Install altair and pandas to see taste journey chart.")
        return

    ratings = []
    for i, brew in enumerate(brew_history, start=1):
        feedback = brew.get("feedback") if isinstance(brew, dict) else brew.feedback
        score = feedback.score if hasattr(feedback, "score") else None
        if score is not None:
            ratings.append({"Brew #": i, "Rating": score})

    if not ratings:
        return

    df = pd.DataFrame(ratings)
    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Brew #:N", title="Brew Number"),
            y=alt.Y("Rating:Q", scale=alt.Scale(domain=(1, 10)), title="Rating"),
        )
        .properties(title="Taste Journey", width=500, height=250)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_parameter_evolution(brew_history):
    """Render a dual-axis chart of temperature and grind over time."""
    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        return

    temps = []
    grinds = []
    for i, brew in enumerate(brew_history, start=1):
        recipe = brew.get("recipe_used") if isinstance(brew, dict) else brew.recipe_used
        if recipe is not None:
            temps.append({"Brew #": i, "Temperature (C)": recipe.water_temp_c})
            grinds.append({"Brew #": i, "Grind Setting": recipe.grind_setting})

    if not temps:
        return

    temp_df = pd.DataFrame(temps)
    grind_df = pd.DataFrame(grinds)

    temp_chart = (
        alt.Chart(temp_df)
        .mark_line(point=True, color="#E53935")
        .encode(
            x=alt.X("Brew #:N", title="Brew Number"),
            y=alt.Y("Temperature (C):Q", scale=alt.Scale(domain=(85, 100)),
                     title="Water Temperature (C)"),
        )
        .properties(width=500, height=200)
    )

    grind_chart = (
        alt.Chart(grind_df)
        .mark_line(point=True, color="#43A047")
        .encode(
            x=alt.X("Brew #:N"),
            y=alt.Y("Grind Setting:Q", scale=alt.Scale(domain=(1, 10)),
                     title="Grind Setting (1-10)"),
        )
        .properties(width=500, height=200)
    )

    st.altair_chart(temp_chart, use_container_width=True)
    st.altair_chart(grind_chart, use_container_width=True)


def render():
    """Render the Demo Mode page."""
    # Honor environment variable.
    if os.environ.get("BREWMATCH_DEMO_MODE", "").lower() == "true":
        st.session_state.demo_mode = True

    st.title("Demo: Meet Alex")
    st.caption("Explore a pre-built profile with 15 brews of personalization history.")
    st.markdown("---")

    # --- Intro card ---
    st.markdown(
        "**Alex** is an intermediate pour-over enthusiast who prefers light roasts "
        "and bright, fruity cups. After 15 brews, the personalization engine has "
        "learned Alex's taste profile and moved into Full Hybrid phase."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Brews", ALEX_DEMO_STATS["total_brews"])
    with col2:
        st.metric("Average Rating", ALEX_DEMO_STATS["avg_rating"])
    with col3:
        st.metric("Phase", ALEX_DEMO_STATS["personalization_phase"])

    st.markdown("---")

    # --- Action buttons ---
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Explore Alex's Profile", use_container_width=True):
            st.session_state.show_alex_profile = True

    with col_b:
        if st.button("Start Brewing", use_container_width=True):
            st.session_state.page = "bean_input"
            st.rerun()

    # --- Exit demo mode ---
    st.markdown("---")
    if st.button("Sign Out of Demo", use_container_width=True):
        _clear_demo_session()
        st.session_state.show_alex_profile = False
        st.session_state.page = "landing"
        st.rerun()

    # --- Expanded profile ---
    if st.session_state.get("show_alex_profile"):
        st.markdown("### Alex's Full Profile")
        st.markdown(
            f"- **Experience**: {ALEX_ONBOARDING.experience_level.value.title()}\n"
            f"- **Roast Preference**: {ALEX_ONBOARDING.roast_preference.value.title()}\n"
            f"- **Favorite Clusters**: {', '.join(ALEX_ONBOARDING.preferred_clusters)}\n"
            f"- **Preferred Temp Range**: "
            f"{ALEX_PREFERENCES.preferred_temp_range[0]}C - "
            f"{ALEX_PREFERENCES.preferred_temp_range[1]}C\n"
            f"- **Preferred Ratio Range**: "
            f"1:{ALEX_PREFERENCES.preferred_ratio_range[0]} - "
            f"1:{ALEX_PREFERENCES.preferred_ratio_range[1]}"
        )
        _render_profile_chart()

    # --- Brew history charts ---
    st.markdown("---")
    st.markdown("### Brew History")

    brew_history = []
    try:
        from src.app.db import get_db, load_brew_history

        with get_db() as conn:
            brew_history = load_brew_history(conn, ALEX_USER_ID)
            if not brew_history:
                from scripts.seed_demo import seed_demo_data

                seed_demo_data(conn)
                brew_history = load_brew_history(conn, ALEX_USER_ID)
    except Exception:
        logger.debug("Could not load demo brew history", exc_info=True)
        brew_history = []

    if brew_history:
        _render_taste_journey(brew_history)
        _render_parameter_evolution(brew_history)
    else:
        st.info(
            "Demo data will be populated when the demo seed script runs. "
            "Charts will appear here showing Alex's taste journey and "
            "parameter evolution over brews."
        )

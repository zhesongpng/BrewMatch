"""Page: Brewing History. See specs/user-interface.md Section 4.6.

Displays brew history, learned taste preferences, user stats, and
parameter trend charts using Altair.
"""
import logging

import streamlit as st

from src.app.utils import escape_markdown
from src.grinder_catalog import get_grinder_display

logger = logging.getLogger(__name__)


def render():
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.warning("Please sign in to view your brew history.")
        if st.button("Go to Home"):
            st.session_state.page = "landing"
            st.rerun()
        return

    st.title("Brew History")
    st.caption("Your journey to a better cup, one brew at a time.")

    _render_stats(user_id)
    _render_taste_preferences()
    _render_brew_list(user_id)
    _render_trend_charts(user_id)


def _render_stats(user_id: str):
    """Display aggregate user statistics."""
    try:
        from src.app.db import get_db, get_user_stats

        with get_db() as conn:
            stats = get_user_stats(conn, user_id)
    except Exception as exc:
        st.error("Could not load stats. Please try again.")
        logger.debug("Stats load failed", exc_info=True)
        return

    phase = st.session_state.get("personalization_phase", "bean_aware")
    phase_display = phase.replace("_", " ").title()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Brews", stats["total_brews"])
    with col2:
        avg = stats["avg_score"]
        st.metric("Avg Rating", f"{avg:.1f}" if avg > 0 else "N/A")
    with col3:
        st.metric("Phase", phase_display)

    # Favorite origins and clusters.
    origins = stats.get("favorite_origins", [])
    clusters = stats.get("favorite_clusters", [])

    if origins:
        st.markdown("**Favorite Origins:** " + "  ".join(
            f"`{o}`" for o in origins
        ))
    if clusters:
        st.markdown("**Favorite Clusters:** " + "  ".join(
            f"`{c}`" for c in clusters
        ))


def _render_taste_preferences():
    """Visualize learned taste preferences as a bar chart."""
    pe = st.session_state.get("personalization_engine")
    if pe is None:
        st.info("Keep brewing to build your taste profile!")
        return

    profile = pe.get_profile()
    learned = profile.learned_preferences

    if learned is None:
        st.info("Keep brewing to build your taste profile!")
        return

    st.subheader("Taste Preferences")

    try:
        _render_preference_chart(learned)
    except Exception as exc:
        # Text fallback if altair is unavailable or chart fails.
        logger.debug("Chart fallback: %s", exc)
        st.markdown(
            f"- Acidity bias: {learned.acidity_bias:+.2f}\n"
            f"- Body bias: {learned.body_bias:+.2f}\n"
            f"- Sweetness bias: {learned.sweetness_bias:+.2f}"
        )


def _render_preference_chart(learned):
    """Render an Altair bar chart of learned preference biases."""
    import pandas as pd

    try:
        import altair as alt
    except ImportError:
        st.markdown(
            f"- Acidity bias: {learned.acidity_bias:+.2f}\n"
            f"- Body bias: {learned.body_bias:+.2f}\n"
            f"- Sweetness bias: {learned.sweetness_bias:+.2f}"
        )
        return

    data = pd.DataFrame({
        "Dimension": ["Acidity", "Body", "Sweetness"],
        "Bias": [learned.acidity_bias, learned.body_bias, learned.sweetness_bias],
    })

    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("Bias:Q", scale=alt.Scale(domain=[-1, 1])),
            y=alt.Y("Dimension:N", sort=None),
            color=alt.condition(
                alt.datum.Bias > 0,
                alt.value("#2ecc71"),
                alt.value("#e74c3c"),
            ),
            tooltip=["Dimension", "Bias"],
        )
        .properties(width=400, height=150, title="Learned Taste Biases")
    )

    st.altair_chart(chart, use_container_width=True)


def _render_brew_list(user_id: str):
    """Display recent brews in reverse chronological order."""
    st.subheader("Recent Brews")

    try:
        from src.app.db import get_db, load_brew_history

        with get_db() as conn:
            history = load_brew_history(conn, user_id)
    except Exception as exc:
        st.error("Could not load brew history. Please try again.")
        logger.debug("Brew history load failed", exc_info=True)
        return

    if not history:
        st.info("No brews recorded yet. Start your first brew!")
        return

    # Brew method filter.
    all_methods = sorted({r["recipe_used"].method.value for r in history})
    filter_options = ["All Methods"] + all_methods
    selected_method = st.selectbox("Filter by method", filter_options, key="history_method_filter")

    if selected_method != "All Methods":
        history = [r for r in history if r["recipe_used"].method.value == selected_method]

    if not history:
        st.info(f"No brews found for {selected_method}.")
        return

    total = len(history)
    for idx, record in enumerate(history):
        brew_num = total - idx
        feedback = record["feedback"]
        recipe = record["recipe_used"]
        bean = record["bean_profile"]

        thumb = "thumbs up" if feedback.thumbs_up else "thumbs down"
        score_str = f" | Score: {feedback.score}" if feedback.score is not None else ""
        flags = feedback.directional_flags or []
        flag_str = " | ".join(f.replace("_", " ").title() for f in flags) if flags else ""

        with st.expander(
            f"Brew #{brew_num} -- {bean.origin_country} -- {thumb}{score_str}",
            expanded=(idx == 0),
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Recipe:** {recipe.recipe_id.replace('-', ' ').title()}")
                st.markdown(f"**Method:** {recipe.method.value}")
                st.markdown(f"**Dose:** {recipe.dose_g:.1f} g  |  **Ratio:** 1:{recipe.ratio:.2f}")
            with col2:
                st.markdown(f"**Water Temp:** {recipe.water_temp_c:.0f} C")
                grinder_id = getattr(st.session_state.get("onboarding"), "grinder_id", None)
                grinder_display = get_grinder_display(grinder_id, recipe.grind_setting)
                if grinder_display:
                    st.markdown(f"**Grind:** {recipe.grind_setting}/10 — {grinder_display}")
                else:
                    st.markdown(f"**Grind:** {recipe.grind_setting}/10")
                st.markdown(f"**Bloom:** {recipe.bloom_time_s} s  |  **Total:** {recipe.total_time_s} s")

            if flag_str:
                st.warning(f"Flags: {flag_str}")
            if feedback.notes:
                st.markdown(f"**Notes:** {escape_markdown(feedback.notes)}")

            ts = record.get("timestamp", "")
            if ts:
                st.caption(_format_timestamp(ts))


def _render_trend_charts(user_id: str):
    """Render parameter trend charts when enough data exists (3+ brews)."""
    try:
        from src.app.db import get_db, load_brew_history

        with get_db() as conn:
            history = load_brew_history(conn, user_id)
    except Exception:
        logger.debug("Could not load brew history for trend charts", exc_info=True)
        return

    if len(history) < 3:
        return

    st.subheader("Parameter Trends")

    try:
        import altair as alt
        import pandas as pd
    except ImportError:
        logger.debug("Altair not available for trend charts")
        return

    # Build chart data in chronological order (history is newest-first).
    records = list(reversed(history))
    data = pd.DataFrame({
        "Brew #": list(range(1, len(records) + 1)),
        "Temperature (C)": [r["recipe_used"].water_temp_c for r in records],
        "Grind Setting": [float(r["recipe_used"].grind_setting) for r in records],
        "Ratio": [r["recipe_used"].ratio for r in records],
        "Date": [_format_timestamp(r["timestamp"]) for r in records],
    })

    chart_specs = [
        ("Temperature (C)", "#e74c3c"),
        ("Grind Setting", "#3498db"),
        ("Ratio", "#2ecc71"),
    ]

    cols = st.columns(3)
    for col, (field, color) in zip(cols, chart_specs):
        with col:
            line = (
                alt.Chart(data)
                .mark_line(point=True, color=color)
                .encode(
                    x=alt.X("Brew #:N", title="Brew"),
                    y=alt.Y(f"{field}:Q"),
                    tooltip=["Brew #", field, "Date"],
                )
                .properties(height=200, title=field)
            )
            st.altair_chart(line, use_container_width=True)


def _format_timestamp(ts: str) -> str:
    """Format an ISO timestamp into a human-readable date string."""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts

"""Page: Brew Session. See specs/user-interface.md Section 4.5.

Step-by-step brewing instructions with timer, feedback collection,
and brew record persistence.
"""
import uuid
from datetime import datetime, timezone

import streamlit as st

from src.app.db import save_brew
from src.app.utils import dict_to_bean_profile, dict_to_recipe, escape_markdown
from src.data_models import (
    DIRECTIONAL_FLAGS,
    BeanProfile,
    BrewRecord,
    Feedback,
    Process,
    Recipe,
    RoastLevel,
)

# Human-readable labels for directional flags.
_FLAG_LABELS = {
    "too_sour": "Too sour",
    "too_bitter": "Too bitter",
    "too_weak": "Too weak",
    "too_harsh": "Too harsh",
    "astringent": "Astringent",
}


def render():
    recipe_raw = st.session_state.get("selected_recipe")
    if recipe_raw is None:
        st.warning("No recipe selected. Please choose a recipe first.")
        if st.button("Go to Recipes"):
            st.session_state.page = "recommend"
            st.rerun()
        return

    recipe = dict_to_recipe(recipe_raw)

    _render_recipe_header(recipe)
    _render_pour_steps(recipe)
    _render_summary_bar(recipe)
    _render_timer(recipe)

    # Feedback section only appears after marking the brew complete.
    if st.session_state.get("brew_completed", False):
        _render_feedback_section(recipe)
    else:
        st.markdown("---")
        if st.button("Mark Brew Complete", type="primary", use_container_width=True):
            st.session_state.brew_completed = True
            st.rerun()


def _render_recipe_header(recipe: Recipe):
    name = recipe.recipe_id.replace("-", " ").title()
    st.title(name)
    st.caption(
        f"{recipe.method.value} via {recipe.source}"
    )


def _render_pour_steps(recipe: Recipe):
    st.subheader("Pour Steps")
    for pour in recipe.pours:
        minutes = pour.time_offset_s // 60
        seconds = pour.time_offset_s % 60
        time_label = f"{minutes}:{seconds:02d}"
        st.markdown(
            f"**Pour {pour.step}** — "
            f"Add {pour.water_g:.0f} g at {time_label}"
        )
    if recipe.instructions:
        st.info(escape_markdown(recipe.instructions))


def _render_summary_bar(recipe: Recipe):
    st.subheader("Recipe Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Dose", f"{recipe.dose_g:.1f} g")
        st.metric("Grind", f"{recipe.grind_setting}")
    with col2:
        st.metric("Ratio", f"1:{recipe.ratio:.1f}")
        st.metric("Bloom", f"{recipe.bloom_time_s} s")
    with col3:
        st.metric("Water Temp", f"{recipe.water_temp_c:.0f} C")
        st.metric("Total Time", _format_seconds(recipe.total_time_s))


def _render_timer(recipe: Recipe):
    st.subheader("Timer")
    timer_placeholder = st.empty()
    timer_placeholder.info(
        f"Target brew time: **{_format_seconds(recipe.total_time_s)}**"
    )


def _render_feedback_section(recipe: Recipe):
    st.markdown("---")
    st.subheader("How did it taste?")

    # Thumbs up / down toggle.
    if "feedback_thumbs_up" not in st.session_state:
        st.session_state.feedback_thumbs_up = True
    col_thumbs1, col_thumbs2 = st.columns(2)
    with col_thumbs1:
        if st.button(
            "Tasty!",
            type="primary" if st.session_state.feedback_thumbs_up else "secondary",
            use_container_width=True,
        ):
            st.session_state.feedback_thumbs_up = True
            st.rerun()
    with col_thumbs2:
        if st.button(
            "Not Great",
            type="primary" if not st.session_state.feedback_thumbs_up else "secondary",
            use_container_width=True,
        ):
            st.session_state.feedback_thumbs_up = False
            st.rerun()

    # Optional rating slider (1-10).
    score = st.slider("Rating", min_value=1, max_value=10, value=7,
                       help="Rate your brew from 1 to 10.")

    # Directional flags.
    st.markdown("**Did you notice any of these issues?** (select all that apply)")
    selected_flags = []
    flag_cols = st.columns(len(DIRECTIONAL_FLAGS))
    for idx, flag_key in enumerate(DIRECTIONAL_FLAGS):
        with flag_cols[idx]:
            if st.checkbox(_FLAG_LABELS.get(flag_key, flag_key), key=f"flag_{flag_key}"):
                selected_flags.append(flag_key)

    # Optional notes.
    notes = st.text_area("Notes", placeholder="Any observations about this brew...",
                         height=80)

    # Submit.
    if st.button("Submit Feedback", type="primary", use_container_width=True):
        _submit_feedback(recipe, score, selected_flags, notes)


def _submit_feedback(recipe: Recipe, score: int, flags: list[str], notes: str):
    bean = st.session_state.get("current_bean")
    if bean is None:
        bean = _fallback_bean_from_recipe(recipe)
    else:
        bean = dict_to_bean_profile(bean)

    feedback = Feedback(
        thumbs_up=st.session_state.feedback_thumbs_up,
        score=score,
        directional_flags=flags if flags else None,
        notes=notes if notes.strip() else None,
    )

    brew_record = BrewRecord(
        brew_id=uuid.uuid4().hex[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        bean_profile=bean,
        recipe_used=recipe,
        feedback=feedback,
    )

    # Persist to database.
    user_id = st.session_state.get("user_id")
    if user_id:
        try:
            from src.app.db import get_db

            with get_db() as conn:
                save_brew(conn, user_id, brew_record)
        except Exception as exc:
            st.error("Could not save brew record. Please try again.")
            logger.debug("Brew save failed", exc_info=True)
            return

    # Update personalization engine.
    pe = st.session_state.get("personalization_engine")
    if pe is not None:
        try:
            pe.record_brew(brew_record)
        except Exception as exc:
            logger.debug("Personalization update failed", exc_info=True)

    # Store last brew for diagnosis page.
    st.session_state.last_brew = brew_record

    # Reset brew-session state for next session.
    st.session_state.brew_completed = False
    st.session_state.feedback_thumbs_up = True
    for flag_key in DIRECTIONAL_FLAGS:
        st.session_state.pop(f"flag_{flag_key}", None)

    st.success("Brew recorded!")

    # Navigate based on feedback.
    if flags:
        st.info("Issues detected. Let's diagnose what happened.")
        st.session_state.page = "diagnosis"
        st.rerun()
    else:
        st.session_state.page = "history"
        st.rerun()


def _fallback_bean_from_recipe(recipe: Recipe) -> BeanProfile:
    """Create a minimal BeanProfile from recipe metadata when none is set."""
    roast = RoastLevel.MEDIUM
    if recipe.suitable_for and recipe.suitable_for.roast_levels:
        roast = recipe.suitable_for.roast_levels[0]

    clusters = ["Balanced"]
    if recipe.suitable_for and recipe.suitable_for.flavor_profiles:
        clusters = recipe.suitable_for.flavor_profiles[:2]

    return BeanProfile(
        origin_country="Unknown",
        process=Process.UNKNOWN,
        roast_level=roast,
        flavor_clusters=clusters,
        source_text="Auto-generated from recipe selection",
    )


def _format_seconds(total_seconds: int) -> str:
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"

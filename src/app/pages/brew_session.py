"""Page: Brew Session. See specs/user-interface.md Section 4.5.

Step-by-step brewing instructions with timer, feedback collection,
and brew record persistence.
"""
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone

import streamlit as st

logger = logging.getLogger(__name__)

# Dose the user is allowed to dial in on the brew screen. The Recipe model
# accepts 12-35 g (data_models.py:110), but pour-over rarely runs above 25 g, so
# the input offers a tighter 12-25 g range. If a recipe's own dose falls outside
# that band the range widens to include it, so the recipe's dose is always
# selectable and the screen never force-rescales on load.
_MIN_DOSE_G = 12.0
_MAX_DOSE_G = 25.0

# Nominal dose for the "≈N brews left" estimate, matching the bag picker
# (bean_input._NOMINAL_DOSE_G) so the count is consistent across screens.
_NOMINAL_DOSE_G = 15.0

from src.app.db import get_bag, get_db, grams_used_for_bag, save_brew
from src.app.utils import dict_to_bean_profile, dict_to_recipe, escape_markdown
from src.grinder_catalog import get_grinder_display
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
    _render_bag_status()

    # The dose control rescales the displayed recipe (water + every pour) to the
    # dose the user actually weighed. The scaled recipe is what gets saved, so
    # history and the running-low count reflect the real cup (B1.5 + B1.6).
    display_recipe = _render_dose_control(recipe)
    _render_pour_steps(display_recipe)
    _render_summary_bar(display_recipe)
    _render_timer(display_recipe)

    # Feedback section only appears after marking the brew complete. It saves the
    # scaled recipe, so the brew record carries the real dose, not the template.
    if st.session_state.get("brew_completed", False):
        _render_feedback_section(display_recipe)
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


def _render_bag_status():
    """Show which bag this brew draws from and roughly how many cups remain.

    Reads the bag selected on the picker (``current_bag_id``) and the real grams
    used so far. Renders nothing for a no-bag brew, so the one-off path is
    unaffected.
    """
    bag_id = st.session_state.get("current_bag_id")
    user_id = st.session_state.get("user_id")
    if not bag_id or not user_id:
        return
    try:
        with get_db() as conn:
            bag = get_bag(conn, user_id, bag_id)
            if bag is None:
                return
            used = grams_used_for_bag(conn, user_id, bag_id)
    except Exception:
        logger.debug("Bag status lookup failed", exc_info=True)
        return

    remaining = max(0.0, bag.bag_size_g - used)
    brews_left = int(remaining // _NOMINAL_DOSE_G)
    st.caption(
        f"From your bag: **{escape_markdown(bag.roaster)} — "
        f"{escape_markdown(bag.name)}** · ≈{brews_left} brews left "
        f"({remaining:.0f} g remaining)"
    )


def _scale_recipe(recipe: Recipe, actual_dose_g: float) -> Recipe:
    """Return a copy of ``recipe`` rescaled to ``actual_dose_g``.

    Water total and every pour scale by ``actual_dose_g / recipe.dose_g``; the
    ratio, grind, water temperature, bloom time, and all pour timings are left
    unchanged -- so the coffee-to-water ratio stays constant while the absolute
    amounts track the dose actually weighed.

    Raises ``ValueError`` (via ``Recipe`` / ``PourStep`` validation) if the
    rescaled recipe falls outside model bounds (e.g. a downscale that pushes
    total water below 180 g or a pour below 10 g). Callers handle that by
    keeping the original recipe on screen.
    """
    factor = actual_dose_g / recipe.dose_g
    scaled_pours = [
        replace(p, water_g=round(p.water_g * factor, 1)) for p in recipe.pours
    ]
    return replace(
        recipe,
        dose_g=round(actual_dose_g, 1),
        water_total_g=round(recipe.water_total_g * factor, 1),
        pours=scaled_pours,
    )


def _render_dose_control(recipe: Recipe) -> Recipe:
    """Render the editable dose field and return the recipe to display.

    The field defaults to the recipe's own dose, so the screen opens unchanged.
    Changing it rescales water and every pour proportionally; a dose that can't
    build a valid recipe falls back to the original with a friendly note.
    """
    st.subheader("Your Dose")
    low = min(_MIN_DOSE_G, recipe.dose_g)
    high = max(_MAX_DOSE_G, recipe.dose_g)
    actual_dose = st.number_input(
        "Coffee dose (g)",
        min_value=float(low),
        max_value=float(high),
        value=float(recipe.dose_g),
        step=0.5,
        help=(
            "Set the dose you actually weighed. The water total and every pour "
            "rescale to match, keeping the same coffee-to-water ratio."
        ),
    )

    # Unchanged (within rounding) -> show the recipe as-is.
    if abs(actual_dose - recipe.dose_g) < 0.05:
        return recipe

    try:
        scaled = _scale_recipe(recipe, actual_dose)
    except ValueError:
        st.warning(
            f"{actual_dose:.1f} g doesn't fit this recipe's range — showing the "
            f"original {recipe.dose_g:.0f} g instead."
        )
        return recipe

    st.caption(
        f"Rescaled from {recipe.dose_g:.0f} g: water now "
        f"{scaled.water_total_g:.0f} g at the same 1:{scaled.ratio:.1f} ratio."
    )
    return scaled


def _render_pour_steps(recipe: Recipe):
    st.subheader("Brew Guide")
    cumulative = 0.0
    prev_time = 0

    for pour in recipe.pours:
        cumulative += pour.water_g
        wait_s = pour.time_offset_s - prev_time

        with st.container(border=True):
            col_step, col_detail = st.columns([1, 3])
            with col_step:
                if pour.step == 1:
                    st.markdown(f"### :material-water_drop: Pour {pour.step}")
                else:
                    st.markdown(f"### :material_water_drop: Pour {pour.step}")
            with col_detail:
                if pour.step == 1:
                    st.markdown(
                        f"**Pour {pour.water_g:.0f} g** of water over the coffee grounds."
                    )
                    if recipe.bloom_time_s and recipe.bloom_time_s > 0:
                        st.caption(
                            f"Let it bloom for {recipe.bloom_time_s} seconds "
                            f"(total water so far: {cumulative:.0f} g)"
                        )
                    else:
                        st.caption(f"Total water so far: {cumulative:.0f} g")
                else:
                    st.markdown(
                        f"Wait **{_format_seconds(wait_s)}**, then **pour {pour.water_g:.0f} g**."
                    )
                    st.caption(
                        f"Timer reads {_format_seconds(pour.time_offset_s)} "
                        f"(total water so far: {cumulative:.0f} g)"
                    )

        prev_time = pour.time_offset_s

    # Final drain note
    remaining = recipe.total_time_s - prev_time
    if remaining > 0:
        st.markdown(
            f"**Wait {_format_seconds(remaining)}** for the water to drain through. "
            f"Your brew is done at **{_format_seconds(recipe.total_time_s)}**!"
        )

    if recipe.instructions:
        st.info(escape_markdown(recipe.instructions))


def _render_summary_bar(recipe: Recipe):
    st.subheader("Recipe Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Dose", f"{recipe.dose_g:.1f} g")
        grinder_id = getattr(st.session_state.get("onboarding"), "grinder_id", None)
        grinder_display = get_grinder_display(grinder_id, recipe.grind_setting)
        if grinder_display:
            st.metric("Grind", f"{recipe.grind_setting}/10", delta=grinder_display)
        else:
            st.metric("Grind", f"{recipe.grind_setting}/10")
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
    # ``recipe`` is the scaled recipe from the dose control, so recipe.dose_g is
    # the dose actually weighed -- mirror it into actual_dose_g.
    bean = st.session_state.get("current_bean")
    if bean is None:
        # No bag/bean was picked -- this is the one-off fallback path. Do NOT
        # link a (possibly stale) bag id; the bag link is additive, never forced.
        bean = _fallback_bean_from_recipe(recipe)
        bag_id = None
    else:
        bean = dict_to_bean_profile(bean)
        bag_id = st.session_state.get("current_bag_id")

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
        bag_id=bag_id,
        actual_dose_g=recipe.dose_g,
    )

    # Persist to database.
    user_id = st.session_state.get("user_id")
    if user_id:
        try:
            with get_db() as conn:
                save_brew(conn, user_id, brew_record)
        except Exception as exc:
            st.error("Could not save brew record. Please try again.")
            logger.debug("Brew save failed", exc_info=True)
            return
    else:
        st.warning("Not logged in — brew not saved. Sign in to track your history.")

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

    if user_id:
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

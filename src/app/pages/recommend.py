"""Page: Recipe Recommendation. See specs/user-interface.md Section 4.4.

Displays ranked recipe recommendations for the current bean, with optional
predicted taste scores and per-recipe optimization.
"""
import logging

import streamlit as st

from src.app.utils import dict_to_bean_profile, escape_markdown, recipe_to_dict
from src.grinder_catalog import get_grinder_display
from src.data_models import (
    BeanProfile,
    BrewMethod,
    Process,
    Recipe,
    RoastLevel,
    SourceTier,
)

logger = logging.getLogger(__name__)

# Trust badges shown on recipe cards. Enthusiast-tier recipes show no badge.
_TIER_BADGES = {
    SourceTier.CHAMPION: "🏆 Championship recipe",
    SourceTier.BARISTA: "☕ Pro recipe",
}


def _format_source_tier_badge(tier: SourceTier) -> str:
    """Plain-language trust badge for a recipe's source tier ('' if none)."""
    return _TIER_BADGES.get(tier, "")

# Labels for grind settings (1-10 scale)
_GRIND_LABELS = {
    1: "Very Fine", 2: "Fine", 3: "Medium-Fine", 4: "Medium-Fine+",
    5: "Medium", 6: "Medium+", 7: "Medium-Coarse", 8: "Coarse",
    9: "Coarse+", 10: "Very Coarse",
}


def _format_grind(grind_value: float) -> str:
    """Format a grind setting for display.

    Returns the grinder-specific clicks when the user has a grinder
    configured (e.g. "Medium (5/10) — ~22 clicks on Comandante C40"),
    otherwise the 1-10 scale alone. The optimizer produces continuous
    values, so round to the nearest whole step before translating —
    grinder mappings are keyed to whole steps.
    """
    step = max(1, min(10, int(round(grind_value))))
    label = _GRIND_LABELS.get(step, str(step))
    grinder_id = getattr(st.session_state.get("onboarding"), "grinder_id", None)
    grinder_display = get_grinder_display(grinder_id, step)
    if grinder_display:
        return f"{label} ({step}/10) — {grinder_display}"
    return f"{label} ({step}/10)"


def render():
    """Render the recipe recommendation page."""
    st.title("Recommended Recipes")
    st.caption("Recipes ranked by predicted taste score for your beans and palate.")

    bean_dict = st.session_state.get("current_bean")
    if bean_dict is None:
        st.warning("No bean profile found. Please enter your beans first.")
        if st.button("Go to Bean Input"):
            st.session_state.page = "bean_input"
            st.rerun()
        return

    bean_profile = dict_to_bean_profile(bean_dict)
    _display_bean_summary(bean_profile)

    retriever = st.session_state.get("retriever")
    if retriever is None:
        st.error("Recipe database is not loaded. Please restart the application.")
        return

    preferences = _build_preferences()
    brew_methods = preferences.get("brew_methods", ["V60"])

    with st.spinner("Finding the best recipes for your beans..."):
        try:
            retrieval_result = retriever.retrieve(bean_profile, preferences, top_k=3)
        except RuntimeError as exc:
            st.error("Could not retrieve recipes. Please try again.")
            logger.debug("Recipe retrieval failed", exc_info=True)
            return
        except Exception as exc:
            st.error("Something went wrong while searching for recipes. Please try again.")
            logger.exception("Recipe retrieval failed: %s", exc)
            return

    st.session_state._retrieval_recipes = retrieval_result.recipes

    if not retrieval_result.recipes:
        st.info(
            "No matching recipes found for your bean profile. "
            "Try adjusting your bean details or using a different dripper."
        )
        return

    count = len(retrieval_result.recipes)
    method = brew_methods[0] if brew_methods else "pour-over"
    st.success(f"Found {count} recipe{'s' if count != 1 else ''} for your {method}")

    predictor = st.session_state.get("predictor")

    for idx, ranked in enumerate(retrieval_result.recipes):
        recipe = ranked.recipe
        predicted_score = None

        if predictor is not None and predictor.is_trained:
            try:
                prediction = predictor.predict(bean_profile, recipe)
                predicted_score = prediction.predicted_rating
            except Exception:
                logger.debug("Prediction failed for recipe %s", recipe.recipe_id)

        _render_recipe_card(idx, recipe, predicted_score, bean_profile)


def _display_bean_summary(bean: BeanProfile):
    """Display a compact summary of the current bean profile."""
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Origin:** {escape_markdown(bean.origin_country)}")
            if bean.origin_region:
                st.caption(escape_markdown(bean.origin_region))
        with col2:
            st.markdown(f"**Roast:** {bean.roast_level.value}")
            st.markdown(f"**Process:** {bean.process.value}")
        with col3:
            clusters = ", ".join(bean.flavor_clusters[:5])
            st.markdown(f"**Flavors:** {escape_markdown(clusters)}")


def _build_preferences() -> dict:
    """Build the preferences dict for the retriever from session state."""
    onboarding = st.session_state.get("onboarding")
    drippers = st.session_state.get("drippers", [])

    brew_methods = []
    for d in drippers:
        if isinstance(d, BrewMethod):
            brew_methods.append(d.value)
        elif isinstance(d, str):
            brew_methods.append(d)

    if not brew_methods:
        brew_methods = ["V60"]

    preferences = {"brew_methods": brew_methods}

    if onboarding is not None:
        if hasattr(onboarding, "experience_level"):
            preferences["experience_level"] = onboarding.experience_level.value

    return preferences


def _render_recipe_card(
    idx: int,
    recipe: Recipe,
    predicted_score: float | None,
    bean_profile: BeanProfile,
):
    """Render a single recipe card with details and action buttons."""
    rank_labels = {0: "Best Match", 1: "Runner Up", 2: "Alternative"}
    rank = rank_labels.get(idx, f"Recipe {idx + 1}")

    with st.container(border=True):
        header_col, score_col = st.columns([3, 1])
        with header_col:
            name = recipe.recipe_id.replace("-", " ").replace("_", " ").title()
            st.subheader(f"#{idx + 1} {name}")
            st.caption(f"{rank} via {recipe.source} | {recipe.method.value}")
            badge = _format_source_tier_badge(recipe.source_tier)
            if badge:
                st.caption(badge)
        with score_col:
            if predicted_score is not None:
                st.metric("Predicted Score", f"{predicted_score:.1f}/10")

        param_col1, param_col2, param_col3, param_col4 = st.columns(4)
        with param_col1:
            st.markdown(f"**Dose:** {recipe.dose_g:.1f} g")
            st.markdown(f"**Ratio:** 1:{recipe.ratio:.1f}")
        with param_col2:
            st.markdown(f"**Grind:** {_format_grind(recipe.grind_setting)}")
            st.markdown(f"**Temp:** {recipe.water_temp_c:.0f} C")
        with param_col3:
            st.markdown(f"**Bloom:** {recipe.bloom_time_s}s")
            st.markdown(f"**Total:** {recipe.total_time_s}s")
        with param_col4:
            st.markdown(f"**Pours:** {len(recipe.pours)}")
            st.markdown(f"**Water:** {recipe.water_total_g:.0f} g")

        with st.expander("View Step-by-Step Instructions"):
            for pour in recipe.pours:
                minutes = pour.time_offset_s // 60
                seconds = pour.time_offset_s % 60
                st.markdown(
                    f"**Pour {pour.step}:** {pour.water_g:.0f} g "
                    f"at {minutes}:{seconds:02d}"
                )
            st.markdown("---")
            st.markdown(escape_markdown(recipe.instructions))

        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button(
                "Start Brewing",
                key=f"brew_{idx}",
                type="primary",
                use_container_width=True,
            ):
                recipe_dict = recipe_to_dict(recipe)
                st.session_state.selected_recipe = recipe_dict
                st.session_state.current_recipes = [
                    recipe_to_dict(ranked.recipe) for ranked in
                    st.session_state.get("_retrieval_recipes", [])
                ]
                st.session_state.page = "brew_session"
                st.rerun()

        with action_col2:
            predictor = st.session_state.get("predictor")
            if predictor is not None and predictor.is_trained:
                if st.button(
                    "Optimize for My Taste",
                    key=f"optimize_{idx}",
                    use_container_width=True,
                ):
                    _run_optimization(idx, recipe, bean_profile, predictor)
            else:
                st.button(
                    "Optimize for My Taste",
                    key=f"optimize_{idx}",
                    disabled=True,
                    use_container_width=True,
                )
                st.caption("Taste predictor not available")


def _run_optimization(
    idx: int,
    recipe: Recipe,
    bean_profile: BeanProfile,
    predictor,
):
    """Run Bayesian optimization for a single recipe."""
    from src.recipe_optimizer.optimizer import RecipeOptimizer

    user_id = st.session_state.get("user_id")

    with st.spinner("Optimizing recipe for your taste..."):
        try:
            optimizer = RecipeOptimizer(predictor, n_trials=50)
            result = optimizer.optimize(bean_profile, recipe, user_id=user_id)

            optimized = result.optimized_recipe

            st.success(
                f"Optimized! Predicted score: {result.predicted_score:.1f}/10 "
                f"(baseline: {result.baseline_score:.1f}/10, "
                f"improvement: +{result.improvement:.2f})"
            )

            opt_col1, opt_col2 = st.columns(2)
            with opt_col1:
                st.markdown("**Original**")
                st.markdown(f"- Grind: {_format_grind(recipe.grind_setting)}")
                st.markdown(f"- Temp: {recipe.water_temp_c:.0f} C")
                st.markdown(f"- Dose: {recipe.dose_g:.1f}g")
                st.markdown(f"- Ratio: 1:{recipe.ratio:.1f}")
            with opt_col2:
                st.markdown("**Optimized**")
                st.markdown(f"- Grind: {_format_grind(optimized.grind_setting)}")
                st.markdown(f"- Temp: {optimized.water_temp_c:.0f} C")
                st.markdown(f"- Dose: {optimized.dose_g:.1f}g")
                st.markdown(f"- Ratio: 1:{optimized.ratio:.1f}")

            if result.parameter_changes:
                st.markdown("**Changes:**")
                for param, (old, new) in result.parameter_changes.items():
                    label = param.replace("_", " ").title()
                    if param == "grind_setting":
                        st.markdown(
                            f"- {label}: {_format_grind(old)} -> "
                            f"{_format_grind(new)}"
                        )
                    else:
                        st.markdown(f"- {label}: {old:.1f} -> {new:.1f}")

            if st.button(
                f"Start Brewing with Optimized Recipe",
                key=f"brew_opt_{idx}",
                use_container_width=True,
            ):
                recipe_dict = recipe_to_dict(optimized)
                st.session_state.selected_recipe = recipe_dict
                st.session_state.optimized_params = {
                    param: {"old": old, "new": new}
                    for param, (old, new) in result.parameter_changes.items()
                }
                st.session_state.page = "brew_session"
                st.rerun()

        except Exception as exc:
            st.error("Optimization failed. The original recipe is still a great choice.")
            logger.exception("Recipe optimization failed: %s", exc)


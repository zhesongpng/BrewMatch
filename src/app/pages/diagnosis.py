"""Page: Diagnosis. See specs/user-interface.md Section 4.7.

Diagnoses brew issues from directional flags using the ML-based
DiagnosisEngine when available, or a rule-based extraction-theory
fallback. Shows explanations, suggestions, and parameter adjustments.
"""
import logging

import streamlit as st

logger = logging.getLogger(__name__)

from src.data_models import (
    DIRECTIONAL_FLAGS,
    BeanProfile,
    BrewRecord,
    Recipe,
)

# Rule-based fallback: maps each directional flag to a human-readable
# assessment and actionable suggestions.
_RULE_BASED_DIAGNOSIS = {
    "too_sour": {
        "cause": "Under-extraction",
        "assessment": (
            "Sourness suggests under-extraction. The coffee compounds "
            "haven't fully dissolved into the water."
        ),
        "suggestions": [
            ("Grind", "Finer", "Increases surface area for better extraction."),
            ("Water Temp", "Higher (+1-2 C)", "Dissolves more flavor compounds."),
            ("Brew Time", "Longer (+15-30 s)", "Allows more contact time."),
        ],
    },
    "too_bitter": {
        "cause": "Over-extraction",
        "assessment": (
            "Bitterness suggests over-extraction. Too many harsh "
            "compounds have dissolved into the cup."
        ),
        "suggestions": [
            ("Grind", "Coarser", "Reduces surface area to slow extraction."),
            ("Water Temp", "Lower (-1-2 C)", "Prevents harsh compounds from dissolving."),
            ("Brew Time", "Shorter (-15-30 s)", "Limits contact time."),
        ],
    },
    "too_weak": {
        "cause": "Under-extraction or low dose",
        "assessment": (
            "Weak coffee may indicate under-extraction or too little "
            "coffee relative to water."
        ),
        "suggestions": [
            ("Grind", "Finer", "Increases extraction strength."),
            ("Dose", "Increase (+0.5-1 g)", "More coffee means more solubles."),
            ("Ratio", "Lower (e.g. 1:15)", "More concentrated brew."),
        ],
    },
    "too_harsh": {
        "cause": "Channeling or over-extraction",
        "assessment": (
            "Harshness can indicate channeling or over-extraction. "
            "Water may be bypassing the coffee bed."
        ),
        "suggestions": [
            ("Grind", "Coarser", "Slows extraction of harsh compounds."),
            ("Pour Technique", "Gentler, centered pours", "Reduces channeling risk."),
            ("Water Temp", "Lower (-1-2 C)", "Reduces astringent compound extraction."),
        ],
    },
    "astringent": {
        "cause": "Over-extraction",
        "assessment": (
            "Astringency often indicates over-extraction. The drying "
            "mouthfeel comes from excess tannin-like compounds."
        ),
        "suggestions": [
            ("Grind", "Coarser", "Slows overall extraction."),
            ("Water Temp", "Lower (-1-2 C)", "Prevents over-dissolving."),
            ("Brew Time", "Shorter (-15-30 s)", "Limits extraction of astringent compounds."),
        ],
    },
}


def render():
    brew = _load_flagged_brew()
    if brew is None:
        st.title("Brew Diagnosis")
        st.info("No recent brews with issues to diagnose. Keep brewing!")
        if st.button("Back to History"):
            st.session_state.page = "history"
            st.rerun()
        return

    recipe = brew.recipe_used
    bean = brew.bean_profile
    flags = brew.feedback.directional_flags or []

    st.title("Brew Diagnosis")
    _render_brew_summary(brew, flags)

    # Try ML-based diagnosis, fall back to rule-based.
    diagnosis_engine = st.session_state.get("diagnosis_engine")
    predictor = st.session_state.get("predictor")
    ml_available = diagnosis_engine is not None and predictor is not None and predictor.is_trained

    if ml_available:
        _render_ml_diagnosis(diagnosis_engine, bean, recipe, flags)
    else:
        _render_rule_based_diagnosis(flags, recipe)

    _render_extraction_theory()
    _render_try_again_button()


def _load_flagged_brew():
    """Load the most recent brew with issues.

    Matches brews with directional flags OR a score <= 6.
    Checks session state first, then falls back to database history.
    """
    last_brew = st.session_state.get("last_brew")
    if last_brew is not None:
        flags = last_brew.feedback.directional_flags
        score = last_brew.feedback.score
        if (flags and len(flags) > 0) or (score is not None and score <= 6):
            return last_brew

    # Try loading from database.
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None

    try:
        from src.app.db import get_db, load_brew_history

        with get_db() as conn:
            history = load_brew_history(conn, user_id, limit=20)
        for record in history:
            fb = record["feedback"]
            has_flags = fb.directional_flags and len(fb.directional_flags) > 0
            low_score = fb.score is not None and fb.score <= 6
            if has_flags or low_score:
                return _dict_to_brew_record(record)
    except Exception:
        logger.debug("Could not load brew history for diagnosis", exc_info=True)

    return None


def _dict_to_brew_record(record: dict) -> BrewRecord:
    """Convert a DB row dict back into a BrewRecord dataclass."""
    return BrewRecord(
        brew_id=record["brew_id"],
        timestamp=record["timestamp"],
        bean_profile=record["bean_profile"],
        recipe_used=record["recipe_used"],
        feedback=record["feedback"],
    )


def _render_brew_summary(brew: BrewRecord, flags: list[str]):
    st.subheader("Brew Summary")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Bean:** {brew.bean_profile.origin_country}")
        st.markdown(f"**Process:** {brew.bean_profile.process.value}")
    with col2:
        st.markdown(f"**Recipe:** {brew.recipe_used.recipe_id.replace('-', ' ').title()}")
        st.markdown(f"**Method:** {brew.recipe_used.method.value}")

    flag_labels = ", ".join(flag.replace("_", " ").title() for flag in flags)
    st.warning(f"Issues detected: {flag_labels}")


def _render_ml_diagnosis(diagnosis_engine, bean, recipe, flags):
    """Use the ML DiagnosisEngine for diagnosis."""
    st.subheader("What Happened")
    try:
        user_id = st.session_state.get("user_id")
        result = diagnosis_engine.diagnose(bean, recipe, flags, user_id=user_id)
        st.write(result.overall_assessment)

        if result.suggestions:
            st.subheader("Suggestions")
            for suggestion in result.suggestions:
                with st.container():
                    col_param, col_current, col_suggested = st.columns(3)
                    with col_param:
                        st.markdown(f"**{suggestion.parameter.replace('_', ' ').title()}**")
                    with col_current:
                        st.markdown(f"Current: `{suggestion.current_value}`")
                    with col_suggested:
                        st.markdown(f"Try: `{suggestion.suggested_value}`")
                    st.caption(suggestion.reason)
                    if suggestion.confidence > 0:
                        st.progress(min(suggestion.confidence, 1.0),
                                    text=f"Confidence: {suggestion.confidence:.0%}")
                    st.markdown("---")
        else:
            st.info("No specific parameter changes suggested. Your recipe looks reasonable.")

    except Exception as exc:
        st.error("Diagnosis engine encountered an error. Using rule-based fallback.")
        logger.debug("ML diagnosis failed", exc_info=True)
        _render_rule_based_diagnosis(flags, recipe)


def _render_rule_based_diagnosis(flags: list[str], recipe: Recipe):
    """Rule-based fallback using extraction theory."""
    st.subheader("What Happened")

    for flag in flags:
        diagnosis = _RULE_BASED_DIAGNOSIS.get(flag)
        if diagnosis is None:
            continue
        st.markdown(f"**{flag.replace('_', ' ').title()}** -- {diagnosis['cause']}")
        st.write(diagnosis["assessment"])

    st.subheader("Suggestions")
    seen_params = set()
    for flag in flags:
        diagnosis = _RULE_BASED_DIAGNOSIS.get(flag)
        if diagnosis is None:
            continue
        for param, suggestion, reason in diagnosis["suggestions"]:
            if param not in seen_params:
                seen_params.add(param)
                current_val = _get_current_param(recipe, param)
                current_str = f" (currently {current_val})" if current_val else ""
                st.markdown(f"**{param}{current_str}:** {suggestion}")
                st.caption(reason)

    # Show current parameters for reference.
    st.markdown("**Current recipe parameters:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Grind", recipe.grind_setting)
        st.metric("Dose", f"{recipe.dose_g:.1f} g")
    with col2:
        st.metric("Water Temp", f"{recipe.water_temp_c:.0f} C")
        st.metric("Ratio", f"1:{recipe.ratio:.2f}")
    with col3:
        st.metric("Bloom Time", f"{recipe.bloom_time_s} s")
        st.metric("Total Time", f"{recipe.total_time_s} s")


def _get_current_param(recipe: Recipe, param_label: str) -> str:
    """Return a display string for the current value of a parameter."""
    mapping = {
        "Grind": lambda r: str(r.grind_setting),
        "Water Temp": lambda r: f"{r.water_temp_c:.0f} C",
        "Dose": lambda r: f"{r.dose_g:.1f} g",
        "Ratio": lambda r: f"1:{r.ratio:.2f}",
        "Brew Time": lambda r: f"{r.total_time_s} s",
    }
    getter = mapping.get(param_label)
    if getter:
        return getter(recipe)
    return ""


def _render_extraction_theory():
    st.subheader("Extraction Theory")
    with st.expander("Learn about extraction", expanded=False):
        st.markdown(
            """
Coffee extraction is the process of dissolving flavor compounds from
ground coffee into water. The goal is to extract the right balance of
sweet, acidic, and bitter compounds.

- **Under-extraction** (too little dissolved): sour, salty, lacking
  sweetness. Usually caused by grind too coarse, water too cool, or
  brew time too short.
- **Over-extraction** (too much dissolved): bitter, harsh, astringent.
  Usually caused by grind too fine, water too hot, or brew time too
  long.
- **Even extraction** is the goal: water passes uniformly through the
  coffee bed, dissolving a balanced mix of compounds.

Key parameters, roughly ordered by impact:
1. **Grind size** -- Finer = faster extraction; coarser = slower.
2. **Water temperature** -- Higher = faster extraction; lower = slower.
3. **Brew time** -- Longer = more extraction; shorter = less.
4. **Dose / ratio** -- More coffee = stronger cup; less = weaker.
            """
        )


def _render_try_again_button():
    st.markdown("---")
    if st.button("Try Again with Adjustments", type="primary", use_container_width=True):
        st.session_state.page = "recommend"
        st.rerun()

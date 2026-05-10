"""Page: Onboarding. See specs/user-interface.md Section 4.2.

Sequential 4-step wizard that collects roast preference, flavor profiles,
experience level, and equipment selection to build the user's initial profile.
"""
import uuid

import streamlit as st

from src.app.db import get_db, save_user
from src.data_models import (
    FLAVOR_CLUSTERS,
    BrewMethod,
    ExperienceLevel,
    Onboarding,
    RoastLevel,
)

_STEP_COUNT = 4

# Step 1 option labels mapped to RoastLevel enum values
_ROAST_OPTIONS = {
    "Bright, fruity, tea-like": RoastLevel.LIGHT,
    "Balanced, sweet, smooth": RoastLevel.MEDIUM_LIGHT,
    "Bold, rich, full-bodied": RoastLevel.MEDIUM_DARK,
}

# Step 3 option labels mapped to ExperienceLevel enum values
_EXPERIENCE_OPTIONS = {
    "I'm new to specialty coffee": ExperienceLevel.BEGINNER,
    "I brew regularly and know the basics": ExperienceLevel.INTERMEDIATE,
    "I experiment with parameters and recipes": ExperienceLevel.ADVANCED,
}

# Step 4 dripper labels mapped to BrewMethod enum values
_DRIPPER_OPTIONS = {
    "V60": BrewMethod.V60,
    "Kalita Wave": BrewMethod.KALITA_WAVE,
    "Origami": BrewMethod.ORIGAMI,
}


def render():
    """Render the onboarding wizard page."""
    st.title("Welcome to BrewMatch")
    st.caption("Let's set up your profile in a few quick steps.")

    current_step = st.session_state.get("onboarding_step", 0)
    progress = (current_step + 1) / _STEP_COUNT
    st.progress(progress, text=f"Step {current_step + 1} of {_STEP_COUNT}")

    if current_step == 0:
        _render_roast_step()
    elif current_step == 1:
        _render_flavor_step()
    elif current_step == 2:
        _render_experience_step()
    elif current_step == 3:
        _render_equipment_step()
    else:
        current_step = 0
        st.session_state.onboarding_step = 0
        st.rerun()


def _render_roast_step():
    """Step 1: Roast preference selection."""
    st.subheader("What kind of coffee do you enjoy?")

    selected_label = st.radio(
        "Choose the description that sounds most like your taste:",
        options=list(_ROAST_OPTIONS.keys()),
        index=None,
        key="onboarding_roast_label",
    )

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("Back", disabled=True, use_container_width=True):
            pass
    with col_next:
        if st.button("Next", use_container_width=True):
            if selected_label is None:
                st.warning("Please select a roast preference to continue.")
                return
            st.session_state.onboarding_roast = _ROAST_OPTIONS[selected_label]
            st.session_state.onboarding_step = 1
            st.rerun()


def _render_flavor_step():
    """Step 2: Flavor cluster selection (1-5 required)."""
    st.subheader("What flavors do you love in coffee?")

    selected = st.multiselect(
        "Pick 1 to 5 flavor profiles that appeal to you:",
        options=list(FLAVOR_CLUSTERS),
        max_selections=5,
        key="onboarding_flavors",
    )

    count_text = f"{len(selected)} of 5 selected"
    if len(selected) == 0:
        st.info(count_text)
    else:
        st.markdown(f"**{count_text}**")

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("Back", use_container_width=True):
            st.session_state.onboarding_step = 0
            st.rerun()
    with col_next:
        if st.button("Next", use_container_width=True):
            if len(selected) < 1:
                st.warning("Please select at least 1 flavor profile.")
                return
            if len(selected) > 5:
                st.warning("Please select no more than 5 flavor profiles.")
                return
            st.session_state.onboarding_flavors_selected = selected
            st.session_state.onboarding_step = 2
            st.rerun()


def _render_experience_step():
    """Step 3: Experience level selection."""
    st.subheader("How experienced are you with pour-over brewing?")

    selected_label = st.radio(
        "Choose the option that best describes you:",
        options=list(_EXPERIENCE_OPTIONS.keys()),
        index=None,
        key="onboarding_experience_label",
    )

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("Back", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.rerun()
    with col_next:
        if st.button("Next", use_container_width=True):
            if selected_label is None:
                st.warning("Please select your experience level.")
                return
            st.session_state.onboarding_experience = _EXPERIENCE_OPTIONS[selected_label]
            st.session_state.onboarding_step = 3
            st.rerun()


def _render_equipment_step():
    """Step 4: Equipment selection and onboarding completion."""
    st.subheader("What drippers do you own?")

    selected_drippers = []
    for label, method in _DRIPPER_OPTIONS.items():
        if st.checkbox(label, key=f"dripper_{method.value}"):
            selected_drippers.append(method)

    col_back, col_next = st.columns([1, 3])
    with col_back:
        if st.button("Back", use_container_width=True):
            st.session_state.onboarding_step = 2
            st.rerun()
    with col_next:
        if st.button("Get Started", use_container_width=True):
            if len(selected_drippers) < 1:
                st.warning("Please select at least one dripper to continue.")
                return

            _complete_onboarding(selected_drippers)


def _complete_onboarding(drippers: list[BrewMethod]):
    """Save the onboarding data and navigate to bean input."""
    user_id = uuid.uuid4().hex[:8]

    onboarding = Onboarding(
        preferred_clusters=st.session_state.onboarding_flavors_selected,
        roast_preference=st.session_state.onboarding_roast,
        experience_level=st.session_state.onboarding_experience,
    )

    st.session_state.user_id = user_id
    st.session_state.onboarding = onboarding
    st.session_state.drippers = drippers

    with get_db() as conn:
        save_user(conn, user_id, onboarding)

    # Wire PersonalizationEngine if the predictor is loaded and trained.
    predictor = st.session_state.get("predictor")
    if predictor is not None and getattr(predictor, "is_trained", False):
        try:
            from src.personalization.engine import PersonalizationEngine

            st.session_state.personalization_engine = PersonalizationEngine(
                predictor=predictor,
                user_id=user_id,
                onboarding=onboarding,
            )
            st.session_state.personalization_phase = "warm_start"
        except Exception:
            pass  # Non-fatal: personalization features will be unavailable

    st.session_state.page = "bean_input"
    st.rerun()

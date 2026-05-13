"""Page: Bean Input. See specs/user-interface.md Section 4.3.

Manual bean profile entry with guided dropdowns for origin, process,
roast level, and flavor profiles. The profile is stored in session state
for the recommendation page.
"""
import logging

import streamlit as st

from src.app.utils import bean_to_dict
from src.bean_extractor.extractor import create_manual_profile
from src.data_models import (
    FLAVOR_CLUSTERS,
    Process,
    RoastLevel,
)

logger = logging.getLogger(__name__)

_ROAST_LABELS = {
    "Light": RoastLevel.LIGHT,
    "Medium-Light": RoastLevel.MEDIUM_LIGHT,
    "Medium": RoastLevel.MEDIUM,
    "Medium-Dark": RoastLevel.MEDIUM_DARK,
    "Dark": RoastLevel.DARK,
    "Unknown": RoastLevel.UNKNOWN,
}

_PROCESS_LABELS = {
    "Washed": Process.WASHED,
    "Natural": Process.NATURAL,
    "Honey": Process.HONEY,
    "Anaerobic": Process.ANAEROBIC,
    "Wet-Hulled": Process.WET_HULLED,
    "Unknown": Process.UNKNOWN,
}

_COMMON_ORIGINS = [
    "Ethiopia", "Colombia", "Kenya", "Guatemala", "Brazil",
    "Costa Rica", "Panama", "Indonesia", "Rwanda", "Honduras",
    "Mexico", "Peru", "Uganda", "Tanzania", "Other",
]


def render():
    """Render the bean input page."""
    st.title("Describe Your Beans")
    st.caption("Enter the details from your coffee bag label.")
    _render_manual_mode()


def _render_manual_mode():
    """Manual form entry mode."""
    with st.form("manual_bean_form"):
        col_left, col_right = st.columns(2)

        with col_left:
            origin_selection = st.selectbox(
                "Origin Country *",
                options=_COMMON_ORIGINS,
                key="manual_origin_select",
            )
            custom_origin = ""
            if origin_selection == "Other":
                custom_origin = st.text_input(
                    "Specify Origin *",
                    placeholder="e.g., Yemen, Burundi, Nicaragua",
                    key="manual_origin_custom",
                )
            region = st.text_input(
                "Region",
                placeholder="e.g., Yirgacheffe, Huila",
                key="manual_region",
            )
            process_label = st.selectbox(
                "Process Method *",
                options=list(_PROCESS_LABELS.keys()),
                key="manual_process",
            )
            roast_label = st.selectbox(
                "Roast Level *",
                options=list(_ROAST_LABELS.keys()),
                key="manual_roast",
            )

        with col_right:
            variety = st.text_input(
                "Variety",
                placeholder="e.g., Gesha, Bourbon, SL28",
                key="manual_variety",
            )
            flavor_selected = st.multiselect(
                "Flavor Profiles * (at least 1)",
                options=list(FLAVOR_CLUSTERS),
                max_selections=10,
                key="manual_flavors",
            )
            altitude = st.text_input(
                "Altitude (m)",
                placeholder="e.g., 1800 or 1500-2000",
                key="manual_altitude",
            )

        submitted = st.form_submit_button("Save Bean Profile", use_container_width=True)

    if submitted:
        origin = custom_origin.strip() if origin_selection == "Other" else origin_selection
        errors = _validate_manual_input(origin, process_label, roast_label, flavor_selected)
        if errors:
            for error in errors:
                st.warning(error)
            return

        altitude_min, altitude_max = _parse_altitude(altitude)

        result = create_manual_profile(
            origin_country=origin,
            process=_PROCESS_LABELS[process_label].value,
            roast_level=_ROAST_LABELS[roast_label].value,
            flavor_clusters=flavor_selected,
            source_text="manual entry",
            origin_region=region.strip() if region.strip() else None,
            variety=variety.strip() if variety.strip() else None,
            altitude_min_m=altitude_min,
            altitude_max_m=altitude_max,
        )

        profile = result.bean_profile
        bean_dict = bean_to_dict(profile)

        st.session_state.current_bean = bean_dict
        st.success("Bean profile saved.")
        st.session_state.page = "recommend"
        st.rerun()


def _validate_manual_input(
    origin: str,
    process_label: str,
    roast_label: str,
    flavors: list[str],
) -> list[str]:
    """Validate manual form inputs. Returns a list of error messages."""
    errors = []
    if not origin or not origin.strip():
        errors.append("Origin country is required.")
    if not process_label:
        errors.append("Please select a process method.")
    if not roast_label:
        errors.append("Please select a roast level.")
    if not flavors:
        errors.append("Please select at least one flavor profile.")
    return errors


def _parse_altitude(altitude_str: str) -> tuple[int | None, int | None]:
    """Parse altitude string into (min, max) tuple."""
    if not altitude_str or not altitude_str.strip():
        return None, None

    text = altitude_str.strip().replace(" ", "")
    if "-" in text:
        parts = text.split("-", 1)
        try:
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return None, None
    try:
        val = int(text)
        return val, val
    except ValueError:
        return None, None

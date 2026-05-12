"""Page: Bean Input. See specs/user-interface.md Section 4.3.

Two-mode bean profile entry: LLM-based text extraction or manual form entry.
The extracted or manually-entered profile is stored in session state for the
recommendation page.
"""
import logging
import os

import streamlit as st

from src.app.utils import bean_to_dict, escape_markdown
from src.bean_extractor.extractor import BeanExtractor, create_manual_profile
from src.data_models import (
    FLAVOR_CLUSTERS,
    Process,
    RoastLevel,
)

logger = logging.getLogger(__name__)

# Roast level display order and labels
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


def render():
    """Render the bean input page."""
    st.title("Describe Your Beans")
    st.caption("Paste the label from your coffee bag, or fill in the details manually.")

    tab_text, tab_manual = st.tabs(["Text Description", "Manual Entry"])

    with tab_text:
        _render_text_mode()

    with tab_manual:
        _render_manual_mode()


def _render_text_mode():
    """LLM-based text extraction mode."""
    st.markdown(
        "Paste the description from your coffee bag label below, "
        "and we will extract the key details automatically."
    )

    source_text = st.text_area(
        "Bean description",
        placeholder="e.g., Ethiopian Yirgacheffe, washed process, light roast, "
        "with notes of jasmine, lemon, and black tea...",
        height=150,
        max_chars=2000,
        key="bean_source_text",
    )

    extracting = st.session_state.get("extracting_beans", False)
    if st.button(
        "Analyze Beans",
        use_container_width=True,
        key="analyze_btn",
        disabled=extracting,
    ):
        if not source_text or len(source_text.strip()) < 5:
            st.warning("Please enter at least a short description of your beans.")
            return

        _run_extraction(source_text.strip())


def _run_extraction(source_text: str):
    """Attempt LLM extraction with graceful fallback on error."""
    st.session_state.extracting_beans = True

    with st.spinner("Analyzing your bean description..."):
        try:
            api_key = os.environ.get("LLM_API_KEY", "")
            if not api_key:
                raise ValueError(
                    "No API key configured. Set LLM_API_KEY in your .env file "
                    "or enter the bean details manually."
                )

            extractor = BeanExtractor()
            result = extractor.extract(source_text)

            _display_extraction_result(result, source_text)

        except (ValueError, RuntimeError) as exc:
            st.error(
                "Could not analyze your description. "
                "Please try entering details manually using the Manual Entry tab."
            )
            logger.debug("Bean extraction failed", exc_info=True)
        except Exception as exc:
            st.error(
                "Could not analyze your description. "
                "Please try entering details manually using the Manual Entry tab."
            )
            logger.debug("Bean extraction failed unexpectedly", exc_info=True)
        finally:
            st.session_state.extracting_beans = False


def _display_extraction_result(result, source_text: str):
    """Display the extraction result with confidence indicator and confirmation."""
    profile = result.bean_profile
    tier = result.confidence_tier

    tier_colors = {"HIGH": "green", "MEDIUM": "orange", "LOW": "red"}
    color = tier_colors.get(tier, "gray")

    st.markdown(f"**Extraction confidence:** :{color}[{tier}] ({result.confidence:.0%})")

    if result.missing_fields:
        st.caption(
            "Missing or uncertain fields: " + ", ".join(result.missing_fields)
        )

    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Origin:** {escape_markdown(profile.origin_country)}")
            region = profile.origin_region or "Not specified"
            st.markdown(f"**Region:** {escape_markdown(region)}")
            st.markdown(f"**Process:** {profile.process.value}")
        with col_b:
            st.markdown(f"**Roast:** {profile.roast_level.value}")
            variety = profile.variety or "Not specified"
            st.markdown(f"**Variety:** {escape_markdown(variety)}")
            clusters = ", ".join(profile.flavor_clusters)
            st.markdown(f"**Flavor clusters:** {escape_markdown(clusters)}")

    if st.button("Looks Good - Find Recipes", use_container_width=True, key="confirm_extraction"):
        bean_dict = bean_to_dict(profile)
        bean_dict["source_text"] = source_text
        st.session_state.current_bean = bean_dict
        st.session_state.page = "recommend"
        st.rerun()


def _render_manual_mode():
    """Manual form entry mode."""
    st.markdown("Enter the details from your coffee bag label.")

    with st.form("manual_bean_form"):
        col_left, col_right = st.columns(2)

        with col_left:
            origin = st.text_input(
                "Origin Country *",
                placeholder="e.g., Ethiopia, Colombia",
                key="manual_origin",
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
        errors = _validate_manual_input(origin, process_label, roast_label, flavor_selected)
        if errors:
            for error in errors:
                st.warning(error)
            return

        altitude_min, altitude_max = _parse_altitude(altitude)

        result = create_manual_profile(
            origin_country=origin.strip(),
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
    """Parse altitude string into (min, max) tuple.

    Accepts single values like '1800' or ranges like '1500-2000'.
    Returns (None, None) for empty or invalid input.
    """
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

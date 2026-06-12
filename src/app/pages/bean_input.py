"""Page: Your Coffees. See specs/user-interface.md Section 4.3.

Pick a saved bag of coffee to brew with, or add a new bag once when you open
it. Selecting a bag sets it as the current bean for the recommendation + brew
flow, exactly as the old per-brew form did -- but entered once per bag instead
of once per cup.

Persistence (COC B1.4): bags are stored in the database via the helpers in
src.app.db, scoped to the logged-in user, so they survive logout and reappear
on next login. The data-access seams below (_load_active_bags / _save_bag /
_grams_used / _finish_bag) are the only place this page touches storage. The
picker page is login-gated (see app._PUBLIC_PAGES), so a user_id is always
present when it renders; the seams degrade to a safe no-op if it is ever absent.
"""
import logging
from datetime import datetime, timezone

import streamlit as st

from src.app.db import (
    create_bag,
    get_db,
    grams_used_for_bag,
    list_active_bags,
    mark_bag_finished,
)
from src.app.utils import bean_to_dict, escape_markdown
from src.bean_extractor.extractor import create_manual_profile
from src.data_models import (
    FLAVOR_CLUSTERS,
    CoffeeBag,
    Process,
    RoastLevel,
    create_bag_id,
)

logger = logging.getLogger(__name__)

# Nominal dose used ONLY to estimate "brews left" for display until real
# per-brew doses are tracked (B1.6). Always shown with a leading "≈" so the
# number reads as an estimate, never a precise count.
_NOMINAL_DOSE_G = 15.0

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


# ---------------------------------------------------------------------------
# Storage seams
#
# The ONLY place this page touches bag storage. Each reads the logged-in user
# from session state and delegates to the database helpers in src.app.db, so
# bags persist across sessions and are scoped per user.
# ---------------------------------------------------------------------------

def _current_user_id() -> str | None:
    return st.session_state.get("user_id")


def _load_active_bags() -> list[CoffeeBag]:
    user_id = _current_user_id()
    if not user_id:
        return []
    with get_db() as conn:
        return list_active_bags(conn, user_id)


def _save_bag(bag: CoffeeBag) -> None:
    user_id = _current_user_id()
    if not user_id:
        return
    with get_db() as conn:
        create_bag(conn, user_id, bag)


def _grams_used(bag: CoffeeBag) -> float:
    # Real running total: sum of actual doses logged against this bag. Stays 0
    # until brews are wired to record their bag + dose (B1.6).
    user_id = _current_user_id()
    if not user_id:
        return 0.0
    with get_db() as conn:
        return grams_used_for_bag(conn, user_id, bag.bag_id)


def _finish_bag(bag_id: str) -> None:
    user_id = _current_user_id()
    if not user_id:
        return
    with get_db() as conn:
        mark_bag_finished(conn, user_id, bag_id)


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without Streamlit)
# ---------------------------------------------------------------------------

def _brews_left(bag: CoffeeBag, grams_used: float) -> int:
    """Estimate how many brews remain in a bag from grams remaining."""
    remaining = bag.bag_size_g - grams_used
    return max(0, int(remaining // _NOMINAL_DOSE_G))


def _validate_bag_input(
    roaster: str,
    coffee_name: str,
    origin: str,
    process_label: str,
    roast_label: str,
    flavors: list[str],
) -> list[str]:
    """Validate the add-bag form. Returns a list of error messages."""
    errors = []
    if not roaster or not roaster.strip():
        errors.append("Roaster is required.")
    if not coffee_name or not coffee_name.strip():
        errors.append("Coffee name is required.")
    if not origin or not origin.strip():
        errors.append("Origin country is required.")
    if not process_label:
        errors.append("Please select a process method.")
    if not roast_label:
        errors.append("Please select a roast level.")
    if not flavors:
        errors.append("Please select at least one flavor profile.")
    return errors


def _build_bag(
    *,
    roaster: str,
    coffee_name: str,
    bag_size_g: float,
    origin: str,
    process_label: str,
    roast_label: str,
    flavor_clusters: list[str],
    region: str = "",
    variety: str = "",
    altitude_min_m: int | None = None,
    altitude_max_m: int | None = None,
) -> CoffeeBag:
    """Build a CoffeeBag from validated form inputs.

    Reuses create_manual_profile for the bean half, then attaches the bag's
    roaster/name to the bean so they flow into history and diagnosis.
    """
    result = create_manual_profile(
        origin_country=origin,
        process=_PROCESS_LABELS[process_label].value,
        roast_level=_ROAST_LABELS[roast_label].value,
        flavor_clusters=flavor_clusters,
        source_text="manual entry",
        origin_region=region.strip() or None,
        variety=variety.strip() or None,
        altitude_min_m=altitude_min_m,
        altitude_max_m=altitude_max_m,
    )
    profile = result.bean_profile
    profile.roaster = roaster.strip()
    profile.name = coffee_name.strip()

    return CoffeeBag(
        bag_id=create_bag_id(),
        roaster=roaster.strip(),
        name=coffee_name.strip(),
        bean_profile=profile,
        bag_size_g=float(bag_size_g),
        date_opened=datetime.now(timezone.utc).date().isoformat(),
        active=True,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render():
    """Render the Your Coffees picker."""
    st.title("Your Coffees")
    st.caption("Pick a bag to brew with, or add a new one when you open it.")

    bags = _load_active_bags()
    if bags:
        _render_bag_list(bags)
    else:
        st.info("No saved bags yet. Add your first bag below to get started.")

    _render_add_bag_form(has_bags=bool(bags))


def _render_bag_list(bags: list[CoffeeBag]) -> None:
    st.subheader("Your open bags")
    for bag in bags:
        with st.container(border=True):
            col_info, col_action = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f"**{escape_markdown(bag.roaster)} — {escape_markdown(bag.name)}**"
                )
                left = _brews_left(bag, _grams_used(bag))
                st.caption(
                    f"{escape_markdown(bag.bean_profile.origin_country)} · "
                    f"≈{left} brews left"
                )
            with col_action:
                if st.button(
                    "Brew this", key=f"pick_{bag.bag_id}", use_container_width=True
                ):
                    _select_bag(bag)
                if st.button(
                    "Finished",
                    key=f"finish_{bag.bag_id}",
                    use_container_width=True,
                    type="secondary",
                    help="Mark this bag empty and remove it from your list.",
                ):
                    _finish_bag(bag.bag_id)
                    st.rerun()


def _select_bag(bag: CoffeeBag) -> None:
    """Set the picked bag as the current bean and move to recommendations."""
    st.session_state.current_bean = bean_to_dict(bag.bean_profile)
    st.session_state.current_bag_id = bag.bag_id
    st.session_state.page = "recommend"
    st.rerun()


def _render_add_bag_form(has_bags: bool) -> None:
    # Open the form by default when there are no bags yet, so a first-time user
    # lands directly on it.
    with st.expander("Add a new bag", expanded=not has_bags):
        with st.form("add_bag_form"):
            col_left, col_right = st.columns(2)

            with col_left:
                roaster = st.text_input(
                    "Roaster *", placeholder="e.g., Onyx Coffee Lab", key="bag_roaster"
                )
                coffee_name = st.text_input(
                    "Coffee name *", placeholder="e.g., Ethiopia Guji", key="bag_name"
                )
                bag_size = st.number_input(
                    "Bag size (g)", min_value=50.0, max_value=2000.0,
                    value=250.0, step=10.0, key="bag_size",
                    help="Most bags are 250 g or 340 g (12 oz).",
                )
                origin_selection = st.selectbox(
                    "Origin Country *", options=_COMMON_ORIGINS, key="manual_origin_select"
                )
                # Rendered unconditionally: inside an st.form the selectbox value
                # is not readable until submit, so a conditional field would need
                # two submits to appear. Always showing it makes "Other" work in
                # one pass; it is only read when "Other" is selected.
                custom_origin = st.text_input(
                    "If 'Other', specify origin",
                    placeholder="e.g., Yemen, Burundi, Nicaragua",
                    key="manual_origin_custom",
                )
                region = st.text_input(
                    "Region", placeholder="e.g., Yirgacheffe, Huila", key="manual_region"
                )

            with col_right:
                process_label = st.selectbox(
                    "Process Method *", options=list(_PROCESS_LABELS.keys()),
                    key="manual_process",
                )
                roast_label = st.selectbox(
                    "Roast Level *", options=list(_ROAST_LABELS.keys()), key="manual_roast"
                )
                variety = st.text_input(
                    "Variety", placeholder="e.g., Gesha, Bourbon, SL28", key="manual_variety"
                )
                flavor_selected = st.multiselect(
                    "Flavor Profiles * (at least 1)", options=list(FLAVOR_CLUSTERS),
                    max_selections=10, key="manual_flavors",
                )
                altitude = st.text_input(
                    "Altitude (m)", placeholder="e.g., 1800 or 1500-2000", key="manual_altitude"
                )

            submitted = st.form_submit_button("Save bag", use_container_width=True)

        if submitted:
            origin = (
                custom_origin.strip()
                if origin_selection == "Other"
                else origin_selection
            )
            errors = _validate_bag_input(
                roaster, coffee_name, origin, process_label, roast_label, flavor_selected
            )
            if errors:
                for error in errors:
                    st.warning(error)
                return

            altitude_min, altitude_max = _parse_altitude(altitude)
            bag = _build_bag(
                roaster=roaster,
                coffee_name=coffee_name,
                bag_size_g=bag_size,
                origin=origin,
                process_label=process_label,
                roast_label=roast_label,
                flavor_clusters=flavor_selected,
                region=region,
                variety=variety,
                altitude_min_m=altitude_min,
                altitude_max_m=altitude_max,
            )
            _save_bag(bag)
            st.success(
                f"Saved {escape_markdown(bag.roaster)} — {escape_markdown(bag.name)}."
            )
            _select_bag(bag)


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

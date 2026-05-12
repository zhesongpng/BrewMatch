"""Page: Profile — Display name, drippers, password, stats, logout."""
import logging
import re

import streamlit as st

from src.app.auth import change_password, logout as auth_logout
from src.app.db import (
    get_db,
    get_user_stats,
    load_user,
    update_user_display_name,
    update_user_drippers,
)
from src.data_models import BrewMethod


_logger = logging.getLogger(__name__)

_SANITIZE_NAME_RE = re.compile(r"<[^>]+>")


def _sanitize_name(name: str) -> str:
    """Strip HTML tags from a display name."""
    return _SANITIZE_NAME_RE.sub("", name).strip()


_DRIPPER_OPTIONS = {
    "V60": BrewMethod.V60,
    "Kalita Wave": BrewMethod.KALITA_WAVE,
    "Origami": BrewMethod.ORIGAMI,
}


def render():
    user_id = st.session_state.get("user_id")

    if not user_id:
        st.session_state.page = "auth"
        st.rerun()
        return

    with get_db() as conn:
        user = load_user(conn, user_id)

    if not user:
        st.error("Could not load your profile.")
        return

    name = _sanitize_name(user.get("display_name") or "Brewer")
    st.title(f"Hello, {name}")
    st.caption("Manage your profile, equipment, and account settings.")

    st.markdown("---")

    _render_display_name(user_id, user)
    st.markdown("---")

    _render_drippers(user_id, user)
    st.markdown("---")

    _render_change_password(user_id)
    st.markdown("---")

    _render_brew_stats(user_id)
    st.markdown("---")

    _render_logout()


def _render_display_name(user_id, user):
    st.markdown("### Display Name")
    current = user.get("display_name") or ""
    new_name = st.text_input("Name", value=current, key="profile_display_name")

    if st.button("Save Name", key="save_name_btn"):
        sanitized = _sanitize_name(new_name)
        if sanitized:
            with get_db() as conn:
                update_user_display_name(conn, user_id, sanitized)
            st.success("Display name updated.")
            st.rerun()
        else:
            st.warning("Name cannot be empty or contain only HTML tags.")


def _render_drippers(user_id, user):
    st.markdown("### Your Drippers")
    current_drippers = user.get("drippers") or []

    selected = []
    for label, method in _DRIPPER_OPTIONS.items():
        default = method in current_drippers
        if st.checkbox(label, value=default, key=f"profile_dripper_{method.value}"):
            selected.append(method)

    if st.button("Save Drippers", key="save_drippers_btn"):
        if selected:
            with get_db() as conn:
                update_user_drippers(conn, user_id, selected)
            st.session_state.drippers = selected
            st.success("Drippers updated.")
            st.rerun()
        else:
            st.warning("Please select at least one dripper.")


def _render_change_password(user_id):
    st.markdown("### Change Password")

    with st.form("change_password_form"):
        current_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password")

    if submitted:
        if not current_pw or not new_pw or not confirm_pw:
            st.warning("Please fill in all fields.")
            return

        if new_pw != confirm_pw:
            st.error("New passwords do not match.")
            return

        if len(new_pw) < 8:
            st.error("Password must be at least 8 characters.")
            return

        with get_db() as conn:
            success = change_password(conn, user_id, current_pw, new_pw)

        if success:
            st.success("Password changed.")
        else:
            st.error("Current password is incorrect.")


def _render_brew_stats(user_id):
    st.markdown("### Brew Stats")

    with get_db() as conn:
        stats = get_user_stats(conn, user_id)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Brews", stats["total_brews"])
    with col2:
        st.metric("Avg Score", f"{stats['avg_score']:.1f}")

    if stats["favorite_origins"]:
        st.markdown("**Top Origins:** " + ", ".join(stats["favorite_origins"]))

    if stats["favorite_clusters"]:
        st.markdown("**Favorite Flavors:** " + ", ".join(stats["favorite_clusters"]))


def _render_logout():
    if st.button("Sign Out", type="primary", use_container_width=True):
        cm = st.session_state.get("cookie_manager")
        token = None
        if cm is not None:
            try:
                token = cm.get("session_token")
                cm.delete("session_token")
            except Exception:
                pass

        if token:
            with get_db() as conn:
                auth_logout(conn, token)

        for key in ["user_id", "onboarding", "drippers", "personalization_phase"]:
            st.session_state.pop(key, None)

        st.session_state.page = "landing"
        st.rerun()

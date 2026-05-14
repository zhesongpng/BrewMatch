"""Page: Admin — user management and cross-user brew history.

Only accessible to the hardcoded admin email.
"""
import logging

import streamlit as st

from src.app.db import get_db

logger = logging.getLogger(__name__)

_ADMIN_EMAIL = "zhesong.png@gmail.com"


def is_admin() -> bool:
    """Check if the current logged-in user is the admin."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return False
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row is not None and row["email"] == _ADMIN_EMAIL
    except Exception:
        return False


def render():
    if not is_admin():
        st.error("You do not have access to this page.")
        if st.button("Go to Home"):
            st.session_state.page = "landing"
            st.rerun()
        return

    st.title("Admin Dashboard")
    st.caption(f"Logged in as **{_ADMIN_EMAIL}**")

    tab_users, tab_brews = st.tabs(["Registered Users", "All Brew History"])

    with tab_users:
        _render_users()

    with tab_brews:
        _render_all_brews()


def _render_users():
    from src.app.db import list_all_users

    try:
        with get_db() as conn:
            users = list_all_users(conn)
    except Exception as exc:
        st.error("Could not load users.")
        logger.debug("Admin users load failed", exc_info=True)
        return

    if not users:
        st.info("No registered users yet.")
        return

    st.metric("Total Users", len(users))
    st.markdown("---")

    for u in users:
        email = u["email"] or "(no email)"
        name = u["display_name"] or "(no name)"
        created = _format_timestamp(u["created_at"])
        brews = u["brew_count"]

        st.markdown(
            f"**{name}** — `{email}`  \n"
            f"Joined: {created}  |  Brews: {brews}"
        )


def _render_all_brews():
    from src.app.db import list_all_brews

    try:
        with get_db() as conn:
            brews = list_all_brews(conn)
    except Exception as exc:
        st.error("Could not load brew history.")
        logger.debug("Admin brews load failed", exc_info=True)
        return

    if not brews:
        st.info("No brews recorded yet.")
        return

    st.metric("Total Brews", len(brews))
    st.markdown("---")

    for b in brews:
        feedback = b["feedback"]
        recipe = b["recipe_used"]
        bean = b["bean_profile"]

        thumb = "thumbs up" if feedback.thumbs_up else "thumbs down"
        score_str = f" | Score: {feedback.score}" if feedback.score is not None else ""
        user_label = b["display_name"] or b["email"] or b["user_id"][:8]

        with st.expander(
            f"{user_label} — {bean.origin_country} — {thumb}{score_str}",
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**User:** {b['email']}")
                st.markdown(f"**Recipe:** {recipe.recipe_id.replace('-', ' ').title()}")
                st.markdown(f"**Dose:** {recipe.dose_g:.1f} g  |  **Ratio:** 1:{recipe.ratio:.2f}")
            with col2:
                st.markdown(f"**Method:** {recipe.method.value}")
                st.markdown(f"**Water Temp:** {recipe.water_temp_c:.0f} C")
                st.markdown(f"**Grind:** {recipe.grind_setting}")

            flags = feedback.directional_flags or []
            if flags:
                flag_str = " | ".join(f.replace("_", " ").title() for f in flags)
                st.warning(f"Flags: {flag_str}")
            if feedback.notes:
                st.markdown(f"**Notes:** {feedback.notes}")

            st.caption(_format_timestamp(b["timestamp"]))


def _format_timestamp(ts: str) -> str:
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts

"""Page: Authentication — Login and Register."""
import logging
import re
import sqlite3

import streamlit as st

from src.app.auth import login as auth_login, register as auth_register
from src.app.db import get_db, load_user

_logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def render():
    st.title("Welcome to BrewMatch")
    st.caption("Sign in to save your brew history and get personalized recommendations.")

    # Demo account hint
    st.info(
        "Want to try it out? Sign in with **demo@brewmatch.com** / **brewmatch** "
        "to explore a pre-built profile with 15 brews of history."
    )

    tab_login, tab_register = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        _render_login()

    with tab_register:
        _render_register()


def _render_login():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        if not email or not password:
            st.warning("Please fill in all fields.")
            return

        with get_db() as conn:
            result = auth_login(conn, email, password)

        if result is None:
            st.error("Invalid email or password.")
            return

        user_id, session_token = result
        _on_auth_success(user_id, session_token, "landing")


def _render_register():
    with st.form("register_form"):
        email = st.text_input("Email")
        display_name = st.text_input("Display Name")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Account", use_container_width=True)

    if submitted:
        if not email or not display_name or not password or not confirm:
            st.warning("Please fill in all fields.")
            return

        if not _EMAIL_RE.match(email.strip()):
            st.error("Please enter a valid email address.")
            return

        if password != confirm:
            st.error("Passwords do not match.")
            return

        if len(password) < 8:
            st.error("Password must be at least 8 characters.")
            return

        with get_db() as conn:
            try:
                auth_register(conn, email, display_name, password)
            except sqlite3.IntegrityError:
                st.error("An account with this email already exists.")
                return

            result = auth_login(conn, email, password)

        if result:
            uid, session_token = result
            _on_auth_success(uid, session_token, "onboarding")


def _on_auth_success(user_id: str, session_token: str, redirect_page: str):
    """Set session state and cookie after successful authentication."""
    st.session_state.user_id = user_id

    with get_db() as conn:
        user = load_user(conn, user_id)

    if user and user.get("onboarding"):
        st.session_state.onboarding = user["onboarding"]
    if user and user.get("drippers"):
        st.session_state.drippers = user["drippers"]

    cm = st.session_state.get("cookie_manager")
    if cm is not None:
        try:
            cm.set("session_token", session_token)
        except Exception:
            _logger.warning("Failed to set session cookie — session may not persist", exc_info=True)

    st.session_state.page = redirect_page
    st.rerun()

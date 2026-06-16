"""Regression: a not-yet-loaded cookie must NOT log the user out.

Bug found in the Phase 1 live-persistence work: every time the app reran from a
fresh state (Streamlit Cloud restart, websocket reconnect, tab reload), the
browser cookie that carries the 30-day session token had not been handed back
to the server yet on the first frame (``CookieManager.ready()`` is False). The
old ``restore_session`` returned with no signal, the auth gate saw no
``user_id``, and immediately bounced the user to the login page — the
"it logged me out right as I went to record the taste" symptom.

The fix makes ``restore_session`` return a status the auth gate can act on:

- ``"pending"``   — cookie not loaded yet; the gate MUST wait a frame.
- ``"anonymous"`` — genuinely not logged in; the gate redirects to login.
- ``"restored"``  — a valid user is in session.

These tests pin that contract. The ``"pending"`` case is the actual regression:
if it ever returns ``"anonymous"`` again, mid-session users get logged out.
"""

from __future__ import annotations

import pytest

import src.app.app as app


class _FakeCookieManager:
    """Stand-in for streamlit_cookies_manager.CookieManager."""

    def __init__(self, *, ready: bool, token: str | None = None, raises: bool = False):
        self._ready = ready
        self._token = token
        self._raises = raises

    def ready(self) -> bool:
        if self._raises:
            raise RuntimeError("cookie component errored")
        return self._ready

    def get(self, key: str) -> str | None:
        return self._token


@pytest.fixture
def fake_session(monkeypatch):
    """Replace st.session_state with a plain dict for the duration of a test."""
    state: dict = {}
    monkeypatch.setattr(app.st, "session_state", state)
    return state


@pytest.mark.regression
class TestSessionRestoreCookieRace:
    def test_unready_cookie_returns_pending_not_anonymous(self, fake_session):
        """THE regression: an unloaded cookie must say 'pending', never log out."""
        fake_session["cookie_manager"] = _FakeCookieManager(ready=False)

        assert app.restore_session() == "pending", (
            "restore_session returned a non-pending status while the cookie "
            "component was still loading — the mid-session logout race has "
            "regressed"
        )

    def test_no_cookie_manager_is_anonymous(self, fake_session):
        # cookie manager failed to initialise → genuinely anonymous.
        assert app.restore_session() == "anonymous"

    def test_ready_cookie_without_token_is_anonymous(self, fake_session):
        fake_session["cookie_manager"] = _FakeCookieManager(ready=True, token=None)
        assert app.restore_session() == "anonymous"

    def test_cookie_ready_check_raising_is_anonymous(self, fake_session):
        # A broken cookie component must not wedge the gate on "pending" forever.
        fake_session["cookie_manager"] = _FakeCookieManager(ready=False, raises=True)
        assert app.restore_session() == "anonymous"

    def test_existing_user_in_session_is_restored(self, fake_session):
        fake_session["user_id"] = "user-1"
        assert app.restore_session() == "restored"

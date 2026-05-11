"""Authentication utilities for BrewMatch.

Handles password hashing with bcrypt, session token generation, and
coordinates login/register/logout flows with the database layer.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt

from src.app.db import (
    authenticate_user as _db_authenticate,
    create_session as _db_create_session,
    delete_session as _db_delete_session,
    get_session_user as _db_get_session_user,
    register_user as _db_register,
    update_user_password as _db_update_password,
)

_SESSION_DURATION_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_session_token() -> str:
    return secrets.token_hex(32)


def register(conn, email: str, display_name: str, password: str) -> str:
    """Create a new user account. Returns user_id."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    email = email.strip().lower()
    pw_hash = hash_password(password)
    return _db_register(conn, email, display_name, pw_hash)


def login(conn, email: str, password: str) -> Optional[tuple[str, str]]:
    """Authenticate and create a session. Returns (user_id, session_token) or None."""
    email = email.strip().lower()
    user = _db_authenticate(conn, email)
    if user is None:
        # Timing-safe: dummy bcrypt check so both paths take the same time
        verify_password("timing-dummy", "$2b$12$g4Gtirjlc3e766Ci7iT4j.yjUEZP8DkGy4PKm9Vmz17tuRdkSQ6La")
        return None
    if not verify_password(password, user["password_hash"]):
        return None

    token = generate_session_token()
    expires = datetime.now(timezone.utc) + timedelta(days=_SESSION_DURATION_DAYS)
    _db_create_session(conn, token, user["user_id"], expires.isoformat())
    return user["user_id"], token


def logout(conn, session_token: str) -> None:
    _db_delete_session(conn, session_token)


def restore_session(conn, session_token: str) -> Optional[str]:
    """Look up a session token and return user_id if valid and not expired."""
    return _db_get_session_user(conn, session_token)


def change_password(conn, user_id: str, current_password: str, new_password: str) -> bool:
    """Verify current password and update to new. Returns True on success."""
    from src.app.db import load_user

    user = load_user(conn, user_id)
    if user is None:
        return False
    # load_user no longer returns password_hash; fetch via email lookup.
    email = user.get("email")
    if not email:
        return False
    creds = _db_authenticate(conn, email)
    if creds is None:
        return False
    if not verify_password(current_password, creds["password_hash"]):
        return False
    _db_update_password(conn, user_id, hash_password(new_password))
    return True

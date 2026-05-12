"""SQLite persistence layer for BrewMatch.

Stores user profiles and brew history in SQLite. Supports demo mode via
an in-memory database controlled by the BREWMATCH_DEMO_MODE environment
variable.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.app.utils import bean_to_dict, recipe_to_dict
from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    ExperienceLevel,
    Feedback,
    LearnedPreferences,
    Onboarding,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
    UserStats,
)

# ---------------------------------------------------------------------------
# Path / connection helpers
# ---------------------------------------------------------------------------

_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_FILENAME = "users.db"
_DEMO_DB_URI = "file:brewmatch_demo?mode=memory&cache=shared"
_CLOUD_DB_URI = "file:brewmatch_cloud?mode=memory&cache=shared"


def get_db_path() -> str:
    """Return the database path.

    Returns a URI-style shared-cache in-memory path when
    ``BREWMATCH_DEMO_MODE`` is set to ``true``, otherwise returns
    ``data/users.db`` (relative to repo root). Falls back to an in-memory
    shared-cache URI when the file-based path is not writable (e.g. on
    Streamlit Community Cloud).
    """
    if os.environ.get("BREWMATCH_DEMO_MODE", "").lower() == "true":
        return _DEMO_DB_URI

    file_path = _DEFAULT_DB_DIR / _DB_FILENAME
    # If the database file already exists and is writable, use it.
    if file_path.exists():
        return str(file_path)

    # Try to create the directory and a test file to check writability.
    try:
        _DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
        test_file = _DEFAULT_DB_DIR / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return str(file_path)
    except (OSError, PermissionError):
        # Read-only filesystem (Streamlit Cloud) — use in-memory DB.
        logger.info("data/ not writable, using in-memory database")
        return _CLOUD_DB_URI


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a new SQLite connection with ``row_factory = sqlite3.Row``.

    For file-based databases the parent directory is created automatically.
    In-memory demo mode uses URI-style shared cache so all connections
    reference the same database.
    """
    path = db_path if db_path is not None else get_db_path()
    is_uri = path.startswith("file:")
    if not is_uri and path != ":memory:":
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True)
        parent.chmod(0o700)
    conn = sqlite3.connect(path, timeout=10, uri=is_uri)
    conn.row_factory = sqlite3.Row
    return conn


_logger = logging.getLogger(__name__)

_db_initialized = False


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they do not already exist. Safe to call repeatedly."""
    global _db_initialized
    if _db_initialized:
        return
    init_db(conn)
    _db_initialized = True


@contextmanager
def get_db():
    """Context manager that yields a connection and guarantees cleanup."""
    conn = get_connection()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            _logger.debug("Error closing DB connection", exc_info=True)


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    display_name TEXT,
    password_hash TEXT,
    onboarding_json TEXT NOT NULL,
    preferences_json TEXT,
    drippers_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_CREATE_BREW_HISTORY = """
CREATE TABLE IF NOT EXISTS brew_history (
    brew_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    bean_json TEXT NOT NULL,
    recipe_json TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    session_token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
"""

_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN email TEXT",
    "ALTER TABLE users ADD COLUMN display_name TEXT",
    "ALTER TABLE users ADD COLUMN password_hash TEXT",
    "ALTER TABLE users ADD COLUMN drippers_json TEXT",
]


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and run migrations if they do not already exist."""
    conn.execute(_CREATE_USERS)
    conn.execute(_CREATE_BREW_HISTORY)
    conn.execute(_CREATE_SESSIONS)

    # Indexes for session lookups and cleanup.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")

    # Run idempotent migrations for existing databases.
    existing = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    for sql in _MIGRATIONS:
        col_name = sql.split()[-1].strip('"')
        if col_name not in existing:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists
    conn.commit()


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_onboarding(onboarding: Onboarding) -> str:
    d = asdict(onboarding)
    d["roast_preference"] = onboarding.roast_preference.value
    d["experience_level"] = onboarding.experience_level.value
    return json.dumps(d)


def _deserialize_onboarding(raw: str) -> Onboarding:
    d = json.loads(raw)
    d["roast_preference"] = RoastLevel(d["roast_preference"])
    d["experience_level"] = ExperienceLevel(d["experience_level"])
    return Onboarding(**d)


def _serialize_preferences(prefs: LearnedPreferences) -> str:
    d = asdict(prefs)
    # tuples become lists through JSON; store as lists.
    return json.dumps(d)


def _deserialize_preferences(raw: str) -> LearnedPreferences:
    d = json.loads(raw)
    d["preferred_temp_range"] = tuple(d["preferred_temp_range"])
    d["preferred_ratio_range"] = tuple(d["preferred_ratio_range"])
    return LearnedPreferences(**d)


def _serialize_bean(bean: BeanProfile) -> str:
    return json.dumps(bean_to_dict(bean))


def _deserialize_bean(raw: str) -> BeanProfile:
    d = json.loads(raw)
    d["process"] = Process(d["process"])
    d["roast_level"] = RoastLevel(d["roast_level"])
    return BeanProfile(**d)


def _serialize_recipe(recipe: Recipe) -> str:
    return json.dumps(recipe_to_dict(recipe))


def _deserialize_recipe(raw: str) -> Recipe:
    d = json.loads(raw)
    d["method"] = BrewMethod(d["method"])
    pours = [PourStep(**p) for p in d.pop("pours")]
    sf = d.pop("suitable_for")
    sf["roast_levels"] = [RoastLevel(rl) for rl in sf["roast_levels"]]
    sf["processes"] = [Process(p) for p in sf["processes"]]
    suitable_for = SuitableFor(**sf)
    d.pop("source_url", None)  # handled via kwargs
    return Recipe(pours=pours, suitable_for=suitable_for, **d)


def _serialize_feedback(feedback: Feedback) -> str:
    return json.dumps(asdict(feedback))


def _deserialize_feedback(raw: str) -> Feedback:
    return Feedback(**json.loads(raw))


# Re-export PourStep for deserialization helper
from src.data_models import PourStep  # noqa: E402


# ---------------------------------------------------------------------------
# CRUD: users
# ---------------------------------------------------------------------------

def save_user(
    conn: sqlite3.Connection,
    user_id: str,
    onboarding: Onboarding,
    drippers: Optional[list[BrewMethod]] = None,
) -> None:
    """UPSERT onboarding/drippers for a user, preserving auth columns."""
    now = datetime.now(timezone.utc).isoformat()
    drippers_json = json.dumps([d.value for d in drippers]) if drippers else None
    conn.execute(
        """
        INSERT INTO users
            (user_id, onboarding_json, preferences_json, drippers_json, created_at, updated_at)
        VALUES (?, ?, NULL, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            onboarding_json = excluded.onboarding_json,
            drippers_json = excluded.drippers_json,
            updated_at = excluded.updated_at
        """,
        (user_id, _serialize_onboarding(onboarding), drippers_json, now, now),
    )
    conn.commit()


def load_user(conn: sqlite3.Connection, user_id: str) -> Optional[dict]:
    """Return a user dict or ``None`` if the user does not exist."""
    row = conn.execute(
        """
        SELECT user_id, email, display_name, password_hash,
               onboarding_json, preferences_json, drippers_json
        FROM users WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    result: dict = {
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "onboarding": _deserialize_onboarding(row["onboarding_json"]),
    }
    if row["preferences_json"] is not None:
        result["preferences"] = _deserialize_preferences(row["preferences_json"])
    else:
        result["preferences"] = None
    if row["drippers_json"] is not None:
        result["drippers"] = [BrewMethod(v) for v in json.loads(row["drippers_json"])]
    else:
        result["drippers"] = None
    return result


def update_preferences(
    conn: sqlite3.Connection, user_id: str, prefs: LearnedPreferences
) -> None:
    """UPDATE the preferences_json column for a user."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE users SET preferences_json = ?, updated_at = ? WHERE user_id = ?",
        (_serialize_preferences(prefs), now, user_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Auth: registration, authentication, sessions
# ---------------------------------------------------------------------------


def register_user(
    conn: sqlite3.Connection,
    email: str,
    display_name: str,
    password_hash: str,
) -> str:
    """Create a user row with auth fields. Returns the new user_id."""
    import secrets

    user_id = secrets.token_hex(16)
    now = datetime.now(timezone.utc).isoformat()
    # Create a minimal onboarding for the DB NOT NULL constraint.
    # Will be overwritten when the user completes the onboarding wizard.
    default_onboarding = json.dumps({
        "preferred_clusters": [],
        "roast_preference": "medium-light",
        "experience_level": "beginner",
    })
    conn.execute(
        """
        INSERT INTO users
            (user_id, email, display_name, password_hash, onboarding_json,
             preferences_json, drippers_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?)
        """,
        (user_id, email, display_name, password_hash, default_onboarding, now, now),
    )
    conn.commit()
    return user_id


def authenticate_user(conn: sqlite3.Connection, email: str) -> Optional[dict]:
    """Look up a user by email. Returns dict with user_id and password_hash, or None."""
    row = conn.execute(
        "SELECT user_id, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if row is None:
        return None
    return {"user_id": row["user_id"], "password_hash": row["password_hash"]}


def update_user_password(conn: sqlite3.Connection, user_id: str, new_hash: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
        (new_hash, now, user_id),
    )
    conn.commit()


def update_user_display_name(conn: sqlite3.Connection, user_id: str, display_name: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE users SET display_name = ?, updated_at = ? WHERE user_id = ?",
        (display_name, now, user_id),
    )
    conn.commit()


def update_user_drippers(conn: sqlite3.Connection, user_id: str, drippers: list[BrewMethod]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    drippers_json = json.dumps([d.value for d in drippers])
    conn.execute(
        "UPDATE users SET drippers_json = ?, updated_at = ? WHERE user_id = ?",
        (drippers_json, now, user_id),
    )
    conn.commit()


def update_onboarding(
    conn: sqlite3.Connection,
    user_id: str,
    onboarding: Onboarding,
    drippers: Optional[list[BrewMethod]] = None,
) -> None:
    """UPDATE onboarding and drippers for an existing user (auth columns untouched)."""
    now = datetime.now(timezone.utc).isoformat()
    drippers_json = json.dumps([d.value for d in drippers]) if drippers else None
    conn.execute(
        "UPDATE users SET onboarding_json = ?, drippers_json = ?, updated_at = ? WHERE user_id = ?",
        (_serialize_onboarding(onboarding), drippers_json, now, user_id),
    )
    conn.commit()


def create_session(conn: sqlite3.Connection, token: str, user_id: str, expires_at: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO sessions (session_token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now, expires_at),
    )
    conn.commit()


def get_session_user(conn: sqlite3.Connection, session_token: str) -> Optional[str]:
    """Return user_id for a valid, non-expired session, or None."""
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE session_token = ?",
        (session_token,),
    ).fetchone()
    if row is None:
        return None
    expires = datetime.fromisoformat(row["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        conn.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
        conn.commit()
        return None
    return row["user_id"]


def delete_session(conn: sqlite3.Connection, session_token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
    conn.commit()


# ---------------------------------------------------------------------------
# CRUD: brew history
# ---------------------------------------------------------------------------

def save_brew(conn: sqlite3.Connection, user_id: str, brew: BrewRecord) -> None:
    """INSERT a brew history record."""
    conn.execute(
        """
        INSERT INTO brew_history (brew_id, user_id, timestamp, bean_json, recipe_json, feedback_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            brew.brew_id,
            user_id,
            brew.timestamp,
            _serialize_bean(brew.bean_profile),
            _serialize_recipe(brew.recipe_used),
            _serialize_feedback(brew.feedback),
        ),
    )
    conn.commit()


def load_brew_history(
    conn: sqlite3.Connection, user_id: str, limit: int = 50
) -> list[dict]:
    """Return recent brews for a user, newest first."""
    rows = conn.execute(
        """
        SELECT brew_id, user_id, timestamp, bean_json, recipe_json, feedback_json
        FROM brew_history
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    results: list[dict] = []
    for row in rows:
        results.append(
            {
                "brew_id": row["brew_id"],
                "user_id": row["user_id"],
                "timestamp": row["timestamp"],
                "bean_profile": _deserialize_bean(row["bean_json"]),
                "recipe_used": _deserialize_recipe(row["recipe_json"]),
                "feedback": _deserialize_feedback(row["feedback_json"]),
            }
        )
    return results


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_user_stats(conn: sqlite3.Connection, user_id: str) -> dict:
    """Compute aggregate stats for a user."""
    # Total brews
    total_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM brew_history WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    total_brews = total_row["cnt"] if total_row else 0

    # Average score (only from feedback that has a score)
    avg_row = conn.execute(
        """
        SELECT AVG(CAST(json_extract(feedback_json, '$.score') AS REAL)) AS avg_score
        FROM brew_history
        WHERE user_id = ? AND json_extract(feedback_json, '$.score') IS NOT NULL
        """,
        (user_id,),
    ).fetchone()
    avg_score = round(avg_row["avg_score"], 2) if avg_row and avg_row["avg_score"] is not None else 0.0

    # Favorite origins (top 3)
    origin_rows = conn.execute(
        """
        SELECT json_extract(bean_json, '$.origin_country') AS origin, COUNT(*) AS cnt
        FROM brew_history
        WHERE user_id = ?
        GROUP BY origin
        ORDER BY cnt DESC
        LIMIT 3
        """,
        (user_id,),
    ).fetchall()
    favorite_origins = [r["origin"] for r in origin_rows]

    # Favorite clusters: flatten the flavor_clusters arrays and count
    cluster_rows = conn.execute(
        """
        SELECT json_extract(bean_json, '$.flavor_clusters') AS clusters_json
        FROM brew_history
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()
    cluster_counts: dict[str, int] = {}
    for r in cluster_rows:
        clusters = json.loads(r["clusters_json"])
        for c in clusters:
            cluster_counts[c] = cluster_counts.get(c, 0) + 1
    sorted_clusters = sorted(cluster_counts.items(), key=lambda x: x[1], reverse=True)
    favorite_clusters = [c for c, _ in sorted_clusters[:3]]

    stats = UserStats(
        total_brews=total_brews,
        avg_score=avg_score,
        favorite_origins=favorite_origins,
        favorite_clusters=favorite_clusters,
    )
    return asdict(stats)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def delete_user_data(conn: sqlite3.Connection, user_id: str) -> None:
    """DELETE all data for a user (brews + user row)."""
    conn.execute("DELETE FROM brew_history WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()

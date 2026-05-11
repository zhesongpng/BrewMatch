# Auth System Red Team Synthesis (Post-M5)

**Posture:** L5_DELEGATED
**Date:** 2026-05-11
**Agents:** security-reviewer, code-reviewer, testing-specialist (parallel)

## Executive Summary

| Severity | Count |
| -------- | ----- |
| CRITICAL | 5     |
| HIGH     | 6     |
| MEDIUM   | 8     |
| LOW      | 5     |

Authentication system (email/password registration, cookie-based sessions, profile management) reviewed by three parallel agents. Found 5 critical issues including a latent data-loss bug in `save_user()`, password hash exposure in session state, no email validation (stored XSS vector), no email normalization (case-sensitive duplicates), and a broad exception catch that hides real errors. Zero test coverage across 15 auth functions. All SQL operations are properly parameterized; bcrypt usage is correct; session tokens have adequate entropy.

**Verdict:** Do not ship as-is. Fix 5 CRITICALs + H6 (latent crash) before committing.

---

## CRITICAL Findings

### C1: password_hash leaked into session state via load_user()

**Location:** `src/app/db.py:274-278`
**Source:** security-reviewer

`load_user()` returns a dict that includes `password_hash` as a top-level field. This dict flows through `_on_auth_success` and `restore_session` into application logic. While Streamlit pages don't currently display the hash, it's available in session state and any future rendering or logging call exposes it.

**Fix:** Remove `password_hash` from the `load_user()` return dict. Auth-specific code already uses `authenticate_user()` which returns only `{user_id, password_hash}` for the narrow verification path.

### C2: No email validation — stored XSS vector

**Location:** `src/app/pages/auth.py:45-52`
**Source:** security-reviewer

Registration accepts any string as email with only an `if not email` check. Whitespace, `<script>` tags, and other malformed values are stored and later rendered in `profile.py:62` via `st.caption(email)`. A malicious email or display_name containing HTML/script could be rendered in Streamlit's markdown context.

**Fix:** Add email format validation (regex or `email-validator` library) in `_render_register()`. Validate and sanitize display_name length and strip HTML.

### C3: save_user() silently wipes email, password_hash, display_name

**Location:** `src/app/db.py:242-259`
**Source:** code-reviewer

`save_user` uses `INSERT OR REPLACE` but only sets `user_id`, `onboarding_json`, `preferences_json`, `drippers_json`, `created_at`, and `updated_at`. The `email`, `display_name`, and `password_hash` columns are absent from the VALUES list. Because `INSERT OR REPLACE` deletes the existing row and inserts a new one, any call to `save_user` after a user has registered will silently destroy their credentials.

No current call site triggers this (onboarding.py correctly uses `update_onboarding` instead), but it's a latent data-loss bomb for any future caller.

**Fix:** Rewrite `save_user` to use `INSERT ... ON CONFLICT(user_id) DO UPDATE SET onboarding_json=excluded.onboarding_json, preferences_json=excluded.preferences_json, drippers_json=excluded.drippers_json, updated_at=excluded.updated_at` which preserves all other columns.

### C4: No email normalization — case-sensitive duplicate accounts

**Location:** `src/app/auth.py:43-46`, `src/app/db.py:109`
**Source:** code-reviewer

Emails are stored and queried exactly as typed. `User@Gmail.com` and `user@gmail.com` are treated as different accounts because SQLite's UNIQUE constraint is case-sensitive.

**Fix:** Add `email = email.strip().lower()` in both `register()` and `login()` entry points in `auth.py`.

### C5: Broad exception catch hides real errors and enables user enumeration

**Location:** `src/app/pages/auth.py:65-69`
**Source:** security-reviewer + code-reviewer

The register flow catches bare `Exception` and tells the user "An account with this email already exists." If the database is unavailable, bcrypt throws a memory error, or the disk is full, the user sees a misleading message. The error message also tells an attacker whether an email is registered (user enumeration).

**Fix:** Catch `sqlite3.IntegrityError` specifically for duplicate-email. Return a generic error message for other exceptions.

---

## HIGH Findings

### H1: Zero test coverage for 15 auth functions

**Source:** testing-specialist + code-reviewer

No `test_auth.py` exists. No test file imports any auth function. The `sessions` table is not asserted in the existing `test_db.py` schema test. Security-critical code requires 100% coverage per project testing rules.

**Missing tests (priority order):**

1. `hash_password` / `verify_password` round-trip
2. `register` — valid, duplicate email (IntegrityError), password hashed before storage
3. `login` — valid credentials, wrong password, nonexistent email, session created on success
4. `restore_session` — valid token, expired token (deleted), nonexistent token
5. `change_password` — correct current password updates hash, wrong current password returns False
6. `register_user` / `authenticate_user` / `create_session` / `get_session_user` / `delete_session` in db.py
7. `update_onboarding` preserves email and password_hash
8. `update_user_display_name` / `update_user_drippers` / `update_user_password`

### H2: No rate limiting on login or registration

**Location:** `src/app/auth.py:49-60`, `src/app/pages/auth.py:21-40`
**Source:** security-reviewer + code-reviewer

No failed-attempt tracking, account lockout, CAPTCHA, or exponential backoff. bcrypt rounds=12 (~250ms per check) provides natural throttling, but unlimited attempts are allowed. Combined with C5 (user enumeration via error messages and timing), an attacker can brute-force passwords.

**Fix:** Implement failed-attempt counter per email in the database. Lock account temporarily after 5-10 failures.

### H3: Cookie security flags not verified

**Location:** `src/app/app.py:43-45`
**Source:** security-reviewer

`streamlit-cookies-manager` is used with no explicit configuration for HttpOnly, Secure, or SameSite flags. If the library doesn't set these by default, JavaScript can read the session token, and the cookie is sent on cross-origin requests.

**Fix:** Verify library defaults. If flags are missing, document the gap or switch session persistence approach.

### H4: Expired sessions never cleaned up

**Location:** `src/app/db.py:395-419`
**Source:** security-reviewer + code-reviewer

Sessions are only deleted when someone presents an expired token. No background cleanup runs. Over time, the `sessions` table accumulates stale rows indefinitely. Logout only deletes the specific token, not all tokens for a user.

**Fix:** Add `delete_expired_sessions()` and call it during `init_db`. Consider "logout all devices" functionality.

### H5: \_db_initialized global unreliable for demo mode

**Location:** `src/app/db.py:77-86`
**Source:** code-reviewer

Module-level boolean gates `ensure_schema`. Once True, it short-circuits for all subsequent calls. In demo mode (`:memory:`), a second connection may skip schema initialization if the flag was already set. Not an active bug (app.py calls `init_db` directly), but `ensure_schema` is exported and any future caller will silently skip.

**Fix:** Remove the flag; `CREATE TABLE IF NOT EXISTS` is already idempotent.

### H6: Default onboarding enum value mismatch — latent crash

**Location:** `src/app/db.py:322-326`
**Source:** code-reviewer

Default onboarding stored during registration uses `"medium_light"` (underscore) but `RoastLevel.MEDIUM_LIGHT.value` is `"medium-light"` (hyphen). If `load_user` is called on a user who registered but didn't complete onboarding (e.g., session restore before onboarding finishes), `_deserialize_onboarding` will raise `ValueError`.

Hasn't surfaced because onboarding overwrites the placeholder before `load_user` is called, but any interrupted flow triggers it.

**Fix:** Change `"medium_light"` to `"medium-light"` in the default onboarding dict, or use `_serialize_onboarding(Onboarding(...))` for consistency.

---

## MEDIUM Findings

### M1: Timing oracle on login — user enumeration via response time

**Location:** `src/app/auth.py:49-60`
**Source:** security-reviewer

When user doesn't exist, `login()` returns `None` immediately (no bcrypt check). When user exists but password is wrong, bcrypt runs (~250ms). Attacker can distinguish "no account" from "wrong password" by timing the response.

**Fix:** Perform a dummy bcrypt check when user is not found so both paths take the same time.

### M2: Password validation only on UI layer, not in auth.py

**Location:** `src/app/auth.py:43`, `pages/auth.py:60-61`, `pages/profile.py:119-120`
**Source:** code-reviewer

The 8-character minimum is enforced in Streamlit page code but not in `auth.register()` or `auth.change_password()`. Any direct caller bypasses the check.

**Fix:** Add validation in `auth.register()` and `auth.change_password()`.

### M3: Display name stored/rendered without sanitization

**Location:** `src/app/pages/profile.py:73`, `profile.py:58`
**Source:** security-reviewer

`update_user_display_name` stores raw input. `_render_header` renders via `st.subheader(f"Hello, {name}")`. While Streamlit sanitizes most script injection, certain HTML tags are supported.

**Fix:** Sanitize display name before storage or rendering.

### M4: SQLite data directory/file created without restrictive permissions

**Location:** `src/app/db.py:68-69`
**Source:** security-reviewer

`get_connection()` creates the parent directory with `mkdir(parents=True, exist_ok=True)` but doesn't set `0o700` on the directory or `0o600` on the database file. On shared hosts, other users could read password hashes and session tokens.

**Fix:** Set restrictive permissions after creation.

### M5: user_id uses only 64 bits of entropy

**Location:** `src/app/db.py:317`, `auth.py:40`
**Source:** security-reviewer

`secrets.token_hex(8)` produces 64 bits. Additionally, `generate_user_id()` in `auth.py` is defined but never used — `register_user` in `db.py` generates its own ID directly.

**Fix:** Use the same function consistently, or increase to `token_hex(16)` (128 bits) for production.

### M6: Cookie set() failure silently swallowed

**Location:** `src/app/pages/auth.py:91-95`
**Source:** code-reviewer

If `cm.set("session_token", session_token)` fails, the exception is silently swallowed with `pass`. User is logged in session state but cookie is not set — they lose their session on reload with no feedback.

**Fix:** Log a warning at minimum; show user a message about session persistence.

### M7: onboarding.py silently catches PersonalizationEngine exceptions

**Location:** `src/app/pages/onboarding.py:205-206`
**Source:** code-reviewer

`except Exception: pass` hides any PersonalizationEngine init failure. User sees no error; personalization silently degrades.

**Fix:** Add `logger.warning("PersonalizationEngine init failed", exc_info=True)`.

### M8: No indexes on sessions table

**Location:** `src/app/db.py:132-139`
**Source:** code-reviewer

The sessions table has a PRIMARY KEY on `session_token` but no index on `user_id` or `expires_at`. Bulk cleanup of expired sessions would be slow without an index.

**Fix:** Add `CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)` and `idx_sessions_user ON sessions(user_id)`.

---

## LOW Findings

### L1: No CSRF protection inherent in Streamlit forms

Mitigated by Streamlit's WebSocket-based architecture and internal tokens. Worth noting for future hardening.

### L2: Multiple sessions allowed per user — no concurrent session control

Login creates a new session without invalidating existing ones. Combined with H4, no mechanism to revoke all sessions.

### L3: load_user() called twice during session restore

`restore_session()` calls `get_session_user` then separately calls `load_user` — two DB queries where one would suffice. Also loads `password_hash` unnecessarily (see C1).

### L4: Duplicated logout logic between app.py and profile.py

If one is updated and the other is not, behavior diverges. Should be extracted to a shared function.

### L5: Register flow re-authenticates instead of returning session directly

`register` calls `login` after `register_user` in a separate operation. Safer to return `(user_id, session_token)` directly from the register flow in the same transaction.

---

## Passed Checks

- **SQL Injection:** All database operations use parameterized queries (`?` placeholders). No string concatenation or f-strings in SQL. CLEAN.
- **Password Hashing:** bcrypt with rounds=12. No plaintext storage. CLEAN.
- **Session Token Entropy:** `secrets.token_hex(32)` = 256 bits. CLEAN.
- **No Hardcoded Secrets:** No API keys, passwords, or tokens in source. CLEAN.
- **No Secrets in Logs:** Debug-level logging only, no sensitive data. CLEAN.
- **`.env` in `.gitignore`:** Confirmed. CLEAN.
- **Auth Gate Coverage:** Protected pages redirect unauthenticated users correctly. PUBLIC_PAGES set is appropriate. CLEAN.
- **Password Comparison:** Uses `bcrypt.checkpw()` (constant-time internally). CLEAN.
- **Dependencies:** `bcrypt>=4.0.0` and `streamlit-cookies-manager>=0.2.0` declared in `pyproject.toml`. CLEAN.
- **Test Suite:** 652 passed, 0 failed, 2 warnings (pre-existing Optuna warnings, unrelated). CLEAN.

---

## Fix Priority

**Must fix before commit:**

1. C1 — Strip `password_hash` from `load_user()` return
2. C2 — Add email format validation
3. C3 — Rewrite `save_user()` to use `ON CONFLICT DO UPDATE`
4. C4 — Normalize email to lowercase
5. C5 — Catch `IntegrityError` specifically, not bare `Exception`
6. H6 — Fix `"medium_light"` → `"medium-light"` in default onboarding

**Should fix before commit (tracked follow-ups acceptable for course project):** 7. H1 — Write `test_auth.py` with coverage for all auth functions 8. H4 — Add expired session cleanup to `init_db` 9. M1 — Add dummy bcrypt check for timing-safe login 10. M2 — Move password validation into `auth.py` 11. M6 — Log cookie set failures instead of silent pass

**Can defer:**

- H2 (rate limiting), H3 (cookie flags), H5 (db_initialized flag), M3-M5, M7-M8, all LOWs

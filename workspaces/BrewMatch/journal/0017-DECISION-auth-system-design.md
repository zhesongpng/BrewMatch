# DECISION: Authentication system — email/password with cookie sessions

**Date:** 2026-05-10

## Decision

BrewMatch now has a full authentication system: email/password registration and login, cookie-based session persistence, and a profile management page. No OAuth — keeps the dependency surface small for a course project heading toward commercialization.

## Architecture

- **Password hashing**: bcrypt (rounds=12) via `src/app/auth.py`
- **Session persistence**: `streamlit-cookies-manager` stores a `session_token` in the browser; token maps to a `sessions` table in SQLite with 30-day expiry
- **DB schema**: Added `email`, `display_name`, `password_hash`, `drippers_json` columns to `users` table via idempotent ALTER TABLE migrations; new `sessions` table for session tokens
- **Profile page**: Edit display name, change drippers, change password, view brew stats, sign out

## Key design choices

1. **Cookie manager over URL params**: Cookies persist across browser restarts; URL query params are visible and fragile
2. **`update_onboarding()` over `INSERT OR REPLACE`**: The original `save_user()` would wipe email/password when saving onboarding data. New function updates only onboarding + drippers columns
3. **Auth gate in `main()`**: Pages not in `{landing, auth, demo}` redirect to sign-in if no user_id. Demo mode bypasses auth entirely (`alex-demo` set directly in session state)
4. **Registration auto-logins**: After creating an account, the user is automatically logged in (session token created, cookie set) and routed to onboarding — no separate "please log in" step

## Why

Users were losing their sessions on browser refresh (random UUID in session state only). Drippers were never persisted to the database. This fixes both issues and adds commercial-grade account management.

## Trade-offs

- Cookie manager uses deprecated `st.cache` internally (Streamlit 1.36+ warning) — acceptable for now, will need migration to `st.cache_resource` when the package updates
- Session restoration may take one rerun cycle on cold start (cookie JS needs to execute) — user briefly sees landing page before session restores
- No email verification or password reset — appropriate for current scale, can add later

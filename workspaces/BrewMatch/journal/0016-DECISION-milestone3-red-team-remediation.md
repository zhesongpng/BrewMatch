# Decision: Milestone 3 Red Team Remediation Strategy

**Date:** 2026-05-10
**Context:** Round 2 red team found 2 CRITICAL, 13 HIGH, 16 MEDIUM, 13 LOW issues after Round 1's 3 CRITICAL flow breaks were fixed.

## Decision

Fix all CRITICAL and HIGH findings before demo. Defer MEDIUM/LOW to post-milestone. Prioritize by severity then by user-facing impact.

## Rationale

Round 2 confirmed the core flows (new user onboarding → brew → feedback, demo mode, return user history) all pass. The remaining breaks are security and code-quality — invisible to users in happy path but risky for a commercial product.

## What Was Fixed (10 items)

### Security (6)

- **SEC-C1**: Prompt injection in LLM bean extraction — added `_sanitize_source()` with injection pattern regex + control char stripping
- **SEC-C2**: XSS via `st.markdown()` — added `escape_markdown()` (HTML escape + markdown special char escape), applied across 5 pages
- **SEC-H1**: Exception messages leaking internal paths — replaced all `st.error(f"...{exc}")` with generic messages + server-side logging
- **SEC-H2**: No input length limit on bean description — added `max_chars=2000`
- **SEC-H3**: Demo page DB connections not closed — migrated to `get_db()` context manager
- **SEC-H5**: No rate limiting on LLM extraction — button-disable guard via session state flag

### Code Quality (4)

- **CQ-H1**: DB connection leaks — added `get_db()` context manager, migrated all 8 call sites
- **CQ-H2**: `init_db()` called on every page load — centralized to app startup with `ensure_schema()` singleton
- **CQ-H3**: Serialization inconsistency — added `bean_to_dict()` / `recipe_to_dict()` as single source of truth, fixed latent bug where `current_recipes` stored nested enums without conversion
- **CQ-H5**: Duplicated serialization logic — `db.py` now delegates to shared helpers from `utils.py`

### Spec Compliance (2)

- **SC-H3**: Diagnosis threshold wrong — expanded to match flags OR score ≤ 6 (per spec §4.7)
- **SC-M5**: Brew method filter on history page — added "Filter by method" dropdown

## Key Design Choice: Button-Disable Over Timestamp Rate Limiting

For SEC-H5, initially considered timestamp-based rate limiting (reject if <10s since last extraction). User questioned this — simpler button-disable pattern is more appropriate: set flag → disable button → run extraction → clear flag in `finally`. Prevents double-clicks without blocking legitimate retries.

## Commercial Framing Decision

User confirmed: "ignore the mba course leh. it could potentially be commercialised." This shifts all future decisions — recommend GPT-4o-mini for production LLM (not Ollama-only), treat security findings as production risks (not academic exercise), and build for real users (not grading).

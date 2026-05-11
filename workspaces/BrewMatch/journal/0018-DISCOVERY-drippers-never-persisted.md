# DISCOVERY: Drippers were never persisted to the database

**Date:** 2026-05-10

## Finding

Before this session, dripper selection from onboarding step 4 was stored only in `st.session_state.drippers`. The `save_user()` function in `db.py` did not accept or store a drippers parameter. This means:

1. On browser refresh, dripper selection was lost
2. The recommendation engine had no access to the user's equipment from the database
3. Profile editing of drippers was impossible — there was nothing to edit

## Fix

- Added `drippers_json TEXT` column to `users` table (via migration)
- Updated `save_user()` and `load_user()` to handle drippers
- Added `update_user_drippers()` and `update_onboarding()` DB functions
- Profile page now reads and writes drippers through the database

## Impact

This was a silent data loss bug — users would complete onboarding, select their V60/Kalita/Origami, and the app would use that selection for the current session only. Next visit, the app had no record of their equipment.

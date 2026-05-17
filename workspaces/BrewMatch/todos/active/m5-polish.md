# Milestone 5: Polish & Course Submission

Estimated sessions: 1
Depends on: Milestone 4 complete (evaluation results generated)

---

- [x] **Update brief to reflect 5 directional flags**
  - Already complete — brief Section 4 and Section 5 step 6 already list all
    five flags (too sour / too bitter / too weak / too harsh / astringent)

- [x] **Final demo walkthrough and polish**
  - Full demo flow verified end-to-end programmatically (landing → demo
    login → Alex's profile → bean input → recommendation → brew → feedback
    → diagnosis → history) — all 9 steps green
  - Evaluation dashboard data loading verified (fixed CWD-relative path bug)
  - Both demo mode (in-memory) and production mode (file SQLite) tested;
    three cloud-only bugs found and fixed (in-memory DB wipe, missing demo
    drippers, eval dashboard path) — guarded by 5 regression tests
  - Backup screenshots: NOT done — requires a browser; must be captured
    manually from the live app after this deploy

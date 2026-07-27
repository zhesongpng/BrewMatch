# Red Team — Plan reconciliation (PR #2) + Streamlit dependency trim (PR #3)

Date: 2026-07-27
Phase: /redteam
Scope: everything produced in the 2026-07-27 session, pre-merge
Verdict: **PASS with one disclosed limitation** (PR #3's install is not
test-run locally — see F-4)

Run before merging, at the user's instruction. This record exists in the first
place because [[0037-GAP-goal-d-parity-redteam-record-lost]] found the previous
red-team round left none.

---

## Method

Adversarial checks against the session's own claims, preferring live probes over
code-reading — because the session's own findings warned that "the code exists"
had been quietly accepted as "the feature works".

---

## Live verification (the claims I had only code-read)

| Claim made in PR #2                          | Check                                              | Result                                                                                       |
| -------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Site live at `brewmatch-sepia.vercel.app`    | `curl`                                             | **HTTP 200**, 0.73s                                                                          |
| Brain live at `brewmatch-iki5.onrender.com`  | `curl /health`                                     | **all green** — `retriever_ready`, `predictor_trained`, `diagnosis_engine_ready` all true    |
| "the brain verifies login tokens"            | `GET /bags/<fake-account-id>` with no token        | **HTTP 401** `"sign-in required for this account"` — per-account enforcement is genuinely ON |
| "Supabase email sign-in is wired end-to-end" | grep deployed JS bundle for a Supabase project URL | **found** — the front-end is configured, not shipping dark                                   |

The last two matter most. `lib/supabase.ts` deliberately makes login inert until
both `NEXT_PUBLIC_SUPABASE_*` vars are set, and the brain stays open until
`SUPABASE_JWT_SECRET` / `SUPABASE_URL` is set. Both are set in production. The
Goal C tick was originally made from code-reading alone; it is now backed by
behaviour.

---

## Findings

### F-1 — Two overclaims, both caught and already fixed (INFO)

1. `specs/web-frontend.md` initially listed `/health` among endpoints the
   front-end consumes. It does not — no warm-up ping exists. Corrected before
   commit.
2. The first commit asserted the Streamlit app "is still running as the
   fallback". That was inferred from Goal E being unfinished, never verified.
   Corrected in `6121dd3`; the spec now records deployment status as unknown.

Both are the same failure mode the session was documenting — asserting from
inference rather than evidence. Worth noting that the session committed the
error it had just written a journal entry about.

### F-2 — PR #3 import analysis: no gaps found (PASS)

Adversarial angles tested:

- **Dynamic imports.** `grep -rnE "importlib|__import__"` across the brain's
  entire reachable module set → **zero hits**. The AST walk cannot have missed a
  dependency hidden behind `importlib.import_module("shap")`.
- **Nested / lazy imports.** The walk uses `ast.walk`, which visits
  function-scope imports, not just module-scope. Confirmed by the walk finding
  `lightgbm`, which is imported inside a function in
  `src/taste_predictor/model.py`.
- **`lightgbm` near-miss.** It IS reachable and was correctly kept. Had the trim
  been done by "looks like an ML package the brain doesn't need", it would have
  been removed and the brain would have crashed on model load.
- **Removal direction is safe.** Removing a pin cannot make a genuinely-required
  transitive package disappear — pip still resolves it. The only true risk is a
  package that is required AND required by nothing else, which is exactly what
  the import walk enumerates.

### F-3 — Diff review: no collateral deletions (PASS)

Every deleted line in both PRs is stale text being replaced. Specifically
checked that PR #3 preserved the `pydantic` pin and its rationale when the
surrounding `numba`/`llvmlite` comment block was removed — it did
(`requirements.txt:43-44`).

### F-4 — PR #3's install is NOT test-run (DISCLOSED LIMITATION)

`pip install --dry-run -r requirements.txt` could not be executed: the local
Python 3.12 is broken —

```
ImportError: dlopen(.../pyexpat.cpython-312-darwin.so):
  Symbol not found: _XML_SetAllocTrackerActivationThreshold
```

a Homebrew-vs-system `libexpat` mismatch. This also explains the absent `.venv`
and why the test suite could not be re-run this session. **It is a local machine
defect, not a repo defect** — CI and Render are unaffected.

Consequence: PR #3's evidence is static import analysis only. Mitigations —
Render's build is the live test; the previous deploy remains available for
one-click rollback; and the failure mode is loud (service fails to boot), not
silent.

**Disposition:** accept and merge, then verify `/health` after the redeploy.
Rejected the alternative of blocking the merge until a Python environment is
repaired: fixing the user's Homebrew Python is unrelated work, and the
verification it would buy is weaker than the real deploy.

### F-5 — Goal D remains genuinely unverified (OPEN, by design)

Nothing in this session verified feature parity against the old app. The
desk-check in PR #2 confirms the parity-list features _exist_; it does not
confirm they _behave_. This is correctly recorded as open, not closed.

---

## Not in scope of this round

- Behavioural testing of the React app's flows (that is Goal D).
- The Python test suite (cannot run — see F-4).
- `optuna` / `pandas` removal candidates (flagged in PR #3, deliberately deferred).

---

## For Discussion

1. Two of this session's own claims were overclaims caught only on re-reading
   (F-1). Both were "inferred from an adjacent fact" rather than probed. Is the
   generalisable defence "probe before asserting", or narrower — "never infer a
   deployment's state from the repo"?
2. F-4 accepts a merge on static analysis because the failure is loud and
   reversible. Would that reasoning still hold if the brain had no rollback, or
   is "loud + reversible" doing all the work?
3. The live probes here (curl `/health`, a 401 check, a bundle grep) took under
   a minute and upgraded four code-read claims to verified. Should that probe
   set run at every gate rather than only when someone asks for a red team?

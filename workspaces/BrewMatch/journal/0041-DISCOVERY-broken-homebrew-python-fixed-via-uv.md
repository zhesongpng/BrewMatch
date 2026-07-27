---
type: DISCOVERY
date: 2026-07-27
created_at: 2026-07-27T00:00:00Z
author: co-authored
project: BrewMatch
topic: Homebrew Python 3.12 was broken by a libexpat mismatch; the project venv now runs on uv-managed Python 3.11
phase: implement
tags: [environment, python, homebrew, uv, pyexpat, test-suite, synthetic-data]
---

# DISCOVERY — Broken Homebrew Python, fixed by letting uv own the interpreter

Date: 2026-07-27
Phase: /implement (environment repair, prerequisite for the Goal D parity check)
Status: RESOLVED — 823 tests passing, 0 warnings

## The symptom

No Python work was possible on this machine. `python3 -m pytest` reported no
pytest; `python3 -m pip` crashed outright:

```
ImportError: dlopen(.../pyexpat.cpython-312-darwin.so):
  Symbol not found: _XML_SetAllocTrackerActivationThreshold
  Expected in: /usr/lib/libexpat.1.dylib
```

This is why the 2026-07-27 reconciliation could not verify the test count, and
why the dependency trim (PR #3) shipped on static analysis alone.

## Root cause

A Homebrew packaging bug, not anything in this repo. Homebrew's
`python@3.12` (3.12.13_4) compiled `pyexpat` against **Homebrew's expat 2.8.2**
but linked the resulting `.so` to macOS's **system** `/usr/lib/libexpat.1.dylib`:

```
$ otool -L .../pyexpat.cpython-312-darwin.so
    /usr/lib/libexpat.1.dylib (compatibility version 7.0.0, current version 8.0.0)
```

The symbol `XML_SetAllocTrackerActivationThreshold` was added in expat 2.7.0. The
system dylib does not export it, so `pyexpat` fails to load. Because `pip`
imports `xml.parsers.expat` transitively, pip dies with it — which is what makes
the failure look catastrophic rather than niche.

## The fix, and why not `brew reinstall`

Two facts made the obvious fix the wrong one:

1. **This project pins Python 3.11** (`.python-version`), not 3.12. The broken
   interpreter was never the right one here.
2. **`uv` was already installed** and `uv.lock` is committed.

So the fix was `uv sync --extra dev`, which provisioned uv-managed **Python
3.11.15** and built `.venv` from the lockfile. Nothing system-wide was touched.

Crucially, uv's Python **bundles its own expat** (2.6.3) rather than linking the
system one, so this class of breakage cannot recur in the project venv regardless
of what Homebrew does next.

`brew reinstall python@3.12` was considered and rejected: it is a system-wide
change with its own risk, it buys this project nothing (wrong version), and it
may not even fix an upstream formula bug. **Homebrew's `python@3.12` is still
broken** — anything else on this machine depending on it still needs that
reinstall.

Note: `.venv/bin/pip` does not exist. That is normal for uv-created venvs — use
`uv pip ...` or `uv add ...`.

## Second finding: the suite needs generated data

With a working interpreter, the first full run was **10 failed, 813 passed**. All
ten were in `tests/unit/test_evaluate_pipeline.py`, all one root cause:

```
FileNotFoundError: .../data/synthetic/ratings.csv
```

`data/synthetic/*.csv` is gitignored — it is generated, not committed. The
generator is documented (`README.md:62`) and seeded (`DEFAULT_SEED = 42`), so the
data is reproducible:

```bash
python -m src.data_generator.generator
# Generated 2895 ratings, 200 users, 60 expert labels, 15 Alex brews
```

After generating: **823 passed, 0 failed, 0 warnings.**

This is a fresh-checkout trap rather than a defect — the step is documented, but
the tests fail with a bare `FileNotFoundError` that never mentions the generator.
Anyone cloning fresh will read ten red failures as "the suite is broken".
Recorded in `todos/active/todo-list.md` so the next reader hits the answer before
the symptom.

## Consequences

- The Goal D parity check can now run with a real test suite behind it.
- The verified count is **823**, correcting two stale claims (646, then 761).
- PR #3's dependency trim could now be validated locally if desired, though the
  Render build has already exercised it.

## For Discussion

1. The ten failures were a documented prerequisite presenting as a hard crash.
   Is the right fix a conftest fixture that generates the data on demand, a
   `pytest.skip` with an actionable message, or nothing at all — on the grounds
   that committing generated data or auto-generating it hides a real setup step?
2. uv-managed Python removed a whole class of system-library breakage. Should the
   project state uv as the supported path outright, given `.python-version`,
   `uv.lock` and the Render build already assume it?
3. Counterfactual: had this environment worked on 2026-07-27, PR #3 would have
   shipped with a local install test rather than static analysis. Did the missing
   verification actually change the risk, given the import trace was mechanical
   and Render's build is the real gate?

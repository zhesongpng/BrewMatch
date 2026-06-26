# RISK — Python .gitignore swallows front-end source (`lib/`)

Date: 2026-06-26
Surfaced during: `/redteam` of Goal B2

## What happened

The new B2 brain-client lived at `apps/web/lib/api.ts`. It built cleanly locally,
but `git status` never listed it. Root `.gitignore:13` has the standard Python
build-artifact pattern `lib/` (unanchored), which matches `lib/` at **any** depth —
including the Next.js source dir `apps/web/lib/`.

Because Vercel deploys from git, the file would never have been pushed, and the
production build would have failed with `Cannot find module '@/lib/api'`. The whole
B2 deliverable would have looked done locally and broken on deploy.

## Why it matters (recurring class)

This is a Python-first repo (`.gitignore` is the GitHub Python template) that now
also hosts a JS/TS app under `apps/web/`. Several Python ignore patterns are
unanchored nouns that collide with normal web-project directory names:
`lib/`, `build/`, `dist/`, `share/`, `bin/`, `include/`. Any front-end folder
named like a Python build artifact will be silently swallowed.

## Fix

Added `!apps/web/lib/` negation in `.gitignore` (mirrors the existing
`!.claude/hooks/lib/` line). Verified `git check-ignore` no longer matches and
`git add --dry-run` stages `api.ts`.

## Guard for next time

When adding a front-end folder under `apps/web/`, run:

```
git check-ignore -v apps/web/<folder>/<file>
```

If it prints a match from the root Python `.gitignore`, add a `!apps/web/<folder>/`
negation. A future improvement: anchor the Python patterns to root (`/lib/`,
`/build/`, …) so they only ignore top-level Python artifacts — but that is a
broader change to vet separately.

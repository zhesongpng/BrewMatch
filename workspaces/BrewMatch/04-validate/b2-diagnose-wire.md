# Red Team — Goal B2 (Connect the Diagnose screen to the brain)

Date: 2026-06-26
Posture: **L5_DELEGATED** (fresh repo, no posture.json — Round 1 OPTIONAL; run on
explicit user request). Scope: the B2 change set only.

Files audited:

- `apps/web/lib/api.ts` (new) — typed brain client
- `apps/web/components/DiagnoseFlags.tsx` (new) — interactive Diagnose UI
- `apps/web/app/page.tsx` (modified) — uses the client component
- `apps/web/app/globals.css` (modified) — result/loading/error styles
- `api/main.py` (modified) — CORS lock

## Findings

| ID   | Sev            | Finding                                                                                                                                                                                                                                                                                          | Disposition                                                                                                                      |
| ---- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| B2-1 | CRITICAL       | `apps/web/lib/api.ts` matched root `.gitignore:13` `lib/` (Python build-artifact ignore, unanchored) → file builds locally but would never reach git, so the Vercel deploy (which builds from git) would fail with `Cannot find module '@/lib/api'`. The entire B2 deliverable would not deploy. | **FIXED** — added `!apps/web/lib/` negation in `.gitignore` (mirrors existing `!.claude/hooks/lib/`).                            |
| B2-2 | LOW (accepted) | `DiagnoseFlags.tsx` maps `result.suggestions` without a null-guard.                                                                                                                                                                                                                              | Brain contract always returns the `suggestions` key (rule_based + ml + no_flags all set it). Defensive-only; not changed.        |
| B2-3 | LOW (accepted) | React `key={s.parameter}` could collide if ml mode returned duplicate parameters.                                                                                                                                                                                                                | Rule-based dedupes by parameter; ml mode is unreachable in B2 (flags-only request always falls back to rule_based). Not changed. |
| B2-4 | INFO           | `.result` CSS class referenced in JSX but undefined.                                                                                                                                                                                                                                             | Cosmetic no-op (element also has `.card`). Not changed.                                                                          |

## Verification evidence (literal commands + output)

**Mock/fake data (convergence criterion 6):**

```
grep -rnE 'MOCK_|FAKE_|DUMMY_|SAMPLE_|generate[A-Z]|mockData|Math\.random' lib components app
→ CLEAN: none
```

**Secrets / console / stubs / hardcoded URLs:**

```
grep console.* / sk- / Bearer / TODO|FIXME / onrender.com  →  all CLEAN in B2 surface
```

(The brain base URL is read from `process.env.NEXT_PUBLIC_BREWMATCH_API_URL`; no
hardcoded URL in `lib/` or `components/`.)

**Flag-id ↔ brain rule-key parity:**

```
client FlagId  = {too_sour, too_bitter, too_weak, astringent}
brain rule keys = {too_sour, too_bitter, too_weak, too_harsh, astringent}
→ every client value has a matching rule key (brain's too_harsh is unused, not a gap)
```

**Live end-to-end (each UI flag → real diagnosis from the deployed brain):**

```
too_sour     mode=rule_based cause='Under-extraction'            suggestions=3
too_bitter   mode=rule_based cause='Over-extraction'             suggestions=3
too_weak     mode=rule_based cause='Under-extraction or low dose' suggestions=3
astringent   mode=rule_based cause='Over-extraction'             suggestions=3
```

**CORS lock:**

```
grep allow_origins api/main.py         → allow_origins=allowed_origins  (no leftover "*")
grep brewmatch-sepia api/main.py       → live site present in default allowlist
import test: default origins = [sepia.vercel.app, localhost:3000, 127.0.0.1:3000]
             BREWMATCH_ALLOWED_ORIGINS override = honored
```

**Deploy-shippability (post-fix):**

```
git check-ignore on all 5 B2 files  →  shippable ✓ (none ignored)
git add --dry-run apps/web/lib/      →  add 'apps/web/lib/api.ts'
sibling sweep: only next-env.d.ts + .vercel/project.json ignored (both correct)
```

**Build (Round 1 + Round 2):** `npm run build` → ✓ compiled, types pass, 7/7 routes
prerender, zero warnings.

## Convergence

- Round 1: 1 CRITICAL (B2-1) found + fixed; 3 LOW/INFO accepted.
- Round 2: re-build clean, fix confirmed, no new findings.
- 0 CRITICAL / 0 HIGH outstanding. No mock data. Real end-to-end against live brain.

Note: criterion 5 ("new code has new tests") — `apps/web` has no test harness yet
(none existed pre-B2). Not introduced as a regression by B2; front-end test setup is
a separate workstream, not a B2 acceptance gate. Flagged for the human, not auto-added.

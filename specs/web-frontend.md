# Web Front-End Specification (React / Next.js)

Authority for the Phase 2 React front-end at `apps/web/` — the current
user-facing BrewMatch. The legacy Streamlit app is specified separately in
`user-interface.md` and is pending retirement (Phase 2 Goal E).

Written 2026-07-27 during the plan reconciliation, derived from the code as
built. Where behaviour below is unproven against the live app, it says so.

---

## 1. Overview

BrewMatch's face is a phone-first React app. It contains **no** recommendation,
diagnosis, or learning logic — all of that stays in the Python "brain" and is
reached over HTTP. The front-end's job is screens, on-device gear preferences,
identity, and presentation maths (formatting, rescaling).

The split is deliberate and load-bearing: catalogs and translation tables live in
the brain so there is exactly one source of truth. Copying a catalog into the
front-end is a defect, not a shortcut.

---

## 2. Technology Stack

| Component  | Choice                                     | Notes                                                    |
| ---------- | ------------------------------------------ | -------------------------------------------------------- |
| Framework  | Next.js 16 (App Router) + React 19         | `apps/web/`; see `apps/web/AGENTS.md` — APIs differ from older Next |
| Language   | TypeScript (strict)                        | `npm run build` must pass lint + types                   |
| Styling    | Tailwind CSS v4 + design system            | `app/globals.css`, coffee palette from the approved mockup |
| Hosting    | Vercel                                     | `https://brewmatch-sepia.vercel.app`, auto-deploys from `main` |
| Auth       | Supabase (`@supabase/supabase-js`)         | Email + password, or emailed magic link                  |
| Tests      | Vitest                                     | `npm test`; unit tests in `lib/__tests__/`               |
| Backend    | Python brain over HTTP                     | `https://brewmatch-iki5.onrender.com`                    |

---

## 3. Screens

Five bottom tabs (`components/TabBar.tsx`): Home, Recipes, Coffees, History,
Profile. Diagnose and Sign-in are routes without a tab.

| Route       | Component          | Purpose                                                              |
| ----------- | ------------------ | -------------------------------------------------------------------- |
| `/`         | `app/page.tsx`     | Two-path hub: "Brewing new beans? → get a recipe" / "Last brew tasted off? → fix it" (journal 0033) |
| `/diagnose` | `DiagnoseFlags`    | Five taste flags → cause + concrete fixes                            |
| `/recipes`  | `RecipesFlow`      | Bean details in → ranked recipes → recipe card                       |
| `/coffees`  | `CoffeesFlow`      | Your bags: add, edit, finish, "≈N brews left", "brew this"           |
| `/history`  | `HistoryFlow`      | Past brews, learning phase, "learned from N brews", re-diagnose      |
| `/profile`  | `ProfileFlow`      | Your grinder + calibration, your brewers, brew stats                 |
| `/signin`   | `SignInFlow`       | Create account / sign in / magic link                                |

`LogBrew` is a shared component, not a route.

### 3.1 Diagnose

Five canonical taste flags, matching the brain's `DIRECTIONAL_FLAGS`: too sour,
too bitter, too weak, too harsh, astringent. Flags-only requests get the brain's
rule-based answer. From History, a logged brew's real recipe + beans + user id
are sent as context, which makes the brain run its ML engine and tune the fix to
that brew's actual grind / temperature / dose.

**Invariant:** the flag list here MUST stay in step with `BREW_FLAGS` in
`lib/api.ts` and `DIRECTIONAL_FLAGS` in the brain. A flag that can be logged but
not diagnosed is the regression that shipped once already (fixed in `2309012`).

### 3.2 Recipes

Bean details → `POST /recommend` → ranked recipes. The recipe card shows:

- pour steps with **running water totals** (`poursWithRunningTotal`)
- **clock-format** times, e.g. `1:35` (`clockFormat`)
- an **editable dose** that rescales water proportionally, ratio held fixed
  (`rescaleToDose`)
- grind in **the user's own grinder dial** (§5)
- a **source trust label** — champion / barista / enthusiast

Brewer selection comes from the brewers the user owns (§5), not from a
bean-details dropdown — a brewer is gear, not a bean attribute.

### 3.3 Coffees

Bags are the unit of coffee. Add, edit, finish. Each card shows origin and an
`≈N brews left` estimate the brain computes from grams used against bag size.
"Brew this" hands the bag's beans to Recipes via a one-shot session stash
(`lib/bagHandoff.ts`).

**Known hazard:** that stash is read-and-clear. React Strict Mode double-invokes
mount effects in dev, so the read MUST stay behind a `useRef` latch — see journal
0036 for the failure this caused.

---

## 4. Talking to the brain

`lib/api.ts` is the **only** module that calls the brain. Base URL from
`NEXT_PUBLIC_BREWMATCH_API_URL`.

Endpoints consumed: `/grinders`, `/brewers`, `/recommend`, `/diagnose`,
`/brews/{user}` (GET + POST), `/bags/{user}` (GET, POST, PUT, `/finish`),
`/stats/{user}`, `/learn/{user}`.

The brain also exposes `/health`, but **the front-end never calls it** — there is
no warm-up ping and no health indicator in the UI. The first real request a user
triggers is what wakes the brain, and it pays the cold start (§4.1). A deliberate
warm-up call on app open is an available option if the wait ever needs hiding.

### 4.1 Cold start is a first-class case

The brain sleeps after ~15 minutes idle on Render's free tier and takes up to
~75 seconds to wake. The client allows a 90-second timeout
(`REQUEST_TIMEOUT_MS`) and translates failures into plain language: asleep too
long, network unreachable, or the brain answered with an error. Screens show
loading / error / retry rather than hanging.

### 4.2 Errors never surface raw

Low-level fetch failures MUST be converted to sentences a user can act on. Raw
status codes and stack traces MUST NOT reach the screen.

---

## 5. On-device state

Everything here is `localStorage`, keyed per device, never sent anywhere except
as part of a normal request.

| Key                             | Module                 | Holds                                          |
| ------------------------------- | ---------------------- | ---------------------------------------------- |
| `brewmatch.user_id`             | `identity.ts`          | Anonymous `device-<uuid>` id, created once      |
| `brewmatch.account_id`          | `identity.ts`          | Signed-in account id, mirrored locally          |
| `brewmatch.grinder_id`          | `grinderPref.ts`       | Which grinder you own                           |
| `brewmatch.grinder_calibration` | `grinderCalibration.ts`| Your usual pour-over reading, per grinder       |
| `brewmatch.brewer_ids`          | `brewerPref.ts`        | Which brewers you own (a list)                  |
| `brewmatch.pending_bag`         | `bagHandoff.ts`        | One-shot "brew this bag" hand-off               |

### 5.1 Grind translation

The brain owns the grinder catalog and the microns-per-setting data; the
front-end asks it to translate. Because hand-grinder dials vary by variant and
unit, a fixed chart can't be trusted, so advice is additionally anchored to one
reading the user gives from their own dial ("your usual pour-over setting") and
expressed relative to it. Python↔TypeScript translation parity is guarded by
tests (`93654b2`).

**Invariant:** the catalog MUST NOT be duplicated into the front-end.

---

## 6. Identity and accounts

Two identity modes, one code path — `getUserId()` returns whichever applies:

- **Anonymous:** every device mints `device-<uuid>` on first use. The app is
  fully usable signed-out; the brain stores that device's data under this id.
- **Signed in:** the Supabase account id is mirrored locally and takes
  precedence. Sign-out drops back to the device id, which is never deleted.

### 6.1 Token discipline

`Authorization: Bearer <token>` is attached **only** to account-id requests.
Anonymous `device-` paths never carry one, because the brain 403s a token whose
subject doesn't match the path id — attaching one even briefly during a
sign-in/out transition would fail the request (`efaecce`).

The brain enforces the matching rule at `api/main.py:173` (`resolve_user`): a
token that doesn't match the requested user is 403; an account id with no token
is 401; anonymous device ids need no token.

### 6.2 Login ships dark by default

Until both `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are
set, `getSupabase()` returns null and the app runs anonymously. The sign-in
screens build and deploy but stay inert. The anon key is public by design;
protection comes from Supabase row-level security plus the brain's token check.

### 6.3 Gaps (not built)

- **"Sign in with Google"** — never built, despite being named in the Phase 2
  plan.
- **Explicit password reset** — not built. The magic link covers "I can't get
  in", but is not the same feature.
- **Anonymous → account migration** — brews logged before signing in stay under
  the device id. `identity.ts` preserves the device id specifically so this can
  be built later; it never was.

---

## 7. Testing

Vitest, unit-level, in `lib/__tests__/`: recipe maths (`recipe.test.ts`) and bag
form validation (`bagForm.test.ts`). The harness landed in `93654b2`, closing the
gap journal 0036 flagged.

**Coverage gap:** there are no component or end-to-end tests. The Strict Mode
hand-off bug (0036) was a component-level failure that unit tests cannot catch.
Any regression in a flow — rather than in a pure function — is currently caught
only by hand.

---

## 8. Open items

Tracked in `workspaces/BrewMatch/todos/active/p2-react-vercel-rebuild.md`:

1. Feature-parity check against the Streamlit app, re-run and **committed** (the
   2026-07-05 pass left no record).
2. Switchover and retirement of the Streamlit app (Goal E).
3. The three Goal C gaps in §6.3.

# BrewMatch — Web Front-End

The phone-first React (Next.js) front-end for BrewMatch. This is "the face" of
the app (Phase 2). It talks to the Python "brain" API (Goal A, live on Render)
over the internet — the recommendation, diagnosis, and learning logic stays in
Python and is not duplicated here.

- **Framework:** Next.js (App Router) + TypeScript
- **Styling:** Tailwind CSS v4 + a small design system in `app/globals.css`
  (the coffee palette from the approved Phase 2 mockup)
- **Hosting:** Vercel — live at <https://brewmatch-sepia.vercel.app>
- **Accounts:** Supabase email sign-in (password or magic link)

## Structure

```
app/
  layout.tsx         # app shell (mobile column) + persistent bottom tab bar
  page.tsx           # Home — the two-path hub ("get a recipe" / "fix a cup")
  diagnose/page.tsx  # Diagnose — five taste flags → cause + fixes
  recipes/page.tsx   # Recipes  — beans in, ranked recipes + recipe card
  coffees/page.tsx   # Coffees  — your bags: add, edit, finish, "≈N brews left"
  history/page.tsx   # History  — past brews, learning phase, "learned from N"
  profile/page.tsx   # Profile  — your grinder, your brewers, brew stats
  signin/page.tsx    # Sign in / create account / magic link
  globals.css        # design system (palette, cards, buttons, tab bar …)
components/
  TabBar.tsx         # bottom navigation (active-route highlighting)
  DiagnoseFlags.tsx  RecipesFlow.tsx  CoffeesFlow.tsx
  HistoryFlow.tsx    ProfileFlow.tsx  LogBrew.tsx  SignInFlow.tsx
  icons.tsx          # hand-built vector icons (ported from the mockup)
lib/
  api.ts             # the only place that talks to the brain
  identity.ts        # anonymous device id, or your account id once signed in
  supabase.ts        # Supabase auth client + useAuth()
  recipe.ts          # pure recipe maths (running totals, clock format, rescale)
  grinderCalibration.ts / grinderPref.ts / brewerPref.ts   # on-device gear prefs
  bagForm.ts  bagHandoff.ts  diagnose.ts
  __tests__/         # Vitest unit tests (recipe maths, bag form validation)
```

## Tests

```bash
npm test             # vitest run
npm run test:watch
```

## Local development

```bash
cd apps/web
npm install          # first time only
npm run dev          # http://localhost:3000
```

## Environment

Copy `.env.example` to `.env.local` and adjust if needed:

```
NEXT_PUBLIC_BREWMATCH_API_URL=https://brewmatch-iki5.onrender.com
```

This is the base URL of the Python brain. The same variable is set in Vercel's
project settings. Supabase sign-in also needs `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY` (see `lib/supabase.ts`).

**First request may be slow.** The brain is on Render's free tier and sleeps
after ~15 minutes idle, so the first call after a quiet spell waits ~50 seconds
while it wakes. `lib/api.ts` allows for this in its timeout. The fix, if it ever
matters enough, is Render's paid Starter tier — a scheduled wake-up ping was
tried and removed (GitHub throttled the schedule too much to help).

## Deploying to Vercel

Already deployed — Vercel redeploys automatically on every push to `main`. The
original one-time setup, kept for reference:

1. On vercel.com → **Add New Project** → import the `BrewMatch` repo.
2. Set **Root Directory** to `apps/web` (this is a monorepo; the front-end is
   not at the repo root).
3. Framework preset auto-detects as **Next.js**. No build-command changes needed.
4. Add the environment variables above.
5. Deploy.

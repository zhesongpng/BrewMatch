# BrewMatch — Web Front-End

The phone-first React (Next.js) front-end for BrewMatch. This is "the face" of
the app (Phase 2). It talks to the Python "brain" API (Goal A, live on Render)
over the internet — the recommendation, diagnosis, and learning logic stays in
Python and is not duplicated here.

- **Framework:** Next.js (App Router) + TypeScript
- **Styling:** Tailwind CSS v4 + a small design system in `app/globals.css`
  (the coffee palette from the approved Phase 2 mockup)
- **Hosting target:** Vercel

## Structure

```
app/
  layout.tsx        # app shell (mobile column) + persistent bottom tab bar
  page.tsx          # Diagnose (home)
  recipes/page.tsx  # Recipes  (shell — built out in B3)
  coffees/page.tsx  # Coffees  (shell — built out in B3)
  history/page.tsx  # History  (shell — built out in B3)
  globals.css       # design system (palette, cards, buttons, tab bar …)
components/
  TabBar.tsx        # bottom navigation (active-route highlighting)
  icons.tsx         # hand-built vector icons (ported from the mockup)
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

This is the base URL of the Python brain. The front-end starts calling it in
Goal B2. Set the same variable in Vercel's project settings.

## Deploying to Vercel

1. Push this repo to GitHub (already the case).
2. On vercel.com → **Add New Project** → import the `BrewMatch` repo.
3. Set **Root Directory** to `apps/web` (this is a monorepo; the front-end is
   not at the repo root).
4. Framework preset auto-detects as **Next.js**. No build-command changes needed.
5. Add the environment variable `NEXT_PUBLIC_BREWMATCH_API_URL` (value above).
6. Deploy. Vercel gives you a live URL and redeploys on every push to `main`.

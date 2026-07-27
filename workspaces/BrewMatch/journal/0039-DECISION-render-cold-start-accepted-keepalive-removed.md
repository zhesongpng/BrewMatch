---
type: DECISION
date: 2026-07-27
created_at: 2026-07-27T00:00:00Z
author: co-authored
project: BrewMatch
topic: The brain's ~50s cold start is accepted; the scheduled keep-alive ping was tried and removed
phase: deploy
tags: [phase-2, render, cold-start, ci, github-actions, retro-recorded]
---

# DECISION — Cold start accepted; keep-alive ping removed

Date: 2026-07-27 (retro-recorded; the attempt ran 2026-07-14, reverted 2026-07-15)
Phase: /deploy
Status: ACCEPTED BEHAVIOUR — revisit only if it becomes worth paying for

> **Retro-recorded** during the 2026-07-27 plan reconciliation.

## The symptom

The Python brain runs on Render's free tier, which sleeps a service after
~15 minutes idle. The next request pays a cold start of roughly 50 seconds —
the "loads very long the first time" complaint. Because BrewMatch is used a few
times a day at most, nearly every real visit hits a sleeping brain.

## What was tried

`4403a11` (2026-07-14) added a GitHub Actions workflow pinging `/health` every
10 minutes, on the theory that a service that never idles never sleeps. The repo
is public, so Actions minutes are free.

`0fbe934` (2026-07-15) removed it the next day. It did not work:

- **GitHub throttled the schedule.** A `*/10` cron on a low-traffic repo was
  delivered at roughly hourly intervals — far longer than the ~15 minute sleep
  window. The ping mostly woke an already-asleep brain instead of preventing
  sleep, which is the thing it existed to avoid.
- **It manufactured false alarms.** The ping sometimes timed out mid-wake and
  surfaced as a red workflow run (curl exit 28), so the repo showed failing runs
  for a service that was fine.

Net effect: no benefit, plus noise. Removed.

## The decision

Accept cold-start-on-first-use. The front-end already treats it as a first-class
case rather than a bug — a 90-second request timeout in `apps/web/lib/api.ts`,
and a plain-language message ("The brain took too long to wake up. Give it a
moment and try again.") rather than a spinner that never resolves.

The honest cost: a first-time visitor may wait most of a minute before anything
appears, which is a poor first impression for a product meant to be held
mid-pour. This is a real product problem, not merely a technical one — it is
accepted because the fix costs money, not because it doesn't matter.

**The reliable fix is Render's paid Starter tier** (an always-on instance).
That is a spending decision for the user, deliberately not made unilaterally.
Alternatives considered and rejected: an external uptime pinger (same throttling
class of problem, plus another third-party account), and moving the brain to
another free host (every free tier sleeps; this trades a known problem for an
unknown one).

## For Discussion

1. Counterfactual: had GitHub honoured the 10-minute schedule exactly, the ping
   would have worked — is the lesson "don't use cron for keep-alive", or the
   narrower "GitHub's scheduler is unreliable on low-traffic repos and can't be
   used for anything time-sensitive"?
2. The front-end waits up to 90 seconds against a measured ~50 second wake. Is
   the headroom right, or does a user who has already waited 90 seconds simply
   leave — making a shorter timeout with a clearer "come back in a minute"
   message the better experience?
3. Phase 2 Goal E retires the Streamlit app. Once BrewMatch is the React app
   only, the brain becomes a single point of failure with a 50-second front
   door. Does switchover change the cost-benefit on the paid tier?

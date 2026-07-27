---
type: DECISION
date: 2026-07-27
created_at: 2026-07-27T00:00:00Z
author: co-authored
project: BrewMatch
topic: Grind advice is anchored to one reading from the user's own dial, not a fixed chart
phase: implement
tags: [phase-2, grinder, calibration, microns, parity, retro-recorded]
---

# DECISION — Grind advice anchored to the user's own dial

Date: 2026-07-27 (retro-recorded; the work shipped 2026-07-08, `086bc08`)
Phase: /implement (Phase 2, B3-grinder)
Status: SHIPPED

> **Retro-recorded.** This entry was written during the 2026-07-27 plan
> reconciliation, which found that work between 2026-07-05 and 2026-07-15 had
> shipped without journal entries. Reconstructed from the commit and the code.

## What changed

The first version of grinder-specific grind guidance (2026-06-26, `5194230`)
translated the generic 1–10 grind scale into each grinder's own dial using a
catalog table — "~28 clicks on a Comandante C40". On 2026-07-08 that catalog was
rebuilt on **real measured microns**, and a second mechanism was added: an
on-device **calibration baseline** (`apps/web/lib/grinderCalibration.ts`).

## The decision

A fixed chart cannot be trusted to name an absolute setting on a specific
grinder. Hand grinders vary by variant, production run, and unit; two Comandante
C40s do not necessarily agree, and the same number means different things across
them. Publishing "28 clicks" as if it were universal is confidently wrong.

So the app now asks for **one reading the user gives from their own dial** — the
setting that makes a pour-over they like — stores it per grinder id, and
expresses recipe grinds **relative to it** ("a bit coarser than your usual").
Absolute micron targets still come from the brain's catalog; the user's baseline
is what makes them meaningful on their actual equipment.

Per-grinder storage means switching grinders keeps each one's baseline intact.

## Why this over the alternatives

- **Keep the fixed chart alone** — simplest, and wrong in a way the user can't
  detect. They'd follow "28 clicks", get a bad cup, and conclude the app is
  useless rather than that the chart didn't fit their unit.
- **Ask the user to measure their grounds** — accurate, absurd for a home
  brewer.
- **Ask for one reading they already know** (chosen) — costs one setup question,
  and turns every subsequent instruction into something they can act on without
  translation.

The cost is real: advice is only as good as that one reading, and a user who
gives a careless baseline gets consistently skewed advice with no signal that
anything is wrong. There is currently no way to detect or correct a bad
baseline beyond the user changing it themselves.

## Related

The translation now exists in two languages — Python in the brain, TypeScript in
the front-end — which is a drift risk. That is guarded by parity tests added in
`93654b2` (2026-07-08), the same commit that stood up the Vitest harness whose
absence [[0036-RISK-brew-this-handoff-strictmode-double-invoke]] flagged.
See also [[0034-GAP-web-grind-translation-defensive-rounding]].

## For Discussion

1. Counterfactual: if a user's baseline reading is simply wrong — they name a
   setting they don't actually brew at — every recommendation skews in one
   direction forever. Should the app sanity-check the baseline against the
   catalog's plausible range for that grinder, or would that reintroduce the
   fixed-chart assumption the design deliberately rejected?
2. The catalog lives in the brain as the single source of truth, yet the
   calibration baseline lives only on the device (`localStorage`). Signing in on
   a second phone loses it. Is that acceptable, given the grinder preference
   itself has the same gap?
3. Two implementations of the same translation now exist in two languages,
   guarded by tests. Would moving translation entirely into the brain (one round
   trip per recipe) be simpler than maintaining parity, given the brain already
   costs ~50s on a cold start?

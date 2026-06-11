# DECISION — Editable dose with proportional recipe rescaling folded into B1

Date: 2026-06-11
Phase: /todos (B1 — bag-based brew logging)

## Decision

Two B1 scope decisions locked with the user:

1. **Running-low = Option B (actual dose).** The bag countdown subtracts the
   real grams used per brew, captured at brew time, not a fixed ~15 g estimate.

2. **The brew screen gains an editable dose field that proportionally rescales
   the recipe.** Today `brew_session.py` is a read-only printout — dose, ratio,
   and pour amounts cannot be changed. B1 adds an editable dose (pre-filled with
   the recipe dose); changing it rescales water total and every pour step by
   `your_dose ÷ recipe_dose`, preserving the recipe's ratio.

## Why

The user asked, on inspecting the brew flow, whether the dose could be adjusted
before brewing and whether the recipe would follow. It does not today. One
control fixes three problems at once: the on-screen brew guide matches the cup
actually being made (ratio integrity), the running-low countdown uses a real
number, and the ML model learns from the true dose instead of an assumed 15 g.

## Trade-off considered

The cheaper alternative — record the actual dose WITHOUT rescaling the recipe —
was rejected. It would show pour amounts that don't match the dose, so the user
pours an off-ratio brew and the model still learns from a mismatch. Recording a
number the guide then contradicts is worse than not asking. The extra cost is
real (rescaling `_render_pour_steps` / `_render_summary_bar`, ~80 LOC) but
contained to one screen.

## Consequence

`02-plans/03-bag-based-logging.md` updated (sections 5–6 + decisions table).
B1 sharded into 7 todos in `todos/active/b1-bag-based-logging.md`. Red-team
surfaced one schema gap: `brew_history` needs `bag_id` + `actual_dose_g` columns,
and the already-deployed Supabase/Postgres table needs an `ALTER` migration
(the `IF NOT EXISTS` create path skips existing tables). Folded into B1.2.

Awaiting user approval before /implement.

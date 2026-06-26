// Pure recipe helpers — formatting and the editable-dose rescale.
//
// Kept free of React so they can be reused by the recipe card, the log-a-brew
// screen (B3b), and unit tests. Nothing here calls the brain.

import type { Grinder, PourStep, Recipe } from "./api";

/** Seconds → clock format, e.g. 180 → "3:00", 95 → "1:35". */
export function clockFormat(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(s / 60);
  const seconds = s % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** One pour annotated with the running water total once it's complete. */
export interface PourWithTotal extends PourStep {
  /** Cumulative grams in the brewer after this pour. */
  runningTotal: number;
}

/**
 * Annotate each pour with the running water total so the card can show
 * "pour up to 150 g" rather than just "+50 g".
 */
export function poursWithRunningTotal(pours: PourStep[]): PourWithTotal[] {
  let running = 0;
  return pours.map((p) => {
    running += p.water_g;
    return { ...p, runningTotal: running };
  });
}

/**
 * Rescale a recipe to a new dose, keeping the ratio fixed.
 *
 * Water total and every pour scale by the same factor; grind, temperature,
 * and timings are unchanged. Used by the editable-dose control so a user who
 * brews 18 g instead of the recipe's 15 g sees the right water amounts.
 */
export function rescaleToDose(recipe: Recipe, newDoseG: number): Recipe {
  if (newDoseG <= 0 || recipe.dose_g <= 0) return recipe;
  const factor = newDoseG / recipe.dose_g;
  return {
    ...recipe,
    dose_g: newDoseG,
    water_total_g: recipe.water_total_g * factor,
    pours: recipe.pours.map((p) => ({ ...p, water_g: p.water_g * factor })),
  };
}

/** Round grams for display: whole numbers, no trailing ".0". */
export function grams(value: number): string {
  return `${Math.round(value)} g`;
}

/** A grind setting translated for one grinder, for the recipe card. */
export interface GrindForGrinder {
  /** The dial value alone, e.g. "~74 clicks", "~3.4 rotations". */
  dial: string;
  /** The grinder it's for, e.g. "Kingrinder K6". */
  grinderName: string;
}

/**
 * Translate a recipe's generic 1-10 grind setting into a grinder's own dial.
 *
 * Mirrors src/grinder_catalog.py::get_grinder_display — the catalog numbers
 * live in Python; this only formats them. Returns null when the grinder has no
 * mapping for that step (so the card falls back to the generic "7 / 10").
 */
export function grindForGrinder(
  grinder: Grinder,
  genericSetting: number,
): GrindForGrinder | null {
  // The grind scale is whole steps 1–10 and the mappings are keyed to them.
  // Round and clamp first so a continuous value still translates — mirrors
  // _format_grind in the Streamlit app ("the optimizer produces continuous
  // values"). Backend recipes are already validated ints, so this is defensive.
  const step = Math.max(1, Math.min(10, Math.round(genericSetting)));
  const value = grinder.mapping[String(step)];
  if (value == null) return null;
  // Rotations always read with one decimal (e.g. "3.4"); other scales show
  // whole numbers unless the mapping itself is fractional (Fellow Ode "2.5").
  const valueStr =
    grinder.scale === "rotations" || !Number.isInteger(value)
      ? value.toFixed(1)
      : String(value);
  return {
    dial: `~${valueStr} ${grinder.scale}`,
    grinderName: `${grinder.brand} ${grinder.model}`,
  };
}

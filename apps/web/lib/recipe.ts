// Pure recipe helpers — formatting and the editable-dose rescale.
//
// Kept free of React so they can be reused by the recipe card, the log-a-brew
// screen (B3b), and unit tests. Nothing here calls the brain.

import type { PourStep, Recipe } from "./api";

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

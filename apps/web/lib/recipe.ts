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
  /** The native setting, e.g. "17 clicks", "dial 15". */
  dial: string;
  /** Plain-language coarseness band, e.g. "Medium-coarse (4:6)". */
  band: string;
  /** The grinder it's for, e.g. "Kingrinder K6". */
  grinderName: string;
  /** How to set the grinder (zero it first, read the dial, etc.). */
  howToSet: string;
}

/** Round/clamp a continuous grind to the whole 1–10 steps the catalog is keyed to. */
function grindStep(genericSetting: number): number {
  return Math.max(1, Math.min(10, Math.round(genericSetting)));
}

/** Target grind size in microns. Mirrors src/grinder_catalog.py::microns_for_generic. */
function genericMicrons(genericSetting: number): number {
  return 200 + grindStep(genericSetting) * 100;
}

/** Plain-language coarseness band. Mirrors src/grinder_catalog.py::coarseness_label. */
export function genericGrindBand(genericSetting: number): string {
  const microns = genericMicrons(genericSetting);
  if (microns < 420) return "Fine (espresso)";
  if (microns < 820) return "Medium (pour-over)";
  if (microns < 1020) return "Medium-coarse (4:6)";
  return "Coarse (French press)";
}

/**
 * Plain-language grind label when no grinder is chosen — replaces the old
 * meaningless "7 / 10".
 */
export function genericGrindLabel(genericSetting: number): string {
  return `${genericGrindBand(genericSetting)} · ~${genericMicrons(genericSetting)} µm`;
}

/** A recipe's grind expressed relative to the user's own calibrated baseline. */
export interface RelativeGrind {
  /** e.g. "A bit coarser than your usual". */
  headline: string;
  /** The user's own reading their baseline is anchored to, e.g. "15". */
  usual: string;
  /** Plain-language coarseness band, e.g. "Medium-coarse (4:6)". */
  band: string;
}

// "A pour-over you like" is a medium V60 grind — step 5 on the internal scale.
const POUR_OVER_BASELINE_STEP = 5;

/**
 * Translate a recipe's grind into advice relative to the user's own dial.
 *
 * Hand-grinder charts can't be trusted per unit, so once the user tells us the
 * setting that gives them a good pour-over, we only ever say how much coarser or
 * finer THIS recipe is than that — which is true for every grinder regardless of
 * variant. The absolute number stays the user's; we never invent one.
 */
export function grindRelativeToUsual(
  genericSetting: number,
  usual: string,
): RelativeGrind {
  const delta = grindStep(genericSetting) - POUR_OVER_BASELINE_STEP;
  let headline: string;
  if (delta <= -3) headline = "Notably finer than your usual";
  else if (delta < 0) headline = "A bit finer than your usual";
  else if (delta === 0) headline = "Your usual pour-over setting";
  else if (delta <= 2) headline = "A bit coarser than your usual";
  else headline = "Notably coarser than your usual";
  return { headline, usual, band: genericGrindBand(genericSetting) };
}

/**
 * Translate a recipe's generic 1-10 grind setting into a grinder's own setting.
 *
 * Mirrors src/grinder_catalog.py::grind_for_grinder — the calibration numbers
 * live in Python; this only reads the precomputed per-step display. Returns null
 * when the grinder has no mapping for that step.
 */
export function grindForGrinder(
  grinder: Grinder,
  genericSetting: number,
): GrindForGrinder | null {
  const entry = grinder.mapping[String(grindStep(genericSetting))];
  if (entry == null) return null;
  return {
    dial: entry.native,
    band: entry.band,
    grinderName: `${grinder.brand} ${grinder.model}`,
    howToSet: grinder.how_to_set,
  };
}

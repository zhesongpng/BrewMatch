// Shared display helpers for diagnosis results.
//
// Both the standalone Diagnose tab (`DiagnoseFlags`) and the per-brew "What went
// wrong?" panel in History render the brain's `/diagnose` answer the same way, so
// the formatting lives here in one place.

import type { DiagnoseResult } from "@/lib/api";

// The brain returns raw parameter keys; show them as plain words.
const PARAM_LABELS: Record<string, string> = {
  grind_setting: "Grind",
  water_temp_c: "Water temperature",
  total_time_s: "Brew time",
  dose_g: "Coffee dose",
  ratio: "Coffee-to-water ratio",
};

/** "grind_setting" → "Grind"; unknown keys fall back to a de-underscored form. */
export function paramLabel(key: string): string {
  return PARAM_LABELS[key] ?? key.replace(/_/g, " ");
}

/**
 * The user-facing change for one suggestion. A suggestion is either rule-based
 * (a direction like "finer") or ML (a current → suggested value); show whichever
 * the brain returned.
 */
export function suggestionChange(
  s: DiagnoseResult["suggestions"][number],
): string {
  if (s.direction) return s.direction;
  if (s.suggested_value !== undefined) {
    return s.current_value !== undefined
      ? `${String(s.current_value)} → ${String(s.suggested_value)}`
      : String(s.suggested_value);
  }
  return "";
}

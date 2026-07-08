import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  genericGrindBand,
  genericMicrons,
  grindRelativeToUsual,
} from "@/lib/recipe";

// The canonical grind table lives at the repo root and is shared with the
// Python brain's parity test (tests/regression/test_grind_parity.py). If this
// TS implementation drifts from the table, this test fails; if Python drifts,
// its test fails. Neither side can silently diverge from the other.
interface ParityRow {
  step: number;
  microns: number;
  band: string;
}
const fixture = JSON.parse(
  readFileSync(
    fileURLToPath(
      new URL("../../../../tests/fixtures/grind_parity.json", import.meta.url),
    ),
    "utf8",
  ),
) as { steps: ParityRow[] };

describe("grind parity with the Python brain (shared fixture)", () => {
  it.each(fixture.steps)(
    "step $step → $microns µm, band $band",
    ({ step, microns, band }) => {
      expect(genericMicrons(step)).toBe(microns);
      expect(genericGrindBand(step)).toBe(band);
    },
  );
});

describe("genericMicrons clamps and rounds to whole 1–10 steps", () => {
  it("clamps below 1 and above 10", () => {
    expect(genericMicrons(0)).toBe(genericMicrons(1)); // step floored to 1
    expect(genericMicrons(99)).toBe(genericMicrons(10)); // step capped at 10
  });

  it("rounds a continuous setting to the nearest step", () => {
    expect(genericMicrons(5.4)).toBe(genericMicrons(5));
    expect(genericMicrons(5.5)).toBe(genericMicrons(6));
  });
});

describe("grindRelativeToUsual headline buckets around the pour-over baseline (step 5)", () => {
  it.each([
    [1, "Notably finer than your usual"],
    [3, "A bit finer than your usual"],
    [5, "Your usual pour-over setting"],
    [7, "A bit coarser than your usual"],
    [9, "Notably coarser than your usual"],
  ])("setting %i → %s", (setting, headline) => {
    expect(grindRelativeToUsual(setting, "14").headline).toBe(headline);
  });

  it("passes the user's own reading through untouched", () => {
    expect(grindRelativeToUsual(5, "14 clicks").usual).toBe("14 clicks");
  });
});

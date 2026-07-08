import { describe, expect, it } from "vitest";
import { formatAltitude, parseAltitude, validateBag } from "@/lib/bagForm";

// A complete, valid form; override one field per test to isolate a rule.
function validForm(overrides: Partial<Parameters<typeof validateBag>[0]> = {}) {
  return {
    roaster: "Onyx",
    name: "Ethiopia Guji",
    origin: "Ethiopia",
    flavors: ["Floral"],
    bagSize: 250,
    ...overrides,
  };
}

describe("validateBag", () => {
  it("accepts a complete, valid form", () => {
    expect(validateBag(validForm())).toEqual([]);
  });

  it("requires roaster, name, origin, and at least one flavour", () => {
    expect(validateBag(validForm({ roaster: "  " }))).toContain(
      "Roaster is required.",
    );
    expect(validateBag(validForm({ name: "" }))).toContain(
      "Coffee name is required.",
    );
    expect(validateBag(validForm({ origin: "" }))).toContain(
      "Origin country is required.",
    );
    expect(validateBag(validForm({ flavors: [] }))).toContain(
      "Pick at least one flavour profile.",
    );
  });

  // Regression for red-team F1: a cleared number field reads as 0 in the
  // browser; the form must catch it, not defer to an opaque server 422.
  it.each([
    ["cleared field (0)", 0],
    ["negative", -50],
    ["NaN", Number.NaN],
  ])("rejects a non-positive bag size: %s", (_label, bagSize) => {
    expect(validateBag(validForm({ bagSize }))).toContain(
      "Bag size must be a number greater than 0 (grams).",
    );
  });

  it.each([50, 250, 12.5, 2000])(
    "accepts a positive bag size: %s",
    (bagSize) => {
      expect(validateBag(validForm({ bagSize }))).not.toContain(
        "Bag size must be a number greater than 0 (grams).",
      );
    },
  );
});

describe("altitude round-trip", () => {
  it("parses a single value and a range", () => {
    expect(parseAltitude("1800")).toEqual({ min: 1800, max: 1800 });
    expect(parseAltitude("1500-2000")).toEqual({ min: 1500, max: 2000 });
    expect(parseAltitude(" 1500 - 2000 ")).toEqual({ min: 1500, max: 2000 });
    expect(parseAltitude("")).toEqual({});
    expect(parseAltitude("not-a-number")).toEqual({});
  });

  it("formats stored bounds back to the input string", () => {
    expect(formatAltitude(1800, 1800)).toBe("1800");
    expect(formatAltitude(1500, 2000)).toBe("1500-2000");
    expect(formatAltitude(null, null)).toBe("");
    expect(formatAltitude(1700, null)).toBe("1700");
  });

  // format ∘ parse must be identity for the shapes the edit form prefills, so a
  // bag's stored altitude shows exactly what the user typed when they edit it.
  it.each(["", "1800", "1500-2000"])(
    "format(parse(x)) === x for %s",
    (input) => {
      const { min, max } = parseAltitude(input);
      expect(formatAltitude(min, max)).toBe(input);
    },
  );
});

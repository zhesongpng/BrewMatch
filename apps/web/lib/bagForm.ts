// Pure helpers for the Coffees add/edit bag form. Kept free of React and Next
// imports so they can be unit-tested directly (see lib/__tests__/bagForm.test.ts).

/** Validate the bag form. Returns a list of plain-language error messages. */
export function validateBag({
  roaster,
  name,
  origin,
  flavors,
  bagSize,
}: {
  roaster: string;
  name: string;
  origin: string;
  flavors: string[];
  bagSize: number;
}): string[] {
  const errors: string[] = [];
  if (!roaster.trim()) errors.push("Roaster is required.");
  if (!name.trim()) errors.push("Coffee name is required.");
  if (!origin.trim()) errors.push("Origin country is required.");
  if (flavors.length === 0) errors.push("Pick at least one flavour profile.");
  // A cleared number field reads as 0; catch it here with a plain message
  // instead of letting the server reject it with an opaque "try again" error.
  if (!Number.isFinite(bagSize) || bagSize <= 0) {
    errors.push("Bag size must be a number greater than 0 (grams).");
  }
  return errors;
}

/**
 * Format a stored altitude min/max back into the single input string, the
 * inverse of parseAltitude — so editing a bag shows what the user typed.
 * Equal bounds collapse to one number; differing bounds show as "min-max".
 */
export function formatAltitude(
  min?: number | null,
  max?: number | null,
): string {
  if (min == null && max == null) return "";
  if (min != null && max != null) {
    return min === max ? String(min) : `${min}-${max}`;
  }
  return String(min ?? max);
}

/** Parse an altitude string like "1800" or "1500-2000" into a min/max range. */
export function parseAltitude(s: string): { min?: number; max?: number } {
  const text = s.trim().replace(/\s/g, "");
  if (!text) return {};
  if (text.includes("-")) {
    const [a, b] = text.split("-", 2);
    const min = parseInt(a, 10);
    const max = parseInt(b, 10);
    if (Number.isNaN(min) || Number.isNaN(max)) return {};
    return { min, max };
  }
  const v = parseInt(text, 10);
  if (Number.isNaN(v)) return {};
  return { min: v, max: v };
}

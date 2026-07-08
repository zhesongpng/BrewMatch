// The user's own "usual pour-over setting" per grinder, remembered on-device.
//
// Hand-grinder dials vary by variant and unit, so a fixed chart can't be trusted
// for a specific grinder. Instead we anchor to ONE reading the user gives from
// their real dial — the setting that makes a pour-over they like — and show every
// recipe grind relative to it ("a bit coarser than your usual"). Stored per
// grinder id so switching grinders keeps each one's baseline. Same storage style
// as grinderPref.ts so the Profile and recipe flows never drift on the key.

const CALIBRATION_KEY = "brewmatch.grinder_calibration";

/** grinder id -> the user's usual pour-over reading in their own dial (free text). */
type Calibration = Record<string, string>;

function readAll(): Calibration {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(CALIBRATION_KEY);
    return raw ? (JSON.parse(raw) as Calibration) : {};
  } catch {
    return {};
  }
}

/** The user's usual pour-over reading for this grinder, or "" if none set. */
export function readGrinderCalibration(grinderId: string): string {
  if (!grinderId) return "";
  return readAll()[grinderId] ?? "";
}

/** Save (or clear, when reading is empty) the usual pour-over reading for a grinder. */
export function writeGrinderCalibration(
  grinderId: string,
  reading: string,
): void {
  if (typeof window === "undefined" || !grinderId) return;
  const all = readAll();
  const trimmed = reading.trim();
  if (trimmed) all[grinderId] = trimmed;
  else delete all[grinderId];
  window.localStorage.setItem(CALIBRATION_KEY, JSON.stringify(all));
}

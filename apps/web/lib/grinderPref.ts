// The user's chosen grinder, remembered on-device.
//
// Until accounts exist (Goal C), this is where the grinder preference lives, so
// every recipe shows its grind in that grinder's own dial. The Profile screen
// and the recipe flow both read and write it through here, so they never drift
// to different storage keys.

const GRINDER_KEY = "brewmatch.grinder_id";

/** The saved grinder id, or "" if none chosen. Browser-only; "" on the server. */
export function readGrinderId(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(GRINDER_KEY) ?? "";
}

/** Save the chosen grinder id; passing "" clears the preference. */
export function writeGrinderId(id: string): void {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(GRINDER_KEY, id);
  else window.localStorage.removeItem(GRINDER_KEY);
}

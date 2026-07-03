// The brewers the user owns, remembered on-device.
//
// A brewer is gear (like the grinder), independent of the beans — and unlike the
// grinder, a user can own several. So this stores a LIST of brewer ids. The
// Profile screen and the recipe flow both read and write it through here, so
// they never drift to different storage keys. Mirrors lib/grinderPref.ts.

const BREWERS_KEY = "brewmatch.brewer_ids";

/** The owned brewer ids, or [] if none chosen. Browser-only; [] on the server. */
export function readBrewerIds(): string[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(BREWERS_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    // Guard against a malformed value written by an older build or hand-edit.
    if (Array.isArray(parsed)) {
      return parsed.filter((x): x is string => typeof x === "string");
    }
    return [];
  } catch {
    return [];
  }
}

/** Save the owned brewer ids; passing [] clears the preference. */
export function writeBrewerIds(ids: string[]): void {
  if (typeof window === "undefined") return;
  if (ids.length > 0)
    window.localStorage.setItem(BREWERS_KEY, JSON.stringify(ids));
  else window.localStorage.removeItem(BREWERS_KEY);
}

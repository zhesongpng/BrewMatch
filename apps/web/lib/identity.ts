// On-device identity + signed-in account id.
//
// Every device gets its own anonymous id so the brain can save and recall that
// device's brews, history, and learning signal even when nobody is signed in.
// The id is generated once and remembered in on-device storage.
//
// When someone signs in (Goal C), their Supabase account id is mirrored here so
// getUserId() returns the account id instead of the device id — nothing that
// calls getUserId() needs to change, only which id it gets. On sign-out we drop
// back to the device id. The device id is never deleted, so a future migration
// (Goal C step 3) can still find and move this device's prior brews.

const DEVICE_ID_KEY = "brewmatch.user_id";
const ACCOUNT_ID_KEY = "brewmatch.account_id";

/**
 * Return this device's anonymous id, creating one on first use.
 *
 * Browser-only — returns "" on the server (there is no device there).
 */
export function getDeviceId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    // The "device-" prefix marks this as an anonymous on-device id, so the brain
    // (and the migration step) can tell it apart from a real account id.
    id = `device-${crypto.randomUUID()}`;
    window.localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

/**
 * Return the id the brain should key this user's data on.
 *
 * The signed-in account id when signed in, otherwise this device's anonymous id.
 * Browser-only — returns "" on the server. Prefer the reactive `userId` from
 * `useAuth()` in components; this sync form is for non-React call sites.
 */
export function getUserId(): string {
  if (typeof window === "undefined") return "";
  const accountId = window.localStorage.getItem(ACCOUNT_ID_KEY);
  if (accountId) return accountId;
  return getDeviceId();
}

/** Mirror the signed-in account id locally so getUserId() returns it. */
export function setAccountId(accountId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCOUNT_ID_KEY, accountId);
}

/** Drop back to the device id on sign-out. The device id itself is preserved. */
export function clearAccountId(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCOUNT_ID_KEY);
}

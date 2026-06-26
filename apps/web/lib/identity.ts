// On-device identity.
//
// Until real accounts land (Goal C), each device gets its own anonymous id so
// the brain can save and recall that device's brews, history, and learning
// signal. The id is generated once and remembered in on-device storage.
//
// When login arrives, the authenticated account id replaces this value and the
// device's prior brews can be migrated to the account — nothing that calls
// getUserId() needs to change, only where the id comes from.

const USER_ID_KEY = "brewmatch.user_id";

/**
 * Return this device's anonymous user id, creating one on first use.
 *
 * MUST be called from the browser (client components / event handlers). On the
 * server there is no device, so it returns "" — callers should read it in an
 * effect or at submit time, never during server render.
 */
export function getUserId(): string {
  if (typeof window === "undefined") return "";
  let id = window.localStorage.getItem(USER_ID_KEY);
  if (!id) {
    // The "device-" prefix marks this as an anonymous on-device id, so a future
    // login flow can tell it apart from a real account id when migrating.
    id = `device-${crypto.randomUUID()}`;
    window.localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

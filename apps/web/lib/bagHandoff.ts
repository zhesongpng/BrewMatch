// Hand-off between the Coffees screen and the Recipes flow.
//
// "Brew this" on a saved bag can't pass React state across a route change, so
// the chosen bag's beans + id are stashed here and picked up when the recipes
// flow mounts. sessionStorage (not localStorage) so the hand-off is one-shot
// per tab and doesn't linger after the brew.

import type { BeanInput } from "@/lib/api";

const PENDING_BAG_KEY = "brewmatch.pending_bag";

export interface PendingBag {
  bagId: string;
  bean: BeanInput;
}

/** Stash the bag the user tapped "Brew this" on, before navigating to /recipes. */
export function setPendingBag(pending: PendingBag): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(PENDING_BAG_KEY, JSON.stringify(pending));
}

/**
 * Read and clear the pending bag (one-shot). Returns null if none is waiting,
 * or if the stored value is unreadable — either way the recipes flow just falls
 * back to its normal bean form.
 */
export function takePendingBag(): PendingBag | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(PENDING_BAG_KEY);
  if (!raw) return null;
  window.sessionStorage.removeItem(PENDING_BAG_KEY);
  try {
    return JSON.parse(raw) as PendingBag;
  } catch {
    return null;
  }
}

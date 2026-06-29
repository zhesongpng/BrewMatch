// Supabase browser client (Goal C — login).
//
// The login service lives in the same Supabase project as the database. Its two
// public connection values come from the environment so the same build can point
// at any project:
//
//   NEXT_PUBLIC_SUPABASE_URL       the project's URL
//   NEXT_PUBLIC_SUPABASE_ANON_KEY  the project's anon (public) key
//
// Both are *public* by design — the anon key is meant to ship in the browser;
// real protection comes from Supabase row-level security + the brain's token
// check, not from hiding this key.
//
// Until BOTH are set, getSupabase() returns null and the app keeps working
// anonymously (on-device ids only). This is what lets login ship dark: the
// sign-in screens build and deploy, but stay inert until the env vars land.

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let _client: SupabaseClient | null = null;

/** True once both public Supabase values are present (login is available). */
export function isAuthConfigured(): boolean {
  return Boolean(URL && ANON_KEY);
}

/**
 * The shared browser Supabase client, or null when login isn't configured yet
 * or when called on the server. Singleton so the session is restored once.
 */
export function getSupabase(): SupabaseClient | null {
  if (typeof window === "undefined") return null;
  if (!URL || !ANON_KEY) return null;
  if (!_client) {
    _client = createClient(URL, ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return _client;
}

/**
 * The current signed-in user's access token, or "" when signed out / not
 * configured. Used to attach `Authorization: Bearer <token>` to brain requests.
 */
export async function getAccessToken(): Promise<string> {
  const sb = getSupabase();
  if (!sb) return "";
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? "";
}

"use client";

// Auth context (Goal C — login).
//
// Wraps the app so any component can read the signed-in state and act on it.
// The single source of truth for "who is this user" is `userId`: the signed-in
// account id when signed in, otherwise this device's anonymous id. Data screens
// read `userId` and refetch when it changes (e.g. after sign-in / sign-out), so
// the right person's coffees and brews show without a manual refresh.
//
// When Supabase isn't configured (no env vars yet) the provider stays in
// anonymous mode: `configured` is false, `userId` is the device id, and the
// sign-in actions return a friendly "not available yet" message. This is what
// lets the sign-in screens ship before the dashboard setup is done.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getSupabase, isAuthConfigured } from "@/lib/supabase";
import { clearAccountId, getDeviceId, setAccountId } from "@/lib/identity";

/** Result of a sign-in / sign-up attempt — plain-language error or success. */
export interface AuthResult {
  error?: string;
  /** Sign-up only: true when the user must confirm their email before logging in. */
  needsConfirmation?: boolean;
}

interface AuthContextValue {
  /** True once the initial session check has finished. */
  ready: boolean;
  /** True when Supabase login is configured (env vars present). */
  configured: boolean;
  /** The signed-in user's email, or null when anonymous. */
  email: string | null;
  /** Account id when signed in, else this device's anonymous id. */
  userId: string;
  signInWithPassword(email: string, password: string): Promise<AuthResult>;
  signUpWithPassword(email: string, password: string): Promise<AuthResult>;
  sendMagicLink(email: string): Promise<AuthResult>;
  signOut(): Promise<void>;
}

const NOT_CONFIGURED: AuthResult = {
  error:
    "Sign-in isn't switched on yet. You can keep using BrewMatch as you are.",
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const configured = isAuthConfigured();
  const [ready, setReady] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>("");

  useEffect(() => {
    let active = true;
    const sb = getSupabase();

    // Anonymous mode (no Supabase): settle on the device id. Deferred to a
    // microtask so we never call setState synchronously inside the effect body.
    if (!sb) {
      const deviceId = getDeviceId();
      queueMicrotask(() => {
        if (!active) return;
        setUserId(deviceId);
        setReady(true);
      });
      return () => {
        active = false;
      };
    }

    // Apply a session (or its absence) to local state + the id mirror, so both
    // the reactive userId and the sync getUserId() agree.
    const apply = (
      session: Awaited<
        ReturnType<typeof sb.auth.getSession>
      >["data"]["session"],
    ) => {
      if (!active) return;
      if (session?.user) {
        setAccountId(session.user.id);
        setEmail(session.user.email ?? null);
        setUserId(session.user.id);
      } else {
        clearAccountId();
        setEmail(null);
        setUserId(getDeviceId());
      }
    };

    sb.auth.getSession().then(({ data }) => {
      apply(data.session);
      if (active) setReady(true);
    });

    // Keep state in sync with later sign-in / sign-out / token-refresh events.
    const { data: sub } = sb.auth.onAuthStateChange((_event, session) => {
      apply(session);
    });

    return () => {
      active = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const signInWithPassword = useCallback(
    async (e: string, password: string): Promise<AuthResult> => {
      const sb = getSupabase();
      if (!sb) return NOT_CONFIGURED;
      const { error } = await sb.auth.signInWithPassword({
        email: e.trim(),
        password,
      });
      return error ? { error: error.message } : {};
    },
    [],
  );

  const signUpWithPassword = useCallback(
    async (e: string, password: string): Promise<AuthResult> => {
      const sb = getSupabase();
      if (!sb) return NOT_CONFIGURED;
      const { data, error } = await sb.auth.signUp({
        email: e.trim(),
        password,
      });
      if (error) return { error: error.message };
      // When email confirmation is on, sign-up returns a user but no session.
      return { needsConfirmation: !data.session };
    },
    [],
  );

  const sendMagicLink = useCallback(async (e: string): Promise<AuthResult> => {
    const sb = getSupabase();
    if (!sb) return NOT_CONFIGURED;
    const { error } = await sb.auth.signInWithOtp({
      email: e.trim(),
      options: { emailRedirectTo: window.location.origin },
    });
    return error ? { error: error.message } : {};
  }, []);

  const signOut = useCallback(async (): Promise<void> => {
    const sb = getSupabase();
    if (sb) await sb.auth.signOut();
    // onAuthStateChange clears state, but do it eagerly for instant feedback.
    clearAccountId();
    setEmail(null);
    setUserId(getDeviceId());
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      configured,
      email,
      userId,
      signInWithPassword,
      signUpWithPassword,
      sendMagicLink,
      signOut,
    }),
    [
      ready,
      configured,
      email,
      userId,
      signInWithPassword,
      signUpWithPassword,
      sendMagicLink,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Read the auth state. Must be called under <AuthProvider> (it wraps the app). */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

type Mode = "signin" | "signup" | "magic";

const MIN_PASSWORD = 6;

export default function SignInFlow() {
  const router = useRouter();
  const { configured, ready, email: signedInEmail, signOut } = useAuth();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { signInWithPassword, signUpWithPassword, sendMagicLink } = useAuth();

  // Already signed in — offer a way back and a way out, no form needed.
  if (ready && signedInEmail) {
    return (
      <section className="card">
        <div className="eyebrow">Your account</div>
        <h2 className="scr">You&apos;re signed in</h2>
        <p className="sub">
          Signed in as <strong>{signedInEmail}</strong>. Your coffees and brews
          now follow you to any device.
        </p>
        <Link className="btn primary" href="/profile">
          Go to your profile
        </Link>
        <button
          className="btn ghost"
          type="button"
          onClick={async () => {
            await signOut();
            router.refresh();
          }}
        >
          Sign out
        </button>
      </section>
    );
  }

  // Login isn't switched on yet — explain plainly, don't show a dead form.
  if (ready && !configured) {
    return (
      <section className="card">
        <div className="eyebrow">Your account</div>
        <h2 className="scr">Sign-in is coming soon</h2>
        <p className="sub">
          Accounts aren&apos;t switched on just yet. You can keep using
          BrewMatch as you are — everything you log is saved on this device, and
          will move to your account when sign-in goes live.
        </p>
        <Link className="btn primary" href="/">
          Back to brewing
        </Link>
      </section>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setError("Enter your email address.");
      return;
    }
    if (mode !== "magic" && password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }

    setBusy(true);
    try {
      if (mode === "magic") {
        const { error: err } = await sendMagicLink(cleanEmail);
        if (err) setError(err);
        else
          setNotice(
            "Check your email — we sent a one-tap sign-in link to " +
              cleanEmail +
              ".",
          );
        return;
      }

      if (mode === "signup") {
        const { error: err, needsConfirmation } = await signUpWithPassword(
          cleanEmail,
          password,
        );
        if (err) {
          setError(err);
          return;
        }
        if (needsConfirmation) {
          setNotice(
            "Almost there — check your email to confirm your address, then sign in.",
          );
          setMode("signin");
          setPassword("");
          return;
        }
        // Signed up and signed in immediately (email confirmation off).
        router.push("/profile");
        router.refresh();
        return;
      }

      // mode === "signin"
      const { error: err } = await signInWithPassword(cleanEmail, password);
      if (err) {
        setError(err);
        return;
      }
      router.push("/profile");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  const isSignup = mode === "signup";
  const isMagic = mode === "magic";

  return (
    <section className="card">
      <div className="eyebrow">Your account</div>
      <h2 className="scr">{isSignup ? "Create your account" : "Sign in"}</h2>
      <p className="sub">
        {isSignup
          ? "Make an account so your coffees, brews, and learning follow you to any device."
          : "Sign in to pick up your coffees and brews on any device."}
      </p>

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        {!isMagic && (
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              placeholder={`At least ${MIN_PASSWORD} characters`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
        )}

        {error && (
          <p className="sub" style={{ color: "var(--danger, #c0392b)" }}>
            {error}
          </p>
        )}
        {notice && <p className="sub">{notice}</p>}

        <button className="btn primary" type="submit" disabled={busy}>
          {busy
            ? "One moment…"
            : isMagic
              ? "Email me a sign-in link"
              : isSignup
                ? "Create account"
                : "Sign in"}
        </button>
      </form>

      {/* Switch between sign in, create account, and magic link. */}
      <div style={{ marginTop: 16 }}>
        {mode !== "signin" && (
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              setMode("signin");
              setError(null);
              setNotice(null);
            }}
          >
            Already have an account? Sign in
          </button>
        )}
        {mode !== "signup" && (
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              setMode("signup");
              setError(null);
              setNotice(null);
            }}
          >
            New here? Create an account
          </button>
        )}
        {mode !== "magic" && (
          <button
            className="btn ghost"
            type="button"
            onClick={() => {
              setMode("magic");
              setError(null);
              setNotice(null);
            }}
          >
            Sign in with a one-tap email link instead
          </button>
        )}
      </div>
    </section>
  );
}

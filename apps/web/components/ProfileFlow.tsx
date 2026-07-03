"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getBrewers,
  getGrinders,
  getStats,
  type Brewer,
  type Grinder,
  type UserStats,
} from "@/lib/api";
import { readGrinderId, writeGrinderId } from "@/lib/grinderPref";
import { readBrewerIds, writeBrewerIds } from "@/lib/brewerPref";
import { useAuth } from "@/lib/auth";

type Status = "loading" | "ready" | "error";

export default function ProfileFlow() {
  const router = useRouter();
  const { ready, userId, email, configured, signOut } = useAuth();
  const [status, setStatus] = useState<Status>("loading");
  const [grinders, setGrinders] = useState<Grinder[]>([]);
  const [brewers, setBrewers] = useState<Brewer[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Read the saved gear lazily so it survives reloads without a hydration
  // mismatch (this screen isn't server-rendered with the values).
  const [grinderId, setGrinderId] = useState<string>(() => readGrinderId());
  const [brewerIds, setBrewerIds] = useState<string[]>(() => readBrewerIds());

  // Refetch when the signed-in user changes (sign-in / sign-out) so the right
  // person's stats show without a manual refresh.
  useEffect(() => {
    if (!ready || !userId) return;
    let cancelled = false;
    Promise.all([getGrinders(), getBrewers(), getStats(userId)])
      .then(([g, b, s]) => {
        if (cancelled) return;
        setGrinders(g);
        setBrewers(b);
        setStats(s);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Couldn't load your profile.",
        );
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [ready, userId]);

  function chooseGrinder(id: string) {
    setGrinderId(id);
    writeGrinderId(id);
  }

  // Tick a brewer on or off. Users own several, so this toggles membership in
  // the owned-brewers list rather than replacing a single value.
  function toggleBrewer(id: string) {
    setBrewerIds((cur) => {
      const next = cur.includes(id)
        ? cur.filter((x) => x !== id)
        : [...cur, id];
      writeBrewerIds(next);
      return next;
    });
  }

  if (status === "loading") {
    return (
      <section className="card">
        <div className="status">
          <div className="spinner" aria-hidden="true" />
          <div>
            <div className="t">Loading your profile…</div>
            <div className="d">
              The first load can take a moment while the brain wakes up.
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (status === "error") {
    return (
      <section className="card error">
        <div className="t">Couldn&apos;t load your profile</div>
        <p className="sub">{error}</p>
      </section>
    );
  }

  const handGrinders = grinders.filter((g) => g.type === "hand");
  const electricGrinders = grinders.filter((g) => g.type === "electric");

  return (
    <>
      {/* Brew stats */}
      <section className="card">
        <div className="eyebrow">Your brewing so far</div>
        {stats && stats.total_brews > 0 ? (
          <>
            <h2 className="scr">
              {stats.total_brews} {stats.total_brews === 1 ? "brew" : "brews"}{" "}
              logged
            </h2>
            <div className="pill-grid">
              <div className="pill">
                <div className="k">Total brews</div>
                <div className="v">{stats.total_brews}</div>
              </div>
              <div className="pill">
                <div className="k">Avg rating</div>
                <div className="v">{stats.avg_score.toFixed(1)} / 10</div>
              </div>
            </div>

            {stats.favorite_origins.length > 0 && (
              <div className="field" style={{ marginTop: 16, marginBottom: 0 }}>
                <label>Top origins</label>
                <div className="badge-row">
                  {stats.favorite_origins.map((o) => (
                    <span key={o} className="badge">
                      {o}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {stats.favorite_clusters.length > 0 && (
              <div className="field" style={{ marginTop: 12, marginBottom: 0 }}>
                <label>Favourite flavours</label>
                <div className="badge-row">
                  {stats.favorite_clusters.map((c) => (
                    <span key={c} className="badge">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <h2 className="scr">No brews yet</h2>
            <p className="sub">
              Brew a recipe and rate it — your average rating, favourite
              origins, and go-to flavours build up here.
            </p>
            <Link className="btn primary" href="/recipes">
              Get a recipe
            </Link>
          </>
        )}
      </section>

      {/* Grinder */}
      <section className="card">
        <div className="eyebrow">Your gear</div>
        <h2 className="scr">Your grinder</h2>
        <p className="sub">
          Pick yours and every recipe shows the grind in its own dial — clicks
          or rotations — not just a 1–10 number.
        </p>
        <div className="field" style={{ marginBottom: 0 }}>
          <label htmlFor="grinder">Grinder</label>
          <select
            id="grinder"
            className="select"
            value={grinderId}
            onChange={(e) => chooseGrinder(e.target.value)}
          >
            <option value="">Generic scale (1–10)</option>
            {handGrinders.length > 0 && (
              <optgroup label="Hand grinders">
                {handGrinders.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.brand} {g.model}
                  </option>
                ))}
              </optgroup>
            )}
            {electricGrinders.length > 0 && (
              <optgroup label="Electric grinders">
                {electricGrinders.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.brand} {g.model}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
          <p className="sub" style={{ marginTop: 8 }}>
            {grinderId
              ? "Saved — every recipe now uses this grinder's dial."
              : "Optional. You can also set this from any recipe."}
          </p>
        </div>
      </section>

      {/* Brewers — gear you own, not a bean attribute. Own several; pick which
          one you're using when you get a recipe. */}
      <section className="card">
        <div className="eyebrow">Your gear</div>
        <h2 className="scr">Your brewers</h2>
        <p className="sub">
          Tick the brewers you own. When you get a recipe you&apos;ll pick which
          one you&apos;re using — the same beans can go through any of them.
        </p>
        <div className="field" style={{ marginBottom: 0 }}>
          {brewers.map((b) => {
            const owned = brewerIds.includes(b.id);
            return (
              <label
                key={b.id}
                className="check-row"
                style={{
                  display: "flex",
                  gap: 10,
                  alignItems: "flex-start",
                  padding: "10px 0",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={owned}
                  onChange={() => toggleBrewer(b.id)}
                  style={{ marginTop: 3 }}
                />
                <span>
                  <span className="t" style={{ fontWeight: 600 }}>
                    {b.name}
                  </span>
                  <span
                    className="sub"
                    style={{ display: "block", marginTop: 2 }}
                  >
                    {b.blurb}
                  </span>
                </span>
              </label>
            );
          })}
          <p className="sub" style={{ marginTop: 8 }}>
            {brewerIds.length > 0
              ? `Saved — you own ${brewerIds.length} ${
                  brewerIds.length === 1 ? "brewer" : "brewers"
                }.`
              : "Optional. Pick the brewers you actually own."}
          </p>
        </div>
      </section>

      {/* Account — sign in to carry data across devices (Goal C) */}
      <section className="card">
        <div className="eyebrow">Your account</div>
        {email ? (
          <>
            <h2 className="scr">Signed in</h2>
            <p className="sub">
              Signed in as <strong>{email}</strong>. Your coffees, brews, and
              grinder follow you to any device.
            </p>
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
          </>
        ) : (
          <>
            <h2 className="scr">Saved on this device</h2>
            {configured ? (
              <>
                <p className="sub">
                  Right now your coffees, brews, and grinder live on this
                  device. Sign in and your history follows you to any device.
                </p>
                <Link className="btn primary" href="/signin">
                  Sign in or create an account
                </Link>
              </>
            ) : (
              <p className="sub">
                Right now your coffees, brews, and grinder live on this device.
                Real accounts — sign in, and your history follows you to any
                device — are coming next.
              </p>
            )}
          </>
        )}
      </section>
    </>
  );
}

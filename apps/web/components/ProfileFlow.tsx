"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getGrinders, getStats, type Grinder, type UserStats } from "@/lib/api";
import { readGrinderId, writeGrinderId } from "@/lib/grinderPref";
import { getUserId } from "@/lib/identity";

type Status = "loading" | "ready" | "error";

export default function ProfileFlow() {
  const [status, setStatus] = useState<Status>("loading");
  const [grinders, setGrinders] = useState<Grinder[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Read the saved grinder lazily so it survives reloads without a hydration
  // mismatch (this screen isn't server-rendered with the value).
  const [grinderId, setGrinderId] = useState<string>(() => readGrinderId());

  useEffect(() => {
    let cancelled = false;
    Promise.all([getGrinders(), getStats(getUserId())])
      .then(([g, s]) => {
        if (cancelled) return;
        setGrinders(g);
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
  }, []);

  function chooseGrinder(id: string) {
    setGrinderId(id);
    writeGrinderId(id);
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

      {/* Account note — real accounts arrive with login (Goal C) */}
      <section className="card">
        <div className="eyebrow">Your account</div>
        <h2 className="scr">Saved on this device</h2>
        <p className="sub">
          Right now your coffees, brews, and grinder live on this device. Real
          accounts — sign in, and your history follows you to any device — are
          coming next.
        </p>
      </section>
    </>
  );
}

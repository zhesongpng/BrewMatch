"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChartIcon, DripIcon } from "@/components/icons";
import {
  getBrews,
  getLearnState,
  type BrewRecord,
  type LearnState,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

// Plain-language names for the brain's learning phases (see /learn docstring).
const PHASE_LABEL: Record<string, string> = {
  bean_aware: "Getting to know your taste",
  directional: "Learning which way to nudge your brews",
  content_based: "Tuning recommendations to you",
  full_hybrid: "Dialed in to your taste",
};

type Status = "loading" | "ready" | "error";

export default function HistoryFlow() {
  const { ready, userId } = useAuth();
  const [status, setStatus] = useState<Status>("loading");
  const [brews, setBrews] = useState<BrewRecord[]>([]);
  const [learn, setLearn] = useState<LearnState | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refetch when the signed-in user changes so the right person's brews show.
  useEffect(() => {
    if (!ready || !userId) return;
    let cancelled = false;

    Promise.all([getBrews(userId), getLearnState(userId)])
      .then(([b, l]) => {
        if (cancelled) return;
        setBrews(b);
        setLearn(l);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Couldn't load your history.",
        );
        setStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [ready, userId]);

  if (status === "loading") {
    return (
      <section className="card">
        <div className="status">
          <div className="spinner" aria-hidden="true" />
          <div>
            <div className="t">Loading your brews…</div>
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
        <div className="t">Couldn&apos;t load your history</div>
        <p className="sub">{error}</p>
      </section>
    );
  }

  if (brews.length === 0) {
    return (
      <div className="empty">
        <span className="icn">
          <ChartIcon />
        </span>
        <h3>Your history starts here</h3>
        <p>
          Brew a recipe, then rate it at the bottom of the recipe — every brew
          you log shows up here, newest first, and teaches BrewMatch your taste.
        </p>
        <Link className="btn primary" href="/recipes">
          Get a recipe
        </Link>
      </div>
    );
  }

  return (
    <>
      {learn && (
        <section className="card">
          <div className="eyebrow">What BrewMatch has learned</div>
          <h2 className="scr">
            {learn.brew_count} {learn.brew_count === 1 ? "brew" : "brews"}{" "}
            logged
          </h2>
          <p className="sub">{PHASE_LABEL[learn.phase] ?? learn.phase}</p>
        </section>
      )}

      {brews.map((b) => (
        <BrewCard key={b.brew_id} brew={b} />
      ))}
    </>
  );
}

function BrewCard({ brew }: { brew: BrewRecord }) {
  const { recipe, feedback, bean } = brew;
  const origin =
    bean.origin_country && bean.origin_country !== "Unknown"
      ? bean.origin_country
      : null;

  return (
    <div className="bag">
      <div className="top">
        <div className="icn">
          <DripIcon />
        </div>
        <div>
          <div className="nm">{recipe.method}</div>
          <div className="rs">
            <strong>{recipe.source}</strong>
            {origin ? ` · ${origin}` : ""}
          </div>
        </div>
        <div className="age">{formatDate(brew.timestamp)}</div>
      </div>

      <div className="badge-row">
        <span className={`badge ${feedback.thumbs_up ? "good" : ""}`}>
          {feedback.thumbs_up ? "Loved it" : "Not quite"}
        </span>
        {feedback.score != null && (
          <span className="badge">{feedback.score}/10</span>
        )}
        {(feedback.directional_flags ?? []).map((f) => (
          <span key={f} className="badge">
            {flagLabel(f)}
          </span>
        ))}
      </div>

      {feedback.notes && <p className="sub">{feedback.notes}</p>}
    </div>
  );
}

/** ISO timestamp → short, friendly date like "Jun 25". */
function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** "too_sour" → "Too sour". */
function flagLabel(flag: string): string {
  const s = flag.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

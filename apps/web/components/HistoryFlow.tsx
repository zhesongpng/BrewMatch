"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChartIcon, DripIcon } from "@/components/icons";
import {
  diagnose,
  getBrews,
  getLearnState,
  type BrewRecord,
  type DiagnoseResult,
  type LearnState,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { paramLabel, suggestionChange } from "@/lib/diagnose";

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
        <BrewCard key={b.brew_id} brew={b} userId={userId} />
      ))}
    </>
  );
}

type DiagState = "idle" | "loading" | "done" | "error";

function BrewCard({ brew, userId }: { brew: BrewRecord; userId: string }) {
  const { recipe, feedback, bean } = brew;
  const origin =
    bean.origin_country && bean.origin_country !== "Unknown"
      ? bean.origin_country
      : null;

  // The taste problems recorded when this brew was rated. Only these can be
  // diagnosed — a brew logged with no problems has nothing to fix.
  const flags = feedback.directional_flags ?? [];

  const [state, setState] = useState<DiagState>("idle");
  const [result, setResult] = useState<DiagnoseResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Diagnose THIS brew: send its real recipe + beans so the brain's ML engine
  // tunes the fix to the actual grind / temp / dose, personalized to the user.
  async function runDiagnose() {
    setState("loading");
    setError(null);
    try {
      const res = await diagnose(flags, { bean, recipe, userId });
      setResult(res);
      setState("done");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't diagnose that brew.",
      );
      setState("error");
    }
  }

  const assessment = result?.assessments?.[0];

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
        {flags.map((f) => (
          <span key={f} className="badge">
            {flagLabel(f)}
          </span>
        ))}
      </div>

      {feedback.notes && <p className="sub">{feedback.notes}</p>}

      {/* Recipe-aware diagnosis — only offered when the brew recorded a problem. */}
      {flags.length > 0 && state !== "done" && (
        <button
          type="button"
          className="btn ghost"
          onClick={runDiagnose}
          disabled={state === "loading"}
          style={{ marginTop: 12 }}
        >
          {state === "loading" ? "Reading your brew…" : "What went wrong?"}
        </button>
      )}

      {state === "error" && error && (
        <p className="sub" role="alert" style={{ color: "var(--warn)" }}>
          {error}
        </p>
      )}

      {state === "done" && result && (
        <div className="result" style={{ marginTop: 12 }}>
          {assessment && (
            <div className="t" style={{ fontWeight: 600 }}>
              {assessment.cause}
            </div>
          )}
          <p className="sub" style={{ marginTop: 4 }}>
            {assessment?.assessment ??
              result.overall_assessment ??
              "Here's what to change next time."}
          </p>
          <div className="fix-list">
            {result.suggestions.map((s) => (
              <div className="fix" key={s.parameter}>
                <div className="fix-k">{paramLabel(s.parameter)}</div>
                <div className="fix-v">{suggestionChange(s)}</div>
                <div className="fix-r">{s.reason}</div>
              </div>
            ))}
          </div>
        </div>
      )}
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

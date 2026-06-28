"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckIcon } from "@/components/icons";
import {
  BREW_FLAGS,
  saveBrew,
  type BeanInput,
  type BrewFlagId,
  type Recipe,
} from "@/lib/api";
import { getUserId } from "@/lib/identity";

type SaveState = "idle" | "saving" | "saved" | "error";

/**
 * Rate a brew you just made and save it to your history.
 *
 * Lives at the bottom of a recipe so the beans and recipe are already known —
 * the user only adds how it tasted. Saving feeds the History screen and the
 * learning loop via POST /brews/{user_id}.
 */
export default function LogBrew({
  bean,
  recipe,
  bagId,
}: {
  bean: BeanInput;
  recipe: Recipe;
  /** Set when this brew came from a saved bag, so it records against that bag. */
  bagId?: string | null;
}) {
  const [thumbsUp, setThumbsUp] = useState(true);
  const [score, setScore] = useState(7);
  const [flags, setFlags] = useState<BrewFlagId[]>([]);
  const [notes, setNotes] = useState("");
  const [state, setState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);

  function toggleFlag(f: BrewFlagId) {
    setFlags((cur) =>
      cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f],
    );
  }

  function stepScore(delta: number) {
    setScore((s) => Math.min(10, Math.max(1, s + delta)));
  }

  async function save() {
    setState("saving");
    setError(null);
    try {
      await saveBrew(
        getUserId(),
        bean,
        recipe,
        {
          thumbs_up: thumbsUp,
          score,
          directional_flags: flags,
          notes: notes.trim() || undefined,
        },
        bagId,
      );
      setState("saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save your brew.");
      setState("error");
    }
  }

  if (state === "saved") {
    return (
      <section className="card">
        <div className="status">
          <div className="check-badge" aria-hidden="true">
            <CheckIcon />
          </div>
          <div>
            <div className="t">Brew saved</div>
            <div className="d">
              It&apos;s in your history, and BrewMatch will use it to learn your
              taste.
            </div>
          </div>
        </div>
        <Link className="btn ghost" href="/history">
          See your history
        </Link>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="eyebrow">After you brew</div>
      <h2 className="scr">How did it taste?</h2>
      <p className="sub">
        Rate it and BrewMatch remembers — your history builds up and the
        recommendations get more tuned to you.
      </p>

      <div className="field">
        <label>Overall</label>
        <div className="chips">
          <button
            type="button"
            className={`chip${thumbsUp ? " on" : ""}`}
            onClick={() => setThumbsUp(true)}
            aria-pressed={thumbsUp}
          >
            Loved it
          </button>
          <button
            type="button"
            className={`chip${!thumbsUp ? " on" : ""}`}
            onClick={() => setThumbsUp(false)}
            aria-pressed={!thumbsUp}
          >
            Not quite
          </button>
        </div>
      </div>

      <div className="stepper">
        <span className="lab">Rating</span>
        <div className="ctl">
          <button
            type="button"
            onClick={() => stepScore(-1)}
            disabled={score <= 1}
            aria-label="Lower rating"
          >
            −
          </button>
          <span className="val">{score} / 10</span>
          <button
            type="button"
            onClick={() => stepScore(1)}
            disabled={score >= 10}
            aria-label="Higher rating"
          >
            +
          </button>
        </div>
      </div>

      <div className="field">
        <label>Anything off? (optional)</label>
        <div className="chips">
          {BREW_FLAGS.map((f) => (
            <button
              type="button"
              key={f.id}
              className={`chip${flags.includes(f.id) ? " on" : ""}`}
              onClick={() => toggleFlag(f.id)}
              aria-pressed={flags.includes(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label htmlFor="brew-notes">Notes (optional)</label>
        <textarea
          id="brew-notes"
          className="textarea"
          placeholder="What you'd change next time, how it smelled, anything memorable."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      {state === "error" && error && (
        <p className="sub" role="alert" style={{ color: "var(--warn)" }}>
          {error}
        </p>
      )}

      <button
        type="button"
        className="btn primary"
        onClick={save}
        disabled={state === "saving"}
      >
        {state === "saving" ? "Saving…" : "Save this brew"}
      </button>
    </section>
  );
}

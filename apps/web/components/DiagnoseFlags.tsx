"use client";

import { useState } from "react";
import {
  AstringentIcon,
  BitterIcon,
  SourIcon,
  WeakIcon,
} from "@/components/icons";
import { diagnose, type DiagnoseResult, type FlagId } from "@/lib/api";

const FLAGS: {
  id: FlagId;
  Icon: typeof SourIcon;
  title: string;
  desc: string;
}[] = [
  {
    id: "too_sour",
    Icon: SourIcon,
    title: "Too sour",
    desc: "Sharp, tangy, empty finish",
  },
  {
    id: "too_bitter",
    Icon: BitterIcon,
    title: "Too bitter",
    desc: "Harsh, drying aftertaste",
  },
  {
    id: "too_weak",
    Icon: WeakIcon,
    title: "Too weak",
    desc: "Watery, thin, not enough",
  },
  {
    id: "astringent",
    Icon: AstringentIcon,
    title: "Astringent",
    desc: "Mouth-puckering, dry",
  },
];

// Turn the brain's raw parameter keys into plain words for the user.
const PARAM_LABELS: Record<string, string> = {
  grind_setting: "Grind",
  water_temp_c: "Water temperature",
  total_time_s: "Brew time",
  dose_g: "Coffee dose",
  ratio: "Coffee-to-water ratio",
};

function paramLabel(key: string): string {
  return PARAM_LABELS[key] ?? key.replace(/_/g, " ");
}

// Each suggestion is either rule-based (a direction like "finer") or ML
// (a current → suggested value). Show whichever the brain returned.
function suggestionChange(s: DiagnoseResult["suggestions"][number]): string {
  if (s.direction) return s.direction;
  if (s.suggested_value !== undefined) {
    return s.current_value !== undefined
      ? `${String(s.current_value)} → ${String(s.suggested_value)}`
      : String(s.suggested_value);
  }
  return "";
}

export default function DiagnoseFlags() {
  const [selected, setSelected] = useState<FlagId | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnoseResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pick(id: FlagId) {
    setSelected(id);
    setResult(null);
    setError(null);
    setLoading(true);
    try {
      setResult(await diagnose([id]));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const assessment = result?.assessments?.[0];

  return (
    <>
      <section className="card">
        <div className="eyebrow">How did it taste?</div>
        <h2 className="scr">What went wrong?</h2>
        <p className="sub">
          Tap what you noticed. We&apos;ll tell you why — and exactly what to
          change next time.
        </p>

        {FLAGS.map(({ id, Icon, title, desc }) => (
          <button
            type="button"
            className={`flag${selected === id ? " selected" : ""}`}
            key={id}
            onClick={() => pick(id)}
            aria-pressed={selected === id}
          >
            <div className="dot">
              <Icon />
            </div>
            <div>
              <div className="t">{title}</div>
              <div className="d">{desc}</div>
            </div>
            <div className="chev">›</div>
          </button>
        ))}
      </section>

      {loading && (
        <section className="card">
          <div className="status">
            <div className="spinner" aria-hidden="true" />
            <div>
              <div className="t">Reading your brew…</div>
              <div className="d">
                The first answer can take up to a minute while the brain wakes
                up.
              </div>
            </div>
          </div>
        </section>
      )}

      {error && (
        <section className="card error">
          <div className="t">Couldn&apos;t diagnose that</div>
          <p className="sub">{error}</p>
          {selected && (
            <button
              type="button"
              className="btn ghost"
              onClick={() => pick(selected)}
            >
              Try again
            </button>
          )}
        </section>
      )}

      {result && !loading && (
        <section className="card result">
          <div className="eyebrow">Diagnosis</div>
          {assessment && <h2 className="scr">{assessment.cause}</h2>}
          <p className="sub">
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
        </section>
      )}
    </>
  );
}

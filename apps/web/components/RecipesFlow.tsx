"use client";

import { useCallback, useEffect, useState } from "react";
import { DripIcon, PinIcon, TrophyIcon, TuneIcon } from "@/components/icons";
import LogBrew from "@/components/LogBrew";
import { takePendingBag } from "@/lib/bagHandoff";
import {
  FLAVOR_CLUSTERS,
  getGrinders,
  recommend,
  type BeanInput,
  type BrewMethodId,
  type Grinder,
  type ProcessId,
  type RankedRecipe,
  type RecommendResult,
  type RoastLevelId,
} from "@/lib/api";
import {
  clockFormat,
  grams,
  grindForGrinder,
  poursWithRunningTotal,
  rescaleToDose,
} from "@/lib/recipe";

// Where the chosen grinder is remembered. Until accounts exist (Goal C) this
// on-device value is the user's identity for grind preferences — pick once and
// every recipe shows settings in that grinder's own units.
const GRINDER_KEY = "brewmatch.grinder_id";

// ---- Plain-language option labels for the bean form ----

const PROCESSES: { id: ProcessId; label: string }[] = [
  { id: "washed", label: "Washed" },
  { id: "natural", label: "Natural" },
  { id: "honey", label: "Honey" },
  { id: "anaerobic", label: "Anaerobic" },
  { id: "wet-hulled", label: "Wet-hulled" },
  { id: "unknown", label: "Not sure" },
];

const ROASTS: { id: RoastLevelId; label: string }[] = [
  { id: "light", label: "Light" },
  { id: "medium-light", label: "Medium-light" },
  { id: "medium", label: "Medium" },
  { id: "medium-dark", label: "Medium-dark" },
  { id: "dark", label: "Dark" },
  { id: "unknown", label: "Not sure" },
];

const METHODS: BrewMethodId[] = ["V60", "Kalita Wave", "Origami"];

const TIER_LABELS: Record<string, string> = {
  champion: "Championship recipe",
  barista: "Barista source",
  enthusiast: "Enthusiast source",
};

type View = "form" | "loading" | "results" | "detail" | "error";

export default function RecipesFlow() {
  const [view, setView] = useState<View>("form");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RecommendResult | null>(null);
  const [chosen, setChosen] = useState<RankedRecipe | null>(null);
  // The bean we recommended for — kept so the recipe detail can log a brew
  // against it without the user re-entering anything.
  const [submittedBean, setSubmittedBean] = useState<BeanInput | null>(null);
  // Set when this flow was opened by "Brew this" on a saved bag, so the logged
  // brew records against that bag (drives its running-low countdown). null for
  // an ordinary "describe your beans" recommendation.
  const [bagId, setBagId] = useState<string | null>(null);

  // Grinder catalog + the user's saved choice. Fetched once; translation is a
  // local lookup after that. The saved choice is read lazily from on-device
  // storage so it survives reloads (the detail view isn't rendered on first
  // paint, so there's no hydration mismatch).
  const [grinders, setGrinders] = useState<Grinder[]>([]);
  const [grinderId, setGrinderId] = useState<string>(() =>
    typeof window === "undefined"
      ? ""
      : (window.localStorage.getItem(GRINDER_KEY) ?? ""),
  );

  useEffect(() => {
    // The catalog needs no model warm-up, so this returns fast even on a cold
    // brain. A failure just leaves the generic 1-10 scale in place.
    getGrinders()
      .then(setGrinders)
      .catch(() => {});
  }, []);

  function chooseGrinder(id: string) {
    setGrinderId(id);
    if (id) window.localStorage.setItem(GRINDER_KEY, id);
    else window.localStorage.removeItem(GRINDER_KEY);
  }

  // Bean form state.
  const [origin, setOrigin] = useState("");
  const [process, setProcess] = useState<ProcessId>("washed");
  const [roast, setRoast] = useState<RoastLevelId>("medium-light");
  const [method, setMethod] = useState<BrewMethodId>("V60");
  const [flavors, setFlavors] = useState<string[]>([]);
  const [notes, setNotes] = useState("");

  function toggleFlavor(f: string) {
    setFlavors((cur) =>
      cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f],
    );
  }

  // Core recommend call, shared by the bean form and the "Brew this" hand-off.
  // `bag` is the originating bag id (null for a form recommendation); it's held
  // so the recipe detail can log the brew against that bag. useCallback keeps a
  // stable reference for the pending-bag effect below.
  const runRecommend = useCallback(
    async (beanInput: BeanInput, m: BrewMethodId, bag: string | null) => {
      setSubmittedBean(beanInput);
      setBagId(bag);
      setView("loading");
      setError(null);
      try {
        const res = await recommend(beanInput, m, 3);
        setResult(res);
        setView("results");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
        setView("error");
      }
    },
    [],
  );

  // If the Coffees screen sent us here via "Brew this", recommend for that bag's
  // beans straight away (no form step) and remember the bag id for logging.
  // Deferred to a microtask so the loading-state updates land in an async
  // continuation, not synchronously in the effect body (cascading-render lint).
  useEffect(() => {
    const pending = takePendingBag();
    if (!pending) return;
    void Promise.resolve().then(() =>
      runRecommend(pending.bean, "V60", pending.bagId),
    );
  }, [runRecommend]);

  async function submit() {
    const cleanOrigin = origin.trim() || "Unknown";
    // The brain requires a non-empty flavour list and source description.
    const clusters = flavors.length > 0 ? flavors : ["Balanced"];
    const sourceText =
      notes.trim() ||
      `${roast} roast ${cleanOrigin} ${process} coffee`.replace(/\s+/g, " ");

    const bean: BeanInput = {
      origin_country: cleanOrigin,
      process,
      roast_level: roast,
      flavor_clusters: clusters,
      source_text: sourceText,
    };

    // A form recommendation is not tied to a saved bag.
    await runRecommend(bean, method, null);
  }

  // ---- Render ----

  if (view === "loading") {
    return (
      <main className="app-body">
        <section className="card">
          <div className="status">
            <div className="spinner" aria-hidden="true" />
            <div>
              <div className="t">Finding your recipes…</div>
              <div className="d">
                The first answer can take up to a minute while the brain wakes
                up.
              </div>
            </div>
          </div>
        </section>
      </main>
    );
  }

  if (view === "error") {
    return (
      <main className="app-body">
        <section className="card error">
          <div className="t">Couldn&apos;t get recipes</div>
          <p className="sub">{error}</p>
          <button
            type="button"
            className="btn ghost"
            onClick={() =>
              submittedBean
                ? runRecommend(submittedBean, method, bagId)
                : submit()
            }
          >
            Try again
          </button>
        </section>
      </main>
    );
  }

  if (view === "detail" && chosen) {
    return (
      <RecipeDetail
        ranked={chosen}
        bean={submittedBean}
        bagId={bagId}
        grinders={grinders}
        grinderId={grinderId}
        onChooseGrinder={chooseGrinder}
        onBack={() => setView("results")}
      />
    );
  }

  if (view === "results" && result) {
    return (
      <main className="app-body">
        <section className="card">
          <div className="eyebrow">Top picks</div>
          <h2 className="scr">
            {result.recipes.length}{" "}
            {result.recipes.length === 1 ? "recipe" : "recipes"} for your beans
          </h2>
          <p className="sub">
            Ranked best-first from {result.total_candidates} pour-over recipes
            the brain knows. Tap one to see the full method.
          </p>
        </section>

        {result.recipes.map((ranked) => (
          <ResultCard
            key={ranked.recipe.recipe_id}
            ranked={ranked}
            onOpen={() => {
              setChosen(ranked);
              setView("detail");
            }}
          />
        ))}

        <button
          type="button"
          className="btn ghost"
          onClick={() => setView("form")}
        >
          Start over with different beans
        </button>
      </main>
    );
  }

  // Default: the bean form.
  return (
    <main className="app-body">
      <section className="card">
        <div className="eyebrow">New beans</div>
        <h2 className="scr">What are you brewing?</h2>
        <p className="sub">
          Tell us about the beans and we&apos;ll rank pour-over recipes tuned to
          them.
        </p>

        <div className="field">
          <label htmlFor="origin">Origin country</label>
          <input
            id="origin"
            className="input"
            type="text"
            placeholder="e.g. Ethiopia, Colombia"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="process">Process</label>
          <select
            id="process"
            className="select"
            value={process}
            onChange={(e) => setProcess(e.target.value as ProcessId)}
          >
            {PROCESSES.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="roast">Roast level</label>
          <select
            id="roast"
            className="select"
            value={roast}
            onChange={(e) => setRoast(e.target.value as RoastLevelId)}
          >
            {ROASTS.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="method">Brewer</label>
          <select
            id="method"
            className="select"
            value={method}
            onChange={(e) => setMethod(e.target.value as BrewMethodId)}
          >
            {METHODS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Flavour notes (optional)</label>
          <div className="chips">
            {FLAVOR_CLUSTERS.map((f) => (
              <button
                type="button"
                key={f}
                className={`chip${flavors.includes(f) ? " on" : ""}`}
                onClick={() => toggleFlavor(f)}
                aria-pressed={flavors.includes(f)}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label htmlFor="notes">Anything on the bag? (optional)</label>
          <textarea
            id="notes"
            className="textarea"
            placeholder="Tasting notes, variety, altitude — whatever's printed."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>

        <button type="button" className="btn primary" onClick={submit}>
          <DripIcon />
          Find recipes
        </button>
      </section>
    </main>
  );
}

// ---- A ranked recipe in the results list ----

function ResultCard({
  ranked,
  onOpen,
}: {
  ranked: RankedRecipe;
  onOpen: () => void;
}) {
  const r = ranked.recipe;
  const match =
    ranked.predicted_score != null
      ? `${Math.round((ranked.predicted_score / 10) * 100)}% match`
      : null;

  return (
    <button
      type="button"
      className="bag"
      onClick={onOpen}
      style={{ width: "100%", textAlign: "left", cursor: "pointer" }}
    >
      <div className="top">
        <div className="icn">
          <DripIcon />
        </div>
        <div>
          <div className="nm">{r.method}</div>
          <div className="rs">
            <strong>{r.source}</strong>
          </div>
        </div>
        <div className="age">#{ranked.rank}</div>
      </div>
      <div className="badge-row">
        {r.source_tier === "champion" && (
          <span className="badge gold">
            <TrophyIcon />
            Championship
          </span>
        )}
        {match && <span className="badge good">{match}</span>}
        <span className="badge">1:{r.ratio.toFixed(0)} ratio</span>
      </div>
    </button>
  );
}

// ---- Full recipe view with the editable dose ----

function RecipeDetail({
  ranked,
  bean,
  bagId,
  grinders,
  grinderId,
  onChooseGrinder,
  onBack,
}: {
  ranked: RankedRecipe;
  bean: BeanInput | null;
  bagId: string | null;
  grinders: Grinder[];
  grinderId: string;
  onChooseGrinder: (id: string) => void;
  onBack: () => void;
}) {
  const base = ranked.recipe;
  const [dose, setDose] = useState<number>(base.dose_g);

  const recipe = dose === base.dose_g ? base : rescaleToDose(base, dose);
  const pours = poursWithRunningTotal(recipe.pours);
  const tier = recipe.source_tier ?? "barista";

  // Translate the generic grind into the chosen grinder's own dial, if any.
  const grinder = grinders.find((g) => g.id === grinderId) ?? null;
  const grind = grinder ? grindForGrinder(grinder, recipe.grind_setting) : null;
  const handGrinders = grinders.filter((g) => g.type === "hand");
  const electricGrinders = grinders.filter((g) => g.type === "electric");
  const match =
    ranked.predicted_score != null
      ? `${Math.round((ranked.predicted_score / 10) * 100)}% match`
      : null;

  function step(delta: number) {
    setDose((d) => {
      const next = Math.round((d + delta) * 2) / 2; // 0.5 g steps
      return Math.min(35, Math.max(12, next));
    });
  }

  return (
    <main className="app-body">
      <section className="card">
        <div className="eyebrow">{recipe.method}</div>
        <h2 className="scr">{recipe.source}</h2>
        <div className="origin">
          <PinIcon />
          {TIER_LABELS[tier] ?? "Recipe"}
        </div>

        <div className="badge-row">
          {tier === "champion" && (
            <span className="badge gold">
              <TrophyIcon />
              Championship
            </span>
          )}
          {match && <span className="badge good">{match}</span>}
        </div>

        <div className="stepper">
          <span className="lab">Dose</span>
          <div className="ctl">
            <button
              type="button"
              onClick={() => step(-0.5)}
              disabled={dose <= 12}
              aria-label="Less coffee"
            >
              −
            </button>
            <span className="val">{recipe.dose_g.toFixed(1)} g</span>
            <button
              type="button"
              onClick={() => step(0.5)}
              disabled={dose >= 35}
              aria-label="More coffee"
            >
              +
            </button>
          </div>
        </div>

        <div className="pill-grid">
          <div className="pill">
            <div className="k">Water</div>
            <div className="v">{grams(recipe.water_total_g)}</div>
          </div>
          <div className="pill">
            <div className="k">Ratio</div>
            <div className="v">1:{recipe.ratio.toFixed(1)}</div>
          </div>
          <div className="pill">
            <div className="k">Grind</div>
            {grind ? (
              <>
                <div className="v">{grind.dial}</div>
                <div className="vsub">
                  {grind.grinderName} · {recipe.grind_setting}/10
                </div>
              </>
            ) : (
              <div className="v">{recipe.grind_setting} / 10</div>
            )}
          </div>
          <div className="pill">
            <div className="k">Water temp</div>
            <div className="v">{Math.round(recipe.water_temp_c)}°C</div>
          </div>
          <div className="pill">
            <div className="k">Bloom</div>
            <div className="v">{clockFormat(recipe.bloom_time_s)}</div>
          </div>
          <div className="pill">
            <div className="k">Total time</div>
            <div className="v">{clockFormat(recipe.total_time_s)}</div>
          </div>
        </div>

        <div className="field" style={{ marginTop: 16, marginBottom: 0 }}>
          <label htmlFor="grinder">Your grinder</label>
          <select
            id="grinder"
            className="select"
            value={grinderId}
            onChange={(e) => onChooseGrinder(e.target.value)}
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
            {grind
              ? "Grind shows in your grinder's own dial. We'll remember it."
              : "Pick yours to see the grind in clicks or rotations, not just 1–10."}
          </p>
        </div>
      </section>

      <section className="card">
        <div className="eyebrow">Pour schedule</div>
        <h2 className="scr">Pour by the clock</h2>
        <p className="sub">
          Times are from the moment you start. Pour up to the running total —
          the brewer should read that weight when you stop.
        </p>
        <div className="pours">
          {pours.map((p) => (
            <div className="pour" key={p.step}>
              <div className="num">{p.step}</div>
              <div>
                <div className="pt">
                  {p.step === 1 ? "Bloom" : `Pour ${p.step - 1}`} — up to{" "}
                  {grams(p.runningTotal)}
                </div>
                <div className="pd">+{grams(p.water_g)} this pour</div>
              </div>
              <div className="ptime">{clockFormat(p.time_offset_s)}</div>
            </div>
          ))}
        </div>
      </section>

      {recipe.instructions && (
        <section className="card">
          <div className="eyebrow">
            <TuneIcon />
            &nbsp;Method
          </div>
          <p className="steps">{recipe.instructions}</p>
          {recipe.source_url && (
            <a
              className="btn ghost"
              href={recipe.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              View original source
            </a>
          )}
        </section>
      )}

      {bean && <LogBrew bean={bean} recipe={recipe} bagId={bagId} />}

      <button type="button" className="btn ghost" onClick={onBack}>
        Back to recipes
      </button>
    </main>
  );
}

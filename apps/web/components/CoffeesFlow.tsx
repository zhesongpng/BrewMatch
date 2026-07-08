"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BeanIcon } from "@/components/icons";
import {
  createBag,
  finishBag,
  FLAVOR_CLUSTERS,
  getBags,
  updateBag,
  type Bag,
  type ProcessId,
  type RoastLevelId,
} from "@/lib/api";
import { setPendingBag } from "@/lib/bagHandoff";
import { useAuth } from "@/lib/auth";

// Plain-language option labels, matching the Recipes bean form.
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

// Common origins, plus "Other" for a free-text country (mirrors the Streamlit page).
const ORIGINS = [
  "Ethiopia",
  "Colombia",
  "Kenya",
  "Guatemala",
  "Brazil",
  "Costa Rica",
  "Panama",
  "Indonesia",
  "Rwanda",
  "Honduras",
  "Mexico",
  "Peru",
  "Uganda",
  "Tanzania",
  "Other",
];

type Status = "loading" | "ready" | "error";

export default function CoffeesFlow() {
  const router = useRouter();
  const { ready, userId } = useAuth();

  const [status, setStatus] = useState<Status>("loading");
  const [bags, setBags] = useState<Bag[]>([]);
  const [error, setError] = useState<string | null>(null);
  // The bag form is open by default for a first-time user (no bags yet).
  const [showForm, setShowForm] = useState(false);
  // Which bag the form is editing, or null when the form is adding a new bag.
  const [editingBagId, setEditingBagId] = useState<string | null>(null);

  // ---- Add-bag form state ----
  const [roaster, setRoaster] = useState("");
  const [name, setName] = useState("");
  const [bagSize, setBagSize] = useState(250);
  const [originSelect, setOriginSelect] = useState("Ethiopia");
  const [customOrigin, setCustomOrigin] = useState("");
  const [region, setRegion] = useState("");
  const [process, setProcess] = useState<ProcessId>("washed");
  const [roast, setRoast] = useState<RoastLevelId>("medium-light");
  const [variety, setVariety] = useState("");
  const [flavors, setFlavors] = useState<string[]>([]);
  const [altitude, setAltitude] = useState("");
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<string[]>([]);

  // Refetch when the signed-in user changes so the right person's coffees show.
  useEffect(() => {
    if (!ready || !userId) return;
    let cancelled = false;
    getBags(userId)
      .then((b) => {
        if (cancelled) return;
        setBags(b);
        setShowForm(b.length === 0);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Couldn't load your coffees.",
        );
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [ready, userId]);

  // Re-fetch after a change (e.g. finishing a bag). Called from a handler, never
  // an effect, so setting the loading state here is safe.
  async function refresh() {
    setStatus("loading");
    try {
      const b = await getBags(userId);
      setBags(b);
      setShowForm(b.length === 0);
      setStatus("ready");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't load your coffees.",
      );
      setStatus("error");
    }
  }

  function toggleFlavor(f: string) {
    setFlavors((cur) =>
      cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f],
    );
  }

  // Clear every form field back to its default. Used when opening a blank
  // add-bag form and when closing the form after an edit.
  function resetForm() {
    setRoaster("");
    setName("");
    setBagSize(250);
    setOriginSelect("Ethiopia");
    setCustomOrigin("");
    setRegion("");
    setProcess("washed");
    setRoast("medium-light");
    setVariety("");
    setFlavors([]);
    setAltitude("");
    setFormErrors([]);
    setSaving(false);
  }

  // Open a blank form for a brand-new bag.
  function openAddForm() {
    resetForm();
    setEditingBagId(null);
    setShowForm(true);
  }

  // Close the form and forget any in-progress edit.
  function closeForm() {
    setShowForm(false);
    setEditingBagId(null);
    resetForm();
  }

  // Open the form pre-filled with an existing bag's details so the user can
  // correct a mistake. Origin maps back to the dropdown when it's a known
  // country, otherwise to the "Other" free-text field.
  function startEdit(bag: Bag) {
    const country = bag.bean.origin_country;
    const known = ORIGINS.includes(country);
    setRoaster(bag.roaster);
    setName(bag.name);
    setBagSize(bag.bag_size_g);
    setOriginSelect(known ? country : "Other");
    setCustomOrigin(known ? "" : country);
    setRegion(bag.bean.origin_region ?? "");
    setProcess(bag.bean.process);
    setRoast(bag.bean.roast_level);
    setVariety(bag.bean.variety ?? "");
    setFlavors(bag.bean.flavor_clusters ?? []);
    setAltitude(
      formatAltitude(bag.bean.altitude_min_m, bag.bean.altitude_max_m),
    );
    setFormErrors([]);
    setSaving(false);
    setEditingBagId(bag.bag_id);
    setShowForm(true);
  }

  // Hand the bag's beans to the recipes flow and go there (mirrors the Streamlit
  // "Brew this" → recommend jump).
  function brewThis(bag: Bag) {
    setPendingBag({ bagId: bag.bag_id, bean: bag.bean });
    router.push("/recipes");
  }

  async function finish(bag: Bag) {
    try {
      await finishBag(userId, bag.bag_id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't update that bag.",
      );
      setStatus("error");
      return;
    }
    await refresh();
  }

  async function save() {
    const origin =
      originSelect === "Other" ? customOrigin.trim() : originSelect;
    const errs = validateBag({ roaster, name, origin, flavors });
    if (errs.length > 0) {
      setFormErrors(errs);
      return;
    }
    setFormErrors([]);

    const { min, max } = parseAltitude(altitude);
    const input = {
      roaster: roaster.trim(),
      name: name.trim(),
      bag_size_g: bagSize,
      origin_country: origin,
      process,
      roast_level: roast,
      flavor_clusters: flavors,
      region: region.trim() || undefined,
      variety: variety.trim() || undefined,
      altitude_min_m: min,
      altitude_max_m: max,
    };
    setSaving(true);
    try {
      if (editingBagId) {
        // Editing corrects a mistake — save and return to the list rather than
        // jumping into a brew (which is the right move only for a new bag).
        await updateBag(userId, editingBagId, input);
        closeForm();
        await refresh();
      } else {
        // Per the build spec, saving a new bag goes straight to recommending.
        const saved = await createBag(userId, input);
        brewThis(saved);
      }
    } catch (err) {
      setFormErrors([
        err instanceof Error
          ? err.message
          : editingBagId
            ? "Couldn't save your changes."
            : "Couldn't save your bag.",
      ]);
      setSaving(false);
    }
  }

  // ---- Render ----

  if (status === "loading") {
    return (
      <section className="card">
        <div className="status">
          <div className="spinner" aria-hidden="true" />
          <div>
            <div className="t">Loading your coffees…</div>
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
        <div className="t">Couldn&apos;t load your coffees</div>
        <p className="sub">{error}</p>
        <button type="button" className="btn ghost" onClick={refresh}>
          Try again
        </button>
      </section>
    );
  }

  return (
    <>
      {bags.length > 0 ? (
        <>
          <section className="card">
            <div className="eyebrow">Your open bags</div>
            <h2 className="scr">
              {bags.length} {bags.length === 1 ? "bag" : "bags"} on the go
            </h2>
            <p className="sub">
              Pick a bag to brew with, or mark one finished when it runs out.
            </p>
          </section>

          {bags.map((bag) => (
            <BagCard
              key={bag.bag_id}
              bag={bag}
              onBrew={() => brewThis(bag)}
              onEdit={() => startEdit(bag)}
              onFinish={() => finish(bag)}
            />
          ))}
        </>
      ) : (
        <div className="empty">
          <span className="icn">
            <BeanIcon />
          </span>
          <h3>No bags yet</h3>
          <p>
            Add your first bag below — enter its details once, then pick it each
            time you brew so BrewMatch can track what&apos;s running low.
          </p>
        </div>
      )}

      {bags.length > 0 && (
        <button
          type="button"
          className="btn ghost"
          onClick={() => (showForm ? closeForm() : openAddForm())}
        >
          {showForm ? "Cancel" : "Add a new bag"}
        </button>
      )}

      {showForm && (
        <section className="card">
          <div className="eyebrow">
            {editingBagId ? "Edit bag" : "Add a new bag"}
          </div>
          <h2 className="scr">
            {editingBagId ? "Edit this coffee" : "A new coffee"}
          </h2>
          <p className="sub">
            Enter what&apos;s on the bag. Fields marked * are required.
          </p>

          <div className="field">
            <label htmlFor="roaster">Roaster *</label>
            <input
              id="roaster"
              className="input"
              type="text"
              placeholder="e.g. Onyx Coffee Lab"
              value={roaster}
              onChange={(e) => setRoaster(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="bag-name">Coffee name *</label>
            <input
              id="bag-name"
              className="input"
              type="text"
              placeholder="e.g. Ethiopia Guji"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="bag-size">Bag size (g)</label>
            <input
              id="bag-size"
              className="input"
              type="number"
              min={50}
              max={2000}
              step={10}
              value={bagSize}
              onChange={(e) => setBagSize(Number(e.target.value))}
            />
          </div>

          <div className="field">
            <label htmlFor="origin">Origin country *</label>
            <select
              id="origin"
              className="select"
              value={originSelect}
              onChange={(e) => setOriginSelect(e.target.value)}
            >
              {ORIGINS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </div>

          {originSelect === "Other" && (
            <div className="field">
              <label htmlFor="custom-origin">Which country? *</label>
              <input
                id="custom-origin"
                className="input"
                type="text"
                placeholder="e.g. Yemen, Burundi, Nicaragua"
                value={customOrigin}
                onChange={(e) => setCustomOrigin(e.target.value)}
              />
            </div>
          )}

          <div className="field">
            <label htmlFor="region">Region</label>
            <input
              id="region"
              className="input"
              type="text"
              placeholder="e.g. Yirgacheffe, Huila"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="bag-process">Process *</label>
            <select
              id="bag-process"
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
            <label htmlFor="bag-roast">Roast level *</label>
            <select
              id="bag-roast"
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
            <label htmlFor="variety">Variety</label>
            <input
              id="variety"
              className="input"
              type="text"
              placeholder="e.g. Gesha, Bourbon, SL28"
              value={variety}
              onChange={(e) => setVariety(e.target.value)}
            />
          </div>

          <div className="field">
            <label>Flavour profiles * (at least 1)</label>
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
            <label htmlFor="altitude">Altitude (m)</label>
            <input
              id="altitude"
              className="input"
              type="text"
              placeholder="e.g. 1800 or 1500-2000"
              value={altitude}
              onChange={(e) => setAltitude(e.target.value)}
            />
          </div>

          {formErrors.length > 0 && (
            <div role="alert" style={{ marginBottom: 12 }}>
              {formErrors.map((msg) => (
                <p key={msg} className="sub" style={{ color: "var(--warn)" }}>
                  {msg}
                </p>
              ))}
            </div>
          )}

          <button
            type="button"
            className="btn primary"
            onClick={save}
            disabled={saving}
          >
            {saving ? "Saving…" : editingBagId ? "Save changes" : "Save bag"}
          </button>
        </section>
      )}
    </>
  );
}

// ---- One saved bag in the list ----

function BagCard({
  bag,
  onBrew,
  onEdit,
  onFinish,
}: {
  bag: Bag;
  onBrew: () => void;
  onEdit: () => void;
  onFinish: () => void;
}) {
  const origin =
    bag.bean.origin_country && bag.bean.origin_country !== "Unknown"
      ? bag.bean.origin_country
      : null;

  return (
    <div className="bag">
      <div className="top">
        <div className="icn">
          <BeanIcon />
        </div>
        <div>
          <div className="nm">
            {bag.roaster} — {bag.name}
          </div>
          <div className="rs">
            {origin ? `${origin} · ` : ""}≈{bag.brews_left} brews left
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button
          type="button"
          className="btn primary"
          style={{ flex: 1 }}
          onClick={onBrew}
        >
          Brew this
        </button>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button
          type="button"
          className="btn ghost"
          style={{ flex: 1 }}
          onClick={onEdit}
        >
          Edit
        </button>
        <button
          type="button"
          className="btn ghost"
          style={{ flex: 1 }}
          onClick={onFinish}
        >
          Finished
        </button>
      </div>
    </div>
  );
}

// ---- Pure helpers ----

/** Validate the add-bag form. Returns a list of plain-language error messages. */
function validateBag({
  roaster,
  name,
  origin,
  flavors,
}: {
  roaster: string;
  name: string;
  origin: string;
  flavors: string[];
}): string[] {
  const errors: string[] = [];
  if (!roaster.trim()) errors.push("Roaster is required.");
  if (!name.trim()) errors.push("Coffee name is required.");
  if (!origin.trim()) errors.push("Origin country is required.");
  if (flavors.length === 0) errors.push("Pick at least one flavour profile.");
  return errors;
}

/**
 * Format a stored altitude min/max back into the single input string, the
 * inverse of parseAltitude — so editing a bag shows what the user typed.
 * Equal bounds collapse to one number; differing bounds show as "min-max".
 */
function formatAltitude(min?: number | null, max?: number | null): string {
  if (min == null && max == null) return "";
  if (min != null && max != null) {
    return min === max ? String(min) : `${min}-${max}`;
  }
  return String(min ?? max);
}

/** Parse an altitude string like "1800" or "1500-2000" into a min/max range. */
function parseAltitude(s: string): { min?: number; max?: number } {
  const text = s.trim().replace(/\s/g, "");
  if (!text) return {};
  if (text.includes("-")) {
    const [a, b] = text.split("-", 2);
    const min = parseInt(a, 10);
    const max = parseInt(b, 10);
    if (Number.isNaN(min) || Number.isNaN(max)) return {};
    return { min, max };
  }
  const v = parseInt(text, 10);
  if (Number.isNaN(v)) return {};
  return { min: v, max: v };
}

// BrewMatch front-end → "brain" API client.
//
// The brain is the Python service (Goal A, live on Render). Its base URL comes
// from NEXT_PUBLIC_BREWMATCH_API_URL so the same build can point at local dev or
// production by changing one environment variable. See apps/web/.env.example.

const API_URL = process.env.NEXT_PUBLIC_BREWMATCH_API_URL;

// The brain's free Render instance sleeps after ~15 min idle and takes up to
// ~75s to wake on the first call. Give requests generous headroom rather than
// hanging forever.
const REQUEST_TIMEOUT_MS = 90_000;

/** The taste problems a user can flag on the Diagnose screen. */
export type FlagId = "too_sour" | "too_bitter" | "too_weak" | "astringent";

// ---------------------------------------------------------------------------
// Grinders — translate the generic 1-10 grind scale into a grinder's own dial
// ---------------------------------------------------------------------------

/** One grinder from the brain's catalog. */
export interface Grinder {
  id: string;
  brand: string;
  model: string;
  type: "hand" | "electric";
  /** The grinder's own unit: "clicks", "rotations", or "setting". */
  scale: string;
  /** Maps each "1".."10" generic step to this grinder's dial value. */
  mapping: Record<string, number>;
}

/**
 * Fetch the grinder catalog from the brain.
 *
 * The catalog rarely changes, so callers should fetch it once and cache it —
 * each grind translation is then a local lookup with no further network call.
 */
export async function getGrinders(): Promise<Grinder[]> {
  const res = await getJson<{ grinders: Grinder[] }>("/grinders");
  return res.grinders;
}

// ---------------------------------------------------------------------------
// Recommend — describe beans, get ranked pour-over recipes
// ---------------------------------------------------------------------------

/** Brew methods the brain knows (matches BrewMethod in the Python brain). */
export type BrewMethodId = "V60" | "Kalita Wave" | "Origami";

/** Coffee processing methods (matches Process enum). */
export type ProcessId =
  "washed" | "natural" | "honey" | "anaerobic" | "wet-hulled" | "unknown";

/** Roast levels (matches RoastLevel enum). */
export type RoastLevelId =
  "light" | "medium-light" | "medium" | "medium-dark" | "dark" | "unknown";

/** The fixed flavour vocabulary the brain accepts (matches FLAVOR_CLUSTERS). */
export const FLAVOR_CLUSTERS = [
  "Floral",
  "Berry",
  "Citrus",
  "Stone Fruit",
  "Tropical",
  "Sweet",
  "Chocolate",
  "Nutty",
  "Spice",
  "Roasted",
  "Vegetal",
  "Tea-like",
  "Fermented",
  "Syrupy",
  "Balanced",
] as const;

/** What the user tells us about a bag of beans before we recommend. */
export interface BeanInput {
  origin_country: string;
  process: ProcessId;
  roast_level: RoastLevelId;
  flavor_clusters: string[];
  /** Free-text the brain stores as the bean's source description. */
  source_text: string;
}

/** One step of the pour schedule. */
export interface PourStep {
  step: number;
  time_offset_s: number;
  water_g: number;
}

/**
 * Which beans a recipe suits. The web doesn't display this, but it's part of
 * the recipe the brain returns and the brain requires it back when saving a
 * brew — so we carry it through verbatim rather than dropping it.
 */
export interface SuitableFor {
  roast_levels: string[];
  origins: string[];
  processes: string[];
  flavor_profiles: string[];
}

/** A full recipe as the brain returns it. */
export interface Recipe {
  recipe_id: string;
  source: string;
  method: BrewMethodId;
  dose_g: number;
  water_total_g: number;
  ratio: number;
  /** Generic 1-10 grind scale; B3-grinder translates this per grinder. */
  grind_setting: number;
  water_temp_c: number;
  bloom_time_s: number;
  total_time_s: number;
  pours: PourStep[];
  suitable_for: SuitableFor;
  instructions: string;
  source_url?: string | null;
  source_tier?: "champion" | "barista" | "enthusiast" | null;
}

/** One ranked recipe in a recommendation result. */
export interface RankedRecipe {
  recipe: Recipe;
  rank: number;
  score: number;
  /** The taste predictor's guess, when a trained model is loaded. */
  predicted_score?: number | null;
}

/** The brain's full answer to a /recommend request. */
export interface RecommendResult {
  recipes: RankedRecipe[];
  total_candidates: number;
}

/**
 * Ask the brain to rank pour-over recipes for a bean and brew method.
 *
 * The bean fields map straight onto the Python BeanProfile; we send a
 * non-empty source_text because the brain requires one.
 */
export async function recommend(
  bean: BeanInput,
  method: BrewMethodId = "V60",
  topK = 3,
): Promise<RecommendResult> {
  return postJson<RecommendResult>("/recommend", {
    bean,
    preferences: { brew_methods: [method] },
    top_k: topK,
  });
}

/** One concrete change the brain suggests for the next brew. */
export interface DiagnoseSuggestion {
  parameter: string;
  reason: string;
  // Rule-based shape (flags-only request):
  direction?: string;
  // ML shape (when a bean + recipe are supplied):
  current_value?: unknown;
  suggested_value?: unknown;
  confidence?: number;
}

/** Plain-language explanation of one flagged problem. */
export interface DiagnoseAssessment {
  flag: string;
  cause: string;
  assessment: string;
}

/** The brain's full answer to a /diagnose request. */
export interface DiagnoseResult {
  mode: "ml" | "rule_based" | "no_flags";
  suggestions: DiagnoseSuggestion[];
  // rule_based mode:
  assessments?: DiagnoseAssessment[];
  // ml mode:
  overall_assessment?: string;
}

/**
 * Ask the brain to diagnose a brew from the taste problems the user noticed.
 *
 * For B2 we send only the flags; the brain answers with its rule-based table.
 * Once the log-a-brew screen exists (B3) we can also pass the bean + recipe so
 * the ML engine personalises the suggestions.
 */
export async function diagnose(flags: FlagId[]): Promise<DiagnoseResult> {
  return postJson<DiagnoseResult>("/diagnose", { flags });
}

// ---------------------------------------------------------------------------
// Brews — log a brew and read it back as history
// ---------------------------------------------------------------------------

/** Taste problems a user can flag when rating a brew (matches DIRECTIONAL_FLAGS). */
export const BREW_FLAGS = [
  { id: "too_sour", label: "Too sour" },
  { id: "too_bitter", label: "Too bitter" },
  { id: "too_weak", label: "Too weak" },
  { id: "too_harsh", label: "Too harsh" },
  { id: "astringent", label: "Astringent" },
] as const;

export type BrewFlagId = (typeof BREW_FLAGS)[number]["id"];

/** How a brew tasted. */
export interface BrewFeedback {
  thumbs_up: boolean;
  /** Optional 1-10 rating. */
  score?: number;
  directional_flags?: BrewFlagId[];
  notes?: string;
}

/**
 * Save a brew: the beans used, the recipe followed, and how it tasted.
 *
 * Feeds the History screen and the learning loop. The full recipe (including
 * suitable_for) is sent back verbatim so the brain can reconstruct it.
 */
export async function saveBrew(
  userId: string,
  bean: BeanInput,
  recipe: Recipe,
  feedback: BrewFeedback,
  bagId?: string | null,
): Promise<{ saved: boolean; brew_id: string }> {
  return postJson(`/brews/${encodeURIComponent(userId)}`, {
    brew_id: `brew-${crypto.randomUUID()}`,
    timestamp: new Date().toISOString(),
    bean,
    recipe,
    feedback,
    // Present only when the brew came from a saved bag, so the bag's running-low
    // countdown can sum the dose against it. One-off brews send null.
    bag_id: bagId ?? null,
    actual_dose_g: recipe.dose_g,
  });
}

/** The bean fields the History screen reads back (a subset of the stored profile). */
export interface BrewBean {
  origin_country?: string;
  roast_level?: string;
  process?: string;
}

/** One saved brew as the brain returns it. */
export interface BrewRecord {
  brew_id: string;
  timestamp: string;
  bean: BrewBean;
  recipe: Recipe;
  feedback: BrewFeedback;
  bag_id?: string | null;
  actual_dose_g?: number | null;
}

/** A user's recent brews, newest first. */
export async function getBrews(
  userId: string,
  limit = 50,
): Promise<BrewRecord[]> {
  const res = await getJson<{ brews: BrewRecord[]; count: number }>(
    `/brews/${encodeURIComponent(userId)}?limit=${limit}`,
  );
  return res.brews;
}

/**
 * The personalization state for a user: how many brews they've logged and which
 * learning phase that puts them in. Drives the "what BrewMatch has learned"
 * line on the History screen.
 */
export interface LearnState {
  phase: string;
  brew_count: number;
}

export async function getLearnState(userId: string): Promise<LearnState> {
  return getJson<LearnState>(`/learn/${encodeURIComponent(userId)}`);
}

// ---------------------------------------------------------------------------
// Coffee bags — the coffees a user owns
// ---------------------------------------------------------------------------

/** What the user enters when adding a bag (mirrors the brain's POST /bags body). */
export interface BagInput {
  roaster: string;
  name: string;
  bag_size_g: number;
  origin_country: string;
  process: ProcessId;
  roast_level: RoastLevelId;
  flavor_clusters: string[];
  region?: string;
  variety?: string;
  altitude_min_m?: number;
  altitude_max_m?: number;
}

/** A saved bag as the brain returns it, with the running-low estimate. */
export interface Bag {
  bag_id: string;
  roaster: string;
  name: string;
  bag_size_g: number;
  date_opened?: string | null;
  /** Full bean profile — fed straight into recommend() when you brew this bag. */
  bean: BeanInput;
  /** Total grams already brewed from this bag. */
  grams_used: number;
  /** Estimated brews remaining (grams left ÷ a nominal dose). Show with "≈". */
  brews_left: number;
}

/** A user's active (unfinished) bags, newest first. */
export async function getBags(userId: string): Promise<Bag[]> {
  const res = await getJson<{ bags: Bag[]; count: number }>(
    `/bags/${encodeURIComponent(userId)}`,
  );
  return res.bags;
}

/** Save a new bag; returns it with its running-low estimate. */
export async function createBag(userId: string, input: BagInput): Promise<Bag> {
  return postJson<Bag>(`/bags/${encodeURIComponent(userId)}`, input);
}

/** Mark a bag finished so it drops off the active list. */
export async function finishBag(userId: string, bagId: string): Promise<void> {
  await postJson(
    `/bags/${encodeURIComponent(userId)}/${encodeURIComponent(bagId)}/finish`,
    {},
  );
}

// ---------------------------------------------------------------------------
// Shared transport — one place for the brain URL, timeout, and plain-language
// error messages so every endpoint behaves the same way.
// ---------------------------------------------------------------------------

/** POST a JSON body to a brain endpoint and parse the JSON answer. */
async function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** GET a brain endpoint and parse the JSON answer. */
async function getJson<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

/**
 * Send a request to a brain endpoint and parse the JSON answer.
 *
 * Centralises the wake-up timeout and turns low-level fetch failures into
 * messages a user can act on (the brain is asleep, the network is down, etc.).
 */
async function request<T>(path: string, init: RequestInit): Promise<T> {
  if (!API_URL) {
    throw new Error(
      "BrewMatch isn't configured to reach the brain yet (missing API URL).",
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new Error(
        `The brain couldn't answer just now (error ${res.status}). Please try again.`,
      );
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(
        "The brain took too long to wake up. Give it a moment and try again.",
      );
    }
    if (err instanceof TypeError) {
      // Network-level failure (offline, DNS, CORS rejection).
      throw new Error(
        "Couldn't reach the brain. Check your connection and try again.",
      );
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

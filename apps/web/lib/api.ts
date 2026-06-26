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
  if (!API_URL) {
    throw new Error(
      "BrewMatch isn't configured to reach the brain yet (missing API URL).",
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_URL}/diagnose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flags }),
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new Error(
        `The brain couldn't answer just now (error ${res.status}). Please try again.`,
      );
    }

    return (await res.json()) as DiagnoseResult;
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

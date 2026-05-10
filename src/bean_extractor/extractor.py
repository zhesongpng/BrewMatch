"""Bean profile extraction pipeline.

Converts free-text roaster descriptions into structured BeanProfile objects
using LLM-based extraction with validation and confidence scoring.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from src.data_models import (
    FLAVOR_CLUSTERS,
    BeanProfile,
    Process,
    RoastLevel,
)

load_dotenv()

logger = logging.getLogger(__name__)

# --- Constants ---

KNOWN_COFFEE_COUNTRIES: set[str] = {
    "Ethiopia", "Colombia", "Brazil", "Guatemala", "Kenya",
    "Costa Rica", "Panama", "Honduras", "Nicaragua", "El Salvador",
    "Peru", "Bolivia", "Ecuador", "Rwanda", "Burundi", "Tanzania",
    "Uganda", "Democratic Republic of Congo", "Mexico", "Jamaica",
    "Haiti", "Dominican Republic", "Yemen", "India", "Indonesia",
    "Vietnam", "Thailand", "Myanmar", "Papua New Guinea", "Hawaii",
    "Australia",
}

VALID_PROCESSES: set[str] = {p.value for p in Process}
VALID_ROAST_LEVELS: set[str] = {r.value for r in RoastLevel}
VALID_FLAVOR_CLUSTERS: set[str] = set(FLAVOR_CLUSTERS)

LLM_TIMEOUT_FIRST = 8  # seconds
LLM_TIMEOUT_RETRY = 5  # seconds
MIN_SOURCE_LENGTH = 5

# Keyword-to-cluster mapping for deterministic normalization.
# Each key is a lowercase keyword; value is the cluster name it maps to.
# A single keyword can map to multiple clusters (e.g., "bergamot" -> Citrus + Floral).
_KEYWORD_TO_CLUSTERS: dict[str, list[str]] = {
    # Berry
    "blueberry": ["Berry"],
    "blackberry": ["Berry"],
    "raspberry": ["Berry"],
    "strawberry": ["Berry"],
    "berry": ["Berry"],
    "berry-like": ["Berry"],
    "currant": ["Berry"],
    "cranberry": ["Berry"],
    "boysenberry": ["Berry"],
    "acai": ["Berry"],
    "jam": ["Berry", "Sweet"],
    "jammy": ["Berry", "Sweet"],
    # Citrus
    "citrus": ["Citrus"],
    "lemon": ["Citrus"],
    "lime": ["Citrus"],
    "orange": ["Citrus", "Sweet"],
    "grapefruit": ["Citrus"],
    "tangerine": ["Citrus"],
    "mandarin": ["Citrus"],
    "yuzu": ["Citrus"],
    "bergamot": ["Citrus", "Floral"],
    "bright": ["Citrus"],
    "acidity": ["Citrus"],
    "zesty": ["Citrus"],
    "acidic": ["Citrus"],
    # Floral
    "jasmine": ["Floral"],
    "rose": ["Floral"],
    "hibiscus": ["Floral", "Citrus"],
    "lavender": ["Floral"],
    "chamomile": ["Floral"],
    "elderflower": ["Floral"],
    "lilac": ["Floral"],
    "violet": ["Floral"],
    "floral": ["Floral"],
    "blossom": ["Floral"],
    "flower": ["Floral"],
    "perfume": ["Floral"],
    "magnolia": ["Floral"],
    # Stone Fruit
    "peach": ["Stone Fruit"],
    "apricot": ["Stone Fruit"],
    "plum": ["Stone Fruit", "Berry"],
    "cherry": ["Stone Fruit", "Berry"],
    "nectarine": ["Stone Fruit"],
    "stone fruit": ["Stone Fruit"],
    # Tropical
    "mango": ["Tropical"],
    "passion fruit": ["Tropical"],
    "passionfruit": ["Tropical"],
    "pineapple": ["Tropical"],
    "coconut": ["Tropical"],
    "banana": ["Tropical"],
    "papaya": ["Tropical"],
    "guava": ["Tropical"],
    "lychee": ["Tropical", "Floral"],
    "tropical": ["Tropical"],
    "kiwi": ["Tropical"],
    # Sweet
    "caramel": ["Sweet"],
    "honey": ["Sweet", "Syrupy"],
    "sugar": ["Sweet"],
    "sugarcane": ["Sweet"],
    "sweet": ["Sweet"],
    "vanilla": ["Sweet"],
    "maple": ["Sweet"],
    "butterscotch": ["Sweet"],
    "toffee": ["Sweet"],
    "molasses": ["Syrupy", "Sweet"],
    "brown sugar": ["Sweet"],
    "candy": ["Sweet"],
    # Chocolate
    "chocolate": ["Chocolate"],
    "dark chocolate": ["Chocolate"],
    "cocoa": ["Chocolate"],
    "cacao": ["Chocolate"],
    "cocoa nibs": ["Chocolate"],
    "mocha": ["Chocolate"],
    "milk chocolate": ["Chocolate", "Sweet"],
    "brownie": ["Chocolate"],
    # Nutty
    "nutty": ["Nutty"],
    "almond": ["Nutty"],
    "hazelnut": ["Nutty"],
    "peanut": ["Nutty"],
    "walnut": ["Nutty"],
    "cashew": ["Nutty"],
    "pecan": ["Nutty"],
    "nut": ["Nutty"],
    "nuts": ["Nutty"],
    "praline": ["Nutty", "Sweet"],
    "marzipan": ["Nutty"],
    # Spice
    "cinnamon": ["Spice"],
    "cardamom": ["Spice"],
    "clove": ["Spice"],
    "ginger": ["Spice"],
    "nutmeg": ["Spice"],
    "pepper": ["Spice"],
    "spicy": ["Spice"],
    "spice": ["Spice"],
    "allspice": ["Spice"],
    "anise": ["Spice"],
    "star anise": ["Spice"],
    # Roasted
    "tobacco": ["Roasted"],
    "smoky": ["Roasted"],
    "roasted": ["Roasted"],
    "toast": ["Roasted"],
    "burnt": ["Roasted"],
    "ash": ["Roasted"],
    "char": ["Roasted"],
    "campfire": ["Roasted"],
    "leather": ["Roasted"],
    "pipe tobacco": ["Roasted"],
    # Vegetal
    "green pepper": ["Vegetal"],
    "grassy": ["Vegetal"],
    "herbal": ["Vegetal"],
    "herb": ["Vegetal"],
    "vegetal": ["Vegetal"],
    "green tea": ["Tea-like", "Vegetal"],
    "olive": ["Vegetal"],
    "tomato": ["Vegetal"],
    "leafy": ["Vegetal"],
    "hay": ["Vegetal"],
    # Tea-like
    "tea": ["Tea-like"],
    "earl grey": ["Tea-like", "Citrus", "Floral"],
    "oolong": ["Tea-like", "Floral"],
    "green tea": ["Tea-like", "Vegetal"],
    "black tea": ["Tea-like"],
    "chai": ["Tea-like", "Spice"],
    "matcha": ["Tea-like"],
    "sencha": ["Tea-like"],
    # Fermented
    "winey": ["Fermented"],
    "wine": ["Fermented"],
    "fermented": ["Fermented"],
    "boozy": ["Fermented"],
    "rum": ["Fermented"],
    "whiskey": ["Fermented"],
    "brandy": ["Fermented"],
    "vinegar": ["Fermented"],
    "kombucha": ["Fermented"],
    "probiotic": ["Fermented"],
    # Syrupy
    "syrup": ["Syrupy"],
    "syrupy": ["Syrupy"],
    "molasses": ["Syrupy", "Sweet"],
    "viscous": ["Syrupy"],
    "thick": ["Syrupy"],
    "juicy": ["Syrupy"],
    "nectar": ["Syrupy", "Sweet"],
    # Balanced
    "balanced": ["Balanced"],
    "clean": ["Balanced"],
    "smooth": ["Balanced"],
    "round": ["Balanced"],
    "mellow": ["Balanced"],
    "harmonious": ["Balanced"],
}

PROMPT_TEMPLATE = """You are a specialty coffee expert. Extract a structured bean profile from this roaster description.

Source text: "{source_text}"

Extract the following fields as JSON:
- origin_country: string (coffee-producing country)
- origin_region: string or null (sub-region, e.g., "Yirgacheffe", "Huila")
- process: one of ["washed", "natural", "honey", "anaerobic", "wet-hulled", "unknown"]
- roast_level: one of ["light", "medium-light", "medium", "medium-dark", "dark", "unknown"]
- flavor_notes: array of individual descriptors from the WCR Sensory Lexicon
- flavor_clusters: array mapped to these 15 clusters: [Floral, Berry, Citrus, Stone Fruit, Tropical, Sweet, Chocolate, Nutty, Spice, Roasted, Vegetal, Tea-like, Fermented, Syrupy, Balanced]
- variety: string or null (cultivar, e.g., "Gesha", "Bourbon", "SL28")
- altitude_min_m: integer or null
- altitude_max_m: integer or null

Rules:
- Map flavor descriptors to the closest cluster(s). A single note may map to multiple clusters.
- If a field cannot be determined, use null (for optional fields) or "unknown" (for enum fields).
- Be conservative: only extract what is explicitly stated or strongly implied.
- Origin country is REQUIRED. If no origin is identifiable, set origin_country to "unknown"."""


# --- Prompt-injection sanitization ---

_MAX_SOURCE_LENGTH = 2000

_INJECTION_PATTERNS = re.compile(
    r"(?i)"
    r"(ignore\s+(previous|above|all|prior)\s*(instructions|prompts|rules|directions))"
    r"|(forget\s+(everything|all|previous|prior))"
    r"|(you\s+are\s+now\b)"
    r"|(new\s+instructions?\s*:)"
    r"|(system\s*:\s*)"
    r"|(\[INST\])"
    r"|(<\|.*?\|>)"
    r"|(###\s*(system|instruction|user|assistant))",
)


def _sanitize_source(source_text: str) -> str:
    """Sanitize user-supplied text before LLM prompt interpolation.

    Strips common prompt-injection patterns, bounds length, and removes
    control characters to prevent manipulation of the extraction prompt.
    """
    text = source_text[:_MAX_SOURCE_LENGTH]
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = _INJECTION_PATTERNS.sub("[redacted]", text)
    return text


# --- Data Classes ---


@dataclass
class ExtractionResult:
    """Result of bean profile extraction."""

    bean_profile: BeanProfile
    confidence: float
    confidence_tier: str  # "HIGH", "MEDIUM", "LOW"
    missing_fields: list[str]
    used_manual_entry: bool


# --- Confidence Weights (per spec Section 3.3) ---

_CONFIDENCE_WEIGHTS = {
    "origin_country": 0.25,
    "process": 0.15,
    "roast_level": 0.15,
    "flavor_clusters": 0.25,
    "variety": 0.05,
    "altitude": 0.05,
    "origin_region": 0.10,
}


def _tier_for_confidence(confidence: float) -> str:
    """Map a confidence score to a tier string."""
    if confidence >= 0.7:
        return "HIGH"
    if confidence >= 0.4:
        return "MEDIUM"
    return "LOW"


# --- Extractor ---


class BeanExtractor:
    """Extracts structured BeanProfile from free-text roaster descriptions.

    Pipeline stages:
        1. LLM structured extraction (JSON response)
        2. Validation against schema constraints
        3. Confidence scoring with tier assignment
        4. Flavor cluster normalization

    Can be constructed with explicit api_key/model parameters, or from
    environment variables (LLM_MODEL, LLM_API_KEY, LLM_BASE_URL). Manual
    profile creation via create_manual_profile() requires no API key.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            api_key: OpenAI-compatible API key. Falls back to LLM_API_KEY env var.
            model: Model name to use. Falls back to LLM_MODEL env var.
            base_url: Optional API base URL for non-OpenAI providers.
        """
        resolved_api_key = api_key or os.environ.get("LLM_API_KEY", "")
        resolved_model = model or os.environ.get("LLM_MODEL", "")
        resolved_base_url = base_url or os.environ.get("LLM_BASE_URL")

        self._model = resolved_model
        self._client: OpenAI | None = None

        if resolved_api_key:
            self._client = OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )

    def extract(self, source_text: str) -> ExtractionResult:
        """Run the full extraction pipeline on source text.

        Args:
            source_text: Free-text roaster description (min 5 characters).

        Returns:
            ExtractionResult with structured profile and confidence metadata.

        Raises:
            ValueError: If source_text is too short or API key is missing.
            RuntimeError: If LLM call fails after retry.
        """
        if len(source_text.strip()) < MIN_SOURCE_LENGTH:
            raise ValueError(
                f"Source text must be at least {MIN_SOURCE_LENGTH} characters. "
                "Please enter a longer description from the coffee bag label."
            )

        if len(source_text) > _MAX_SOURCE_LENGTH:
            source_text = source_text[:_MAX_SOURCE_LENGTH]

        logger.info("extractor.extract.start text_length=%d", len(source_text))

        raw = self._call_llm(source_text)
        validated = self._validate(raw)
        confidence, tier, missing = self._compute_confidence(validated)

        profile = BeanProfile(
            origin_country=validated["origin_country"],
            process=Process(validated["process"]),
            roast_level=RoastLevel(validated["roast_level"]),
            flavor_clusters=validated["flavor_clusters"],
            source_text=source_text,
            origin_region=validated.get("origin_region"),
            flavor_notes=validated.get("flavor_notes"),
            variety=validated.get("variety"),
            altitude_min_m=validated.get("altitude_min_m"),
            altitude_max_m=validated.get("altitude_max_m"),
            extraction_confidence=confidence,
        )

        return ExtractionResult(
            bean_profile=profile,
            confidence=confidence,
            confidence_tier=tier,
            missing_fields=missing,
            used_manual_entry=False,
        )

    @staticmethod
    def _parse_llm_json(raw_text: str) -> dict:
        """Parse JSON from LLM output, handling common variations.

        Strips markdown code fences (```json ... ```), leading/trailing
        whitespace, and trailing commas before parsing. Raises ValueError
        with a clear message when the content cannot be parsed as JSON.

        Args:
            raw_text: Raw text output from the LLM.

        Returns:
            Parsed dict from the JSON content.

        Raises:
            ValueError: If the text cannot be parsed as valid JSON.
        """
        import re

        text = raw_text.strip()

        # Strip markdown code fences: ```json ... ``` or ``` ... ```
        fence_match = re.match(
            r"^```(?:json)?\s*\n?(.*?)\n?\s*```$",
            text,
            re.DOTALL,
        )
        if fence_match:
            text = fence_match.group(1).strip()

        # Remove trailing commas before } or ] (common LLM artefact)
        text = re.sub(r",\s*([}\]])", r"\1", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse LLM response as JSON: {exc}. "
                "Please enter the bean details manually."
            ) from exc

    def _call_llm(self, source_text: str) -> dict:
        """Call the LLM with the extraction prompt. Retries once on failure.

        Args:
            source_text: The roaster description to extract from.

        Returns:
            Parsed JSON dict from the LLM response.

        Raises:
            ValueError: If API key is missing (no client configured).
            RuntimeError: If both the initial call and retry fail.
        """
        if self._client is None:
            raise ValueError(
                "API key is required for LLM extraction. "
                "Set LLM_API_KEY in .env or pass api_key to BeanExtractor()."
            )

        prompt = PROMPT_TEMPLATE.format(source_text=_sanitize_source(source_text))

        for attempt, timeout in enumerate([LLM_TIMEOUT_FIRST, LLM_TIMEOUT_RETRY]):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=512,
                    response_format={"type": "json_object"},
                    timeout=timeout,
                )
                content = response.choices[0].message.content
                if not content:
                    if attempt == 0:
                        logger.warning("LLM returned empty response, retrying...")
                        continue
                    raise RuntimeError("LLM returned empty response after retry.")

                return self._parse_llm_json(content)

            except json.JSONDecodeError as exc:
                if attempt == 0:
                    logger.warning("LLM returned invalid JSON, retrying: %s", exc)
                    continue
                raise RuntimeError(
                    "LLM returned invalid JSON after retry. "
                    "Please enter the bean details manually."
                ) from exc

            except Exception as exc:
                if attempt == 0:
                    logger.warning("LLM call failed, retrying: %s", exc)
                    continue
                raise RuntimeError(
                    "Could not analyze the description. "
                    "Please enter the details manually."
                ) from exc

        # Should not reach here, but satisfy type checker
        raise RuntimeError("LLM extraction failed after retry.")

    def _validate(self, raw: dict) -> dict:
        """Validate and sanitize raw LLM output against schema constraints.

        For each field: coerce to the correct type, apply enum constraints,
        filter invalid values, and set defaults for missing data.
        """
        validated: dict = {}

        # origin_country: non-empty string, must be in known list or "unknown"
        origin = str(raw.get("origin_country", "unknown")).strip()
        if not origin:
            origin = "unknown"
        # Case-insensitive match against known countries
        matched_country = None
        for country in KNOWN_COFFEE_COUNTRIES:
            if origin.lower() == country.lower():
                matched_country = country
                break
        validated["origin_country"] = matched_country if matched_country else "unknown"

        # origin_region: string or null
        region = raw.get("origin_region")
        validated["origin_region"] = str(region).strip() if region else None

        # process: must be in enum set, else "unknown"
        process = str(raw.get("process", "unknown")).strip().lower()
        validated["process"] = process if process in VALID_PROCESSES else "unknown"

        # roast_level: must be in enum set, else "unknown"
        roast = str(raw.get("roast_level", "unknown")).strip().lower()
        validated["roast_level"] = roast if roast in VALID_ROAST_LEVELS else "unknown"

        # flavor_notes: array of strings, filter empty
        notes = raw.get("flavor_notes", [])
        if not isinstance(notes, list):
            notes = []
        validated["flavor_notes"] = [
            str(n).strip() for n in notes if n and str(n).strip()
        ] or None

        # flavor_clusters: filter to valid cluster names, with keyword normalization
        clusters = raw.get("flavor_clusters", [])
        if not isinstance(clusters, list):
            clusters = []
        validated["flavor_clusters"] = self._normalize_clusters(clusters)
        # Guarantee at least one cluster (default to ["Balanced"])
        if not validated["flavor_clusters"]:
            validated["flavor_clusters"] = ["Balanced"]

        # variety: string or null
        variety = raw.get("variety")
        validated["variety"] = str(variety).strip() if variety else None

        # altitude_min_m: integer >= 0, <= 3000
        alt_min = raw.get("altitude_min_m")
        if alt_min is not None:
            try:
                alt_min = int(alt_min)
                if not (0 <= alt_min <= 3000):
                    alt_min = None
            except (ValueError, TypeError):
                alt_min = None
        validated["altitude_min_m"] = alt_min

        # altitude_max_m: integer >= 0, <= 3000, >= min if both present
        alt_max = raw.get("altitude_max_m")
        if alt_max is not None:
            try:
                alt_max = int(alt_max)
                if not (0 <= alt_max <= 3000):
                    alt_max = None
                elif validated["altitude_min_m"] is not None and alt_max < validated["altitude_min_m"]:
                    alt_max = None
            except (ValueError, TypeError):
                alt_max = None
        validated["altitude_max_m"] = alt_max

        return validated

    def _compute_confidence(
        self, validated: dict
    ) -> tuple[float, str, list[str]]:
        """Compute confidence score, tier, and list of missing fields.

        Uses weighted scoring per spec Section 3.3:
        - origin_country (0.25): present and not "unknown"
        - process (0.15): present and not "unknown"
        - roast_level (0.15): present and not "unknown"
        - flavor_clusters (0.25): has >= 1 entry
        - variety (0.05): present and non-null
        - altitude (0.05): either min or max present
        - origin_region (0.10): present and non-null

        Args:
            validated: The validated extraction dict.

        Returns:
            Tuple of (confidence score, tier string, list of missing field names).
        """
        scores: dict[str, float] = {}
        missing: list[str] = []

        # origin_country
        if validated["origin_country"] != "unknown":
            scores["origin_country"] = _CONFIDENCE_WEIGHTS["origin_country"]
        else:
            missing.append("origin_country")

        # process
        if validated["process"] != "unknown":
            scores["process"] = _CONFIDENCE_WEIGHTS["process"]
        else:
            missing.append("process")

        # roast_level
        if validated["roast_level"] != "unknown":
            scores["roast_level"] = _CONFIDENCE_WEIGHTS["roast_level"]
        else:
            missing.append("roast_level")

        # flavor_clusters
        if len(validated["flavor_clusters"]) >= 1:
            scores["flavor_clusters"] = _CONFIDENCE_WEIGHTS["flavor_clusters"]
        else:
            missing.append("flavor_clusters")

        # variety
        if validated.get("variety"):
            scores["variety"] = _CONFIDENCE_WEIGHTS["variety"]
        else:
            missing.append("variety")

        # altitude (either min or max)
        if validated.get("altitude_min_m") is not None or validated.get("altitude_max_m") is not None:
            scores["altitude"] = _CONFIDENCE_WEIGHTS["altitude"]
        else:
            missing.append("altitude")

        # origin_region
        if validated.get("origin_region"):
            scores["origin_region"] = _CONFIDENCE_WEIGHTS["origin_region"]
        else:
            missing.append("origin_region")

        confidence = sum(scores.values())
        # Clamp to [0.0, 1.0] for floating-point safety
        confidence = round(min(1.0, max(0.0, confidence)), 2)

        return confidence, _tier_for_confidence(confidence), missing

    def _normalize_clusters(self, clusters: list) -> list[str]:
        """Normalize cluster names to the 15-cluster taxonomy.

        First tries exact/case-insensitive match against valid cluster names.
        Then falls back to keyword-based mapping for free-text descriptors.
        Deduplicates results while preserving order.
        """
        normalized: list[str] = []
        seen: set[str] = set()

        for c in clusters:
            c_str = str(c).strip()
            if not c_str:
                continue

            # Exact match against valid clusters
            if c_str in VALID_FLAVOR_CLUSTERS:
                if c_str not in seen:
                    normalized.append(c_str)
                    seen.add(c_str)
                continue

            # Case-insensitive exact match against valid clusters
            matched = False
            for valid in VALID_FLAVOR_CLUSTERS:
                if c_str.lower() == valid.lower():
                    if valid not in seen:
                        normalized.append(valid)
                        seen.add(valid)
                    matched = True
                    break
            if matched:
                continue

            # Keyword-based matching for free-text flavor descriptors
            lower = c_str.lower()
            for keyword, mapped_clusters in _KEYWORD_TO_CLUSTERS.items():
                if keyword in lower:
                    for mc in mapped_clusters:
                        if mc not in seen:
                            normalized.append(mc)
                            seen.add(mc)

        return normalized


# --- Manual Entry ---


def create_manual_profile(
    origin_country: str,
    process: str,
    roast_level: str,
    flavor_clusters: list[str],
    source_text: str = "manual entry",
    **optional_fields,
) -> ExtractionResult:
    """Create a BeanProfile from manual user entry.

    Bypasses the LLM entirely. The resulting profile has
    extraction_confidence=None to distinguish it from LLM-extracted profiles.

    Args:
        origin_country: Coffee-producing country (required).
        process: Processing method (required).
        roast_level: Roast level (required).
        flavor_clusters: List of flavor cluster names (required, min 1).
        source_text: Origin text, defaults to "manual entry".
        **optional_fields: Optional fields: origin_region, flavor_notes,
            variety, altitude_min_m, altitude_max_m.

    Returns:
        ExtractionResult with used_manual_entry=True and confidence=1.0.
    """
    # Normalize flavor clusters using keyword-aware normalization
    extractor = BeanExtractor.__new__(BeanExtractor)
    clusters = extractor._normalize_clusters(flavor_clusters)
    if not clusters:
        clusters = ["Balanced"]

    profile = BeanProfile(
        origin_country=origin_country,
        process=Process(process),
        roast_level=RoastLevel(roast_level),
        flavor_clusters=clusters,
        source_text=source_text,
        origin_region=optional_fields.get("origin_region"),
        flavor_notes=optional_fields.get("flavor_notes"),
        variety=optional_fields.get("variety"),
        altitude_min_m=optional_fields.get("altitude_min_m"),
        altitude_max_m=optional_fields.get("altitude_max_m"),
        extraction_confidence=None,
    )

    return ExtractionResult(
        bean_profile=profile,
        confidence=1.0,
        confidence_tier="HIGH",
        missing_fields=[],
        used_manual_entry=True,
    )

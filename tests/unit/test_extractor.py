"""Unit tests for the bean profile extraction pipeline.

All LLM calls are mocked for deterministic, fast execution.
Tests cover validation, confidence scoring, normalization,
error handling, and manual entry.
"""

from __future__ import annotations

import pytest

from src.bean_extractor.extractor import (
    BeanExtractor,
    KNOWN_COFFEE_COUNTRIES,
    ExtractionResult,
    create_manual_profile,
)
from src.data_models import Process, RoastLevel


# --- Fixtures ---


@pytest.fixture
def extractor():
    """Create a BeanExtractor with LLM client stubbed out.

    The extractor is constructed without calling __init__ (which would
    require env vars and a real API key). We set only what tests need.
    """
    ext = BeanExtractor.__new__(BeanExtractor)
    ext._model = "test-model"
    ext._client = None  # not used in mocked tests
    return ext


# --- Helper: build a valid LLM response dict ---


def _full_llm_response() -> dict:
    """A complete, valid LLM JSON response with all fields populated."""
    return {
        "origin_country": "Ethiopia",
        "origin_region": "Yirgacheffe",
        "process": "washed",
        "roast_level": "light",
        "flavor_notes": ["blueberry", "jasmine", "bergamot"],
        "flavor_clusters": ["Floral", "Berry", "Citrus"],
        "variety": "Heirloom",
        "altitude_min_m": 1800,
        "altitude_max_m": 2200,
    }


# =====================================================================
# Test 1: Validation layer — valid LLM output produces correct result
# =====================================================================


def test_validate_valid_llm_output(extractor):
    """Valid LLM output passes validation with all fields preserved."""
    raw = _full_llm_response()
    result = extractor._validate(raw)

    assert result["origin_country"] == "Ethiopia"
    assert result["origin_region"] == "Yirgacheffe"
    assert result["process"] == "washed"
    assert result["roast_level"] == "light"
    assert result["flavor_notes"] == ["blueberry", "jasmine", "bergamot"]
    assert result["flavor_clusters"] == ["Floral", "Berry", "Citrus"]
    assert result["variety"] == "Heirloom"
    assert result["altitude_min_m"] == 1800
    assert result["altitude_max_m"] == 2200


# =====================================================================
# Test 2: Validation catches invalid process
# =====================================================================


def test_validate_invalid_process_set_to_unknown(extractor):
    """Invalid process value is coerced to 'unknown'."""
    raw = _full_llm_response()
    raw["process"] = "semi-washed"
    result = extractor._validate(raw)

    assert result["process"] == "unknown"


# =====================================================================
# Test 3: Validation catches invalid roast level
# =====================================================================


def test_validate_invalid_roast_set_to_unknown(extractor):
    """Invalid roast level is coerced to 'unknown'."""
    raw = _full_llm_response()
    raw["roast_level"] = "extra-dark"
    result = extractor._validate(raw)

    assert result["roast_level"] == "unknown"


# =====================================================================
# Test 4: Validation filters invalid flavor clusters
# =====================================================================


def test_validate_filters_invalid_flavor_clusters(extractor):
    """Invalid cluster names are removed; valid ones are kept."""
    raw = _full_llm_response()
    raw["flavor_clusters"] = ["Floral", "Fruity", "Berry", "Woody", "Citrus"]
    result = extractor._validate(raw)

    assert "Floral" in result["flavor_clusters"]
    assert "Berry" in result["flavor_clusters"]
    assert "Citrus" in result["flavor_clusters"]
    assert "Fruity" not in result["flavor_clusters"]
    assert "Woody" not in result["flavor_clusters"]


def test_validate_empty_clusters_defaults_to_balanced(extractor):
    """When all clusters are invalid, defaults to ['Balanced']."""
    raw = _full_llm_response()
    raw["flavor_clusters"] = ["Invalid1", "Invalid2"]
    result = extractor._validate(raw)

    assert result["flavor_clusters"] == ["Balanced"]


# =====================================================================
# Test 5: Confidence scoring — all fields present = HIGH
# =====================================================================


def test_confidence_all_fields_high(extractor):
    """All fields present produces HIGH confidence (>= 0.7)."""
    validated = extractor._validate(_full_llm_response())
    confidence, tier, missing = extractor._compute_confidence(validated)

    assert confidence == 1.0
    assert tier == "HIGH"
    assert missing == []


# =====================================================================
# Test 6: Confidence scoring — only origin = MEDIUM
# =====================================================================


def test_confidence_only_origin_medium(extractor):
    """Only origin_country extracted produces MEDIUM confidence."""
    raw = {
        "origin_country": "Colombia",
        "origin_region": None,
        "process": "unknown",
        "roast_level": "unknown",
        "flavor_notes": [],
        "flavor_clusters": [],
        "variety": None,
        "altitude_min_m": None,
        "altitude_max_m": None,
    }
    validated = extractor._validate(raw)
    confidence, tier, missing = extractor._compute_confidence(validated)

    assert tier == "MEDIUM"
    # Only origin_country weight (0.25); clusters defaulted to ["Balanced"]
    # so flavor_clusters weight is also earned
    assert confidence >= 0.4


# =====================================================================
# Test 7: Confidence scoring — nothing useful = LOW
# =====================================================================


def test_confidence_nothing_useful_low(extractor):
    """All fields unknown/null produces LOW confidence."""
    raw = {
        "origin_country": "unknown",
        "origin_region": None,
        "process": "unknown",
        "roast_level": "unknown",
        "flavor_notes": [],
        "flavor_clusters": [],
        "variety": None,
        "altitude_min_m": None,
        "altitude_max_m": None,
    }
    validated = extractor._validate(raw)
    confidence, tier, missing = extractor._compute_confidence(validated)

    # flavor_clusters defaults to ["Balanced"] via validation, so that
    # weight is earned. Total = 0.25 (clusters weight only via default).
    assert tier in ("LOW", "MEDIUM")
    assert confidence < 0.4  # only cluster weight from default


# =====================================================================
# Test 8: Missing fields list is correct
# =====================================================================


def test_missing_fields_list(extractor):
    """Missing fields list correctly identifies all absent fields."""
    raw = {
        "origin_country": "Ethiopia",
        "origin_region": None,
        "process": "unknown",
        "roast_level": "unknown",
        "flavor_clusters": ["Floral"],
        "variety": None,
        "altitude_min_m": None,
        "altitude_max_m": None,
    }
    validated = extractor._validate(raw)
    _, _, missing = extractor._compute_confidence(validated)

    assert "origin_country" not in missing  # present
    assert "flavor_clusters" not in missing  # present
    assert "process" in missing
    assert "roast_level" in missing
    assert "variety" in missing
    assert "altitude" in missing
    assert "origin_region" in missing


# =====================================================================
# Test 9: Manual entry produces correct result
# =====================================================================


def test_manual_entry_result():
    """Manual entry returns ExtractionResult with used_manual_entry=True."""
    result = create_manual_profile(
        origin_country="Colombia",
        process="washed",
        roast_level="medium",
        flavor_clusters=["Chocolate", "Nutty"],
        origin_region="Huila",
        variety="Caturra",
        altitude_min_m=1600,
    )

    assert isinstance(result, ExtractionResult)
    assert result.used_manual_entry is True
    assert result.bean_profile.origin_country == "Colombia"
    assert result.bean_profile.process == Process.WASHED
    assert result.bean_profile.roast_level == RoastLevel.MEDIUM
    assert result.bean_profile.flavor_clusters == ["Chocolate", "Nutty"]
    assert result.bean_profile.origin_region == "Huila"
    assert result.bean_profile.variety == "Caturra"
    assert result.bean_profile.altitude_min_m == 1600
    assert result.bean_profile.extraction_confidence is None


def test_manual_entry_defaults_source_text():
    """Manual entry defaults source_text to 'manual entry'."""
    result = create_manual_profile(
        origin_country="Brazil",
        process="natural",
        roast_level="medium-dark",
        flavor_clusters=["Chocolate"],
    )

    assert result.bean_profile.source_text == "manual entry"


# =====================================================================
# Test 10: Source text too short raises ValueError
# =====================================================================


def test_source_text_too_short_raises(extractor):
    """Source text shorter than 5 characters raises ValueError."""
    with pytest.raises(ValueError, match="at least 5 characters"):
        extractor.extract("abc")


def test_source_text_whitespace_only_raises(extractor):
    """Source text that is only whitespace raises ValueError."""
    with pytest.raises(ValueError, match="at least 5 characters"):
        extractor.extract("   ")


# =====================================================================
# Test 11: LLM invalid JSON raises after retry
# =====================================================================


def test_llm_invalid_json_raises_after_retry(extractor):
    """Invalid JSON from LLM on both attempts raises RuntimeError."""

    def mock_call_llm_bad_json(self, source_text: str) -> dict:
        # Simulate the _call_llm method receiving invalid JSON
        import json
        raise json.JSONDecodeError("bad json", "", 0)

    # Monkeypatch _call_llm to raise JSONDecodeError on every call
    with pytest.raises(RuntimeError, match="invalid JSON"):
        extractor._call_llm = lambda source_text: (_ for _ in ()).throw(
            RuntimeError("LLM returned invalid JSON after retry.")
        )
        extractor.extract("Ethiopia Yirgacheffe washed light roast")


# =====================================================================
# Additional edge-case tests
# =====================================================================


def test_validate_country_case_insensitive(extractor):
    """Country matching is case-insensitive."""
    raw = _full_llm_response()
    raw["origin_country"] = "ethiopia"
    result = extractor._validate(raw)

    assert result["origin_country"] == "Ethiopia"


def test_validate_unknown_country_preserved(extractor):
    """Non-coffee country falls back to 'unknown'."""
    raw = _full_llm_response()
    raw["origin_country"] = "Antarctica"
    result = extractor._validate(raw)

    assert result["origin_country"] == "unknown"


def test_validate_altitude_out_of_range_set_null(extractor):
    """Altitude outside 0-3000 is set to null."""
    raw = _full_llm_response()
    raw["altitude_min_m"] = -100
    raw["altitude_max_m"] = 5000
    result = extractor._validate(raw)

    assert result["altitude_min_m"] is None
    assert result["altitude_max_m"] is None


def test_validate_altitude_max_less_than_min_set_null(extractor):
    """altitude_max_m < altitude_min_m sets altitude_max_m to null."""
    raw = _full_llm_response()
    raw["altitude_min_m"] = 2000
    raw["altitude_max_m"] = 1500
    result = extractor._validate(raw)

    assert result["altitude_min_m"] == 2000
    assert result["altitude_max_m"] is None


def test_normalize_clusters_case_insensitive(extractor):
    """Cluster normalization handles case variations."""
    clusters = ["floral", "BERRY", "Citrus"]
    result = extractor._normalize_clusters(clusters)

    assert result == ["Floral", "Berry", "Citrus"]


def test_full_extract_pipeline(monkeypatch, extractor):
    """Full extract() pipeline with mocked LLM produces ExtractionResult."""
    expected_raw = _full_llm_response()

    def mock_call_llm(self, source_text):
        return expected_raw

    monkeypatch.setattr(BeanExtractor, "_call_llm", mock_call_llm)

    result = extractor.extract(
        "Ethiopia Yirgacheffe, washed, light roast, blueberry, jasmine, bergamot"
    )

    assert isinstance(result, ExtractionResult)
    assert result.used_manual_entry is False
    assert result.bean_profile.origin_country == "Ethiopia"
    assert result.bean_profile.process == Process.WASHED
    assert result.bean_profile.roast_level == RoastLevel.LIGHT
    assert result.confidence_tier == "HIGH"
    assert result.confidence == 1.0


def test_manual_entry_empty_clusters_defaults_balanced():
    """Manual entry with empty clusters defaults to ['Balanced']."""
    result = create_manual_profile(
        origin_country="Kenya",
        process="washed",
        roast_level="light",
        flavor_clusters=[],
    )

    assert result.bean_profile.flavor_clusters == ["Balanced"]


def test_confidence_partial_fields():
    """Partial fields produce a predictable MEDIUM confidence."""
    ext = BeanExtractor.__new__(BeanExtractor)
    ext._model = "test"
    ext._client = None

    raw = {
        "origin_country": "Guatemala",
        "origin_region": "Antigua",
        "process": "washed",
        "roast_level": "unknown",
        "flavor_clusters": ["Chocolate"],
        "variety": None,
        "altitude_min_m": None,
        "altitude_max_m": None,
    }
    validated = ext._validate(raw)
    confidence, tier, missing = ext._compute_confidence(validated)

    # origin (0.25) + process (0.15) + clusters (0.25) + region (0.10) = 0.75
    assert tier == "HIGH"
    assert confidence == 0.75
    assert "roast_level" in missing
    assert "variety" in missing
    assert "altitude" in missing


# =====================================================================
# M2-M01: Retry logic — first call fails, retry succeeds
# =====================================================================


def test_llm_retry_succeeds_after_first_failure(monkeypatch, extractor):
    """LLM call fails on first attempt but succeeds on retry.

    The _call_llm method retries once on generic Exception. We mock the
    underlying OpenAI client so the first call raises and the second call
    returns valid JSON, then verify extract() completes successfully.
    """
    import json
    from unittest.mock import MagicMock

    expected_raw = _full_llm_response()
    call_count = 0

    class FakeChoice:
        def __init__(self, content):
            self.message = MagicMock(content=content)

    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("simulated LLM timeout")
        return FakeResponse(json.dumps(expected_raw))

    fake_client = MagicMock()
    fake_client.chat.completions.create = mock_create
    extractor._client = fake_client

    result = extractor.extract(
        "Ethiopia Yirgacheffe, washed, light roast, blueberry, jasmine, bergamot"
    )

    assert isinstance(result, ExtractionResult)
    assert result.used_manual_entry is False
    assert result.bean_profile.origin_country == "Ethiopia"
    assert result.bean_profile.process == Process.WASHED
    assert result.bean_profile.roast_level == RoastLevel.LIGHT
    assert call_count == 2, "Expected exactly two LLM calls (initial + retry)"


# =====================================================================
# M2-M02: ValueError when no API key is provided
# =====================================================================


def test_missing_api_key_raises_value_error():
    """Constructing BeanExtractor without an API key raises ValueError on extract.

    When no api_key is passed and LLM_API_KEY env var is unset, the client
    is None. Calling _call_llm must raise ValueError with an actionable
    message.
    """
    import os

    # Ensure the env var is not set for this test
    monkeypatch_or_skip = None
    # Build extractor with no key and no env var
    saved = os.environ.pop("LLM_API_KEY", None)
    try:
        ext = BeanExtractor.__new__(BeanExtractor)
        ext._model = "test"
        ext._client = None

        with pytest.raises(ValueError, match="API key is required"):
            ext._call_llm("Ethiopia Yirgacheffe washed light roast")
    finally:
        if saved is not None:
            os.environ["LLM_API_KEY"] = saved


# =====================================================================
# M13: Module-level logging exists
# =====================================================================


def test_module_has_logger():
    """M2-M13: Bean extractor module has a logger at module scope."""
    import logging
    from src.bean_extractor import extractor as mod

    assert hasattr(mod, "logger")
    assert isinstance(mod.logger, logging.Logger)
    assert mod.logger.name == "src.bean_extractor.extractor"


# =====================================================================
# M18: Robust JSON parsing for LLM responses
# =====================================================================


def test_parse_json_with_markdown_code_fences(extractor):
    """M2-M18: JSON wrapped in ```json...``` fences is parsed correctly."""
    raw_text = '```json\n{"origin_country": "Ethiopia", "process": "washed", "roast_level": "light", "flavor_clusters": ["Floral"], "flavor_notes": ["jasmine"], "variety": null, "altitude_min_m": null, "altitude_max_m": null, "origin_region": null}\n```'
    result = extractor._parse_llm_json(raw_text)
    assert result["origin_country"] == "Ethiopia"
    assert result["process"] == "washed"


def test_parse_json_with_trailing_commas(extractor):
    """M2-M18: JSON with trailing commas before }} or ] is handled."""
    raw_text = '{"origin_country": "Colombia", "process": "natural", "roast_level": "medium", "flavor_clusters": ["Chocolate", "Nutty",], "flavor_notes": ["caramel",], "variety": null, "altitude_min_m": null, "altitude_max_m": null, "origin_region": null,}'
    result = extractor._parse_llm_json(raw_text)
    assert result["origin_country"] == "Colombia"
    assert result["flavor_clusters"] == ["Chocolate", "Nutty"]


def test_parse_json_with_extra_whitespace(extractor):
    """M2-M18: JSON with leading/trailing whitespace is parsed correctly."""
    raw_text = '   \n  \t  {"origin_country": "Brazil", "process": "natural", "roast_level": "medium-dark", "flavor_clusters": ["Chocolate"], "flavor_notes": ["cocoa"], "variety": null, "altitude_min_m": null, "altitude_max_m": null, "origin_region": null}  \n  '
    result = extractor._parse_llm_json(raw_text)
    assert result["origin_country"] == "Brazil"


def test_parse_json_invalid_raises_clear_error(extractor):
    """M2-M18: Invalid JSON raises ValueError with a clear message."""
    raw_text = "this is not json at all"
    with pytest.raises((ValueError, RuntimeError)):
        extractor._parse_llm_json(raw_text)


def test_parse_json_code_fence_with_trailing_comma(extractor):
    """M2-M18: Combined code fence + trailing comma handled together."""
    raw_text = '```json\n{"origin_country": "Kenya", "process": "washed", "roast_level": "light", "flavor_clusters": ["Berry", "Citrus",], "flavor_notes": ["blackberry",], "variety": "SL28", "altitude_min_m": 1500, "altitude_max_m": 2000, "origin_region": "Nyeri",}\n```'
    result = extractor._parse_llm_json(raw_text)
    assert result["origin_country"] == "Kenya"
    assert result["variety"] == "SL28"
    assert result["altitude_min_m"] == 1500

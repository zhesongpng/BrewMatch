"""Shared UI utilities for session-state ↔ dataclass conversion."""

import html
import re
from dataclasses import asdict

from src.data_models import (
    BeanProfile,
    BrewMethod,
    Process,
    PourStep,
    Recipe,
    RoastLevel,
    SuitableFor,
)


def bean_to_dict(profile: BeanProfile) -> dict:
    """Convert a BeanProfile dataclass to a JSON-safe dict with enum strings."""
    d = asdict(profile)
    d["process"] = profile.process.value
    d["roast_level"] = profile.roast_level.value
    return d


def recipe_to_dict(recipe: Recipe) -> dict:
    """Convert a Recipe dataclass to a JSON-safe dict with enum strings."""
    d = asdict(recipe)
    d["method"] = recipe.method.value
    d["suitable_for"]["roast_levels"] = [
        rl.value for rl in recipe.suitable_for.roast_levels
    ]
    d["suitable_for"]["processes"] = [
        p.value for p in recipe.suitable_for.processes
    ]
    return d


def dict_to_bean_profile(bean_dict: dict) -> BeanProfile:
    """Convert a session-state dict back into a BeanProfile dataclass."""
    process = bean_dict.get("process", "unknown")
    if isinstance(process, str):
        process = Process(process)
    elif not isinstance(process, Process):
        process = Process.UNKNOWN

    roast_level = bean_dict.get("roast_level", "unknown")
    if isinstance(roast_level, str):
        roast_level = RoastLevel(roast_level)
    elif not isinstance(roast_level, RoastLevel):
        roast_level = RoastLevel.UNKNOWN

    return BeanProfile(
        origin_country=bean_dict.get("origin_country", "Unknown"),
        process=process,
        roast_level=roast_level,
        flavor_clusters=bean_dict.get("flavor_clusters", ["Balanced"]),
        source_text=bean_dict.get("source_text", ""),
        origin_region=bean_dict.get("origin_region"),
        flavor_notes=bean_dict.get("flavor_notes"),
        variety=bean_dict.get("variety"),
        altitude_min_m=bean_dict.get("altitude_min_m"),
        altitude_max_m=bean_dict.get("altitude_max_m"),
        extraction_confidence=bean_dict.get("extraction_confidence"),
        roaster=bean_dict.get("roaster"),
        name=bean_dict.get("name"),
    )


def dict_to_recipe(recipe_dict: dict) -> Recipe:
    """Convert a session-state dict back into a Recipe dataclass.

    Handles string enum values produced by ``asdict(recipe)`` + manual
    ``recipe_dict["method"] = recipe.method.value`` serialization in
    recommend.py.
    """
    method = recipe_dict["method"]
    if isinstance(method, str):
        method = BrewMethod(method)

    pours = [
        PourStep(
            step=p["step"],
            time_offset_s=p["time_offset_s"],
            water_g=p["water_g"],
        )
        for p in recipe_dict["pours"]
    ]

    sf = recipe_dict["suitable_for"]
    roast_levels = [
        RoastLevel(rl) if isinstance(rl, str) else rl
        for rl in sf["roast_levels"]
    ]
    processes = [
        Process(p) if isinstance(p, str) else p
        for p in sf["processes"]
    ]
    suitable_for = SuitableFor(
        roast_levels=roast_levels,
        origins=sf["origins"],
        processes=processes,
        flavor_profiles=sf["flavor_profiles"],
    )

    return Recipe(
        recipe_id=recipe_dict["recipe_id"],
        source=recipe_dict["source"],
        method=method,
        dose_g=recipe_dict["dose_g"],
        water_total_g=recipe_dict["water_total_g"],
        ratio=recipe_dict["ratio"],
        grind_setting=recipe_dict["grind_setting"],
        water_temp_c=recipe_dict["water_temp_c"],
        bloom_time_s=recipe_dict["bloom_time_s"],
        total_time_s=recipe_dict["total_time_s"],
        pours=pours,
        suitable_for=suitable_for,
        instructions=recipe_dict["instructions"],
        source_url=recipe_dict.get("source_url"),
    )


_MARKDOWN_SPECIAL = re.compile(r"([\\\*\_\#\`\|\[\]\(\)\{\}\~\>\+])")


def escape_markdown(text: str) -> str:
    """Escape user-supplied text for safe rendering via st.markdown().

    HTML-escapes the content first (prevents XSS via <script>, <img onerror>,
    etc.), then escapes markdown special characters to prevent markdown
    injection (link payloads, bold/italic manipulation, heading injection).
    """
    escaped = html.escape(text, quote=True)
    escaped = _MARKDOWN_SPECIAL.sub(r"\\\1", escaped)
    return escaped

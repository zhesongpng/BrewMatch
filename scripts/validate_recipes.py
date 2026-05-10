"""Validate recipe JSON files against the BrewMatch data model schema."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_models import (
    BrewMethod, FLAVOR_CLUSTERS, Process, RoastLevel, Recipe, PourStep, SuitableFor,
)


VALID_METHODS = {m.value for m in BrewMethod}
VALID_ROASTS = {r.value for r in RoastLevel}
VALID_PROCESSES = {p.value for p in Process}


def validate_recipe(data: dict) -> list[str]:
    errors = []

    # Required string fields
    for field in ["recipe_id", "source", "instructions"]:
        if not data.get(field):
            errors.append(f"Missing or empty '{field}'")

    # Method
    method = data.get("method", "")
    if method not in VALID_METHODS:
        errors.append(f"Invalid method '{method}'. Must be one of {VALID_METHODS}")

    # Numeric ranges
    if not (12.0 <= data.get("dose_g", 0) <= 22.0):
        errors.append(f"dose_g must be 12.0-22.0, got {data.get('dose_g')}")
    if not (180.0 <= data.get("water_total_g", 0) <= 400.0):
        errors.append(f"water_total_g must be 180.0-400.0, got {data.get('water_total_g')}")
    if not (14.0 <= data.get("ratio", 0) <= 18.0):
        errors.append(f"ratio must be 14.0-18.0, got {data.get('ratio')}")
    if not (1 <= data.get("grind_setting", 0) <= 10):
        errors.append(f"grind_setting must be 1-10, got {data.get('grind_setting')}")
    if not (85.0 <= data.get("water_temp_c", 0) <= 100.0):
        errors.append(f"water_temp_c must be 85.0-100.0, got {data.get('water_temp_c')}")
    if not (15 <= data.get("bloom_time_s", 0) <= 90):
        errors.append(f"bloom_time_s must be 15-90, got {data.get('bloom_time_s')}")
    if not (120 <= data.get("total_time_s", 0) <= 360):
        errors.append(f"total_time_s must be 120-360, got {data.get('total_time_s')}")

    # Pours
    pours = data.get("pours", [])
    if not (1 <= len(pours) <= 6):
        errors.append(f"Must have 1-6 pours, got {len(pours)}")
    else:
        pours_total = 0
        last_offset = 0
        for i, p in enumerate(pours):
            if p.get("step") != i + 1:
                errors.append(f"Pour step {p.get('step')} should be {i+1}")
            if not (10.0 <= p.get("water_g", 0) <= 200.0):
                errors.append(f"Pour {i+1} water_g must be 10.0-200.0")
            pours_total += p.get("water_g", 0)
            last_offset = p.get("time_offset_s", 0)

        if errors is not None:
            water = data.get("water_total_g", 0)
            if water > 0 and pours_total > 0 and abs(pours_total - water) > water * 0.05:
                errors.append(
                    f"water_total_g ({water}) != sum of pours ({pours_total:.1f}), "
                    f"diff exceeds 5%"
                )

        total_time = data.get("total_time_s", 0)
        if total_time > 0 and total_time < last_offset + 30:
            errors.append(
                f"total_time_s ({total_time}) < last pour offset ({last_offset}) + 30"
            )

    # Ratio check
    dose = data.get("dose_g", 0)
    water = data.get("water_total_g", 0)
    ratio = data.get("ratio", 0)
    if dose > 0 and water > 0:
        expected = water / dose
        if abs(ratio - expected) > 0.1:
            errors.append(f"ratio ({ratio}) != water_total_g/dose_g ({expected:.2f})")

    # suitable_for
    sf = data.get("suitable_for", {})
    for key, valid_set in [
        ("roast_levels", VALID_ROASTS),
        ("processes", VALID_PROCESSES),
    ]:
        vals = sf.get(key, [])
        if not vals:
            errors.append(f"suitable_for.{key} must have at least 1 element")
        for v in vals:
            if v not in valid_set:
                errors.append(f"suitable_for.{key}: invalid value '{v}'")

    origins = sf.get("origins", [])
    if not origins:
        errors.append("suitable_for.origins must have at least 1 element")

    fps = sf.get("flavor_profiles", [])
    if not fps:
        errors.append("suitable_for.flavor_profiles must have at least 1 element")
    for fp in fps:
        if fp not in FLAVOR_CLUSTERS:
            errors.append(f"suitable_for.flavor_profiles: unknown cluster '{fp}'")

    return errors


def main():
    recipes_dir = Path(__file__).resolve().parent.parent / "data" / "recipes"

    json_files = sorted(recipes_dir.glob("*.json"))
    if not json_files:
        print("No recipe JSON files found in data/recipes/")
        return

    passed = 0
    failed = 0
    for f in json_files:
        data = json.loads(f.read_text())
        errors = validate_recipe(data)
        if errors:
            failed += 1
            print(f"FAIL {f.name}:")
            for e in errors:
                print(f"  - {e}")
        else:
            passed += 1
            print(f"PASS {f.name}")

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()

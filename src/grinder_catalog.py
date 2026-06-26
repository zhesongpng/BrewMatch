"""Grinder catalog: maps the generic 1-10 grind scale to grinder-specific settings."""

from __future__ import annotations

GRINDERS: dict[str, dict] = {
    # ── Hand grinders ──────────────────────────────────────────────
    "kingrinder-k6": {
        "brand": "Kingrinder",
        "model": "K6",
        "type": "hand",
        "scale": "clicks",
        "mapping": {
            1: 8, 2: 18, 3: 28, 4: 38, 5: 50,
            6: 62, 7: 74, 8: 86, 9: 98, 10: 112,
        },
    },
    "timemore-c2": {
        "brand": "Timemore",
        "model": "Chestnut C2",
        "type": "hand",
        "scale": "clicks",
        "mapping": {
            1: 4, 2: 7, 3: 10, 4: 12, 5: 14,
            6: 17, 7: 20, 8: 22, 9: 25, 10: 28,
        },
    },
    "timemore-c3": {
        "brand": "Timemore",
        "model": "Chestnut C3",
        "type": "hand",
        "scale": "clicks",
        "mapping": {
            1: 4, 2: 8, 3: 11, 4: 14, 5: 17,
            6: 20, 7: 23, 8: 26, 9: 29, 10: 32,
        },
    },
    "comandante-c40": {
        "brand": "Comandante",
        "model": "C40",
        "type": "hand",
        "scale": "clicks",
        "mapping": {
            1: 8, 2: 14, 3: 18, 4: 22, 5: 26,
            6: 28, 7: 30, 8: 33, 9: 38, 10: 44,
        },
    },
    "1zpresso-kmax": {
        "brand": "1Zpresso",
        "model": "K-Max",
        "type": "hand",
        "scale": "rotations",
        "mapping": {
            1: 1.0, 2: 1.4, 3: 1.8, 4: 2.2, 5: 2.6,
            6: 3.0, 7: 3.4, 8: 4.0, 9: 4.8, 10: 5.6,
        },
    },
    "1zpresso-jmax": {
        "brand": "1Zpresso",
        "model": "J-Max",
        "type": "hand",
        "scale": "rotations",
        "mapping": {
            1: 0.6, 2: 0.9, 3: 1.2, 4: 1.5, 5: 1.8,
            6: 2.1, 7: 2.4, 8: 2.8, 9: 3.4, 10: 4.0,
        },
    },
    # ── Electric grinders ───────────────────────────────────────────
    "baratza-encore": {
        "brand": "Baratza",
        "model": "Encore",
        "type": "electric",
        "scale": "setting",
        "mapping": {
            1: 4, 2: 6, 3: 8, 4: 10, 5: 14,
            6: 18, 7: 22, 8: 28, 9: 34, 10: 38,
        },
    },
    "fellow-ode-gen2": {
        "brand": "Fellow",
        "model": "Ode Gen 2",
        "type": "electric",
        "scale": "setting",
        "mapping": {
            1: 1, 2: 2, 3: 2.5, 4: 3, 5: 4,
            6: 5, 7: 6, 8: 7, 9: 8, 10: 10,
        },
    },
    "niche-zero": {
        "brand": "Niche",
        "model": "Zero",
        "type": "electric",
        "scale": "setting",
        "mapping": {
            1: 5, 2: 10, 3: 15, 4: 20, 5: 25,
            6: 30, 7: 35, 8: 40, 9: 45, 10: 50,
        },
    },
}


def get_grinder_display(
    grinder_id: str | None,
    generic_setting: int,
) -> str | None:
    """Return a grinder-specific display string, or None if no grinder.

    Example returns: "~75 clicks", "~3.4 rotations", "~22 setting"
    """
    if not grinder_id or grinder_id == "other":
        return None

    grinder = GRINDERS.get(grinder_id)
    if not grinder:
        return None

    value = grinder["mapping"].get(generic_setting)
    if value is None:
        return None

    scale = grinder["scale"]
    brand = grinder["brand"]
    model = grinder["model"]

    if scale == "rotations":
        value_str = f"{value:.1f}"
    elif isinstance(value, float):
        value_str = f"{value:.1f}"
    else:
        value_str = str(value)

    return f"~{value_str} {scale} on {brand} {model}"


def get_grinder_catalog() -> list[dict]:
    """Return the full catalog as JSON-serializable dicts for the HTTP API.

    Each entry carries the per-step mapping so a client can translate any
    1-10 grind setting locally without a round-trip. Ordered hand grinders
    first, then electric — the same order the picker uses. This keeps the
    catalog (the actual click/rotation/setting numbers) owned by Python; the
    web only mirrors the trivial display string in get_grinder_display.
    """
    return [
        {
            "id": gid,
            "brand": g["brand"],
            "model": g["model"],
            "type": g["type"],
            "scale": g["scale"],
            # JSON object keys are strings, so the 1-10 steps serialize as
            # "1".."10"; the client reads them back by string key.
            "mapping": {str(step): value for step, value in g["mapping"].items()},
        }
        for gid, g in GRINDERS.items()
    ]


def get_grinder_options() -> list[tuple[str, str]]:
    """Return (grinder_id, display_label) pairs for UI selectboxes.

    Grouped by type: hand grinders first, then electric, then Other.
    """
    options = []
    hand = [(gid, f"{g['brand']} {g['model']} (hand)")
            for gid, g in GRINDERS.items() if g["type"] == "hand"]
    electric = [(gid, f"{g['brand']} {g['model']} (electric)")
                for gid, g in GRINDERS.items() if g["type"] == "electric"]

    options.extend(hand)
    options.extend(electric)
    options.append(("other", "Other / not listed"))
    return options

"""Grinder catalog: translate a recipe's grind target into each grinder's own setting.

Rebuilt 2026-07-06 from the calibration spec at
``workspaces/BrewMatch/grinder-calibration-spec.md``. The model:

* The internal grind scale stays 1-10 (the taste model + optimizer need it), but
  it is converted to **microns** — the one physical unit true across every
  grinder — and never shown to users raw.
* Each grinder stores ``anchors``: ``(microns, native_value)`` pairs taken from
  manufacturer-official / authoritative brew-method settings. A micron target is
  linear-interpolated between the nearest anchors and clamped to the grinder's
  usable range. Interpolating between real sourced anchors beats a microns-per-
  click formula from zero (which ignores burr offset — the reason naive click
  numbers miss).
* Native reading differs by grinder: ``clicks`` / ``rotations`` counted from a
  zero point (hand grinders), or a printed ``dial`` number (electric, no zeroing).

Every displayed setting is a starting point; the UI pairs it with a taste-adjust
nudge (sour -> finer, bitter -> coarser).
"""

from __future__ import annotations

# ── 1-10 internal scale <-> microns ────────────────────────────────────────
# microns = 200 + setting * 100  (setting 1 = 300um fine ... 10 = 1200um coarse)
_MICRONS_BASE = 200
_MICRONS_PER_STEP = 100


def microns_for_generic(generic_setting: float) -> int:
    """Map the internal 1-10 grind scale to a target grind size in microns."""
    step = max(1, min(10, round(generic_setting)))
    return _MICRONS_BASE + step * _MICRONS_PER_STEP


# ── Coarseness bands (plain-language label from microns) ────────────────────
def coarseness_label(microns: int) -> str:
    """Plain-language band a user can act on, e.g. 'Medium-coarse (4:6)'."""
    if microns < 420:
        return "Fine (espresso)"
    if microns < 820:
        return "Medium (pour-over)"
    if microns < 1020:
        return "Medium-coarse (4:6)"
    return "Coarse (French press)"


# ── Catalog ─────────────────────────────────────────────────────────────────
# reading:  "clicks" | "rotations" (from zero) | "dial" (printed number)
# anchors:  ascending (microns, native_value) from the calibration spec
# decimals: display precision for the native value
GRINDERS: dict[str, dict] = {
    # ── Hand grinders ──────────────────────────────────────────────
    "timemore-c3": {
        "brand": "Timemore",
        "model": "Chestnut C3 / C3S",
        "type": "hand",
        "reading": "clicks",
        "zero_required": True,
        "decimals": 0,
        "how_to_set": "Turn the dial clockwise until the burrs touch (that's zero), then open counter-clockwise and count clicks.",
        "anchors": [(350, 8), (700, 14), (900, 17), (1050, 19)],
        "range": (7, 20),
        "notes": "Standard C3/C3S only — 15 clicks per full rotation (confirmed on a real unit; the dial reads 1-15, not 12). The C3 ESP is a different grinder — pick 'Timemore C3 ESP'.",
    },
    "timemore-c3-esp": {
        "brand": "Timemore",
        "model": "Chestnut C3 ESP",
        "type": "hand",
        "reading": "rotations",
        "zero_required": True,
        "decimals": 1,
        "how_to_set": "Zero it (dial clockwise until the burrs touch), then count full turns opening counter-clockwise — 30 clicks per turn.",
        "anchors": [(350, 0.8), (650, 1.5), (900, 2.1), (1050, 2.4)],
        "range": (0.3, 2.8),
        "notes": "ESP fine burr (23 um/click, 30 clicks/turn) — needs far more clicks than the standard C3.",
    },
    "timemore-c2": {
        "brand": "Timemore",
        "model": "Chestnut C2",
        "type": "hand",
        "reading": "clicks",
        "zero_required": True,
        "decimals": 0,
        "how_to_set": "Turn the dial clockwise until the burrs touch (zero), then open counter-clockwise and count clicks.",
        "anchors": [(350, 9), (650, 16), (900, 19), (1050, 22)],
        "range": (6, 24),
        "notes": "",
    },
    "kingrinder-k6": {
        "brand": "Kingrinder",
        "model": "K6",
        "type": "hand",
        "reading": "rotations",
        "zero_required": True,
        "decimals": 1,
        "how_to_set": "Turn the adjustment nut clockwise to zero, then open anti-clockwise — 60 clicks per full turn.",
        "anchors": [(350, 0.35), (650, 0.85), (900, 1.15), (1050, 1.5)],
        "range": (0.2, 3.0),
        "notes": "60 clicks/turn, 16 um/click.",
    },
    "comandante-c40": {
        "brand": "Comandante",
        "model": "C40",
        "type": "hand",
        "reading": "clicks",
        "zero_required": True,
        "decimals": 0,
        "how_to_set": "Turn the ring clockwise until the burrs contact (a light scrape = zero, the red dot), then count clicks back. Re-check zero monthly.",
        "anchors": [(350, 13), (650, 25), (900, 28), (1100, 32)],
        "range": (8, 40),
        "notes": "",
    },
    "1zpresso-kmax": {
        "brand": "1Zpresso",
        "model": "K-Max",
        "type": "hand",
        "reading": "rotations",
        "zero_required": True,
        "decimals": 1,
        "how_to_set": "Turn the dial clockwise until the handle stops (zero), then count full turns — 90 clicks per turn.",
        "anchors": [(350, 2.2), (650, 4.0), (900, 4.7), (1050, 5.5)],
        "range": (1.0, 6.5),
        "notes": "90 clicks/turn, 22 um/click.",
    },
    "1zpresso-jmax": {
        "brand": "1Zpresso",
        "model": "J-Max",
        "type": "hand",
        "reading": "rotations",
        "zero_required": True,
        "decimals": 1,
        "how_to_set": "Turn the dial clockwise until the handle stops (zero), then count full turns — 90 clicks per turn.",
        "anchors": [(350, 2.0), (650, 3.4), (900, 4.0), (1050, 4.3)],
        "range": (0.6, 4.5),
        "notes": "Fine espresso burr (8.8 um/click); filter settings are best-estimate — confirm against the official J-Max chart.",
    },
    # ── Electric grinders (dial number, no zeroing) ─────────────────
    "baratza-encore": {
        "brand": "Baratza",
        "model": "Encore",
        "type": "electric",
        "reading": "dial",
        "zero_required": False,
        "decimals": 0,
        "how_to_set": "Set the printed dial to the number — no zeroing needed.",
        "anchors": [(350, 9), (650, 15), (900, 20), (1100, 28)],
        "range": (1, 40),
        "notes": "Baratza-official brew settings.",
    },
    "fellow-ode-gen2": {
        "brand": "Fellow",
        "model": "Ode Gen 2",
        "type": "electric",
        "reading": "dial",
        "zero_required": False,
        "decimals": 1,
        "how_to_set": "Set the dial to the number (each number has 3 sub-clicks) — no zeroing.",
        "anchors": [(350, 3.0), (650, 4.8), (900, 6.5), (1100, 9.5)],
        "range": (1.0, 11.0),
        "notes": "Filter-focused; 1-11 dial with sub-clicks.",
    },
    "niche-zero": {
        "brand": "Niche",
        "model": "Zero",
        "type": "electric",
        "reading": "dial",
        "zero_required": False,
        "decimals": 0,
        "how_to_set": "Set the stepless dial to the number — no zeroing. Units vary, so treat it as a starting point.",
        "anchors": [(300, 15), (650, 38), (900, 43), (1100, 48)],
        "range": (0, 50),
        "notes": "Stepless; dial numbers vary unit-to-unit.",
    },
}


# ── Conversion ──────────────────────────────────────────────────────────────
def _interpolate(anchors: list[tuple[int, float]], microns: int) -> float:
    """Linear-interpolate a native value for a micron target; clamp at the ends."""
    if microns <= anchors[0][0]:
        return anchors[0][1]
    if microns >= anchors[-1][0]:
        return anchors[-1][1]
    for (m0, v0), (m1, v1) in zip(anchors, anchors[1:]):
        if m0 <= microns <= m1:
            frac = (microns - m0) / (m1 - m0)
            return v0 + frac * (v1 - v0)
    return anchors[-1][1]


def _format_native(grinder: dict, value: float) -> str:
    """Format a native value in the grinder's own unit, e.g. '17 clicks', 'dial 15'."""
    reading = grinder["reading"]
    decimals = grinder.get("decimals", 1 if reading == "rotations" else 0)
    number = f"{value:.{decimals}f}" if decimals else f"{round(value)}"
    if reading == "clicks":
        return f"{number} clicks"
    if reading == "rotations":
        turns = "turn" if number in ("1", "1.0") else "turns"
        return f"{number} {turns}"
    return f"dial {number}"


def grind_for_grinder(grinder_id: str | None, generic_setting: float) -> dict | None:
    """Translate the internal 1-10 grind into a grinder's native setting.

    Returns a dict with the native display string, the coarseness band, the
    micron target, and how to set the grinder — or None when there's no grinder.
    """
    if not grinder_id or grinder_id == "other":
        return None
    grinder = GRINDERS.get(grinder_id)
    if not grinder:
        return None

    microns = microns_for_generic(generic_setting)
    lo, hi = grinder["range"]
    value = max(lo, min(hi, _interpolate(grinder["anchors"], microns)))
    return {
        "grinder_id": grinder_id,
        "grinder_name": f"{grinder['brand']} {grinder['model']}",
        "native": _format_native(grinder, value),
        "band": coarseness_label(microns),
        "microns": microns,
        "how_to_set": grinder["how_to_set"],
        "zero_required": grinder["zero_required"],
    }


def get_grinder_display(
    grinder_id: str | None,
    generic_setting: float,
) -> str | None:
    """Back-compat native display string, e.g. '~17 clicks', '~dial 15'.

    Retained for the Streamlit pages; prefer ``grind_for_grinder`` for new code.
    """
    result = grind_for_grinder(grinder_id, generic_setting)
    if result is None:
        return None
    return f"~{result['native']} on {result['grinder_name']}"


def get_grinder_catalog() -> list[dict]:
    """Full catalog for the HTTP API, with a precomputed 1-10 -> native mapping.

    Each grinder carries its reading convention, how-to-set text, and a mapping
    of every generic step "1".."10" to ``{microns, native, band}`` so the web can
    translate any grind locally without a round-trip. All calibration numbers are
    owned here in Python; the web only mirrors the precomputed display strings.

    Only hand grinders ship in the picker — filter/pour-over is a hand-grinder
    audience, and hand-grinder settings are calibrated to the user's own dial
    (see grind-calibration). Electric grinders stay defined in ``GRINDERS`` for a
    future re-enable but are not returned here.
    """
    catalog = []
    for gid, g in GRINDERS.items():
        if g["type"] != "hand":
            continue
        mapping = {}
        for step in range(1, 11):
            microns = microns_for_generic(step)
            lo, hi = g["range"]
            value = max(lo, min(hi, _interpolate(g["anchors"], microns)))
            mapping[str(step)] = {
                "microns": microns,
                "native": _format_native(g, value),
                "band": coarseness_label(microns),
            }
        catalog.append(
            {
                "id": gid,
                "brand": g["brand"],
                "model": g["model"],
                "type": g["type"],
                "reading": g["reading"],
                "zero_required": g["zero_required"],
                "how_to_set": g["how_to_set"],
                "notes": g["notes"],
                "mapping": mapping,
            }
        )
    return catalog


def get_grinder_options() -> list[tuple[str, str]]:
    """Return (grinder_id, display_label) pairs for UI selectboxes.

    Hand grinders only (see get_grinder_catalog), then Other.
    """
    hand = [
        (gid, f"{g['brand']} {g['model']} (hand)")
        for gid, g in GRINDERS.items()
        if g["type"] == "hand"
    ]
    return [*hand, ("other", "Other / not listed")]

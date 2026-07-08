"""Grinder calibration invariants.

The catalog translates the internal 1-10 grind scale into each grinder's own
setting. Its load-bearing contracts: every step maps for every grinder, the
native value never leaves the grinder's usable range, coarseness bands are
correct, and coarser recipes always mean a coarser (larger) setting. These lock
the calibration rebuilt from workspaces/BrewMatch/grinder-calibration-spec.md.
"""

import pytest

from src.grinder_catalog import (
    GRINDERS,
    coarseness_label,
    get_grinder_catalog,
    grind_for_grinder,
    microns_for_generic,
)


def test_catalog_is_hand_only_with_stable_ids():
    cat = get_grinder_catalog()
    ids = {g["id"] for g in cat}
    # Only hand grinders ship in the picker (filter/pour-over audience).
    assert {g["type"] for g in cat} == {"hand"}
    for expected in ("timemore-c3", "kingrinder-k6", "comandante-c40"):
        assert expected in ids
    # The C3 variant split landed as a new, separate entry.
    assert "timemore-c3-esp" in ids
    # Electric grinders are hidden from the catalog but kept in GRINDERS.
    assert "baratza-encore" in GRINDERS
    assert "baratza-encore" not in ids


def test_microns_bridge_is_monotonic():
    values = [microns_for_generic(s) for s in range(1, 11)]
    assert values == sorted(values)
    assert values[0] == 300 and values[-1] == 1200


@pytest.mark.parametrize("microns,expected", [
    (300, "Fine (espresso)"),
    (700, "Medium (pour-over)"),
    (900, "Medium-coarse (4:6)"),
    (1200, "Coarse (French press)"),
])
def test_coarseness_bands(microns, expected):
    assert coarseness_label(microns) == expected


def test_every_step_maps_for_every_grinder():
    for gid in GRINDERS:
        for step in range(1, 11):
            result = grind_for_grinder(gid, step)
            assert result is not None, f"{gid} has no mapping for step {step}"
            assert result["native"], f"{gid} step {step} produced empty native string"


def _native_number(result: dict) -> float:
    """Pull the numeric part out of '17 clicks' / 'dial 15' / '2.1 turns'."""
    for token in result["native"].replace("dial ", "").split():
        try:
            return float(token)
        except ValueError:
            continue
    raise AssertionError(f"no number in {result['native']!r}")


def test_native_value_never_leaves_usable_range():
    for gid, g in GRINDERS.items():
        lo, hi = g["range"]
        for step in range(1, 11):
            value = _native_number(grind_for_grinder(gid, step))
            assert lo <= value <= hi, f"{gid} step {step} -> {value} outside {(lo, hi)}"


def test_coarser_setting_never_grinds_finer():
    # Load-bearing: a higher generic setting must map to a >= native value.
    for gid in GRINDERS:
        values = [_native_number(grind_for_grinder(gid, s)) for s in range(1, 11)]
        assert values == sorted(values), f"{gid} native values not monotonic: {values}"


def test_timemore_c3_46_is_within_range_not_the_old_23():
    # The rebuild's headline fix: 4:6 (setting 7) lands ~17 clicks, well inside
    # the C3's 7-20 range — never the old, out-of-range 23.
    result = grind_for_grinder("timemore-c3", 7)
    clicks = _native_number(result)
    assert 7 <= clicks <= 20
    assert clicks < 23
    assert result["band"] == "Medium-coarse (4:6)"


def test_c3_variants_differ_in_native_but_share_band():
    standard = grind_for_grinder("timemore-c3", 7)
    esp = grind_for_grinder("timemore-c3-esp", 7)
    assert standard["native"] != esp["native"]
    assert standard["band"] == esp["band"] == "Medium-coarse (4:6)"


def test_other_and_missing_grinder_return_none():
    assert grind_for_grinder(None, 7) is None
    assert grind_for_grinder("other", 7) is None
    assert grind_for_grinder("does-not-exist", 7) is None


def test_catalog_entries_have_all_display_fields():
    for entry in get_grinder_catalog():
        for key in ("id", "brand", "model", "type", "reading", "zero_required",
                    "how_to_set", "notes", "mapping"):
            assert key in entry, f"{entry.get('id')} missing {key}"
        for step in ("1", "5", "10"):
            cell = entry["mapping"][step]
            assert set(cell) == {"microns", "native", "band"}

"""Brewer catalog invariants.

The catalog is the one source of truth for the brewers a user can own. Its
load-bearing contract is that every brewer's ``method`` is a real BrewMethod the
recommend engine keys on — if that drifts, the web sends an unknown brew method
and the recommend call silently returns nothing. These tests lock that contract.
"""

from src.brewer_catalog import BREWERS, get_brewer_catalog, get_brewer_method
from src.data_models import BrewMethod

_VALID_METHODS = {m.value for m in BrewMethod}


def test_catalog_not_empty():
    assert len(get_brewer_catalog()) == len(BREWERS) > 0


def test_every_brewer_method_is_a_real_brewmethod():
    # The load-bearing invariant: a brewer id maps to a method the engine accepts.
    for entry in get_brewer_catalog():
        assert entry["method"] in _VALID_METHODS, (
            f"brewer {entry['id']!r} has method {entry['method']!r} "
            f"which is not a BrewMethod ({sorted(_VALID_METHODS)})"
        )


def test_catalog_entries_have_all_display_fields():
    for entry in get_brewer_catalog():
        for key in ("id", "name", "method", "style", "blurb"):
            assert entry.get(key), f"brewer {entry.get('id')!r} missing {key!r}"


def test_brewer_ids_are_unique():
    ids = [e["id"] for e in get_brewer_catalog()]
    assert len(ids) == len(set(ids))


def test_get_brewer_method_maps_and_guards():
    assert get_brewer_method("v60") == "V60"
    assert get_brewer_method("kalita-wave") == "Kalita Wave"
    assert get_brewer_method("origami") == "Origami"
    # Unknown id and None fall through to None, never raise.
    assert get_brewer_method(None) is None
    assert get_brewer_method("") is None
    assert get_brewer_method("not-a-brewer") is None


def test_get_brewer_method_agrees_with_catalog():
    for entry in get_brewer_catalog():
        assert get_brewer_method(entry["id"]) == entry["method"]

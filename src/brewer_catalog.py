"""Brewer catalog: the pour-over brewers a user can own and choose between.

A brewer is equipment (like the grinder), not a property of the beans — the same
beans can run through any brewer. This module owns the one true list of brewers
the engine has recipes for, so the website can only offer brewers we can actually
recommend for. Each brewer's ``method`` is the exact BrewMethod string the brain
expects in a /recommend request (see src/data_models.py::BrewMethod), which keeps
the recipe request shape unchanged when the web sends the chosen brewer.

Scope is pour-over only (V60 / Kalita Wave / Origami). New brewer types are added
here, in one place — the catalog is built to grow.
"""

from __future__ import annotations

BREWERS: dict[str, dict] = {
    "v60": {
        "name": "Hario V60",
        # Exact BrewMethod value the recommend engine keys on.
        "method": "V60",
        "style": "conical",
        "blurb": (
            "Cone-shaped dripper with spiral ribs and one big hole. Fast flow, "
            "bright and clear in the cup, rewards a steady pour."
        ),
    },
    "kalita-wave": {
        "name": "Kalita Wave",
        "method": "Kalita Wave",
        "style": "flat-bottom",
        "blurb": (
            "Flat bottom with three small holes and a wavy filter. Even, "
            "repeatable extraction — the most forgiving of the three."
        ),
    },
    "origami": {
        "name": "Origami",
        "method": "Origami",
        "style": "hybrid",
        "blurb": (
            "Ribbed dripper that takes both cone and wave filters. Versatile, "
            "sits between the V60 and the Kalita depending on the filter."
        ),
    },
}


def get_brewer_catalog() -> list[dict]:
    """Return the full catalog as JSON-serializable dicts for the HTTP API.

    The website mirrors this list to offer the brewers a user can own and to map
    a chosen brewer back to its BrewMethod for the recommend call. Ordered the
    same way the picker shows them.
    """
    return [
        {
            "id": bid,
            "name": b["name"],
            "method": b["method"],
            "style": b["style"],
            "blurb": b["blurb"],
        }
        for bid, b in BREWERS.items()
    ]


def get_brewer_method(brewer_id: str | None) -> str | None:
    """Return the BrewMethod string for a brewer id, or None if unknown.

    Lets any caller translate an owned-brewer id into the exact value the
    recommend engine expects without duplicating the mapping.
    """
    if not brewer_id:
        return None
    brewer = BREWERS.get(brewer_id)
    return brewer["method"] if brewer else None

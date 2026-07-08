"""Guard the grind table shared by the Python brain and the web app.

Both `src/grinder_catalog.py` (microns_for_generic + coarseness_label) and
`apps/web/lib/recipe.ts` (genericMicrons + genericGrindBand) implement the same
1-10 grind scale. They are tested against ONE canonical fixture
(`tests/fixtures/grind_parity.json`), so neither side can drift from the other
without a test failing. The web-side twin lives at
`apps/web/lib/__tests__/recipe.test.ts`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.grinder_catalog import coarseness_label, microns_for_generic

_FIXTURE = Path(__file__).parents[1] / "fixtures" / "grind_parity.json"
_STEPS = json.loads(_FIXTURE.read_text())["steps"]


@pytest.mark.regression
@pytest.mark.parametrize("row", _STEPS, ids=lambda r: f"step-{r['step']}")
def test_python_grind_matches_shared_fixture(row):
    """microns + band for each step must equal the shared canonical table."""
    step = row["step"]
    assert microns_for_generic(step) == row["microns"]
    assert coarseness_label(row["microns"]) == row["band"]
    # And the composed path a caller actually uses.
    assert coarseness_label(microns_for_generic(step)) == row["band"]

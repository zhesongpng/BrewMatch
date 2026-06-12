"""Regression: a bag is reusable across sessions and its remaining coffee
decreases by the SUM OF ACTUAL DOSES, never the recipe's assumed dose (B1).

This guards the whole B1 loop end-to-end against silent breakage:

- B1.2 storage helpers (`create_bag`, `grams_used_for_bag`, `list_active_bags`)
- B1.5 dose rescaling (`brew_session._scale_recipe`) — the saved recipe's dose
  IS the dose actually weighed
- B1.6 persistence (`save_brew` writes `bag_id` + `actual_dose_g`)

Persistence is proven across *separate connections to a temp-file database* —
each connection stands in for a fresh login session. If a future change drops
the bag link, sums the recipe dose instead of the real dose, or stops persisting
bags, this test fails.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.app.db import (
    create_bag,
    get_connection,
    grams_used_for_bag,
    init_db,
    list_active_bags,
    save_brew,
    save_user,
)
from src.app.pages.brew_session import _scale_recipe
from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    CoffeeBag,
    ExperienceLevel,
    Feedback,
    Onboarding,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)

# The recipe's *assumed* dose. The brews below are pulled at DIFFERENT real
# doses, so summing recipe doses (2 × 15 = 30) gives a wrong answer and summing
# real doses (18 + 16.5 = 34.5) gives the right one — the two are kept distinct
# on purpose so the test can tell which path the code took.
_RECIPE_DOSE_G = 15.0
_BAG_SIZE_G = 250.0


def _bean() -> BeanProfile:
    return BeanProfile(
        origin_country="Ethiopia",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral"],
        source_text="regression bean",
        roaster="Onyx",
        name="Ethiopia Guji",
    )


def _recipe() -> Recipe:
    return Recipe(
        recipe_id="regr-v60",
        source="regression",
        method=BrewMethod.V60,
        dose_g=_RECIPE_DOSE_G,
        water_total_g=240.0,
        ratio=16.0,
        grind_setting=5,
        water_temp_c=94.0,
        bloom_time_s=45,
        total_time_s=180,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=45.0),
            PourStep(step=2, time_offset_s=45, water_g=95.0),
            PourStep(step=3, time_offset_s=90, water_g=100.0),
        ],
        suitable_for=SuitableFor(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia"],
            processes=[Process.WASHED],
            flavor_profiles=["Floral"],
        ),
        instructions="Brew it.",
    )


def _brew_at_dose(bag_id: str, actual_dose_g: float) -> BrewRecord:
    """Build a brew exactly as brew_session does: the saved recipe is the
    dose-scaled recipe, and actual_dose_g mirrors its dose."""
    scaled = _scale_recipe(_recipe(), actual_dose_g)
    return BrewRecord(
        brew_id=uuid.uuid4().hex[:8],
        timestamp=datetime.now(timezone.utc).isoformat(),
        bean_profile=_bean(),
        recipe_used=scaled,
        feedback=Feedback(thumbs_up=True, score=8),
        bag_id=bag_id,
        actual_dose_g=scaled.dose_g,
    )


@pytest.mark.regression
def test_bag_reusable_across_sessions_decrements_by_real_dose(tmp_path):
    db_file = str(tmp_path / "brewmatch.sqlite")
    onboarding = Onboarding(
        preferred_clusters=["Floral"],
        roast_preference=RoastLevel.LIGHT,
        experience_level=ExperienceLevel.INTERMEDIATE,
    )

    # --- Session 1: open the bag, brew once at 18 g, then close the session ---
    c1 = get_connection(db_file)
    init_db(c1)
    save_user(c1, "u1", onboarding)
    bag = CoffeeBag(
        bag_id="bag-1",
        roaster="Onyx",
        name="Ethiopia Guji",
        bean_profile=_bean(),
        bag_size_g=_BAG_SIZE_G,
    )
    create_bag(c1, "u1", bag)
    save_brew(c1, "u1", _brew_at_dose("bag-1", 18.0))
    c1.close()

    # --- Session 2: fresh connection. Bag still there; brew again at 16.5 g ---
    c2 = get_connection(db_file)
    active = list_active_bags(c2, "u1")
    assert [b.bag_id for b in active] == ["bag-1"], "bag must survive logout/login"
    save_brew(c2, "u1", _brew_at_dose("bag-1", 16.5))
    c2.close()

    # --- Session 3: fresh connection. Remaining reflects the SUM OF REAL doses ---
    c3 = get_connection(db_file)
    used = grams_used_for_bag(c3, "u1", "bag-1")
    assert used == pytest.approx(34.5), "must sum actual doses (18 + 16.5), not recipe doses"
    assert used != pytest.approx(2 * _RECIPE_DOSE_G), "must NOT sum the recipe's assumed dose"
    remaining = _BAG_SIZE_G - used
    assert remaining == pytest.approx(215.5)
    # Still active and reusable for the next brew.
    assert [b.bag_id for b in list_active_bags(c3, "u1")] == ["bag-1"]
    c3.close()

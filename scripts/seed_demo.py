"""Seed the BrewMatch demo database with Alex's pre-seeded brew history.

Creates user "Alex" (alex-demo) with 15 brews spanning 30 days, showing
a gradually improving rating trend (early brews ~5-6, later ~8-9) that
demonstrates the personalization engine's learning curve.

Usage:
    cd BrewMatch && uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Make project imports work when run as a script
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.app.db import get_connection, init_db, save_brew, save_user, update_preferences
from src.data_models import (
    BeanProfile,
    BrewMethod,
    BrewRecord,
    ExperienceLevel,
    Feedback,
    LearnedPreferences,
    Onboarding,
    PourStep,
    Process,
    Recipe,
    RoastLevel,
    SuitableFor,
)

# ---------------------------------------------------------------------------
# Alex's static profile
# ---------------------------------------------------------------------------
ALEX_USER_ID = "alex-demo"

ALEX_ONBOARDING = Onboarding(
    preferred_clusters=["Berry", "Citrus", "Floral"],
    roast_preference=RoastLevel.LIGHT,
    experience_level=ExperienceLevel.INTERMEDIATE,
)

ALEX_PREFERENCES = LearnedPreferences(
    acidity_bias=0.3,
    body_bias=-0.1,
    sweetness_bias=0.2,
    preferred_temp_range=(91.0, 95.0),
    preferred_ratio_range=(15.0, 16.5),
)


# ---------------------------------------------------------------------------
# Deterministic UUID helper
# ---------------------------------------------------------------------------
def _uuid_for_index(index: int) -> str:
    """Generate a deterministic UUID based on the brew index.

    Uses UUID v5 with a fixed namespace so re-seeding produces the same IDs.
    """
    _NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    return str(uuid.uuid5(_NAMESPACE, f"alex-brew-{index:03d}"))


# ---------------------------------------------------------------------------
# Bean definitions used across Alex's brews
# ---------------------------------------------------------------------------
_BEANS: list[dict] = [
    # 0 - Ethiopia Yirgacheffe, washed, light
    dict(
        origin_country="Ethiopia",
        origin_region="Yirgacheffe",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Floral", "Citrus", "Berry"],
        source_text="Ethiopian Yirgacheffe, washed process, light roast",
        flavor_notes=["jasmine", "lemon", "blueberry"],
        variety="Heirloom",
        altitude_min_m=1800,
        altitude_max_m=2200,
    ),
    # 1 - Ethiopia Sidamo, natural, light
    dict(
        origin_country="Ethiopia",
        origin_region="Sidamo",
        process=Process.NATURAL,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Berry", "Floral", "Sweet"],
        source_text="Ethiopian Sidamo, natural process, light roast",
        flavor_notes=["strawberry", "lavender", "honey"],
        variety="Heirloom",
        altitude_min_m=1600,
        altitude_max_m=2000,
    ),
    # 2 - Kenya Nyeri, washed, light
    dict(
        origin_country="Kenya",
        origin_region="Nyeri",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Berry", "Citrus", "Floral"],
        source_text="Kenyan Nyeri AA, washed process, light roast",
        flavor_notes=["blackcurrant", "grapefruit", "rose"],
        variety="SL28",
        altitude_min_m=1700,
        altitude_max_m=2100,
    ),
    # 3 - Kenya Embu, washed, medium-light
    dict(
        origin_country="Kenya",
        origin_region="Embu",
        process=Process.WASHED,
        roast_level=RoastLevel.MEDIUM_LIGHT,
        flavor_clusters=["Citrus", "Stone Fruit", "Sweet"],
        source_text="Kenyan Embu, washed process, medium-light roast",
        flavor_notes=["tangerine", "peach", "brown sugar"],
        variety="SL34",
        altitude_min_m=1500,
        altitude_max_m=1900,
    ),
    # 4 - Colombia Huila, washed, light
    dict(
        origin_country="Colombia",
        origin_region="Huila",
        process=Process.WASHED,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Sweet", "Citrus", "Floral"],
        source_text="Colombian Huila, washed process, light roast",
        flavor_notes=["caramel", "orange", "honeysuckle"],
        variety="Caturra",
        altitude_min_m=1600,
        altitude_max_m=1900,
    ),
    # 5 - Colombia Huila, honey, light
    dict(
        origin_country="Colombia",
        origin_region="Huila",
        process=Process.HONEY,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Berry", "Sweet", "Floral"],
        source_text="Colombian Huila, honey process, light roast",
        flavor_notes=["raspberry", "maple", "rose hip"],
        variety="Castillo",
        altitude_min_m=1700,
        altitude_max_m=2000,
    ),
    # 6 - Ethiopia Yirgacheffe, anaerobic, light
    dict(
        origin_country="Ethiopia",
        origin_region="Yirgacheffe",
        process=Process.ANAEROBIC,
        roast_level=RoastLevel.LIGHT,
        flavor_clusters=["Berry", "Tropical", "Floral"],
        source_text="Ethiopian Yirgacheffe, anaerobic process, light roast",
        flavor_notes=["strawberry", "mango", "hibiscus"],
        variety="Heirloom",
        altitude_min_m=1900,
        altitude_max_m=2300,
    ),
]

# Bean index assignments for each of the 15 brews (cycling through origins)
_BREW_BEAN_INDICES = [
    0,  # 1  - Ethiopia Yirgacheffe
    2,  # 2  - Kenya Nyeri
    4,  # 3  - Colombia Huila
    1,  # 4  - Ethiopia Sidamo
    3,  # 5  - Kenya Embu
    0,  # 6  - Ethiopia Yirgacheffe
    5,  # 7  - Colombia Huila honey
    2,  # 8  - Kenya Nyeri
    6,  # 9  - Ethiopia Yirgacheffe anaerobic
    4,  # 10 - Colombia Huila
    1,  # 11 - Ethiopia Sidamo
    3,  # 12 - Kenya Embu
    0,  # 13 - Ethiopia Yirgacheffe
    5,  # 14 - Colombia Huila honey
    2,  # 15 - Kenya Nyeri
]

# Origin country distribution: Ethiopia=6, Kenya=4, Colombia=5


# ---------------------------------------------------------------------------
# Recipe definitions used across Alex's brews
# ---------------------------------------------------------------------------
def _suitable_for(
    roast_levels: list[RoastLevel] | None = None,
    origins: list[str] | None = None,
    processes: list[Process] | None = None,
    flavor_profiles: list[str] | None = None,
) -> SuitableFor:
    return SuitableFor(
        roast_levels=roast_levels or [RoastLevel.LIGHT, RoastLevel.MEDIUM_LIGHT],
        origins=origins or ["Ethiopia", "Kenya", "Colombia"],
        processes=processes or [Process.WASHED, Process.NATURAL],
        flavor_profiles=flavor_profiles or ["Floral", "Citrus", "Berry"],
    )


def _recipe_hoffmann_classic() -> Recipe:
    return Recipe(
        recipe_id="hoffmann-v60-classic",
        source="James Hoffmann",
        method=BrewMethod.V60,
        dose_g=15.0,
        water_total_g=250.0,
        ratio=16.67,
        grind_setting=5,
        water_temp_c=93.0,
        bloom_time_s=45,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=50.0),
            PourStep(step=2, time_offset_s=45, water_g=100.0),
            PourStep(step=3, time_offset_s=90, water_g=100.0),
        ],
        suitable_for=_suitable_for(),
        instructions=(
            "Bloom with 3x dose water. Swirl gently. At 45s, pour to 150g "
            "in slow concentric circles. At 90s, pour remaining to 250g. "
            "Allow to draw down."
        ),
    )


def _recipe_kasuya_4_6() -> Recipe:
    """Kasuya 4:6 method - two-stage pouring for flavor control."""
    return Recipe(
        recipe_id="kasuya-4-6-v60",
        source="Tetsu Kasuya",
        method=BrewMethod.V60,
        dose_g=15.0,
        water_total_g=240.0,
        ratio=16.0,
        grind_setting=4,
        water_temp_c=93.0,
        bloom_time_s=30,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=60.0),
            PourStep(step=2, time_offset_s=30, water_g=60.0),
            PourStep(step=3, time_offset_s=75, water_g=60.0),
            PourStep(step=4, time_offset_s=120, water_g=60.0),
        ],
        suitable_for=_suitable_for(
            flavor_profiles=["Berry", "Citrus", "Floral", "Balanced"],
        ),
        instructions=(
            "First two pours control balance and sweetness. Last two pours "
            "control strength. Pour in 60g increments, maintaining gentle "
            "circulation."
        ),
    )


def _recipe_rao_spin() -> Recipe:
    """Scott Rao-inspired V60 with spin technique."""
    return Recipe(
        recipe_id="rao-v60-spin",
        source="Scott Rao",
        method=BrewMethod.V60,
        dose_g=16.0,
        water_total_g=256.0,
        ratio=16.0,
        grind_setting=5,
        water_temp_c=94.0,
        bloom_time_s=30,
        total_time_s=210,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=64.0),
            PourStep(step=2, time_offset_s=30, water_g=96.0),
            PourStep(step=3, time_offset_s=90, water_g=96.0),
        ],
        suitable_for=_suitable_for(
            roast_levels=[RoastLevel.LIGHT],
            flavor_profiles=["Floral", "Citrus", "Berry", "Balanced"],
        ),
        instructions=(
            "Bloom with 4x dose water. Give the slurry a gentle spin after "
            "each pour to level the bed. Second pour at 30s, final pour at "
            "90s. Aim for even extraction."
        ),
    )


def _recipe_hoffmann_light_delicate() -> Recipe:
    """Hoffmann's method for delicate light roasts."""
    return Recipe(
        recipe_id="hoffmann-v60-light-delicate",
        source="James Hoffmann",
        method=BrewMethod.V60,
        dose_g=14.0,
        water_total_g=238.0,
        ratio=17.0,
        grind_setting=4,
        water_temp_c=95.0,
        bloom_time_s=45,
        total_time_s=240,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=47.6),
            PourStep(step=2, time_offset_s=45, water_g=95.2),
            PourStep(step=3, time_offset_s=100, water_g=95.2),
        ],
        suitable_for=_suitable_for(
            roast_levels=[RoastLevel.LIGHT],
            origins=["Ethiopia", "Kenya"],
            flavor_profiles=["Floral", "Citrus", "Tea-like"],
        ),
        instructions=(
            "Gentle bloom with higher water temp. Use a very light hand on "
            "pouring to avoid agitating fine grounds. Allow extra drawdown "
            "time for delicate flavors."
        ),
    )


def _recipe_kalita_wave_bright() -> Recipe:
    """Kalita Wave recipe optimized for bright, fruity coffees."""
    return Recipe(
        recipe_id="kalita-wave-bright",
        source="BrewMatch",
        method=BrewMethod.KALITA_WAVE,
        dose_g=15.0,
        water_total_g=240.0,
        ratio=16.0,
        grind_setting=5,
        water_temp_c=93.0,
        bloom_time_s=30,
        total_time_s=195,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=45.0),
            PourStep(step=2, time_offset_s=30, water_g=97.5),
            PourStep(step=3, time_offset_s=80, water_g=97.5),
        ],
        suitable_for=_suitable_for(
            processes=[Process.WASHED, Process.NATURAL],
            flavor_profiles=["Citrus", "Berry", "Floral", "Balanced"],
        ),
        instructions=(
            "Bloom with 3x dose. Kalita's flat bed promotes even extraction. "
            "Pour in concentric circles avoiding the paper. Two main pours "
            "after bloom."
        ),
    )


def _recipe_origami_versatile() -> Recipe:
    """Origami dripper recipe - versatile for various beans."""
    return Recipe(
        recipe_id="bh-origami-versatile",
        source="BrewMatch",
        method=BrewMethod.ORIGAMI,
        dose_g=15.0,
        water_total_g=225.0,
        ratio=15.0,
        grind_setting=5,
        water_temp_c=92.0,
        bloom_time_s=40,
        total_time_s=180,
        pours=[
            PourStep(step=1, time_offset_s=0, water_g=45.0),
            PourStep(step=2, time_offset_s=40, water_g=90.0),
            PourStep(step=3, time_offset_s=85, water_g=90.0),
        ],
        suitable_for=_suitable_for(
            origins=["Colombia", "Ethiopia", "Kenya"],
            flavor_profiles=["Sweet", "Berry", "Citrus", "Balanced"],
        ),
        instructions=(
            "Origami works well with both cone and flat-bottom filters. "
            "This recipe uses a moderate ratio and temp for balanced "
            "extraction across various beans."
        ),
    )


# Recipe rotation for the 15 brews
_RECIPES = [
    _recipe_hoffmann_classic,   # 1  - starting with the classic
    _recipe_hoffmann_classic,   # 2  - same recipe, learning the technique
    _recipe_kasuya_4_6,         # 3  - trying Kasuya 4:6
    _recipe_hoffmann_classic,   # 4  - back to Hoffmann
    _recipe_rao_spin,           # 5  - exploring Rao's spin
    _recipe_hoffmann_light_delicate,  # 6 - delicate method for Ethiopian
    _recipe_kalita_wave_bright, # 7  - switching to Kalita Wave
    _recipe_hoffmann_classic,   # 8  - back to trusted Hoffmann
    _recipe_kasuya_4_6,         # 9  - Kasuya for anaerobic bean
    _recipe_rao_spin,           # 10 - Rao spin refinement
    _recipe_hoffmann_classic,   # 11 - consistent approach
    _recipe_kalita_wave_bright, # 12 - Kalita for Kenyan
    _recipe_hoffmann_light_delicate,  # 13 - delicate Ethiopian again
    _recipe_origami_versatile,  # 14 - trying Origami dripper
    _recipe_hoffmann_classic,   # 15 - mastered the classic
]

# Hoffmann Classic: 7, Kasuya 4:6: 2, Rao Spin: 2, Hoffmann Light: 2,
# Kalita Wave Bright: 2, Origami Versatile: 1
# V60: 13, Kalita Wave: 2, Origami: 1


# ---------------------------------------------------------------------------
# Brew outcome definitions
# ---------------------------------------------------------------------------
# Scores show a learning curve: early brews ~5-6, middle ~7, later ~8-9
# Average should be approximately 7.2
_BREW_OUTCOMES: list[dict] = [
    # index 0: brew 1 - early attempt, still learning
    dict(score=5, thumbs_up=False, directional_flags=["too_sour"],
         notes="Under-extracted. Water may have been too cool."),
    # index 1: brew 2 - improving but still off
    dict(score=6, thumbs_up=False, directional_flags=None,
         notes="Better, but pour was uneven. Some channeling."),
    # index 2: brew 3 - tried new recipe, over-extracted
    dict(score=4, thumbs_up=False, directional_flags=["too_bitter", "too_harsh"],
         notes="Too fine a grind. Over-extracted and harsh. Need to coarsen."),
    # index 3: brew 4 - back to classic, decent result
    dict(score=7, thumbs_up=True, directional_flags=None,
         notes="Good cup. Balanced. Getting the hang of the pour rate."),
    # index 4: brew 5 - trying Rao spin, decent
    dict(score=7, thumbs_up=True, directional_flags=None,
         notes="Spin technique helped with even extraction."),
    # index 5: brew 6 - delicate method, good match for Ethiopian
    dict(score=8, thumbs_up=True, directional_flags=None,
         notes="Excellent clarity. Jasmine and lemon really came through."),
    # index 6: brew 7 - switched to Kalita, too weak
    dict(score=5, thumbs_up=False, directional_flags=["too_weak"],
         notes="Kalita drew down too fast. Grind may be too coarse."),
    # index 7: brew 8 - back to Hoffmann, solid
    dict(score=8, thumbs_up=True, directional_flags=None,
         notes="Really nice. Blackcurrant notes from the Nyeri were clear."),
    # index 8: brew 9 - Kasuya with anaerobic, very good
    dict(score=9, thumbs_up=True, directional_flags=None,
         notes="Best yet. The anaerobic Ethiopian was incredible with this method."),
    # index 9: brew 10 - Rao spin, consistent
    dict(score=8, thumbs_up=True, directional_flags=None,
         notes="Consistent cup. The spin technique is really working."),
    # index 10: brew 11 - back to classic, slight over-extraction
    dict(score=6, thumbs_up=False, directional_flags=["too_harsh", "astringent"],
         notes="Let it draw down too long. Astringent finish. Need to watch timing."),
    # index 11: brew 12 - Kalita redemption, great
    dict(score=8, thumbs_up=True, directional_flags=None,
         notes="Adjusted grind finer. Kalita shines with this Kenyan bean."),
    # index 12: brew 13 - delicate Ethiopian, excellent
    dict(score=9, thumbs_up=True, directional_flags=None,
         notes="Perfect. Blueberry and jasmine in harmony."),
    # index 13: brew 14 - trying Origami, good result
    dict(score=8, thumbs_up=True, directional_flags=None,
         notes="Origami is fun. Sweet and balanced cup."),
    # index 14: brew 15 - classic method, mastered
    dict(score=9, thumbs_up=True, directional_flags=None,
         notes="Confident with the Hoffmann method now. Consistently great cups."),
]

# Score sum: 5+6+4+7+7+8+5+8+9+8+6+8+9+8+9 = 107
# Average: 107/15 = 7.13 ~ 7.1 (close enough to 7.2 target)


# ---------------------------------------------------------------------------
# Core seeding function
# ---------------------------------------------------------------------------
def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Seed Alex's user profile and 15 brew records into the given connection.

    Idempotent: deletes any existing Alex data before seeding.
    """
    from src.app.db import delete_user_data

    # Create tables first (safe to call multiple times)
    init_db(conn)

    # Clear any prior demo data for a clean slate
    delete_user_data(conn, ALEX_USER_ID)

    # Save Alex's user profile
    save_user(conn, ALEX_USER_ID, ALEX_ONBOARDING)
    update_preferences(conn, ALEX_USER_ID, ALEX_PREFERENCES)

    # Generate 15 brews spanning 30 days, one every ~2 days
    # Most recent brew is today, oldest is 28 days ago
    now = datetime.now(timezone.utc)
    base_date = now - timedelta(days=28)

    for i in range(15):
        # Space brews ~2 days apart: day 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28
        brew_date = base_date + timedelta(days=2 * i)
        # Add a random-ish time of day so timestamps are distinct
        hour = 7 + (i % 5)  # between 7:00 and 11:00
        minute = (i * 13) % 60
        brew_ts = brew_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        bean_data = _BEANS[_BREW_BEAN_INDICES[i]]
        bean = BeanProfile(**bean_data)

        recipe = _RECIPES[i]()

        outcome = _BREW_OUTCOMES[i]
        feedback = Feedback(
            thumbs_up=outcome["thumbs_up"],
            score=outcome["score"],
            directional_flags=outcome["directional_flags"],
            notes=outcome["notes"],
        )

        brew = BrewRecord(
            brew_id=_uuid_for_index(i),
            timestamp=brew_ts.isoformat(),
            bean_profile=bean,
            recipe_used=recipe,
            feedback=feedback,
        )

        save_brew(conn, ALEX_USER_ID, brew)


def seed_demo_data_for_user(
    conn: sqlite3.Connection,
    user_id: str,
    onboarding: Onboarding | None = None,
    preferences: LearnedPreferences | None = None,
) -> None:
    """Seed demo brew data for an arbitrary user_id.

    Used by the demo account auto-provisioning in app.py.
    """
    onboarding = onboarding or ALEX_ONBOARDING
    preferences = preferences or ALEX_PREFERENCES

    save_user(conn, user_id, onboarding)
    update_preferences(conn, user_id, preferences)

    now = datetime.now(timezone.utc)
    base_date = now - timedelta(days=28)

    for i in range(15):
        brew_date = base_date + timedelta(days=2 * i)
        hour = 7 + (i % 5)
        minute = (i * 13) % 60
        brew_ts = brew_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        bean_data = _BEANS[_BREW_BEAN_INDICES[i]]
        bean = BeanProfile(**bean_data)
        recipe = _RECIPES[i]()

        outcome = _BREW_OUTCOMES[i]
        feedback = Feedback(
            thumbs_up=outcome["thumbs_up"],
            score=outcome["score"],
            directional_flags=outcome["directional_flags"],
            notes=outcome["notes"],
        )

        brew = BrewRecord(
            brew_id=_uuid_for_index(i),
            timestamp=brew_ts.isoformat(),
            bean_profile=bean,
            recipe_used=recipe,
            feedback=feedback,
        )

        save_brew(conn, user_id, brew)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Create and seed the demo database at data/demo.db."""
    db_path = _PROJECT_ROOT / "data" / "demo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing demo DB for a clean seed
    if db_path.exists():
        db_path.unlink()

    conn = get_connection(str(db_path))
    try:
        seed_demo_data(conn)

        # Verify the seed
        from src.app.db import get_user_stats, load_brew_history, load_user

        user = load_user(conn, ALEX_USER_ID)
        assert user is not None, "Alex user was not created"
        assert user["user_id"] == ALEX_USER_ID

        history = load_brew_history(conn, ALEX_USER_ID)
        assert len(history) == 15, f"Expected 15 brews, got {len(history)}"

        stats = get_user_stats(conn, ALEX_USER_ID)
        assert stats["total_brews"] == 15, f"Expected 15 total brews, got {stats['total_brews']}"

        print(f"Demo database seeded successfully at: {db_path}")
        print(f"  User: {ALEX_USER_ID}")
        print(f"  Total brews: {stats['total_brews']}")
        print(f"  Average score: {stats['avg_score']:.1f}")
        print(f"  Favorite origins: {', '.join(stats['favorite_origins'])}")
        print(f"  Favorite clusters: {', '.join(stats['favorite_clusters'])}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

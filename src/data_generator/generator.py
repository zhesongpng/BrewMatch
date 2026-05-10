"""Synthetic data generator for BrewMatch.

Generates virtual users, ratings, expert labels, and demo user data
based on coffee extraction theory. All output is reproducible with seed=42.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Seed for reproducibility
DEFAULT_SEED = 42

# Constants
DIRECTIONAL_FLAGS = ("too_sour", "too_bitter", "too_weak", "too_harsh", "astringent")
ROAST_LEVELS = ("light", "medium-light", "medium", "medium-dark", "dark")
PROCESSES = ("washed", "natural", "honey", "anaerobic", "wet-hulled")
FLAVOR_CLUSTERS = (
    "Floral", "Berry", "Citrus", "Stone Fruit", "Tropical",
    "Sweet", "Chocolate", "Nutty", "Spice", "Roasted",
    "Vegetal", "Tea-like", "Fermented", "Syrupy", "Balanced",
)
ORIGINS = (
    "Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala",
    "Costa Rica", "Honduras", "Panama", "Rwanda", "Sumatra",
    "Uganda", "Burundi", "India", "El Salvador", "Peru",
)
ORIGIN_REGIONS = {
    "Ethiopia": ["Yirgacheffe", "Sidamo", "Guji", "Limu"],
    "Colombia": ["Huila", "Narino", "Cauca", "Antioquia"],
    "Brazil": ["Minas Gerais", "Sao Paulo", "Bahia"],
    "Kenya": ["Nyeri", "Embu", "Muranga"],
    "Guatemala": ["Antigua", "Huehuetenango", "Atitlan"],
    "Costa Rica": ["Tarrazu", "West Valley", "Central Valley"],
    "Panama": ["Boquete", "Volcan"],
}
VARIETIES = ["Gesha", "Bourbon", "SL28", "Typica", "Caturra", "Catuai", "Pacamara", None]


# --- Virtual User ---

@dataclass
class VirtualUser:
    user_id: str
    roast_preference: str
    preferred_clusters: list[str]
    rating_bias: float
    acidity_tolerance: float
    body_preference: float
    sweetness_preference: float
    experience_level: str


@dataclass
class Expert:
    expert_id: str
    specialty: str
    rating_bias: float
    preferred_roasts: list[str]
    preferred_clusters: list[str]
    noise_std: float


# --- Alignment Functions ---

def compute_roast_temp_alignment(roast_level: str, water_temp_c: float) -> float:
    light_roasts = ("light", "medium-light")
    dark_roasts = ("dark", "medium-dark")

    if roast_level in light_roasts:
        if 92.0 <= water_temp_c <= 98.0:
            return 1.0
        elif water_temp_c < 92.0:
            return max(0.0, 1.0 - (92.0 - water_temp_c) * 0.15)
        else:
            return max(0.0, 1.0 - (water_temp_c - 98.0) * 0.1)
    elif roast_level in dark_roasts:
        if 89.0 <= water_temp_c <= 94.0:
            return 1.0
        elif water_temp_c > 94.0:
            return max(0.0, 1.0 - (water_temp_c - 94.0) * 0.15)
        else:
            return max(0.0, 1.0 - (89.0 - water_temp_c) * 0.1)
    else:  # medium
        if 91.0 <= water_temp_c <= 95.0:
            return 1.0
        else:
            return max(0.0, 1.0 - abs(water_temp_c - 93.0) * 0.08)


def compute_grind_time_alignment(grind_setting: int, total_time_s: int) -> float:
    if grind_setting <= 3:  # fine
        if 150 <= total_time_s <= 210:
            return 1.0
        elif total_time_s > 210:
            return max(0.0, 1.0 - (total_time_s - 210) / 100)
        else:
            return max(0.0, 1.0 - (150 - total_time_s) / 50)
    elif grind_setting >= 7:  # coarse
        if 240 <= total_time_s <= 330:
            return 1.0
        elif total_time_s < 240:
            return max(0.0, 1.0 - (240 - total_time_s) / 80)
        else:
            return max(0.0, 1.0 - (total_time_s - 330) / 60)
    else:  # medium
        if 180 <= total_time_s <= 270:
            return 1.0
        else:
            return max(0.0, 1.0 - abs(total_time_s - 225) / 80)


def compute_process_grind_alignment(process: str, grind_setting: int) -> float:
    if process == "natural":
        if 5 <= grind_setting <= 8:
            return 1.0
        elif grind_setting < 5:
            return max(0.0, 1.0 - (5 - grind_setting) * 0.2)
        else:
            return max(0.0, 1.0 - (grind_setting - 8) * 0.2)
    elif process == "washed":
        if 3 <= grind_setting <= 6:
            return 1.0
        else:
            return max(0.0, 1.0 - abs(grind_setting - 4.5) * 0.15)
    else:
        return 0.7  # neutral for other processes


def extraction_quality_score(bean: dict, recipe: dict) -> float:
    score = 0.5
    score += 0.20 * compute_roast_temp_alignment(bean["roast_level"], recipe["water_temp_c"])
    score += 0.15 * compute_grind_time_alignment(recipe["grind_setting"], recipe["total_time_s"])
    ratio_score = 1.0 - abs(recipe["ratio"] - 16.0) / 3.0
    score += 0.10 * max(0.0, ratio_score)
    dose_score = 1.0 - abs(recipe["dose_g"] - 16.0) / 6.0
    score += 0.05 * max(0.0, dose_score)
    score += 0.10 * compute_process_grind_alignment(bean["process"], recipe["grind_setting"])
    return float(np.clip(score, 0.0, 1.0))


# --- Preference Alignment ---

def compute_preference_alignment(user: VirtualUser, bean: dict) -> float:
    alignment = 0.0
    if bean.get("roast_level") == user.roast_preference:
        alignment += 1.0
    elif bean.get("roast_level"):
        roast_idx_a = ROAST_LEVELS.index(user.roast_preference)
        roast_idx_b = ROAST_LEVELS.index(bean["roast_level"])
        alignment -= abs(roast_idx_a - roast_idx_b) * 0.3
    for cluster in bean.get("flavor_clusters", []):
        if cluster in user.preferred_clusters:
            alignment += 0.5
    return np.clip(alignment, -2.0, 3.0)


# --- Rating Generation ---

def generate_rating(quality_score: float, user: VirtualUser, bean: dict,
                    noise_std: float = 0.8, rng: random.Random = None) -> int:
    base_rating = 2.0 + quality_score * 5.0
    biased_rating = base_rating + user.rating_bias
    preference_bonus = compute_preference_alignment(user, bean)
    biased_rating += preference_bonus * 0.5
    noise = rng.gauss(0, noise_std) if rng else np.random.normal(0, noise_std)
    noisy_rating = biased_rating + noise
    return int(round(float(np.clip(noisy_rating, 1, 10))))


def is_underextracted(bean: dict, recipe: dict) -> bool:
    temp_too_low = (bean["roast_level"] in ("light", "medium-light")
                    and recipe["water_temp_c"] < 92)
    grind_time_mismatch = recipe["grind_setting"] >= 7 and recipe["total_time_s"] < 200
    ratio_too_high = recipe["ratio"] >= 17.5
    return temp_too_low or grind_time_mismatch or ratio_too_high


def is_overextracted(bean: dict, recipe: dict) -> bool:
    temp_too_high = (bean["roast_level"] in ("dark", "medium-dark")
                     and recipe["water_temp_c"] > 95)
    grind_time_mismatch = recipe["grind_setting"] <= 3 and recipe["total_time_s"] > 250
    ratio_too_low = recipe["ratio"] <= 14.5
    return temp_too_high or grind_time_mismatch or ratio_too_low


def generate_directional_flags(bean: dict, recipe: dict, rating: int) -> list[str]:
    flags = []
    if rating >= 7:
        return flags
    if is_underextracted(bean, recipe):
        if random.random() < 0.6:
            flags.append("too_sour")
        if random.random() < 0.3:
            flags.append("too_weak")
    if is_overextracted(bean, recipe):
        if random.random() < 0.6:
            flags.append("too_bitter")
        if random.random() < 0.3:
            flags.append("too_harsh")
    if rating <= 3 and is_overextracted(bean, recipe):
        if random.random() < 0.4:
            flags.append("astringent")
    return flags


# --- Bean Generation ---

CLUSTER_NOTE_MAP = {
    "Floral": ["Jasmine", "Chamomile", "Hibiscus", "Rose", "Lavender", "Elderflower"],
    "Berry": ["Blueberry", "Blackberry", "Raspberry", "Strawberry", "Cranberry", "Acai"],
    "Citrus": ["Lemon", "Orange", "Grapefruit", "Lime", "Tangerine", "Yuzu"],
    "Stone Fruit": ["Peach", "Apricot", "Plum", "Cherry", "Nectarine"],
    "Tropical": ["Mango", "Pineapple", "Passion Fruit", "Papaya", "Guava", "Coconut"],
    "Sweet": ["Honey", "Caramel", "Brown Sugar", "Maple", "Vanilla", "Molasses"],
    "Chocolate": ["Dark Chocolate", "Cocoa", "Milk Chocolate", "Cacao Nib"],
    "Nutty": ["Almond", "Hazelnut", "Peanut", "Walnut", "Pecan"],
    "Spice": ["Cinnamon", "Clove", "Cardamom", "Ginger", "Black Pepper", "Nutmeg"],
    "Roasted": ["Toasted Bread", "Smoky", "Tobacco", "Charred Oak"],
    "Vegetal": ["Green Tea", "Herbal", "Grassy", "Spinach", "Bell Pepper"],
    "Tea-like": ["Earl Grey", "Oolong", "Green Tea", "Black Tea", "White Tea"],
    "Fermented": ["Wine", "Whiskey", "Kombucha", "Overripe Fruit"],
    "Syrupy": ["Maple Syrup", "Agave", "Treacle", "Golden Syrup"],
    "Balanced": ["Round", "Smooth", "Clean", "Mellow", "Harmonious"],
}


def generate_random_bean(rng: random.Random) -> dict:
    origin = rng.choice(ORIGINS)
    regions = ORIGIN_REGIONS.get(origin, [])
    clusters = rng.sample(list(FLAVOR_CLUSTERS), rng.randint(1, 4))
    # Derive notes from clusters — pick 2-5 notes that match the clusters
    pool = []
    for c in clusters:
        pool.extend(CLUSTER_NOTE_MAP.get(c, [c]))
    # Ensure at least some notes come from the chosen clusters
    n_notes = rng.randint(2, min(5, len(pool)))
    flavor_notes = rng.sample(pool, min(n_notes, len(pool)))
    return {
        "origin_country": origin,
        "origin_region": rng.choice(regions) if regions and rng.random() < 0.6 else None,
        "process": rng.choice(PROCESSES),
        "roast_level": rng.choice(ROAST_LEVELS),
        "flavor_notes": flavor_notes,
        "flavor_clusters": clusters,
        "variety": rng.choice(VARIETIES),
        "altitude_min_m": rng.randint(800, 1800) if rng.random() < 0.7 else None,
        "altitude_max_m": None,
    }


def generate_recipe_params(rng: random.Random, bean: dict = None) -> dict:
    dose = round(rng.uniform(12.0, 35.0), 1)
    ratio = round(rng.uniform(14.0, 18.0), 1)
    water = round(dose * ratio, 1)
    grind = rng.randint(1, 10)
    temp = round(rng.uniform(85.0, 100.0), 1)
    bloom = rng.randint(15, 90)
    total = rng.randint(120, 360)
    return {
        "dose_g": dose,
        "ratio": ratio,
        "grind_setting": grind,
        "water_temp_c": temp,
        "bloom_time_s": bloom,
        "total_time_s": total,
        "pour_count": rng.randint(1, 6),
    }


# --- User Generation ---

def generate_user(user_id: str, rng: random.Random) -> VirtualUser:
    r = rng.random()
    if r < 0.30:
        level = "beginner"
    elif r < 0.80:
        level = "intermediate"
    else:
        level = "advanced"

    return VirtualUser(
        user_id=user_id,
        roast_preference=rng.choice(ROAST_LEVELS),
        preferred_clusters=rng.sample(list(FLAVOR_CLUSTERS), rng.randint(2, 4)),
        rating_bias=rng.gauss(0, 0.8),
        acidity_tolerance=rng.uniform(-1, 1),
        body_preference=rng.uniform(-1, 1),
        sweetness_preference=rng.uniform(-1, 1),
        experience_level=level,
    )


# --- Expert Generation ---

EXPERT_TEMPLATES = [
    ("expert-a-sca", "SCA judge", 0.0, list(ROAST_LEVELS), list(FLAVOR_CLUSTERS[:5]), 0.3),
    ("expert-b-light", "Light roast specialist", 0.5, ["light", "medium-light"],
     ["Berry", "Citrus", "Floral", "Stone Fruit"], 0.3),
    ("expert-c-traditional", "Traditional cupper", -0.3, ["medium", "medium-dark", "dark"],
     ["Chocolate", "Nutty", "Sweet", "Balanced"], 0.3),
    ("expert-d-modern", "Modern barista", 0.2, ["light", "medium-light"],
     ["Tea-like", "Floral", "Citrus", "Balanced"], 0.4),
    ("expert-e-home", "Home brewer", 0.8, list(ROAST_LEVELS), list(FLAVOR_CLUSTERS[:8]), 0.5),
]


def generate_experts() -> list[Expert]:
    return [
        Expert(expert_id=t[0], specialty=t[1], rating_bias=t[2],
               preferred_roasts=t[3], preferred_clusters=t[4], noise_std=t[5])
        for t in EXPERT_TEMPLATES
    ]


def expert_rating(quality_score: float, expert: Expert, bean: dict) -> int:
    base = 3.0 + quality_score * 6.0 + expert.rating_bias
    if bean["roast_level"] in expert.preferred_roasts:
        base += 0.3
    for c in bean.get("flavor_clusters", []):
        if c in expert.preferred_clusters:
            base += 0.2
    noisy = base + np.random.normal(0, expert.noise_std)
    return int(round(float(np.clip(noisy, 1, 10))))


# --- Main Generation ---

def _biased_recipe(rng: random.Random, bean: dict, user: VirtualUser,
                   tightness: float) -> dict:
    """Generate recipe params biased toward user's roast preference.

    tightness: 0.0 = fully random, 1.0 = tightly clustered around optimal.
    """
    base = generate_recipe_params(rng, bean)

    if tightness <= 0:
        return base

    # Bias temperature toward roast-optimal range
    roast = user.roast_preference
    if roast in ("light", "medium-light"):
        opt_temp = rng.uniform(92.0, 98.0)
    elif roast in ("dark", "medium-dark"):
        opt_temp = rng.uniform(89.0, 94.0)
    else:
        opt_temp = rng.uniform(91.0, 95.0)
    base["water_temp_c"] = round(
        base["water_temp_c"] * (1 - tightness) + opt_temp * tightness, 1
    )

    # Bias grind toward middle range (4-6) for pour-over
    opt_grind = rng.randint(4, 6)
    base["grind_setting"] = int(round(
        base["grind_setting"] * (1 - tightness) + opt_grind * tightness
    ))

    # Bias ratio toward golden zone (15-17)
    opt_ratio = rng.uniform(15.0, 17.0)
    base["ratio"] = round(
        base["ratio"] * (1 - tightness) + opt_ratio * tightness, 1
    )

    return base


def generate_brew_history(user: VirtualUser, n_brews: int, rng: random.Random,
                          base_date: datetime) -> list[dict]:
    noise_map = {"beginner": 1.0, "intermediate": 0.8, "advanced": 0.6}
    rows = []
    elapsed_days = 0
    for i in range(n_brews):
        bean = generate_random_bean(rng)

        # Phase 1: Exploration (brews 0-4) — random params, high noise
        if i < 5:
            recipe = generate_recipe_params(rng, bean)
            noise = noise_map.get(user.experience_level, 0.8) + 0.3
        # Phase 2: Learning (brews 5-14) — params start clustering toward preferences
        elif i < 15:
            progress = (i - 5) / 10.0  # 0.0 → 1.0 across learning phase
            tightness = 0.3 * progress  # gradually increase from 0.0 to 0.3
            recipe = _biased_recipe(rng, bean, user, tightness)
            noise = noise_map.get(user.experience_level, 0.8)
        # Phase 3: Exploitation (brew 15+) — tight params, low noise, occasional exploration
        else:
            if rng.random() < 0.1:
                recipe = generate_recipe_params(rng, bean)
                noise = noise_map.get(user.experience_level, 0.8)
            else:
                recipe = _biased_recipe(rng, bean, user, 0.6)
                noise = max(noise_map.get(user.experience_level, 0.8) - 0.2, 0.3)

        quality = extraction_quality_score(bean, recipe)
        rating = generate_rating(quality, user, bean, max(noise, 0.3), rng)
        flags = generate_directional_flags(bean, recipe, rating)

        elapsed_days += rng.randint(1, 5)
        ts = base_date + timedelta(days=elapsed_days)
        rows.append({
            "user_id": user.user_id,
            "bean_profile": bean,
            "recipe_params": recipe,
            "rating": rating,
            "directional_flags": flags,
            "timestamp": ts.isoformat() + "Z",
        })
    return rows


def generate_demo_alex(rng: random.Random) -> dict:
    alex = VirtualUser(
        user_id="demo-alex-001",
        roast_preference="light",
        preferred_clusters=["Berry", "Citrus", "Floral"],
        rating_bias=0.3,
        acidity_tolerance=0.5,
        body_preference=-0.2,
        sweetness_preference=0.3,
        experience_level="intermediate",
    )
    base_date = datetime(2026, 1, 1)
    brews = generate_brew_history(alex, 15, rng, base_date)

    # Ensure last 5 brews have ratings >= 7 by biasing the recipe params
    for i in range(10, 15):
        bean = brews[i]["bean_profile"]
        # Bias towards light-roast-friendly parameters
        recipe = brews[i]["recipe_params"]
        recipe["water_temp_c"] = round(rng.uniform(93.0, 97.0), 1)
        recipe["grind_setting"] = rng.randint(3, 6)
        recipe["ratio"] = round(rng.uniform(15.5, 17.0), 1)
        quality = extraction_quality_score(bean, recipe)
        brews[i]["recipe_params"] = recipe
        brews[i]["rating"] = max(7, generate_rating(quality, alex, bean, 0.7, rng))
        brews[i]["directional_flags"] = []

    return {
        "user_id": alex.user_id,
        "experience_level": alex.experience_level,
        "roast_preference": alex.roast_preference,
        "preferred_clusters": alex.preferred_clusters,
        "rating_bias": alex.rating_bias,
        "acidity_tolerance": alex.acidity_tolerance,
        "body_preference": alex.body_preference,
        "sweetness_preference": alex.sweetness_preference,
        "brew_history": brews,
    }


def generate_all(seed: int = DEFAULT_SEED, output_dir: str = "data/synthetic") -> dict:
    np.random.seed(seed)
    random.seed(seed)
    rng = random.Random(seed)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Generate 200 users
    users = [generate_user(f"synth-{i:03d}", rng) for i in range(200)]

    # Generate ratings (5K-10K)
    all_rows = []
    for user in users:
        n_brews = rng.randint(0, 30)
        brews = generate_brew_history(user, n_brews, rng, datetime(2025, 1, 1))
        all_rows.extend(brews)

    # Flatten for CSV
    flat_rows = []
    for row in all_rows:
        bp = row["bean_profile"]
        rp = row["recipe_params"]
        flat_rows.append({
            "user_id": row["user_id"],
            "origin_country": bp["origin_country"],
            "origin_region": bp.get("origin_region", ""),
            "process": bp["process"],
            "roast_level": bp["roast_level"],
            "flavor_clusters": "|".join(bp.get("flavor_clusters", [])),
            "flavor_notes": "|".join(bp.get("flavor_notes", [])),
            "variety": bp.get("variety", ""),
            "altitude_min_m": bp.get("altitude_min_m", ""),
            "dose_g": rp["dose_g"],
            "ratio": rp["ratio"],
            "grind_setting": rp["grind_setting"],
            "water_temp_c": rp["water_temp_c"],
            "bloom_time_s": rp["bloom_time_s"],
            "total_time_s": rp["total_time_s"],
            "pour_count": rp["pour_count"],
            "rating": row["rating"],
            "directional_flags": "|".join(row["directional_flags"]),
            "timestamp": row["timestamp"],
        })

    df = pd.DataFrame(flat_rows)
    df.to_csv(out / "ratings.csv", index=False)

    # Save users
    users_data = []
    for u in users:
        users_data.append({
            "user_id": u.user_id,
            "roast_preference": u.roast_preference,
            "preferred_clusters": u.preferred_clusters,
            "rating_bias": round(u.rating_bias, 3),
            "acidity_tolerance": round(u.acidity_tolerance, 3),
            "body_preference": round(u.body_preference, 3),
            "sweetness_preference": round(u.sweetness_preference, 3),
            "experience_level": u.experience_level,
        })
    (out / "users.json").write_text(json.dumps(users_data, indent=2))

    # Generate expert labels (60 bean-recipe pairings rated by all 5 experts)
    experts = generate_experts()
    expert_rows = []
    for i in range(60):
        bean = generate_random_bean(rng)
        recipe = generate_recipe_params(rng, bean)
        quality = extraction_quality_score(bean, recipe)

        ratings = {}
        for exp in experts:
            r = expert_rating(quality, exp, bean)
            ratings[exp.expert_id] = r

        mean_rating = round(sum(ratings.values()) / len(ratings), 1)
        disagreement = max(ratings.values()) - min(ratings.values())
        controversial = disagreement > 2

        expert_rows.append({
            "pairing_id": f"pair-{i:03d}",
            "origin_country": bean["origin_country"],
            "process": bean["process"],
            "roast_level": bean["roast_level"],
            "dose_g": recipe["dose_g"],
            "ratio": recipe["ratio"],
            "grind_setting": recipe["grind_setting"],
            "water_temp_c": recipe["water_temp_c"],
            "expert_a": ratings["expert-a-sca"],
            "expert_b": ratings["expert-b-light"],
            "expert_c": ratings["expert-c-traditional"],
            "expert_d": ratings["expert-d-modern"],
            "expert_e": ratings["expert-e-home"],
            "mean_rating": mean_rating,
            "controversial": controversial,
        })

    pd.DataFrame(expert_rows).to_csv(out / "expert_labels.csv", index=False)

    # Generate demo user Alex
    alex_rng = random.Random(seed)
    np.random.seed(seed)
    alex_data = generate_demo_alex(alex_rng)
    (out / "demo_alex.json").write_text(json.dumps(alex_data, indent=2))

    # Metadata
    metadata = {
        "seed": seed,
        "generated_at": datetime.now().isoformat(),
        "n_ratings": len(all_rows),
        "n_users": len(users),
        "n_expert_labels": len(expert_rows),
        "n_alex_brews": len(alex_data["brew_history"]),
        "rating_distribution": {
            str(k): int(v) for k, v in sorted(df["rating"].value_counts().items())
        },
        "experience_distribution": {
            level: sum(1 for u in users if u.experience_level == level)
            for level in ("beginner", "intermediate", "advanced")
        },
        "controversial_expert_labels": sum(1 for r in expert_rows if r["controversial"]),
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return metadata


if __name__ == "__main__":
    meta = generate_all()
    print(f"Generated {meta['n_ratings']} ratings, {meta['n_users']} users, "
          f"{meta['n_expert_labels']} expert labels, {meta['n_alex_brews']} Alex brews")
    print(f"Rating distribution: {meta['rating_distribution']}")
    print(f"Experience: {meta['experience_distribution']}")
    print(f"Controversial labels: {meta['controversial_expert_labels']}")

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


# --- Enums ---

class BrewMethod(str, Enum):
    V60 = "V60"
    KALITA_WAVE = "Kalita Wave"
    ORIGAMI = "Origami"


class Process(str, Enum):
    WASHED = "washed"
    NATURAL = "natural"
    HONEY = "honey"
    ANAEROBIC = "anaerobic"
    WET_HULLED = "wet-hulled"
    UNKNOWN = "unknown"


class RoastLevel(str, Enum):
    LIGHT = "light"
    MEDIUM_LIGHT = "medium-light"
    MEDIUM = "medium"
    MEDIUM_DARK = "medium-dark"
    DARK = "dark"
    UNKNOWN = "unknown"


class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


DIRECTIONAL_FLAGS = ("too_sour", "too_bitter", "too_weak", "too_harsh", "astringent")

FLAVOR_CLUSTERS = (
    "Floral", "Berry", "Citrus", "Stone Fruit", "Tropical",
    "Sweet", "Chocolate", "Nutty", "Spice", "Roasted",
    "Vegetal", "Tea-like", "Fermented", "Syrupy", "Balanced",
)


# --- Data Classes ---

@dataclass
class PourStep:
    step: int
    time_offset_s: int
    water_g: float

    def __post_init__(self):
        if self.step < 1:
            raise ValueError(f"Pour step must be 1-indexed, got {self.step}")
        if self.step == 1 and self.time_offset_s != 0:
            raise ValueError(f"First pour (bloom) must have time_offset_s=0, got {self.time_offset_s}")
        if not (10.0 <= self.water_g <= 200.0):
            raise ValueError(f"Pour water_g must be 10.0-200.0, got {self.water_g}")


@dataclass
class SuitableFor:
    roast_levels: list[RoastLevel]
    origins: list[str]
    processes: list[Process]
    flavor_profiles: list[str]

    def __post_init__(self):
        if not self.roast_levels:
            raise ValueError("suitable_for.roast_levels must have at least 1 element")
        if not self.origins:
            raise ValueError("suitable_for.origins must have at least 1 element")
        if not self.processes:
            raise ValueError("suitable_for.processes must have at least 1 element")
        if not self.flavor_profiles:
            raise ValueError("suitable_for.flavor_profiles must have at least 1 element")
        for fp in self.flavor_profiles:
            if fp not in FLAVOR_CLUSTERS:
                raise ValueError(f"Unknown flavor profile '{fp}'. Must be one of {FLAVOR_CLUSTERS}")


@dataclass
class Recipe:
    recipe_id: str
    source: str
    method: BrewMethod
    dose_g: float
    water_total_g: float
    ratio: float
    grind_setting: int
    water_temp_c: float
    bloom_time_s: int
    total_time_s: int
    pours: list[PourStep]
    suitable_for: SuitableFor
    instructions: str
    source_url: Optional[str] = None

    def __post_init__(self):
        if not self.recipe_id or not self.recipe_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"recipe_id must be kebab-case alphanumeric, got '{self.recipe_id}'")
        if not self.source or not self.source.strip():
            raise ValueError("source must be non-empty (whitespace-only is not allowed)")
        if not (12.0 <= self.dose_g <= 35.0):
            raise ValueError(f"dose_g must be 12.0-35.0, got {self.dose_g}")
        if not (180.0 <= self.water_total_g <= 600.0):
            raise ValueError(f"water_total_g must be 180.0-600.0, got {self.water_total_g}")
        if not (14.0 <= self.ratio <= 18.0):
            raise ValueError(f"ratio must be 14.0-18.0, got {self.ratio}")
        if not (1 <= self.grind_setting <= 10):
            raise ValueError(f"grind_setting must be 1-10, got {self.grind_setting}")
        if not (85.0 <= self.water_temp_c <= 100.0):
            raise ValueError(f"water_temp_c must be 85.0-100.0, got {self.water_temp_c}")
        if not (15 <= self.bloom_time_s <= 90):
            raise ValueError(f"bloom_time_s must be 15-90, got {self.bloom_time_s}")
        if not (120 <= self.total_time_s <= 360):
            raise ValueError(f"total_time_s must be 120-360, got {self.total_time_s}")
        if not (1 <= len(self.pours) <= 6):
            raise ValueError(f"Must have 1-6 pours, got {len(self.pours)}")
        if not self.instructions or not self.instructions.strip():
            raise ValueError("instructions must be non-empty (whitespace-only is not allowed)")

        # water_total_g ≈ sum of pours (within 5%)
        pours_total = sum(p.water_g for p in self.pours)
        if abs(pours_total - self.water_total_g) > self.water_total_g * 0.05:
            raise ValueError(
                f"water_total_g ({self.water_total_g}) must be within 5% of "
                f"sum of pours ({pours_total})"
            )

        # ratio = water_total_g / dose_g (within 0.1)
        expected_ratio = self.water_total_g / self.dose_g
        if abs(self.ratio - expected_ratio) > 0.1:
            raise ValueError(
                f"ratio ({self.ratio}) must equal water_total_g/dose_g "
                f"({expected_ratio:.2f}) within 0.1"
            )

        # total_time_s >= last pour time_offset_s + 30
        last_pour_time = max(p.time_offset_s for p in self.pours)
        if self.total_time_s < last_pour_time + 30:
            raise ValueError(
                f"total_time_s ({self.total_time_s}) must be >= "
                f"last pour offset ({last_pour_time}) + 30"
            )


@dataclass
class BeanProfile:
    origin_country: str
    process: Process
    roast_level: RoastLevel
    flavor_clusters: list[str]
    source_text: str
    origin_region: Optional[str] = None
    flavor_notes: Optional[list[str]] = None
    variety: Optional[str] = None
    altitude_min_m: Optional[int] = None
    altitude_max_m: Optional[int] = None
    extraction_confidence: Optional[float] = None
    # Bag identity (optional): present when the bean comes from a saved bag.
    # Older brew records predate these fields and deserialize with both as None.
    roaster: Optional[str] = None
    name: Optional[str] = None

    def __post_init__(self):
        if not self.origin_country or not self.origin_country.strip():
            raise ValueError("origin_country is required (whitespace-only is not allowed)")
        if not self.source_text:
            raise ValueError("source_text is required")
        if not self.flavor_clusters:
            raise ValueError("flavor_clusters must have at least 1 element")
        for fc in self.flavor_clusters:
            if fc not in FLAVOR_CLUSTERS:
                raise ValueError(f"Unknown flavor cluster '{fc}'. Must be one of {FLAVOR_CLUSTERS}")
        if self.extraction_confidence is not None:
            if not (0.0 <= self.extraction_confidence <= 1.0):
                raise ValueError(f"extraction_confidence must be 0.0-1.0, got {self.extraction_confidence}")
        if self.altitude_min_m is not None and self.altitude_min_m < 0:
            raise ValueError(f"altitude_min_m must be >= 0, got {self.altitude_min_m}")
        if self.altitude_max_m is not None and self.altitude_max_m < 0:
            raise ValueError(f"altitude_max_m must be >= 0, got {self.altitude_max_m}")
        if (self.altitude_min_m is not None and self.altitude_max_m is not None
                and self.altitude_min_m > self.altitude_max_m):
            raise ValueError(
                f"altitude_min_m ({self.altitude_min_m}) > altitude_max_m ({self.altitude_max_m})"
            )


@dataclass
class CoffeeBag:
    """A saved bag of coffee the user owns.

    Entered once when a bag is opened, then picked for each brew until it runs
    out. Carries the full bean details via ``bean_profile`` plus the bag's own
    identity (roaster, product name) and tracking fields (size, open date,
    active flag). ``bag_size_g`` drives the "running low" countdown.
    """

    bag_id: str
    roaster: str
    name: str
    bean_profile: BeanProfile
    bag_size_g: float = 250.0
    date_opened: Optional[str] = None
    active: bool = True

    def __post_init__(self):
        if not self.bag_id:
            raise ValueError("bag_id is required")
        if not self.roaster or not self.roaster.strip():
            raise ValueError("roaster is required (whitespace-only is not allowed)")
        if not self.name or not self.name.strip():
            raise ValueError("name is required (whitespace-only is not allowed)")
        if self.bag_size_g <= 0:
            raise ValueError(f"bag_size_g must be > 0, got {self.bag_size_g}")


@dataclass
class Feedback:
    thumbs_up: bool
    score: Optional[int] = None
    directional_flags: Optional[list[str]] = None
    notes: Optional[str] = None

    def __post_init__(self):
        if self.score is not None and not (1 <= self.score <= 10):
            raise ValueError(f"score must be 1-10, got {self.score}")
        if self.directional_flags:
            for flag in self.directional_flags:
                if flag not in DIRECTIONAL_FLAGS:
                    raise ValueError(f"Unknown directional flag '{flag}'. Must be one of {DIRECTIONAL_FLAGS}")


@dataclass
class BrewRecord:
    brew_id: str
    timestamp: str
    bean_profile: BeanProfile
    recipe_used: Recipe
    feedback: Feedback
    # Bag link (optional): present when the brew came from a saved bag. The
    # dose actually weighed is mirrored from ``recipe_used.dose_g`` into
    # ``actual_dose_g`` so the running-low countdown can SUM it cheaply without
    # JSON extraction. Older records predate both fields and load with None.
    bag_id: Optional[str] = None
    actual_dose_g: Optional[float] = None

    def __post_init__(self):
        if not self.brew_id:
            raise ValueError("brew_id is required")
        if not self.timestamp:
            raise ValueError("timestamp is required")
        if self.actual_dose_g is not None and self.actual_dose_g <= 0:
            raise ValueError(f"actual_dose_g must be > 0, got {self.actual_dose_g}")


@dataclass
class LearnedPreferences:
    acidity_bias: float = 0.0
    body_bias: float = 0.0
    sweetness_bias: float = 0.0
    preferred_temp_range: tuple[float, float] = (90.0, 96.0)
    preferred_ratio_range: tuple[float, float] = (15.0, 17.0)

    def __post_init__(self):
        for name, val in [("acidity_bias", self.acidity_bias),
                          ("body_bias", self.body_bias),
                          ("sweetness_bias", self.sweetness_bias)]:
            if not (-1.0 <= val <= 1.0):
                raise ValueError(f"{name} must be -1.0 to 1.0, got {val}")
        for name, (lo, hi) in [("preferred_temp_range", self.preferred_temp_range),
                                ("preferred_ratio_range", self.preferred_ratio_range)]:
            if lo > hi:
                raise ValueError(f"{name} low ({lo}) must be <= high ({hi})")
        if not (80.0 <= self.preferred_temp_range[0] <= 100.0):
            raise ValueError(f"preferred_temp_range low must be 80.0-100.0, got {self.preferred_temp_range[0]}")
        if not (80.0 <= self.preferred_temp_range[1] <= 100.0):
            raise ValueError(f"preferred_temp_range high must be 80.0-100.0, got {self.preferred_temp_range[1]}")
        if not (12.0 <= self.preferred_ratio_range[0] <= 20.0):
            raise ValueError(f"preferred_ratio_range low must be 12.0-20.0, got {self.preferred_ratio_range[0]}")
        if not (12.0 <= self.preferred_ratio_range[1] <= 20.0):
            raise ValueError(f"preferred_ratio_range high must be 12.0-20.0, got {self.preferred_ratio_range[1]}")


@dataclass
class Onboarding:
    preferred_clusters: list[str]
    roast_preference: RoastLevel
    experience_level: ExperienceLevel
    grinder_id: Optional[str] = None

    def __post_init__(self):
        if not (1 <= len(self.preferred_clusters) <= 5):
            raise ValueError(f"Must select 1-5 preferred clusters, got {len(self.preferred_clusters)}")
        for c in self.preferred_clusters:
            if c not in FLAVOR_CLUSTERS:
                raise ValueError(f"Unknown cluster '{c}'. Must be one of {FLAVOR_CLUSTERS}")


@dataclass
class UserStats:
    total_brews: int = 0
    avg_score: float = 0.0
    favorite_origins: list[str] = field(default_factory=list)
    favorite_clusters: list[str] = field(default_factory=list)


@dataclass
class UserTasteProfile:
    user_id: str
    onboarding: Onboarding
    brew_history: list[BrewRecord] = field(default_factory=list)
    learned_preferences: Optional[LearnedPreferences] = None
    stats: UserStats = field(default_factory=UserStats)

    def __post_init__(self):
        if not self.user_id:
            raise ValueError("user_id is required")


def create_user_id() -> str:
    return str(uuid4())


def create_bag_id() -> str:
    return uuid4().hex[:12]

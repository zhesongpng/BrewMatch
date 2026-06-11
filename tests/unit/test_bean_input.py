"""Unit tests for the Your Coffees picker logic (src.app.pages.bean_input).

Covers the pure, Streamlit-free helpers: bag construction from form inputs,
the "brews left" estimate, and add-bag validation. The st.* rendering is
exercised manually / in B1.4 integration.
"""
from src.app.pages import bean_input as bi
from src.data_models import CoffeeBag


class TestBuildBag:
    def _build(self, **overrides) -> CoffeeBag:
        defaults = dict(
            roaster="Onyx Coffee Lab",
            coffee_name="Ethiopia Guji",
            bag_size_g=250.0,
            origin="Ethiopia",
            process_label="Washed",
            roast_label="Light",
            flavor_clusters=["Floral", "Citrus"],
        )
        defaults.update(overrides)
        return bi._build_bag(**defaults)

    def test_builds_valid_bag(self):
        bag = self._build(bag_size_g=340.0)
        assert isinstance(bag, CoffeeBag)
        assert bag.roaster == "Onyx Coffee Lab"
        assert bag.name == "Ethiopia Guji"
        assert bag.bag_size_g == 340.0
        assert bag.active is True
        assert bag.date_opened is not None
        assert len(bag.bag_id) == 12

    def test_bean_carries_roaster_and_name(self):
        # The bag's identity must flow onto the bean so history/diagnosis show
        # "Roaster — Coffee".
        bag = self._build()
        assert bag.bean_profile.roaster == "Onyx Coffee Lab"
        assert bag.bean_profile.name == "Ethiopia Guji"
        assert bag.bean_profile.origin_country == "Ethiopia"

    def test_strips_whitespace(self):
        bag = self._build(roaster="  Sey  ", coffee_name="  Kenya Karatu  ")
        assert bag.roaster == "Sey"
        assert bag.name == "Kenya Karatu"
        assert bag.bean_profile.roaster == "Sey"

    def test_optional_bean_fields_pass_through(self):
        bag = self._build(region="Guji", variety="Heirloom",
                          altitude_min_m=1800, altitude_max_m=2100)
        assert bag.bean_profile.origin_region == "Guji"
        assert bag.bean_profile.variety == "Heirloom"
        assert bag.bean_profile.altitude_min_m == 1800

    def test_unique_bag_ids(self):
        assert self._build().bag_id != self._build().bag_id


class TestBrewsLeft:
    def _bag(self, size: float) -> CoffeeBag:
        return bi._build_bag(
            roaster="R", coffee_name="C", bag_size_g=size, origin="Ethiopia",
            process_label="Washed", roast_label="Light", flavor_clusters=["Floral"],
        )

    def test_full_250g_bag(self):
        # 250 / 15 ≈ 16
        assert bi._brews_left(self._bag(250.0), 0.0) == 16

    def test_full_340g_bag(self):
        # 340 / 15 ≈ 22
        assert bi._brews_left(self._bag(340.0), 0.0) == 22

    def test_partially_used(self):
        # (250 - 200) / 15 ≈ 3
        assert bi._brews_left(self._bag(250.0), 200.0) == 3

    def test_never_negative(self):
        assert bi._brews_left(self._bag(250.0), 999.0) == 0


class TestValidateBagInput:
    def test_valid_passes(self):
        assert bi._validate_bag_input(
            "Onyx", "Guji", "Ethiopia", "Washed", "Light", ["Floral"]
        ) == []

    def test_missing_roaster(self):
        errs = bi._validate_bag_input("  ", "Guji", "Ethiopia", "Washed", "Light", ["Floral"])
        assert any("Roaster" in e for e in errs)

    def test_missing_coffee_name(self):
        errs = bi._validate_bag_input("Onyx", "", "Ethiopia", "Washed", "Light", ["Floral"])
        assert any("Coffee name" in e for e in errs)

    def test_missing_flavors(self):
        errs = bi._validate_bag_input("Onyx", "Guji", "Ethiopia", "Washed", "Light", [])
        assert any("flavor" in e.lower() for e in errs)

    def test_missing_origin(self):
        errs = bi._validate_bag_input("Onyx", "Guji", "", "Washed", "Light", ["Floral"])
        assert any("Origin" in e for e in errs)


class TestParseAltitude:
    def test_single_value(self):
        assert bi._parse_altitude("1800") == (1800, 1800)

    def test_range(self):
        assert bi._parse_altitude("1500-2000") == (1500, 2000)

    def test_empty(self):
        assert bi._parse_altitude("") == (None, None)

    def test_garbage(self):
        assert bi._parse_altitude("abc") == (None, None)

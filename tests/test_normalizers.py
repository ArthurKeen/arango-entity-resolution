"""Unit tests for entity_resolution.etl.normalizers."""

import pytest

from entity_resolution.etl.normalizers import (
    AddressNormalizer,
    PostalNormalizer,
    TokenNormalizer,
    STREET_SUFFIX_MAP,
    DIRECTIONAL_MAP,
    ORDINAL_MAP,
)


class TestTokenNormalizer:
    def test_empty_input(self):
        tn = TokenNormalizer()
        assert tn.normalize("") == ""
        assert tn.normalize(None) == ""
        assert tn.normalize("NULL") == ""

    def test_expansion(self):
        tn = TokenNormalizer(expansions={"ST": "STREET"})
        assert tn.normalize("123 Main ST") == "123 MAIN STREET"

    def test_strip_after(self):
        tn = TokenNormalizer(strip_after={"UNIT"})
        assert tn.normalize("123 Main UNIT 5") == "123 MAIN"

    def test_track_transforms(self):
        tn = TokenNormalizer(
            expansions={"ST": "STREET"},
            strip_after={"APT"},
        )
        result, transforms = tn.normalize("123 main st apt 2", track=True)
        assert result == "123 MAIN STREET"
        assert any("expand:ST->STREET" in t for t in transforms)
        assert any("unit_stripped" in t for t in transforms)

    def test_case_lower(self):
        tn = TokenNormalizer(expansions={"ST": "STREET"}, case="lower")
        assert tn.normalize("123 Main ST") == "123 main street"

    def test_punctuation_stripped(self):
        tn = TokenNormalizer()
        assert tn.normalize("O'Brien-Smith, Jr.") == "O BRIEN SMITH JR"


class TestAddressNormalizer:
    @pytest.fixture
    def norm(self):
        return AddressNormalizer()

    def test_street_suffix_expansion(self, norm):
        assert norm.normalize_street("123 Main St") == "123 MAIN STREET"
        assert norm.normalize_street("456 Oak Ave") == "456 OAK AVENUE"
        assert norm.normalize_street("789 Pine Blvd") == "789 PINE BOULEVARD"

    def test_directional_expansion(self, norm):
        assert norm.normalize_street("325 E Palmer Cir") == "325 EAST PALMER CIRCLE"

    def test_ordinal_expansion(self, norm):
        assert norm.normalize_street("100 1st Ave") == "100 FIRST AVENUE"

    def test_unit_stripping(self, norm):
        assert norm.normalize_street("100 Main St Ste 200") == "100 MAIN STREET"
        assert norm.normalize_street("200 Oak Ave Apt 3B") == "200 OAK AVENUE"

    def test_empty_and_null(self, norm):
        assert norm.normalize_street("") == ""
        assert norm.normalize_street("NULL") == ""
        assert norm.normalize_street(None) == ""

    def test_tracking(self, norm):
        result, transforms = norm.normalize_street("325 E Palmer Cir", track=True)
        assert result == "325 EAST PALMER CIRCLE"
        assert any("expand:E->EAST" in t for t in transforms)
        assert any("expand:CIR->CIRCLE" in t for t in transforms)

    def test_city(self, norm):
        assert norm.normalize_city("  new  york  ") == "NEW YORK"
        assert norm.normalize_city("NULL") == ""
        assert norm.normalize_city("") == ""

    def test_state(self, norm):
        assert norm.normalize_state("South Dakota") == "SD"
        assert norm.normalize_state("SD") == "SD"
        assert norm.normalize_state("CA") == "CA"
        assert norm.normalize_state("") == ""

    def test_postal(self, norm):
        assert norm.normalize_postal("57435-1234") == "57435"
        assert norm.normalize_postal("57435") == "57435"
        assert norm.normalize_postal("") == ""
        assert norm.normalize_postal("NULL") == ""

    def test_mixed_case_punctuation(self, norm):
        result = norm.normalize_street("123 N. Main St., Ste 100")
        assert result == "123 NORTH MAIN STREET"

    def test_po_box(self, norm):
        assert norm.normalize_street("PO BOX 67") == "PO BOX 67"

    def test_default_maps_are_canonical(self):
        assert AddressNormalizer.DEFAULT_SUFFIXES is STREET_SUFFIX_MAP
        assert AddressNormalizer.DEFAULT_DIRECTIONALS is DIRECTIONAL_MAP
        assert AddressNormalizer.DEFAULT_ORDINALS is ORDINAL_MAP


class TestPostalNormalizer:
    def test_normalize_5_digit(self):
        pn = PostalNormalizer()
        assert pn.normalize("57435") == "57435"
        assert pn.normalize("57435-1234") == "57435"

    def test_normalize_empty(self):
        pn = PostalNormalizer()
        assert pn.normalize("") == ""
        assert pn.normalize("NULL") == ""

    def test_shard_prefix(self):
        pn = PostalNormalizer()
        assert pn.shard_prefix("57435") == "574"
        assert pn.shard_prefix("57435-1234") == "574"

    def test_shard_prefix_fallback(self):
        pn = PostalNormalizer()
        assert pn.shard_prefix("") == "000"
        assert pn.shard_prefix("AB") == "000"

    def test_custom_digits(self):
        pn = PostalNormalizer(digits=4)
        assert pn.normalize("57435") == "5743"

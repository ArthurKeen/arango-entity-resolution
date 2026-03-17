"""
Address and text normalizers for ETL-time canonicalization.

Provides the single source of truth for street suffix, directional,
and ordinal expansion maps used throughout the entity resolution library.
"""

from __future__ import annotations

import re
from typing import Optional


STREET_SUFFIX_MAP: dict[str, str] = {
    "ST": "STREET",
    "STR": "STREET",
    "STREET": "STREET",
    "AVE": "AVENUE",
    "AV": "AVENUE",
    "AVENUE": "AVENUE",
    "RD": "ROAD",
    "ROAD": "ROAD",
    "DR": "DRIVE",
    "DRIVE": "DRIVE",
    "LN": "LANE",
    "LANE": "LANE",
    "BLVD": "BOULEVARD",
    "BOULEVARD": "BOULEVARD",
    "CT": "COURT",
    "CRT": "COURT",
    "COURT": "COURT",
    "PL": "PLACE",
    "PLACE": "PLACE",
    "HWY": "HIGHWAY",
    "HIGHWAY": "HIGHWAY",
    "PKWY": "PARKWAY",
    "PARKWAY": "PARKWAY",
    "CIR": "CIRCLE",
    "CIRCLE": "CIRCLE",
    "TRL": "TRAIL",
    "TRAIL": "TRAIL",
    "WAY": "WAY",
    "SQ": "SQUARE",
    "SQUARE": "SQUARE",
    "TER": "TERRACE",
    "TERR": "TERRACE",
    "TERRACE": "TERRACE",
}

DIRECTIONAL_MAP: dict[str, str] = {
    "N": "NORTH",
    "S": "SOUTH",
    "E": "EAST",
    "W": "WEST",
    "NE": "NORTHEAST",
    "NW": "NORTHWEST",
    "SE": "SOUTHEAST",
    "SW": "SOUTHWEST",
}

ORDINAL_MAP: dict[str, str] = {
    "1ST": "FIRST",
    "2ND": "SECOND",
    "3RD": "THIRD",
    "4TH": "FOURTH",
    "5TH": "FIFTH",
    "6TH": "SIXTH",
    "7TH": "SEVENTH",
    "8TH": "EIGHTH",
    "9TH": "NINTH",
    "10TH": "TENTH",
}

UNIT_DESIGNATORS: set[str] = {
    "STE", "SUITE", "APT", "APARTMENT", "UNIT", "RM", "ROOM", "#", "FL", "FLOOR",
}

_PUNCTUATION_RE = re.compile(r'[.,#\-\'"()]')
_WHITESPACE_RE = re.compile(r"\s+")
_NON_DIGIT_RE = re.compile(r"[^0-9]")


class TokenNormalizer:
    """Configurable token-level normalizer with optional transform tracking.

    Parameters
    ----------
    expansions : dict[str, str] | None
        Token-level expansion map (e.g. ``{"ST": "STREET"}``).
    strip_after : set[str] | None
        Tokens that trigger truncation of the remainder
        (e.g. unit designators).
    case : str
        ``"upper"`` or ``"lower"`` — target case for all tokens.
    """

    def __init__(
        self,
        expansions: Optional[dict[str, str]] = None,
        strip_after: Optional[set[str]] = None,
        case: str = "upper",
    ):
        self.expansions = expansions or {}
        self.strip_after = strip_after or set()
        self.case = case

    def normalize(
        self, raw: str, track: bool = False
    ) -> str | tuple[str, list[str]]:
        """Normalize *raw* using the configured token maps.

        When *track* is ``True``, returns ``(normalized, transforms)``
        where *transforms* is a list of human-readable strings describing
        each transformation applied.
        """
        if not raw or raw.upper() in ("NULL", "NONE", ""):
            return ("", []) if track else ""

        s = raw.upper().strip() if self.case == "upper" else raw.lower().strip()
        s = _PUNCTUATION_RE.sub(" ", s)
        s = _WHITESPACE_RE.sub(" ", s).strip()

        tokens = s.split()
        result: list[str] = []
        transforms: list[str] = []

        for tok in tokens:
            lookup = tok.upper()
            if lookup in self.strip_after:
                if track:
                    stripped = " ".join(tokens[tokens.index(tok):])
                    transforms.append(f"unit_stripped:{stripped}")
                break
            if lookup in self.expansions:
                expanded = self.expansions[lookup]
                if self.case == "lower":
                    expanded = expanded.lower()
                result.append(expanded)
                if track:
                    transforms.append(f"expand:{tok}->{expanded}")
            else:
                result.append(tok)

        normalized = " ".join(result)
        if track and raw.strip().upper() != normalized.upper():
            transforms.insert(0, "case_normalized")
        return (normalized, transforms) if track else normalized


class AddressNormalizer:
    """US-locale address normalizer (street + city + state + postal).

    Implements the normalizer protocol expected by ``CanonicalResolver``:
    a ``normalize(field, raw, track=False)`` method that dispatches to
    field-specific logic. The first signature field is tracked by default.

    The class-level ``DEFAULT_*`` maps are the **single source of truth**
    shared by ``WeightedFieldSimilarity`` and the ``CanonicalResolver``.
    """

    DEFAULT_SUFFIXES = STREET_SUFFIX_MAP
    DEFAULT_DIRECTIONALS = DIRECTIONAL_MAP
    DEFAULT_ORDINALS = ORDINAL_MAP
    DEFAULT_UNIT_DESIGNATORS = UNIT_DESIGNATORS

    STATE_LOOKUP: dict[str, str] = {
        "ALABAMA": "AL", "AL": "AL",
        "ALASKA": "AK", "AK": "AK",
        "ARIZONA": "AZ", "AZ": "AZ",
        "ARKANSAS": "AR", "AR": "AR",
        "CALIFORNIA": "CA", "CA": "CA",
        "COLORADO": "CO", "CO": "CO",
        "CONNECTICUT": "CT", "CT": "CT",
        "DELAWARE": "DE", "DE": "DE",
        "FLORIDA": "FL", "FL": "FL",
        "GEORGIA": "GA", "GA": "GA",
        "HAWAII": "HI", "HI": "HI",
        "IDAHO": "ID", "ID": "ID",
        "ILLINOIS": "IL", "IL": "IL",
        "INDIANA": "IN", "IN": "IN",
        "IOWA": "IA", "IA": "IA",
        "KANSAS": "KS", "KS": "KS",
        "KENTUCKY": "KY", "KY": "KY",
        "LOUISIANA": "LA", "LA": "LA",
        "MAINE": "ME", "ME": "ME",
        "MARYLAND": "MD", "MD": "MD",
        "MASSACHUSETTS": "MA", "MA": "MA",
        "MICHIGAN": "MI", "MI": "MI",
        "MINNESOTA": "MN", "MN": "MN",
        "MISSISSIPPI": "MS", "MS": "MS",
        "MISSOURI": "MO", "MO": "MO",
        "MONTANA": "MT", "MT": "MT",
        "NEBRASKA": "NE", "NE": "NE",
        "NEVADA": "NV", "NV": "NV",
        "NEW HAMPSHIRE": "NH", "NH": "NH",
        "NEW JERSEY": "NJ", "NJ": "NJ",
        "NEW MEXICO": "NM", "NM": "NM",
        "NEW YORK": "NY", "NY": "NY",
        "NORTH CAROLINA": "NC", "NC": "NC",
        "NORTH DAKOTA": "ND", "ND": "ND",
        "OHIO": "OH", "OH": "OH",
        "OKLAHOMA": "OK", "OK": "OK",
        "OREGON": "OR", "OR": "OR",
        "PENNSYLVANIA": "PA", "PA": "PA",
        "RHODE ISLAND": "RI", "RI": "RI",
        "SOUTH CAROLINA": "SC", "SC": "SC",
        "SOUTH DAKOTA": "SD", "SD": "SD",
        "TENNESSEE": "TN", "TN": "TN",
        "TEXAS": "TX", "TX": "TX",
        "UTAH": "UT", "UT": "UT",
        "VERMONT": "VT", "VT": "VT",
        "VIRGINIA": "VA", "VA": "VA",
        "WASHINGTON": "WA", "WA": "WA",
        "WEST VIRGINIA": "WV", "WV": "WV",
        "WISCONSIN": "WI", "WI": "WI",
        "WYOMING": "WY", "WY": "WY",
        "DISTRICT OF COLUMBIA": "DC", "DC": "DC",
    }

    def __init__(
        self,
        suffix_map: Optional[dict[str, str]] = None,
        directional_map: Optional[dict[str, str]] = None,
        ordinal_map: Optional[dict[str, str]] = None,
        unit_designators: Optional[set[str]] = None,
        locale: str = "en_US",
    ):
        self.suffix_map = suffix_map or self.DEFAULT_SUFFIXES
        self.directional_map = directional_map or self.DEFAULT_DIRECTIONALS
        self.ordinal_map = ordinal_map or self.DEFAULT_ORDINALS
        self.unit_designators = unit_designators or self.DEFAULT_UNIT_DESIGNATORS
        self.locale = locale

        combined = {}
        combined.update(self.ordinal_map)
        combined.update(self.directional_map)
        combined.update(self.suffix_map)
        self._street_normalizer = TokenNormalizer(
            expansions=combined,
            strip_after=self.unit_designators,
            case="upper",
        )

    def normalize(
        self, field: str, raw: str, track: bool = False
    ) -> str | tuple[str, list[str]]:
        """Normalize *raw* for the given *field* name.

        This is the protocol method called by ``CanonicalResolver``.
        Dispatches to ``normalize_street``, ``normalize_city``,
        ``normalize_state``, or ``normalize_postal`` based on *field*.
        Unknown fields are uppercased and whitespace-collapsed.
        """
        method = getattr(self, f"normalize_{field}", None)
        if method is not None:
            if field == "street":
                return method(raw, track=track)
            result = method(raw)
            return (result, []) if track else result
        # Unknown field: basic uppercasing
        val = _WHITESPACE_RE.sub(" ", raw.upper().strip()) if raw else ""
        return (val, []) if track else val

    def normalize_street(
        self, raw: str, track: bool = False
    ) -> str | tuple[str, list[str]]:
        """Normalize a street address string."""
        return self._street_normalizer.normalize(raw, track=track)

    def normalize_city(self, raw: str) -> str:
        """Normalize a city name (uppercase, collapsed whitespace)."""
        if not raw or raw.upper() in ("NULL", "NONE", ""):
            return ""
        return _WHITESPACE_RE.sub(" ", raw.upper().strip())

    def normalize_state(self, raw: str) -> str:
        """Normalize state to 2-letter abbreviation."""
        if not raw or raw.upper() in ("NULL", "NONE", ""):
            return ""
        cleaned = _PUNCTUATION_RE.sub("", raw).strip().upper()
        cleaned = _WHITESPACE_RE.sub(" ", cleaned)
        return self.STATE_LOOKUP.get(cleaned, cleaned)

    def normalize_postal(self, raw: str, digits: int = 5) -> str:
        """Extract first *digits* digits from a postal code string."""
        if not raw or raw.upper() in ("NULL", "NONE", ""):
            return ""
        d = _NON_DIGIT_RE.sub("", raw.split("-")[0].strip())
        return d[:digits] if len(d) >= digits else d


class PostalNormalizer:
    """Extract N-digit postal code prefix and derive shard keys."""

    def __init__(self, digits: int = 5):
        self.digits = digits

    def normalize(self, raw: str) -> str:
        """Extract the first *self.digits* digits from a raw postal string."""
        if not raw or raw.upper() in ("NULL", "NONE", ""):
            return ""
        d = _NON_DIGIT_RE.sub("", raw.split("-")[0].strip())
        return d[: self.digits] if len(d) >= self.digits else d

    def shard_prefix(self, raw: str, length: int = 3) -> str:
        """Derive a shard prefix (e.g. ZIP3) from a raw postal string.

        Falls back to ``"000"`` when insufficient digits are available.
        """
        postal = self.normalize(raw)
        if len(postal) >= length and postal[:length].isdigit():
            return postal[:length]
        d = _NON_DIGIT_RE.sub("", raw.split("-")[0].strip()) if raw else ""
        if len(d) >= length:
            return d[:length].zfill(length)
        return "0" * length

"""
Geospatial and temporal validation for entity resolution.

Validates candidate entity pairs by geographic distance (Haversine) and
temporal proximity. Designed to plug into the similarity pipeline as
optional pre- or post-filters.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class GeospatialValidator:
    """Validate candidate pairs by geographic distance.

    Uses the Haversine formula to compute great-circle distance between
    two lat/lon coordinate pairs.

    Parameters
    ----------
    max_distance_km:
        Maximum allowed distance in kilometers. Pairs exceeding this
        are flagged as invalid.
    lat_field:
        Field name for latitude in entity documents.
    lon_field:
        Field name for longitude in entity documents.
    """

    EARTH_RADIUS_KM = 6371.0

    def __init__(
        self,
        max_distance_km: float = 50.0,
        lat_field: str = "latitude",
        lon_field: str = "longitude",
    ) -> None:
        self.max_distance_km = max_distance_km
        self.lat_field = lat_field
        self.lon_field = lon_field

    def haversine(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Compute Haversine distance in kilometers."""
        lat1, lon1, lat2, lon2 = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * self.EARTH_RADIUS_KM * math.asin(math.sqrt(a))

    def validate_pair(
        self,
        record_a: Dict[str, Any],
        record_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate a single candidate pair by distance.

        Returns
        -------
        dict
            ``valid`` (bool), ``distance_km`` (float or None),
            ``reason`` (str).
        """
        lat_a = record_a.get(self.lat_field)
        lon_a = record_a.get(self.lon_field)
        lat_b = record_b.get(self.lat_field)
        lon_b = record_b.get(self.lon_field)

        if any(v is None for v in (lat_a, lon_a, lat_b, lon_b)):
            return {"valid": True, "distance_km": None, "reason": "missing coordinates; skipped"}

        try:
            dist = self.haversine(float(lat_a), float(lon_a), float(lat_b), float(lon_b))
        except (ValueError, TypeError) as exc:
            return {"valid": True, "distance_km": None, "reason": f"invalid coordinates: {exc}"}

        valid = dist <= self.max_distance_km
        return {
            "valid": valid,
            "distance_km": round(dist, 2),
            "reason": "within range" if valid else f"exceeds {self.max_distance_km}km threshold",
        }

    def filter_candidates(
        self,
        candidates: List[Dict[str, Any]],
        records: Dict[str, Dict[str, Any]],
        key_field_a: str = "doc1_key",
        key_field_b: str = "doc2_key",
    ) -> List[Dict[str, Any]]:
        """Filter a candidate list, keeping only geospatially valid pairs.

        Parameters
        ----------
        candidates:
            List of candidate pair dicts with key fields.
        records:
            Dict mapping document keys to full records (with lat/lon).
        key_field_a, key_field_b:
            Field names in candidates for document keys.

        Returns
        -------
        list[dict]
            Filtered candidates with ``geo_distance_km`` added.
        """
        kept = []
        for cand in candidates:
            rec_a = records.get(cand.get(key_field_a, ""), {})
            rec_b = records.get(cand.get(key_field_b, ""), {})
            result = self.validate_pair(rec_a, rec_b)
            if result["valid"]:
                cand_copy = cand.copy()
                cand_copy["geo_distance_km"] = result["distance_km"]
                kept.append(cand_copy)
        logger.info(
            "Geospatial filter: %d / %d candidates passed (max %.1fkm)",
            len(kept), len(candidates), self.max_distance_km,
        )
        return kept


class TemporalValidator:
    """Validate candidate pairs by temporal proximity.

    Checks whether two entities overlap in time (e.g. founding year,
    date ranges, active periods).

    Parameters
    ----------
    max_gap_days:
        Maximum allowed gap in days between the two time points.
    date_field:
        Field name for the date/year value.
    """

    def __init__(
        self,
        max_gap_days: int = 365,
        date_field: str = "founded_date",
    ) -> None:
        self.max_gap_days = max_gap_days
        self.date_field = date_field

    def validate_pair(
        self,
        record_a: Dict[str, Any],
        record_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate a single candidate pair by temporal proximity."""
        val_a = record_a.get(self.date_field)
        val_b = record_b.get(self.date_field)

        if val_a is None or val_b is None:
            return {"valid": True, "gap_days": None, "reason": "missing date; skipped"}

        date_a = self._to_date(val_a)
        date_b = self._to_date(val_b)

        if date_a is None or date_b is None:
            return {"valid": True, "gap_days": None, "reason": "unparseable date; skipped"}

        gap = abs((date_a - date_b).days)
        valid = gap <= self.max_gap_days
        return {
            "valid": valid,
            "gap_days": gap,
            "reason": "within range" if valid else f"exceeds {self.max_gap_days} day threshold",
        }

    def filter_candidates(
        self,
        candidates: List[Dict[str, Any]],
        records: Dict[str, Dict[str, Any]],
        key_field_a: str = "doc1_key",
        key_field_b: str = "doc2_key",
    ) -> List[Dict[str, Any]]:
        """Filter candidates by temporal proximity."""
        kept = []
        for cand in candidates:
            rec_a = records.get(cand.get(key_field_a, ""), {})
            rec_b = records.get(cand.get(key_field_b, ""), {})
            result = self.validate_pair(rec_a, rec_b)
            if result["valid"]:
                cand_copy = cand.copy()
                cand_copy["temporal_gap_days"] = result["gap_days"]
                kept.append(cand_copy)
        return kept

    @staticmethod
    def _to_date(value: Any) -> Optional[date]:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            return date(int(value), 1, 1)
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None

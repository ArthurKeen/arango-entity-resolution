"""Tests for GeospatialValidator and TemporalValidator."""

import pytest
from datetime import date, datetime

from entity_resolution.similarity.geospatial_validator import (
    GeospatialValidator,
    TemporalValidator,
)


class TestGeospatialValidator:
    def test_haversine_same_point(self):
        v = GeospatialValidator()
        assert v.haversine(40.7128, -74.0060, 40.7128, -74.0060) == pytest.approx(0.0, abs=0.01)

    def test_haversine_known_distance(self):
        v = GeospatialValidator()
        # NYC to LA is ~3944 km
        dist = v.haversine(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < dist < 4000

    def test_validate_pair_within_range(self):
        v = GeospatialValidator(max_distance_km=100)
        rec_a = {"latitude": 40.7128, "longitude": -74.0060}  # NYC
        rec_b = {"latitude": 40.7580, "longitude": -73.9855}  # Midtown (< 10km)
        result = v.validate_pair(rec_a, rec_b)
        assert result["valid"] is True
        assert result["distance_km"] < 10

    def test_validate_pair_exceeds_range(self):
        v = GeospatialValidator(max_distance_km=50)
        rec_a = {"latitude": 40.7128, "longitude": -74.0060}
        rec_b = {"latitude": 34.0522, "longitude": -118.2437}
        result = v.validate_pair(rec_a, rec_b)
        assert result["valid"] is False
        assert result["distance_km"] > 3000

    def test_validate_pair_missing_coords(self):
        v = GeospatialValidator()
        result = v.validate_pair({"latitude": 40.0}, {"longitude": -74.0})
        assert result["valid"] is True
        assert result["distance_km"] is None

    def test_filter_candidates(self):
        v = GeospatialValidator(max_distance_km=50)
        candidates = [
            {"doc1_key": "a", "doc2_key": "b"},
            {"doc1_key": "c", "doc2_key": "d"},
        ]
        records = {
            "a": {"latitude": 40.7128, "longitude": -74.0060},
            "b": {"latitude": 40.7580, "longitude": -73.9855},  # close
            "c": {"latitude": 40.7128, "longitude": -74.0060},
            "d": {"latitude": 34.0522, "longitude": -118.2437},  # far
        }
        result = v.filter_candidates(candidates, records)
        assert len(result) == 1
        assert result[0]["doc1_key"] == "a"

    def test_custom_field_names(self):
        v = GeospatialValidator(lat_field="lat", lon_field="lon")
        result = v.validate_pair(
            {"lat": 40.7128, "lon": -74.0060},
            {"lat": 40.7580, "lon": -73.9855},
        )
        assert result["valid"] is True
        assert result["distance_km"] is not None


class TestTemporalValidator:
    def test_validate_pair_within_range(self):
        v = TemporalValidator(max_gap_days=365, date_field="founded")
        result = v.validate_pair(
            {"founded": "2020-01-01"},
            {"founded": "2020-06-01"},
        )
        assert result["valid"] is True
        assert result["gap_days"] < 365

    def test_validate_pair_exceeds_range(self):
        v = TemporalValidator(max_gap_days=30, date_field="founded")
        result = v.validate_pair(
            {"founded": "2020-01-01"},
            {"founded": "2022-06-01"},
        )
        assert result["valid"] is False
        assert result["gap_days"] > 30

    def test_validate_pair_missing_date(self):
        v = TemporalValidator(date_field="founded")
        result = v.validate_pair({"founded": "2020-01-01"}, {})
        assert result["valid"] is True
        assert result["gap_days"] is None

    def test_validate_with_year_integer(self):
        v = TemporalValidator(max_gap_days=730, date_field="year")
        result = v.validate_pair({"year": 2020}, {"year": 2021})
        assert result["valid"] is True
        assert result["gap_days"] == 366 or result["gap_days"] == 365

    def test_validate_with_date_objects(self):
        v = TemporalValidator(max_gap_days=10, date_field="d")
        result = v.validate_pair(
            {"d": date(2023, 1, 1)},
            {"d": date(2023, 1, 5)},
        )
        assert result["valid"] is True
        assert result["gap_days"] == 4

    def test_filter_candidates(self):
        v = TemporalValidator(max_gap_days=30, date_field="founded")
        candidates = [
            {"doc1_key": "a", "doc2_key": "b"},
            {"doc1_key": "c", "doc2_key": "d"},
        ]
        records = {
            "a": {"founded": "2020-01-01"},
            "b": {"founded": "2020-01-15"},  # 14 days, valid
            "c": {"founded": "2020-01-01"},
            "d": {"founded": "2023-06-01"},  # years apart, invalid
        }
        result = v.filter_candidates(candidates, records)
        assert len(result) == 1
        assert result[0]["doc1_key"] == "a"

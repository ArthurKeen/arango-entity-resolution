"""Tests for AddressERPipeline."""

import pytest
from unittest.mock import MagicMock, patch

from entity_resolution.core.address_pipeline import AddressERPipeline


class TestAddressERPipeline:
    def test_requires_collection_and_field_mapping(self):
        db = MagicMock()
        with pytest.raises(ValueError, match="collection"):
            AddressERPipeline(db, {"field_mapping": {}})

        with pytest.raises(ValueError, match="field_mapping"):
            AddressERPipeline(db, {"collection": "test"})

    def test_init_creates_service(self):
        db = MagicMock()
        config = {
            "collection": "addresses",
            "field_mapping": {"street": "addr", "city": "city", "state": "state", "postal_code": "zip"},
        }
        pipeline = AddressERPipeline(db, config)
        assert pipeline.service is not None
        assert pipeline.config["collection"] == "addresses"

    @patch("entity_resolution.core.address_pipeline.AddressERService")
    def test_run_calls_service_methods(self, mock_service_cls):
        db = MagicMock()
        mock_service = MagicMock()
        mock_service.run.return_value = {
            "edges_created": 42,
            "total_pairs": 100,
            "clusters": [["a", "b"], ["c", "d"]],
        }
        mock_service_cls.return_value = mock_service

        config = {
            "collection": "addresses",
            "field_mapping": {"street": "addr"},
            "max_block_size": 50,
            "cluster": True,
        }
        pipeline = AddressERPipeline(db, config)
        results = pipeline.run()

        mock_service.setup_infrastructure.assert_called_once()
        mock_service.run.assert_called_once_with(
            max_block_size=50,
            create_edges=True,
            cluster=True,
        )
        assert results["edges_created"] == 42
        assert results["cluster_count"] == 2

    @patch("entity_resolution.core.address_pipeline.AddressERService")
    def test_progress_callback(self, mock_service_cls):
        db = MagicMock()
        mock_service = MagicMock()
        mock_service.run.return_value = {"edges_created": 0, "clusters": []}
        mock_service_cls.return_value = mock_service

        config = {"collection": "c", "field_mapping": {"street": "s"}}
        pipeline = AddressERPipeline(db, config)

        steps = []
        pipeline.run(progress_callback=lambda step, pct: steps.append((step, pct)))
        assert len(steps) >= 3
        assert steps[0][0] == "setup_infrastructure"
        assert steps[-1][0] == "complete"
        assert steps[-1][1] == 1.0

    def test_get_results_empty_before_run(self):
        db = MagicMock()
        config = {
            "collection": "c",
            "field_mapping": {"street": "s", "city": "c", "state": "st", "postal_code": "z"},
        }
        pipeline = AddressERPipeline(db, config)
        assert pipeline.get_results() == {}

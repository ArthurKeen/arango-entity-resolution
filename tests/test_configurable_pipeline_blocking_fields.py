import pytest

from entity_resolution.config.er_config import BlockingConfig, ClusteringConfig, ERPipelineConfig, SimilarityConfig
from entity_resolution.core.configurable_pipeline import ConfigurableERPipeline


def test_configurable_pipeline_uses_blocking_fields_from_config(monkeypatch):
    captured = {}

    class DummyCollectBlockingStrategy:
        def __init__(
            self,
            db,
            collection,
            blocking_fields,
            filters=None,
            max_block_size=100,
            min_block_size=2,
            computed_fields=None,
        ):
            captured["collection"] = collection
            captured["blocking_fields"] = blocking_fields
            captured["max_block_size"] = max_block_size
            captured["min_block_size"] = min_block_size
            captured["computed_fields"] = computed_fields

        def generate_candidates(self):
            return []

    monkeypatch.setattr(
        "entity_resolution.core.configurable_pipeline.CollectBlockingStrategy",
        DummyCollectBlockingStrategy,
    )

    cfg = ERPipelineConfig(
        entity_type="person",
        collection_name="Person",
        edge_collection="similarToPerson",
        cluster_collection="person_clusters",
        blocking=BlockingConfig(
            strategy="exact",
            min_block_size=2,
            max_block_size=50,
            fields=[{"name": "panNumber"}, {"name": "aadhaarMasked"}],
        ),
        similarity=SimilarityConfig(field_weights={"name": 1.0}),
        clustering=ClusteringConfig(store_results=False),
    )

    p = ConfigurableERPipeline(db=object(), config=cfg)
    pairs = p._run_blocking()
    assert pairs == []

    assert captured["collection"] == "Person"
    assert captured["blocking_fields"] == ["panNumber", "aadhaarMasked"]
    assert captured["min_block_size"] == 2
    assert captured["max_block_size"] == 50
    assert captured["computed_fields"] is None


def test_configurable_pipeline_supports_computed_fields_in_blocking_config(monkeypatch):
    captured = {}

    class DummyCollectBlockingStrategy:
        def __init__(
            self,
            db,
            collection,
            blocking_fields,
            filters=None,
            max_block_size=100,
            min_block_size=2,
            computed_fields=None,
        ):
            captured["blocking_fields"] = blocking_fields
            captured["computed_fields"] = computed_fields

        def generate_candidates(self):
            return []

    monkeypatch.setattr(
        "entity_resolution.core.configurable_pipeline.CollectBlockingStrategy",
        DummyCollectBlockingStrategy,
    )

    cfg = ERPipelineConfig(
        entity_type="person",
        collection_name="Person",
        edge_collection="similarToPerson",
        cluster_collection="person_clusters",
        blocking=BlockingConfig(
            strategy="exact",
            fields=[
                {"name": "zip5", "expression": "LEFT(d.pincode, 5)"},
                {"name": "zip5"},  # duplicate; should be de-duped
            ],
        ),
        similarity=SimilarityConfig(field_weights={"name": 1.0}),
        clustering=ClusteringConfig(store_results=False),
    )

    p = ConfigurableERPipeline(db=object(), config=cfg)
    p._run_blocking()

    assert captured["blocking_fields"] == ["zip5"]
    assert captured["computed_fields"] == {"zip5": "LEFT(d.pincode, 5)"}


def test_config_validation_requires_blocking_fields_for_exact():
    cfg = ERPipelineConfig(
        entity_type="person",
        collection_name="Person",
        edge_collection="similarToPerson",
        cluster_collection="person_clusters",
        blocking=BlockingConfig(strategy="exact", fields=[]),
        similarity=SimilarityConfig(field_weights={"name": 1.0}),
        clustering=ClusteringConfig(store_results=False),
    )
    errors = cfg.validate()
    assert any("blocking.fields" in e for e in errors)


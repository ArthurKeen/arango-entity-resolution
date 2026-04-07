"""Tests for AddressERPipeline and AddressERService improvements."""

import pytest
from unittest.mock import MagicMock, patch, call
import logging

from entity_resolution.core.address_pipeline import AddressERPipeline
from entity_resolution.services.address_er_service import AddressERService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_FIELD_MAPPING = {
    "street": "ADDR",
    "city": "CITY",
    "state": "STATE",
    "postal_code": "ZIP",
}


def _make_service(*, edge_loading_method="api", arangoimport_on_path=False, **extra_config):
    """Build an AddressERService with a mocked DB and controlled config."""
    db = MagicMock()
    config = {"edge_loading_method": edge_loading_method, **extra_config}
    with patch("shutil.which", return_value="/usr/bin/arangoimport" if arangoimport_on_path else None):
        svc = AddressERService(
            db=db,
            collection="addresses",
            field_mapping=MINIMAL_FIELD_MAPPING,
            config=config,
        )
    return svc


def _fake_cursor(blocks):
    """Return an iterable mimicking an AQL cursor from a list of block dicts."""
    return iter(blocks)


# ===================================================================
# 1. edge_loading_method='auto' selection logic
# ===================================================================

def test_auto_selects_csv_when_arangoimport_available_and_large_edge_count():
    svc = _make_service(
        edge_loading_method="auto",
        arangoimport_on_path=True,
        edge_count_threshold_for_csv=10,
    )

    # 3 addresses in a block => 3 edges, plus another block with 5 => 10 edges
    # We need > threshold, so use blocks that generate > 10 edges
    blocks = {
        "blk1": [f"addresses/{i}" for i in range(6)],  # 15 edges
    }
    empty_skip_stats = {
        "blocks_skipped_max_size": 0,
        "largest_skipped_block_size": 0,
        "skipped_block_samples": [],
    }

    with patch.object(svc, "_find_duplicate_addresses", return_value=(blocks, 6, empty_skip_stats)), \
         patch.object(svc, "_create_edges_via_csv", return_value=15) as mock_csv, \
         patch.object(svc, "_create_edges") as mock_api:

        results = svc.run(create_edges=True, cluster=False)

    mock_csv.assert_called_once()
    mock_api.assert_not_called()
    assert results["edges_created"] == 15


def test_auto_selects_api_when_arangoimport_not_available():
    svc = _make_service(
        edge_loading_method="auto",
        arangoimport_on_path=False,
        edge_count_threshold_for_csv=1,
    )

    blocks = {"blk1": [f"addresses/{i}" for i in range(10)]}  # 45 edges, above threshold
    empty_skip_stats = {
        "blocks_skipped_max_size": 0,
        "largest_skipped_block_size": 0,
        "skipped_block_samples": [],
    }

    with patch.object(svc, "_find_duplicate_addresses", return_value=(blocks, 10, empty_skip_stats)), \
         patch.object(svc, "_create_edges", return_value=45) as mock_api, \
         patch.object(svc, "_create_edges_via_csv") as mock_csv:

        results = svc.run(create_edges=True, cluster=False)

    mock_api.assert_called_once()
    mock_csv.assert_not_called()
    assert results["edges_created"] == 45


def test_auto_selects_api_when_edges_below_threshold():
    svc = _make_service(
        edge_loading_method="auto",
        arangoimport_on_path=True,
        edge_count_threshold_for_csv=1_000_000,
    )

    blocks = {"blk1": ["addresses/1", "addresses/2"]}  # 1 edge
    empty_skip_stats = {
        "blocks_skipped_max_size": 0,
        "largest_skipped_block_size": 0,
        "skipped_block_samples": [],
    }

    with patch.object(svc, "_find_duplicate_addresses", return_value=(blocks, 2, empty_skip_stats)), \
         patch.object(svc, "_create_edges", return_value=1) as mock_api, \
         patch.object(svc, "_create_edges_via_csv") as mock_csv:

        svc.run(create_edges=True, cluster=False)

    mock_api.assert_called_once()
    mock_csv.assert_not_called()


def test_explicit_api_with_large_edge_count_logs_warning(caplog):
    svc = _make_service(
        edge_loading_method="api",
        arangoimport_on_path=True,
        edge_count_threshold_for_csv=10,
    )

    blocks = {"blk1": [f"addresses/{i}" for i in range(6)]}  # 15 edges > threshold 10
    empty_skip_stats = {
        "blocks_skipped_max_size": 0,
        "largest_skipped_block_size": 0,
        "skipped_block_samples": [],
    }

    with patch.object(svc, "_find_duplicate_addresses", return_value=(blocks, 6, empty_skip_stats)), \
         patch.object(svc, "_create_edges", return_value=15):
        with caplog.at_level(logging.WARNING):
            svc.run(create_edges=True, cluster=False)

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("may be slow" in m for m in warning_messages), (
        f"Expected a performance warning but got: {warning_messages}"
    )


def test_arangoimport_availability_controlled_by_shutil_which():
    with patch("shutil.which", return_value="/usr/local/bin/arangoimport"):
        svc = AddressERService(
            db=MagicMock(),
            collection="c",
            field_mapping=MINIMAL_FIELD_MAPPING,
        )
        assert svc._arangoimport_available is True

    with patch("shutil.which", return_value=None):
        svc = AddressERService(
            db=MagicMock(),
            collection="c",
            field_mapping=MINIMAL_FIELD_MAPPING,
        )
        assert svc._arangoimport_available is False


# ===================================================================
# 2. blocks_skipped tracking
# ===================================================================

def test_partition_blocks_counts_skipped():
    svc = _make_service()
    cursor_data = [
        {"block_key": "k1", "addresses": ["a/1", "a/2"], "size": 2},
        {"block_key": "k2", "addresses": [f"a/{i}" for i in range(200)], "size": 200},
        {"block_key": "k3", "addresses": ["a/10", "a/11", "a/12"], "size": 3},
    ]

    blocks, total_addrs, skip_stats = svc._partition_blocks(_fake_cursor(cursor_data), max_block_size=10)

    assert "k1" in blocks
    assert "k3" in blocks
    assert "k2" not in blocks
    assert total_addrs == 5
    assert skip_stats["blocks_skipped_max_size"] == 1
    assert skip_stats["largest_skipped_block_size"] == 200


def test_partition_blocks_captures_largest_skipped():
    svc = _make_service()
    cursor_data = [
        {"block_key": "small", "addresses": ["a/1", "a/2"], "size": 2},
        {"block_key": "big", "addresses": [f"a/{i}" for i in range(500)], "size": 500},
        {"block_key": "bigger", "addresses": [f"a/{i}" for i in range(1000)], "size": 1000},
        {"block_key": "medium_skip", "addresses": [f"a/{i}" for i in range(150)], "size": 150},
    ]

    blocks, total, skip_stats = svc._partition_blocks(_fake_cursor(cursor_data), max_block_size=10)

    assert skip_stats["blocks_skipped_max_size"] == 3
    assert skip_stats["largest_skipped_block_size"] == 1000
    assert len(blocks) == 1
    assert total == 2


def test_partition_blocks_no_skipped():
    svc = _make_service()
    cursor_data = [
        {"block_key": "k1", "addresses": ["a/1", "a/2"], "size": 2},
        {"block_key": "k2", "addresses": ["a/3", "a/4", "a/5"], "size": 3},
    ]

    blocks, total, skip_stats = svc._partition_blocks(_fake_cursor(cursor_data), max_block_size=100)

    assert len(blocks) == 2
    assert total == 5
    assert skip_stats["blocks_skipped_max_size"] == 0
    assert skip_stats["largest_skipped_block_size"] == 0
    assert skip_stats["skipped_block_samples"] == []


def test_partition_blocks_all_skipped():
    svc = _make_service()
    cursor_data = [
        {"block_key": "k1", "addresses": [f"a/{i}" for i in range(50)], "size": 50},
        {"block_key": "k2", "addresses": [f"a/{i}" for i in range(100)], "size": 100},
    ]

    blocks, total, skip_stats = svc._partition_blocks(_fake_cursor(cursor_data), max_block_size=5)

    assert len(blocks) == 0
    assert total == 0
    assert skip_stats["blocks_skipped_max_size"] == 2
    assert skip_stats["largest_skipped_block_size"] == 100


def test_run_exposes_skip_stats_in_results():
    svc = _make_service()
    skip_stats = {
        "blocks_skipped_max_size": 3,
        "largest_skipped_block_size": 999,
        "skipped_block_samples": [{"block_key": "hub", "size": 999}],
    }

    with patch.object(
        svc, "_find_duplicate_addresses",
        return_value=({"k1": ["a/1", "a/2"]}, 2, skip_stats),
    ), patch.object(svc, "_create_edges", return_value=1):

        results = svc.run(create_edges=True, cluster=False)

    assert results["blocks_skipped_max_size"] == 3
    assert results["largest_skipped_block_size"] == 999
    assert results["skipped_block_samples"][0]["block_key"] == "hub"


# ===================================================================
# 3. shard-parallel blocking
# ===================================================================

def test_shard_parallel_mode_dispatches_to_shard_method():
    svc = _make_service(blocking_mode="shard_parallel")

    with patch.object(svc, "_find_duplicate_addresses_shard_parallel") as mock_sp, \
         patch.object(svc, "_find_duplicate_addresses_single_query") as mock_sq:
        mock_sp.return_value = ({}, 0, {"blocks_skipped_max_size": 0, "largest_skipped_block_size": 0, "skipped_block_samples": []})
        svc._find_duplicate_addresses(max_block_size=100)

    mock_sp.assert_called_once_with(100)
    mock_sq.assert_not_called()


def test_single_query_mode_dispatches_to_single_method():
    svc = _make_service(blocking_mode="single_query")

    with patch.object(svc, "_find_duplicate_addresses_shard_parallel") as mock_sp, \
         patch.object(svc, "_find_duplicate_addresses_single_query") as mock_sq:
        mock_sq.return_value = ({}, 0, {"blocks_skipped_max_size": 0, "largest_skipped_block_size": 0, "skipped_block_samples": []})
        svc._find_duplicate_addresses(max_block_size=50)

    mock_sq.assert_called_once_with(50)
    mock_sp.assert_not_called()


def test_shard_parallel_produces_same_structure_as_single_query():
    """Both methods should return (blocks_dict, total_addresses, skip_stats_dict)."""
    db = MagicMock()

    block_data = [
        {"block_key": "k1", "addresses": ["a/1", "a/2"], "size": 2},
        {"block_key": "k2", "addresses": ["a/3", "a/4", "a/5"], "size": 3},
    ]

    with patch("shutil.which", return_value=None):
        svc_sq = AddressERService(
            db=db,
            collection="addresses",
            field_mapping=MINIMAL_FIELD_MAPPING,
            config={"blocking_mode": "single_query"},
        )
        svc_sp = AddressERService(
            db=db,
            collection="addresses",
            field_mapping=MINIMAL_FIELD_MAPPING,
            config={"blocking_mode": "shard_parallel"},
        )

    db.aql.execute.return_value = iter(block_data)
    sq_blocks, sq_total, sq_skip = svc_sq._find_duplicate_addresses_single_query(max_block_size=100)

    db.aql.execute.side_effect = [
        iter(["123", "456"]),  # prefix query
        iter(block_data[:1]),  # shard prefix "123"
        iter(block_data[1:]),  # shard prefix "456"
    ]
    sp_blocks, sp_total, sp_skip = svc_sp._find_duplicate_addresses_shard_parallel(max_block_size=100)

    assert set(sq_blocks.keys()) == set(sp_blocks.keys())
    assert sq_total == sp_total
    for key in ("blocks_skipped_max_size", "largest_skipped_block_size"):
        assert key in sq_skip
        assert key in sp_skip


def test_shard_parallel_aggregates_skipped_across_prefixes():
    db = MagicMock()

    with patch("shutil.which", return_value=None):
        svc = AddressERService(
            db=db,
            collection="addresses",
            field_mapping=MINIMAL_FIELD_MAPPING,
            config={"blocking_mode": "shard_parallel", "shard_key_prefix_length": 3},
        )

    prefix_results = iter(["100", "200"])
    shard_100_results = iter([
        {"block_key": "k_ok", "addresses": ["a/1", "a/2"], "size": 2},
        {"block_key": "k_skip_100", "addresses": [f"a/{i}" for i in range(50)], "size": 50},
    ])
    shard_200_results = iter([
        {"block_key": "k_skip_200", "addresses": [f"a/{i}" for i in range(300)], "size": 300},
    ])

    db.aql.execute.side_effect = [prefix_results, shard_100_results, shard_200_results]

    blocks, total, skip_stats = svc._find_duplicate_addresses_shard_parallel(max_block_size=10)

    assert "k_ok" in blocks
    assert "k_skip_100" not in blocks
    assert "k_skip_200" not in blocks
    assert skip_stats["blocks_skipped_max_size"] == 2
    assert skip_stats["largest_skipped_block_size"] == 300


# ===================================================================
# 4. AddressERPipeline config passthrough
# ===================================================================

def test_pipeline_passes_blocking_mode_to_service():
    db = MagicMock()
    config = {
        "collection": "addresses",
        "field_mapping": MINIMAL_FIELD_MAPPING,
        "blocking_mode": "shard_parallel",
    }
    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline(db, config)

    assert pipeline.service.blocking_mode == "shard_parallel"


def test_pipeline_passes_edge_loading_method_to_service():
    db = MagicMock()
    config = {
        "collection": "addresses",
        "field_mapping": MINIMAL_FIELD_MAPPING,
        "edge_loading_method": "csv",
    }
    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline(db, config)

    assert pipeline.service.edge_loading_method == "csv"


def test_pipeline_passes_all_service_config_keys():
    db = MagicMock()
    config = {
        "collection": "addresses",
        "field_mapping": MINIMAL_FIELD_MAPPING,
        "blocking_mode": "shard_parallel",
        "edge_loading_method": "auto",
        "edge_count_threshold_for_csv": 50_000,
        "max_block_size": 200,
        "min_bm25_score": 3.5,
        "batch_size": 2000,
        "shard_key_field": "ZIP",
        "shard_key_prefix_length": 5,
    }

    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline(db, config)

    svc = pipeline.service
    assert svc.blocking_mode == "shard_parallel"
    assert svc.edge_loading_method == "auto"
    assert svc.edge_count_threshold_for_csv == 50_000
    assert svc.max_block_size == 200
    assert svc.min_bm25_score == 3.5
    assert svc.batch_size == 2000
    assert svc.shard_key_field == "ZIP"
    assert svc.shard_key_prefix_length == 5


def test_pipeline_uses_defaults_for_missing_service_config():
    db = MagicMock()
    config = {
        "collection": "addresses",
        "field_mapping": MINIMAL_FIELD_MAPPING,
    }

    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline(db, config)

    svc = pipeline.service
    assert svc.blocking_mode == "single_query"
    assert svc.edge_loading_method == "auto"
    assert svc.edge_count_threshold_for_csv == 100_000
    assert svc.max_block_size == 100


def test_pipeline_from_yaml(tmp_path):
    yaml_content = """
address_resolution:
    collection: my_addresses
    field_mapping:
        street: STREET
        city: CITY
        state: STATE
        postal_code: ZIP
    blocking_mode: shard_parallel
    edge_loading_method: csv
"""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content)

    db = MagicMock()
    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline.from_yaml(db, str(yaml_file))

    assert pipeline.config["collection"] == "my_addresses"
    assert pipeline.service.blocking_mode == "shard_parallel"
    assert pipeline.service.edge_loading_method == "csv"


def test_pipeline_from_yaml_flat_config(tmp_path):
    """YAML without an address_resolution wrapper should work too."""
    yaml_content = """
collection: flat_coll
field_mapping:
    street: s
    city: c
    state: st
    postal_code: z
"""
    yaml_file = tmp_path / "flat.yaml"
    yaml_file.write_text(yaml_content)

    db = MagicMock()
    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline.from_yaml(db, str(yaml_file))

    assert pipeline.config["collection"] == "flat_coll"


def test_pipeline_missing_collection_raises():
    db = MagicMock()
    with pytest.raises(ValueError, match="collection"):
        AddressERPipeline(db, {"field_mapping": MINIMAL_FIELD_MAPPING})


def test_pipeline_missing_field_mapping_raises():
    db = MagicMock()
    with pytest.raises(ValueError, match="field_mapping"):
        AddressERPipeline(db, {"collection": "test"})


def test_pipeline_get_results_empty_before_run():
    db = MagicMock()
    config = {"collection": "c", "field_mapping": MINIMAL_FIELD_MAPPING}
    with patch("shutil.which", return_value=None):
        pipeline = AddressERPipeline(db, config)
    assert pipeline.get_results() == {}


@patch("entity_resolution.core.address_pipeline.AddressERService")
def test_pipeline_run_calls_service_methods(mock_service_cls):
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
        "field_mapping": MINIMAL_FIELD_MAPPING,
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
def test_pipeline_progress_callback(mock_service_cls):
    db = MagicMock()
    mock_service = MagicMock()
    mock_service.run.return_value = {"edges_created": 0, "clusters": []}
    mock_service_cls.return_value = mock_service

    config = {"collection": "c", "field_mapping": MINIMAL_FIELD_MAPPING}
    pipeline = AddressERPipeline(db, config)

    steps = []
    pipeline.run(progress_callback=lambda step, pct: steps.append((step, pct)))
    assert len(steps) >= 3
    assert steps[0][0] == "setup_infrastructure"
    assert steps[-1][0] == "complete"
    assert steps[-1][1] == 1.0

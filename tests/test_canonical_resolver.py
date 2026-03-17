"""Unit tests for entity_resolution.etl.canonical_resolver."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from entity_resolution.etl.canonical_resolver import CanonicalResolver
from entity_resolution.etl.normalizers import AddressNormalizer


@pytest.fixture
def resolver():
    return CanonicalResolver(
        normalizer=AddressNormalizer(),
        signature_fields=["street", "city", "state", "postal"],
        field_mapping={
            "street": "ADDRESS_LINE_1",
            "city": "PRIMARY_TOWN",
            "state": "TERRITORY_CODE",
            "postal": "POSTAL_CODE",
        },
        shard_key_output_name="ZIP3",
        hub_threshold=3,
        hub_markers={"ROLE_TYPE": "Agent"},
        provenance=True,
        type_fields=["ADDR_TYPE"],
        node_label="ADDRESS",
    )


SAMPLE_RECORDS = [
    {
        "ADDRESS_LINE_1": "123 Main St",
        "PRIMARY_TOWN": "Springfield",
        "TERRITORY_CODE": "IL",
        "POSTAL_CODE": "62701",
        "ROLE_TYPE": "",
    },
    {
        "ADDRESS_LINE_1": "123 Main Street",
        "PRIMARY_TOWN": "SPRINGFIELD",
        "TERRITORY_CODE": "IL",
        "POSTAL_CODE": "62701-1234",
        "ROLE_TYPE": "",
    },
    {
        "ADDRESS_LINE_1": "456 Oak Ave",
        "PRIMARY_TOWN": "Chicago",
        "TERRITORY_CODE": "IL",
        "POSTAL_CODE": "60601",
        "ROLE_TYPE": "Agent",
    },
]


class TestCanonicalResolverAdd:
    def test_dedup_same_signature(self, resolver):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        resolver.add(SAMPLE_RECORDS[1], source_key="627:key2")
        assert resolver.stats["unique_signatures"] == 1
        assert resolver.stats["input_rows"] == 2

    def test_different_addresses(self, resolver):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        resolver.add(SAMPLE_RECORDS[2], source_key="606:key2")
        assert resolver.stats["unique_signatures"] == 2

    def test_skips_empty(self, resolver):
        resolver.add({"ADDRESS_LINE_1": "", "PRIMARY_TOWN": "", "TERRITORY_CODE": "", "POSTAL_CODE": ""})
        assert resolver.stats["skipped"] == 1

    def test_hub_by_marker(self, resolver):
        resolver.add(SAMPLE_RECORDS[2], source_key="606:key1")
        resolver._classify_hubs()
        sig_data = list(resolver._sig_data.values())
        assert sig_data[0]["is_hub"] is True

    def test_hub_by_degree(self, resolver):
        for i in range(5):
            resolver.add(SAMPLE_RECORDS[0], source_key=f"627:key{i}")
        resolver._classify_hubs()
        sig_data = list(resolver._sig_data.values())
        assert sig_data[0]["is_hub"] is True

    def test_edges_created(self, resolver):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        resolver.add(SAMPLE_RECORDS[1], source_key="627:key2")
        assert resolver.stats["total_edges"] == 2


class TestCanonicalResolverProvenance:
    def test_node_provenance(self, resolver):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        resolver.add(SAMPLE_RECORDS[1], source_key="627:key2")
        sig = list(resolver._sig_data.keys())[0]
        prov = resolver._provenance.get_node_provenance(sig)
        assert prov["DISTINCT_RAW_VARIANTS"] >= 1
        assert prov["TOTAL_RAW_ROWS"] == 2
        assert isinstance(prov["RAW_VARIANTS"], list)

    def test_edge_provenance(self, resolver):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        sig = list(resolver._sig_edges.keys())[0]
        edge = resolver._sig_edges[sig][0]
        assert "raw_fields" in edge
        assert "RAW_STREET" in edge["raw_fields"]


class TestCanonicalResolverOutput:
    def test_write_nodes_jsonl(self, resolver, tmp_path):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        resolver.add(SAMPLE_RECORDS[1], source_key="627:key2")
        resolver.add(SAMPLE_RECORDS[2], source_key="606:key3")

        out = tmp_path / "nodes.jsonl"
        count = resolver.write_nodes(str(out))
        assert count == 2

        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        doc = json.loads(lines[0])
        assert "_key" in doc
        assert "ADDRESS_SIGNATURE" in doc
        assert "NORM_STREET" in doc
        assert "RAW_VARIANTS" in doc

    def test_write_edges_consolidated(self, resolver, tmp_path):
        """Two records from different source keys to the same address => 2 edges."""
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        resolver.add(SAMPLE_RECORDS[1], source_key="627:key2")

        out = tmp_path / "edges.jsonl"
        count = resolver.write_edges(str(out), "regs", "canonical_addresses")
        assert count == 2

        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        doc = json.loads(lines[0])
        assert doc["_from"].startswith("regs/")
        assert doc["_to"].startswith("canonical_addresses/")
        assert "CANONICAL_SIGNATURE" in doc
        assert "RECORDS" in doc
        assert doc["RECORD_COUNT"] == 1

    def test_write_edges_consolidates_same_pair(self, resolver, tmp_path):
        """Multiple address types from same source to same addr => 1 edge, N subdocs."""
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "mailing"})
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "registered"})

        out = tmp_path / "edges.jsonl"
        count = resolver.write_edges(str(out), "regs", "canonical_addresses")
        assert count == 1

        doc = json.loads(out.read_text().strip())
        assert doc["RECORD_COUNT"] == 2
        assert len(doc["RECORDS"]) == 2
        assert set(doc["RECORD_TYPES"]) == {"mailing", "registered"}

    def test_write_edges_flat_mode(self, resolver, tmp_path):
        """consolidate=False preserves legacy one-edge-per-record."""
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "mailing"})
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "registered"})

        out = tmp_path / "edges.jsonl"
        count = resolver.write_edges(str(out), "regs", "canonical_addresses", consolidate=False)
        assert count == 2

    def test_edge_deduplication_flat(self, resolver, tmp_path):
        """Flat mode deduplicates identical edges."""
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "mailing"})
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "mailing"})

        out = tmp_path / "edges.jsonl"
        count = resolver.write_edges(str(out), "regs", "canonical_addresses", consolidate=False)
        assert count == 1

    def test_write_nodes_tsv(self, resolver, tmp_path):
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1")
        out = tmp_path / "nodes.tsv"
        count = resolver.write_nodes(str(out), format="tsv")
        assert count == 1
        content = out.read_text()
        assert "_key" in content
        assert "ADDRESS_SIGNATURE" in content


class TestCanonicalResolverProcessFile:
    def test_process_file_with_header(self, resolver, tmp_path):
        header_file = tmp_path / "header.tsv"
        header_file.write_text("ADDRESS_LINE_1\tPRIMARY_TOWN\tTERRITORY_CODE\tPOSTAL_CODE\tROLE_TYPE\n")

        data_file = tmp_path / "data.tsv"
        lines = [
            "123 Main St\tSpringfield\tIL\t62701\t\n",
            "123 Main Street\tSPRINGFIELD\tIL\t62701-1234\t\n",
            "456 Oak Ave\tChicago\tIL\t60601\tAgent\n",
        ]
        data_file.write_text("".join(lines))

        stats = resolver.process_file(
            str(data_file),
            delimiter="\t",
            header_path=str(header_file),
        )

        assert stats["input_rows"] == 3
        assert stats["unique_signatures"] == 2

    def test_process_file_inline_header(self, tmp_path):
        resolver = CanonicalResolver(
            normalizer=AddressNormalizer(),
            field_mapping={
                "street": "street",
                "city": "city",
                "state": "state",
                "postal": "postal",
            },
        )
        data_file = tmp_path / "data.tsv"
        data_file.write_text(
            "street\tcity\tstate\tpostal\n"
            "100 Main St\tSpringfield\tIL\t62701\n"
            "100 Main Street\tSpringfield\tIL\t62701\n"
        )
        stats = resolver.process_file(str(data_file), delimiter="\t")
        assert stats["unique_signatures"] == 1


class TestCanonicalResolverStats:
    def test_reduction_pct(self, resolver):
        for i, rec in enumerate(SAMPLE_RECORDS):
            resolver.add(rec, source_key=f"627:key{i}")
        stats = resolver.stats
        assert stats["reduction_pct"] > 0
        assert stats["input_rows"] == 3
        assert stats["unique_signatures"] == 2


class TestCanonicalResolverGeneric:
    """Verify that the resolver works with non-address, custom normalizers."""

    def test_custom_normalizer_protocol(self, tmp_path):
        """A plain normalizer that just uppercases fields."""

        class UpperNormalizer:
            def normalize(self, field, raw, track=False):
                val = raw.upper().strip() if raw else ""
                transforms = [f"uppercased:{field}"] if track and raw != val else []
                return (val, transforms) if track else val

        resolver = CanonicalResolver(
            normalizer=UpperNormalizer(),
            signature_fields=["name", "country"],
            field_mapping={"name": "COMPANY_NAME", "country": "COUNTRY_CODE"},
            required_fields=["name"],
            shard_key_field="country",
            shard_key_length=2,
            shard_key_extractor=lambda raw, length: (raw.upper().strip()[:length] or "XX"),
            hub_threshold=5,
            provenance=True,
            track_fields=["name"],
            type_fields=["RECORD_TYPE"],
            node_label="COMPANY",
        )

        resolver.add(
            {"COMPANY_NAME": "Acme Corp", "COUNTRY_CODE": "US", "RECORD_TYPE": "HQ"},
            source_key="US:key1",
            edge_fields={"RECORD_TYPE": "HQ"},
        )
        resolver.add(
            {"COMPANY_NAME": "ACME CORP", "COUNTRY_CODE": "us", "RECORD_TYPE": "Branch"},
            source_key="US:key2",
            edge_fields={"RECORD_TYPE": "Branch"},
        )
        resolver.add(
            {"COMPANY_NAME": "Globex Inc", "COUNTRY_CODE": "UK"},
            source_key="UK:key3",
        )

        stats = resolver.stats
        assert stats["unique_signatures"] == 2
        assert stats["input_rows"] == 3

        # Write nodes — verify custom label
        out_nodes = tmp_path / "nodes.jsonl"
        resolver.write_nodes(str(out_nodes))
        nodes = [json.loads(l) for l in out_nodes.read_text().strip().split("\n")]
        assert len(nodes) == 2
        for n in nodes:
            assert "COMPANY_SIGNATURE" in n
            assert "IS_COMPANY_HUB" in n
            assert "NORM_NAME" in n
            assert "NORM_COUNTRY" in n
            assert "SHARD_COUNTRY" in n

        # Write consolidated edges — verify type extraction
        out_edges = tmp_path / "edges.jsonl"
        resolver.write_edges(str(out_edges), "companies", "canonical_companies")
        edges = [json.loads(l) for l in out_edges.read_text().strip().split("\n")]

        acme_edges = [e for e in edges if "ACME CORP" in e.get("CANONICAL_SIGNATURE", "")]
        assert len(acme_edges) == 2
        for e in acme_edges:
            assert "RECORDS" in e

        typed = [e for e in acme_edges if "RECORD_TYPES" in e]
        assert len(typed) >= 1
        all_types = set()
        for e in typed:
            all_types.update(e["RECORD_TYPES"])
        assert "HQ" in all_types

    def test_no_type_fields_omits_record_types(self, tmp_path):
        """When type_fields is empty, RECORD_TYPES is not emitted."""
        resolver = CanonicalResolver(
            normalizer=AddressNormalizer(),
            signature_fields=["street", "city", "state", "postal"],
            field_mapping={
                "street": "ADDRESS_LINE_1",
                "city": "PRIMARY_TOWN",
                "state": "TERRITORY_CODE",
                "postal": "POSTAL_CODE",
            },
            type_fields=[],
        )
        resolver.add(SAMPLE_RECORDS[0], source_key="627:key1", edge_fields={"ADDR_TYPE": "mailing"})

        out = tmp_path / "edges.jsonl"
        resolver.write_edges(str(out), "regs", "addrs")
        doc = json.loads(out.read_text().strip())
        assert "RECORD_TYPES" not in doc

    def test_required_fields_custom(self):
        """Custom required_fields controls skip logic."""
        resolver = CanonicalResolver(
            normalizer=AddressNormalizer(),
            signature_fields=["street", "city", "state", "postal"],
            field_mapping={
                "street": "ADDRESS_LINE_1",
                "city": "PRIMARY_TOWN",
                "state": "TERRITORY_CODE",
                "postal": "POSTAL_CODE",
            },
            required_fields=["postal"],
        )
        # Empty postal => skipped even though street is present
        resolver.add({"ADDRESS_LINE_1": "123 Main St", "PRIMARY_TOWN": "X",
                       "TERRITORY_CODE": "IL", "POSTAL_CODE": ""})
        assert resolver.stats["skipped"] == 1

        # Present postal => kept even if street empty
        resolver.add({"ADDRESS_LINE_1": "", "PRIMARY_TOWN": "",
                       "TERRITORY_CODE": "IL", "POSTAL_CODE": "62701"})
        assert resolver.stats["skipped"] == 1
        assert resolver.stats["unique_signatures"] == 1

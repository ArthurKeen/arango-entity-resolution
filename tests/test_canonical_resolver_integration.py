"""
Integration test for the CanonicalResolver ETL pipeline.

Processes a small sample TSV file end-to-end, writes JSONL output,
and validates the output structure and deduplication logic.

Marked with ``pytest.mark.integration`` — skip in fast unit-test runs
via ``pytest -m "not integration"``.
"""

import json
from pathlib import Path

import pytest

from entity_resolution.etl import CanonicalResolver, AddressNormalizer


SAMPLE_HEADER = (
    "REGISTRATION_HASH_KEY\tADDRESS_LINE_1\tPRIMARY_TOWN\t"
    "TERRITORY_CODE\tPOSTAL_CODE\tDNB_ADDR_TYPE\t"
    "ROLE_PLAYER_TYPE_DNB_CD_TXT\tROLE_PLAYER_NME\n"
)

SAMPLE_DATA = """\
REG001\t123 Main St\tSpringfield\tIL\t62701\tMailing\t\tJohn Doe
REG002\t123 Main Street\tSPRINGFIELD\tIL\t62701-1234\tRegistered\t\tJane Doe
REG003\t456 Oak Ave\tChicago\tIL\t60601\tMailing\tAgent\tCT Corp
REG004\t456 Oak Avenue\tChicago\tIL\t60601\tRegistered\tAgent\tCT Corp
REG005\t789 Pine Blvd\tChicago\tIL\t60602\tMailing\t\tBob Smith
REG006\t325 E Palmer Cir\tAberdeen\tSD\t57401\tMailing\t\tAlice Test
REG007\t325 E Palmer Cir\tAberdeen\tSD\t57401\tRegistered\t\tAlice Test
REG008\tPO BOX 67\tCresbard\tSD\t57435\tMailing\t\tBill Test
"""


@pytest.fixture
def sample_files(tmp_path):
    header = tmp_path / "header.tsv"
    header.write_text(SAMPLE_HEADER)

    data = tmp_path / "data.tsv"
    data.write_text(SAMPLE_DATA)

    source_lookup = {
        "REG001": ("627", "627:reg001key"),
        "REG002": ("627", "627:reg002key"),
        "REG003": ("606", "606:reg003key"),
        "REG004": ("606", "606:reg004key"),
        "REG005": ("606", "606:reg005key"),
        "REG006": ("574", "574:reg006key"),
        "REG007": ("574", "574:reg007key"),
        "REG008": ("574", "574:reg008key"),
    }

    return header, data, source_lookup, tmp_path


@pytest.mark.integration
class TestCanonicalResolverIntegration:
    def test_end_to_end(self, sample_files):
        header, data, source_lookup, out_dir = sample_files

        resolver = CanonicalResolver(
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
            hub_markers={"ROLE_PLAYER_TYPE_DNB_CD_TXT": "Agent"},
            provenance=True,
            type_fields=["DNB_ADDR_TYPE"],
            node_label="ADDRESS",
        )

        stats = resolver.process_file(
            str(data),
            delimiter="\t",
            header_path=str(header),
            key_field="REGISTRATION_HASH_KEY",
            source_lookup=source_lookup,
            edge_extra_fields=["DNB_ADDR_TYPE", "ROLE_PLAYER_TYPE_DNB_CD_TXT"],
        )

        assert stats["input_rows"] == 8
        assert stats["unique_signatures"] == 5

        # REG001+REG002 collapse; REG003+REG004 collapse;
        # REG006+REG007 collapse; REG005 unique; REG008 unique => 5

        nodes_path = out_dir / "canonical_addresses.jsonl"
        edges_path = out_dir / "hasAddress.jsonl"

        nodes_written = resolver.write_nodes(str(nodes_path))
        edges_written = resolver.write_edges(str(edges_path), "regs", "canonical_addresses")

        assert nodes_written == 5
        # Consolidated: 8 raw records across 8 unique (source, addr) pairs = 8 edges
        # REG006+REG007 go to the same addr but from *different* regs => 2 edges
        assert edges_written == 8

        nodes = [json.loads(line) for line in nodes_path.read_text().strip().split("\n")]
        edges = [json.loads(line) for line in edges_path.read_text().strip().split("\n")]

        assert len(nodes) == 5
        assert len(edges) == 8

        for node in nodes:
            assert "_key" in node
            assert ":" in node["_key"]
            assert "ADDRESS_SIGNATURE" in node
            assert "NORM_STREET" in node
            assert "RAW_VARIANTS" in node
            assert "IS_ADDRESS_HUB" in node

        hub_nodes = [n for n in nodes if n["IS_ADDRESS_HUB"]]
        assert len(hub_nodes) >= 1

        for edge in edges:
            assert "_from" in edge
            assert "_to" in edge
            assert edge["_from"].startswith("regs/")
            assert edge["_to"].startswith("canonical_addresses/")
            assert "CANONICAL_SIGNATURE" in edge
            assert "RECORDS" in edge
            assert "RECORD_COUNT" in edge
            assert edge["RECORD_COUNT"] == len(edge["RECORDS"])

    def test_reduction_ratio(self, sample_files):
        header, data, source_lookup, out_dir = sample_files

        resolver = CanonicalResolver(
            normalizer=AddressNormalizer(),
            field_mapping={
                "street": "ADDRESS_LINE_1",
                "city": "PRIMARY_TOWN",
                "state": "TERRITORY_CODE",
                "postal": "POSTAL_CODE",
            },
        )

        stats = resolver.process_file(
            str(data),
            delimiter="\t",
            header_path=str(header),
        )

        assert stats["reduction_pct"] > 30

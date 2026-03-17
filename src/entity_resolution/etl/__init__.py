"""
ETL module for pre-load entity deduplication.

Provides :class:`CanonicalResolver` for O(n) canonicalization of address
(or other entity) records before bulk loading into ArangoDB, and a
:func:`arangoimport_jsonl` helper for performant JSONL import.

Example::

    from entity_resolution.etl import (
        CanonicalResolver,
        AddressNormalizer,
        arangoimport_jsonl,
    )

    resolver = CanonicalResolver(
        normalizer=AddressNormalizer(),
        signature_fields=["street", "city", "state", "postal"],
        field_mapping={"street": "ADDRESS_LINE_1", ...},
    )
    resolver.process_file("regaddrs.tsv", ...)
    resolver.write_nodes("canonical_addresses.jsonl")
    resolver.write_edges("hasAddress.jsonl", "regs", "canonical_addresses")

    arangoimport_jsonl("canonical_addresses.jsonl", "canonical_addresses")
    arangoimport_jsonl("hasAddress.jsonl", "hasAddress", collection_type="edge")
"""

from .normalizers import (
    AddressNormalizer,
    PostalNormalizer,
    TokenNormalizer,
    STREET_SUFFIX_MAP,
    DIRECTIONAL_MAP,
    ORDINAL_MAP,
    UNIT_DESIGNATORS,
)
from .provenance import ProvenanceTracker
from .canonical_resolver import CanonicalResolver
from .arangoimport import arangoimport_jsonl, get_arangoimport_connection_args

__all__ = [
    "CanonicalResolver",
    "AddressNormalizer",
    "PostalNormalizer",
    "TokenNormalizer",
    "ProvenanceTracker",
    "arangoimport_jsonl",
    "get_arangoimport_connection_args",
    "STREET_SUFFIX_MAP",
    "DIRECTIONAL_MAP",
    "ORDINAL_MAP",
    "UNIT_DESIGNATORS",
]

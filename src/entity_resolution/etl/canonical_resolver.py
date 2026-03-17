"""
Canonical Resolver — ETL-time entity deduplication by normalized signature.

Streams input records (TSV/CSV or programmatic ``add()``), normalizes
each row, groups by canonical signature, and writes deduplicated JSONL
output suitable for bulk loading via ``arangoimport``.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from .normalizers import AddressNormalizer, PostalNormalizer
from .provenance import ProvenanceTracker


def _signature_to_key(sig: str, length: int = 16) -> str:
    """Hash a signature into an ArangoDB-safe ``_key`` suffix."""
    return hashlib.sha256(sig.encode("utf-8")).hexdigest()[:length]


class CanonicalResolver:
    """Deduplicate records at ETL time by canonical signature.

    The resolver is **domain-agnostic**: it delegates all normalization to
    a pluggable *normalizer* object that must implement::

        def normalize(self, field: str, raw: str, track: bool = False
                      ) -> str | tuple[str, list[str]]: ...

    When *track* is ``True`` the method returns ``(normalized, transforms)``.

    Parameters
    ----------
    normalizer : object
        Any object implementing ``normalize(field, raw, track=False)``.
        ``AddressNormalizer`` is a ready-made US-address implementation.
    signature_fields : list[str]
        Ordered list of logical field names that form the canonical
        signature (e.g. ``["street", "city", "state", "postal"]``).
    field_mapping : dict[str, str]
        Maps logical field names to input column names
        (e.g. ``{"street": "ADDRESS_LINE_1", "city": "PRIMARY_TOWN"}``).
    required_fields : list[str] | None
        Logical fields that must be non-empty for a record to be kept.
        A record is skipped when **all** required fields are empty after
        normalization. Defaults to the first two ``signature_fields``.
    shard_key_field : str
        Which logical field to derive the SmartGraph shard prefix from.
    shard_key_length : int
        Characters in the shard prefix (e.g. 3 for a 3-digit prefix).
    shard_key_output_name : str | None
        Field name written to output documents for the shard key. Defaults
        to ``"SHARD_{field.upper()}"``.
    shard_key_extractor : callable | None
        ``(raw_value, length) -> str`` function to derive the shard prefix
        from a raw field value. Defaults to ``PostalNormalizer.shard_prefix``
        which extracts leading digits.
    hub_threshold : int
        In-degree above which a node is classified as a hub.
    hub_markers : dict[str, str] | None
        ``{input_column: value}`` pairs that also classify a row as a hub.
    provenance : bool
        Whether to track raw variants and transforms.
    max_variants : int
        Maximum raw variant entries per signature.
    track_fields : list[str] | None
        Logical fields whose normalization transforms are recorded. Defaults
        to the **first** signature field only (e.g. ``["street"]``).
    type_fields : list[str] | None
        Edge extra-field names to collect into a top-level ``RECORD_TYPES``
        array on consolidated edges (for indexed filtering). Defaults to
        ``[]`` (no type extraction — caller must specify).
    node_label : str
        Label used in output field names: ``"{LABEL}_SIGNATURE"``,
        ``"IS_{LABEL}_HUB"``. Defaults to ``"ADDRESS"``.
    extra_node_fields : list[str] | None
        Additional input columns to carry through onto canonical nodes.
    """

    def __init__(
        self,
        normalizer: Optional[Any] = None,
        signature_fields: Optional[list[str]] = None,
        field_mapping: Optional[dict[str, str]] = None,
        required_fields: Optional[list[str]] = None,
        shard_key_field: str = "postal",
        shard_key_length: int = 3,
        shard_key_output_name: Optional[str] = None,
        shard_key_extractor: Optional[Any] = None,
        hub_threshold: int = 50,
        hub_markers: Optional[dict[str, str]] = None,
        provenance: bool = True,
        max_variants: int = 20,
        track_fields: Optional[list[str]] = None,
        type_fields: Optional[list[str]] = None,
        node_label: str = "ADDRESS",
        extra_node_fields: Optional[list[str]] = None,
    ):
        self.normalizer = normalizer or AddressNormalizer()
        self.signature_fields = signature_fields or ["street", "city", "state", "postal"]
        self.field_mapping = field_mapping or {}
        self.required_fields = required_fields if required_fields is not None else list(
            self.signature_fields[:2]
        )
        self.shard_key_field = shard_key_field
        self.shard_key_length = shard_key_length
        self.shard_key_output_name = (
            shard_key_output_name
            or f"SHARD_{shard_key_field.upper()}"
        )
        self._shard_extractor = shard_key_extractor
        if self._shard_extractor is None:
            _postal = PostalNormalizer(digits=5)
            self._shard_extractor = _postal.shard_prefix
        self.hub_threshold = hub_threshold
        self.hub_markers = hub_markers or {}
        self.track_provenance = provenance
        self.max_variants = max_variants
        self.track_fields = set(
            track_fields if track_fields is not None else self.signature_fields[:1]
        )
        self.type_fields = type_fields or []
        self.node_label = node_label
        self.extra_node_fields = extra_node_fields or []

        self._provenance = ProvenanceTracker(max_variants=max_variants) if provenance else None

        self._sig_data: dict[str, dict[str, Any]] = {}
        self._sig_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._input_rows = 0
        self._skipped = 0

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    def _normalize_field(
        self, field: str, raw: str, track: bool = False
    ) -> str | tuple[str, list[str]]:
        """Delegate to the normalizer's ``normalize`` protocol method."""
        return self.normalizer.normalize(field, raw, track=track)

    def _build_signature(self, normalized: dict[str, str]) -> str:
        return "|".join(normalized.get(f, "") for f in self.signature_fields)

    def _derive_shard_prefix(self, raw_value: str) -> str:
        return self._shard_extractor(raw_value, self.shard_key_length)

    # ------------------------------------------------------------------
    # Public API: add / process_file
    # ------------------------------------------------------------------

    def add(
        self,
        record: dict[str, str],
        source_key: str | None = None,
        edge_fields: dict[str, str] | None = None,
    ) -> None:
        """Add a single input record.

        Parameters
        ----------
        record : dict
            Input record (column name -> value).
        source_key : str | None
            ``_key`` of the source vertex (for building ``_from`` on edges).
            When ``None`` no edge is created for this record.
        edge_fields : dict | None
            Extra fields to store on the edge document
            (e.g. ``{"ADDR_TYPE": "mailing"}``).
        """
        self._input_rows += 1

        normalized: dict[str, str] = {}
        transforms: list[str] = []

        for norm_field in self.signature_fields:
            col = self.field_mapping.get(norm_field, norm_field)
            raw_val = record.get(col, "")

            if norm_field in self.track_fields:
                result = self._normalize_field(norm_field, raw_val, track=True)
                norm_val, field_transforms = result
                transforms.extend(field_transforms)
            else:
                norm_val = self._normalize_field(norm_field, raw_val, track=False)

            normalized[norm_field] = norm_val

        if self.required_fields and all(
            not normalized.get(f, "") for f in self.required_fields
        ):
            self._skipped += 1
            return

        sig = self._build_signature(normalized)

        shard_col = self.field_mapping.get(self.shard_key_field, self.shard_key_field)
        raw_shard_val = record.get(shard_col, "")
        shard_prefix = self._derive_shard_prefix(raw_shard_val)

        is_hub_by_marker = any(
            record.get(col, "").strip() == val
            for col, val in self.hub_markers.items()
        )

        if sig not in self._sig_data:
            node: dict[str, Any] = {
                "shard_prefix": shard_prefix,
                "normalized": dict(normalized),
                "has_hub_marker": is_hub_by_marker,
            }
            for ef in self.extra_node_fields:
                node[ef] = record.get(ef, "")
            self._sig_data[sig] = node
        elif is_hub_by_marker:
            self._sig_data[sig]["has_hub_marker"] = True

        if self.track_provenance and self._provenance is not None:
            raw_parts = []
            for norm_field in self.signature_fields:
                col = self.field_mapping.get(norm_field, norm_field)
                raw_parts.append(record.get(col, "").strip())
            raw_variant = "|".join(raw_parts)
            self._provenance.record(sig, raw_variant, transforms)

        if source_key is not None:
            edge_info: dict[str, Any] = {
                "source_key": source_key,
                "transforms": transforms,
            }
            if self.track_provenance:
                raw_edge_fields: dict[str, str] = {}
                for norm_field in self.signature_fields:
                    col = self.field_mapping.get(norm_field, norm_field)
                    raw_edge_fields[f"RAW_{norm_field.upper()}"] = record.get(col, "").strip()
                edge_info["raw_fields"] = raw_edge_fields

            if edge_fields:
                edge_info["extra"] = dict(edge_fields)
            self._sig_edges[sig].append(edge_info)

    def process_file(
        self,
        input_path: str | Path,
        delimiter: str = "\t",
        header_path: str | Path | None = None,
        key_field: str | None = None,
        source_lookup: dict[str, tuple[str, str]] | None = None,
        edge_extra_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Process an entire TSV/CSV file.

        Parameters
        ----------
        input_path : path
            Path to the data file (no header row expected when *header_path*
            is provided).
        delimiter : str
            Column delimiter.
        header_path : path | None
            Separate header file. If ``None``, the first row of *input_path*
            is used as the header.
        key_field : str | None
            Column name for the join key used to look up source vertex keys
            via *source_lookup*.
        source_lookup : dict | None
            ``{join_key_value: (shard_prefix, vertex_key)}`` mapping built
            from the source vertex file. When provided, edges are generated.
        edge_extra_fields : list[str] | None
            Additional columns from the input to carry onto edge documents.

        Returns
        -------
        dict
            Summary statistics (same as :attr:`stats`).
        """
        input_path = Path(input_path)
        edge_extra_fields = edge_extra_fields or []

        if header_path is not None:
            header_path = Path(header_path)
            with open(header_path, "r") as hf:
                field_names = next(csv.reader(hf, delimiter=delimiter))
                field_names = [n.strip() for n in field_names]
        else:
            field_names = None

        csv.field_size_limit(10_000_000)

        with open(input_path, "r", encoding="utf-8", errors="ignore") as fin:
            if field_names is not None:
                reader = csv.DictReader(fin, fieldnames=field_names, delimiter=delimiter)
            else:
                reader = csv.DictReader(fin, delimiter=delimiter)

            for row in reader:
                join_val = (row.get(key_field, "") or "").strip() if key_field else None
                source_key = None
                if source_lookup and join_val:
                    info = source_lookup.get(join_val)
                    if info:
                        source_key = info[1]

                extra = {}
                for ef in edge_extra_fields:
                    extra[ef] = (row.get(ef, "") or "").strip()

                self.add(
                    record=row,
                    source_key=source_key,
                    edge_fields=extra if extra else None,
                )

        self._classify_hubs()
        return self.stats

    # ------------------------------------------------------------------
    # Hub classification
    # ------------------------------------------------------------------

    def _classify_hubs(self) -> None:
        """Tag signatures as hubs based on in-degree and hub markers.

        In-degree counts unique source vertices (registrations), not raw
        edge records — a reg with 3 address-type variants still counts as 1.
        """
        for sig, data in self._sig_data.items():
            edges = self._sig_edges.get(sig, [])
            unique_sources = len({e["source_key"] for e in edges})
            data["in_degree"] = unique_sources
            data["is_hub"] = data.get("has_hub_marker", False) or unique_sources >= self.hub_threshold

    # ------------------------------------------------------------------
    # Output writers
    # ------------------------------------------------------------------

    def write_nodes(
        self,
        output_path: str | Path,
        format: str = "jsonl",
    ) -> int:
        """Write canonical nodes to JSONL (or TSV for flat fields only).

        Returns the number of nodes written.
        """
        output_path = Path(output_path)
        self._classify_hubs()
        count = 0

        sig_key = f"{self.node_label}_SIGNATURE"
        hub_key = f"IS_{self.node_label}_HUB"

        if format == "jsonl":
            with open(output_path, "w", encoding="utf-8") as fout:
                for sig, data in self._sig_data.items():
                    key_suffix = _signature_to_key(sig)
                    smart_key = f"{data['shard_prefix']}:{key_suffix}"

                    doc: dict[str, Any] = {
                        "_key": smart_key,
                        self.shard_key_output_name: data["shard_prefix"],
                        sig_key: sig,
                    }

                    for field in self.signature_fields:
                        doc[f"NORM_{field.upper()}"] = data["normalized"].get(field, "")

                    doc[hub_key] = data.get("is_hub", False)
                    doc["IN_DEGREE"] = data.get("in_degree", 0)

                    if self.track_provenance and self._provenance is not None:
                        prov = self._provenance.get_node_provenance(sig)
                        doc.update(prov)

                    for ef in self.extra_node_fields:
                        if ef in data:
                            doc[ef] = data[ef]

                    fout.write(json.dumps(doc) + "\n")
                    count += 1
        else:
            flat_fields = [
                "_key",
                self.shard_key_output_name,
                sig_key,
            ] + [f"NORM_{f.upper()}" for f in self.signature_fields] + [
                hub_key, "IN_DEGREE",
            ]

            with open(output_path, "w", encoding="utf-8", newline="") as fout:
                writer = csv.DictWriter(fout, fieldnames=flat_fields, delimiter="\t", extrasaction="ignore")
                writer.writeheader()
                for sig, data in self._sig_data.items():
                    key_suffix = _signature_to_key(sig)
                    smart_key = f"{data['shard_prefix']}:{key_suffix}"
                    row_dict: dict[str, Any] = {
                        "_key": smart_key,
                        flat_fields[1]: data["shard_prefix"],
                        sig_key: sig,
                        hub_key: str(data.get("is_hub", False)).lower(),
                        "IN_DEGREE": data.get("in_degree", 0),
                    }
                    for field in self.signature_fields:
                        row_dict[f"NORM_{field.upper()}"] = data["normalized"].get(field, "")
                    writer.writerow(row_dict)
                    count += 1

        return count

    def write_edges(
        self,
        output_path: str | Path,
        from_collection: str,
        to_collection: str,
        format: str = "jsonl",
        consolidate: bool = True,
    ) -> int:
        """Write edge documents to JSONL.

        Parameters
        ----------
        consolidate : bool
            When ``True`` (default), multiple raw edges between the same
            ``(source_key, canonical_address)`` pair are merged into a single
            edge document carrying an ``ADDRESS_RECORDS`` subdocument array.
            This dramatically reduces edge count and prevents duplicate
            traversal paths.  Top-level ``ADDR_TYPES`` and ``RECORD_COUNT``
            fields are added for indexed filtering.

            When ``False``, one edge document per raw input record is written
            (legacy behaviour).

        Returns the number of edges written.
        """
        output_path = Path(output_path)

        if consolidate:
            return self._write_edges_consolidated(output_path, from_collection, to_collection)
        return self._write_edges_flat(output_path, from_collection, to_collection)

    def _write_edges_consolidated(
        self,
        output_path: Path,
        from_collection: str,
        to_collection: str,
    ) -> int:
        """Merge edges per (source_key, signature) into one doc with subdocuments."""
        count = 0

        # Group all raw edge records by (source_key, sig)
        pair_records: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

        for sig, edges in self._sig_edges.items():
            for edge in edges:
                pair_key = (edge["source_key"], sig)
                pair_records[pair_key].append(edge)

        with open(output_path, "w", encoding="utf-8") as fout:
            for (source_key, sig), records in pair_records.items():
                addr_key_suffix = _signature_to_key(sig)
                shard_prefix = self._sig_data[sig]["shard_prefix"]
                addr_key = f"{shard_prefix}:{addr_key_suffix}"

                from_id = f"{from_collection}/{source_key}"
                addr_id = f"{to_collection}/{addr_key}"

                # Build subdocument array from each raw record
                address_records: list[dict[str, Any]] = []
                addr_types: list[str] = []

                for rec in records:
                    subdoc: dict[str, Any] = {}
                    extra = rec.get("extra", {})
                    if extra:
                        subdoc.update(extra)

                    if self.track_provenance and self._provenance is not None:
                        raw_fields = rec.get("raw_fields", {})
                        transforms = rec.get("transforms", [])
                        prov = self._provenance.get_edge_provenance(
                            raw_fields, transforms, sig,
                        )
                        subdoc.update(prov)

                    address_records.append(subdoc)

                    for type_field in self.type_fields:
                        val = extra.get(type_field, "")
                        if val and val not in addr_types:
                            addr_types.append(val)

                doc: dict[str, Any] = {
                    "_from": from_id,
                    "_to": addr_id,
                    "CANONICAL_SIGNATURE": sig,
                    "RECORD_COUNT": len(address_records),
                }
                if addr_types:
                    doc["RECORD_TYPES"] = addr_types
                doc["RECORDS"] = address_records

                fout.write(json.dumps(doc) + "\n")
                count += 1

        return count

    def _write_edges_flat(
        self,
        output_path: Path,
        from_collection: str,
        to_collection: str,
    ) -> int:
        """Write one edge per raw input record (legacy mode)."""
        count = 0
        seen_edge_keys: set[str] = set()

        with open(output_path, "w", encoding="utf-8") as fout:
            for sig, edges in self._sig_edges.items():
                addr_key_suffix = _signature_to_key(sig)
                shard_prefix = self._sig_data[sig]["shard_prefix"]
                addr_key = f"{shard_prefix}:{addr_key_suffix}"
                addr_id = f"{to_collection}/{addr_key}"

                for edge in edges:
                    source_key = edge["source_key"]
                    from_id = f"{from_collection}/{source_key}"

                    extra = edge.get("extra", {})
                    safe_extra = "_".join(
                        str(v).replace(" ", "_").replace("/", "_")
                        for v in extra.values()
                    ) if extra else ""
                    edge_sig = f"{source_key}|{addr_key}|{safe_extra}"
                    edge_hash = hashlib.sha256(edge_sig.encode("utf-8")).hexdigest()[:16]

                    source_shard = source_key.split(":")[0] if ":" in source_key else shard_prefix
                    edge_key = f"{source_shard}:{edge_hash}"

                    if edge_key in seen_edge_keys:
                        continue
                    seen_edge_keys.add(edge_key)

                    doc: dict[str, Any] = {
                        "_from": from_id,
                        "_to": addr_id,
                    }
                    if extra:
                        doc.update(extra)

                    if self.track_provenance and self._provenance is not None:
                        raw_fields = edge.get("raw_fields", {})
                        transforms = edge.get("transforms", [])
                        prov = self._provenance.get_edge_provenance(raw_fields, transforms, sig)
                        doc.update(prov)

                    fout.write(json.dumps(doc) + "\n")
                    count += 1

        return count

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        """Return dedup statistics."""
        hub_count = sum(1 for d in self._sig_data.values() if d.get("is_hub", False))
        unique = len(self._sig_data)
        return {
            "input_rows": self._input_rows,
            "skipped": self._skipped,
            "unique_signatures": unique,
            "reduction_pct": round(100 * (1 - unique / max(self._input_rows, 1)), 1),
            "hubs": hub_count,
            "regular": unique - hub_count,
            "total_edges": sum(len(e) for e in self._sig_edges.values()),
        }

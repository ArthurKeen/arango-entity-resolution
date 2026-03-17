"""
Provenance tracking for ETL canonicalization.

Records raw address variants, normalization transforms, and per-edge
provenance so downstream consumers can trace every canonical node and
edge back to its original source data.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class ProvenanceTracker:
    """Track raw variants and normalization transforms per canonical signature.

    Parameters
    ----------
    max_variants : int
        Cap the number of raw variant entries stored per signature
        (keeps the most frequent variants).
    """

    def __init__(self, max_variants: int = 20):
        self.max_variants = max_variants
        self._variants: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._transforms: dict[str, list[str]] = {}

    def record(
        self,
        signature: str,
        raw_variant: str,
        transforms: list[str],
    ) -> None:
        """Record a raw variant and its transforms for *signature*.

        The first set of transforms seen for a signature is retained as
        the representative normalization trace.
        """
        self._variants[signature][raw_variant] += 1
        if signature not in self._transforms:
            self._transforms[signature] = list(transforms)

    def get_node_provenance(self, signature: str) -> dict[str, Any]:
        """Return provenance metadata suitable for embedding in a canonical node."""
        raw = self._variants.get(signature, {})
        variant_list = sorted(raw.items(), key=lambda x: -x[1])
        if len(variant_list) > self.max_variants:
            variant_list = variant_list[: self.max_variants]

        return {
            "RAW_VARIANTS": [{"raw": v, "count": c} for v, c in variant_list],
            "NORM_TRANSFORMS": self._transforms.get(signature, []),
            "DISTINCT_RAW_VARIANTS": len(raw),
            "TOTAL_RAW_ROWS": sum(raw.values()),
        }

    def get_edge_provenance(
        self,
        raw_fields: dict[str, str],
        transforms: list[str],
        canonical_sig: str,
    ) -> dict[str, Any]:
        """Return per-edge provenance dict.

        Parameters
        ----------
        raw_fields : dict
            Original raw field values for the edge (e.g. RAW_STREET, RAW_CITY).
        transforms : list[str]
            Normalization transforms applied to this specific edge's source row.
        canonical_sig : str
            The canonical signature this edge resolves to.
        """
        result = dict(raw_fields)
        result["CANONICAL_SIGNATURE"] = canonical_sig
        if transforms:
            result["NORM_TRANSFORMS"] = transforms
        return result

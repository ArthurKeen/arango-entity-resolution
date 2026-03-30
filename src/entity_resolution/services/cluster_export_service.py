"""
Cluster export and reporting helpers.

Builds portable JSON/CSV artifacts from persisted cluster results and existing
pipeline statistics without recomputing clustering.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from arango.database import StandardDatabase

from ..utils.pipeline_utils import get_pipeline_statistics
from ..utils.validation import validate_collection_name


class ClusterExportService:
    """Export persisted cluster results plus summary stats."""

    def __init__(
        self,
        db: StandardDatabase,
        source_collection: str,
        edge_collection: Optional[str] = None,
        cluster_collection: Optional[str] = None,
        golden_collection: str = "golden_records",
        resolved_edge_collection: str = "resolvedTo",
    ):
        self.db = db
        self.source_collection = validate_collection_name(source_collection)
        self.edge_collection = validate_collection_name(
            edge_collection or f"{self.source_collection}_similarity_edges"
        )
        self.cluster_collection = validate_collection_name(
            cluster_collection or f"{self.source_collection}_clusters"
        )
        self.golden_collection = validate_collection_name(golden_collection)
        self.resolved_edge_collection = validate_collection_name(resolved_edge_collection)

    def build_report(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Build an in-memory export report."""
        clusters = self._load_clusters(limit=limit)
        stats = get_pipeline_statistics(
            self.db,
            vertex_collection=self.source_collection,
            edge_collection=self.edge_collection,
            cluster_collection=self.cluster_collection,
        )
        stats["artifacts"] = self._artifact_counts()
        stats["quality"] = self._quality_summary(clusters)

        return {
            "metadata": {
                "source_collection": self.source_collection,
                "edge_collection": self.edge_collection,
                "cluster_collection": self.cluster_collection,
                "golden_collection": self.golden_collection,
                "resolved_edge_collection": self.resolved_edge_collection,
                "generated_at": datetime.utcnow().isoformat(),
            },
            "stats": stats,
            "clusters": clusters,
        }

    def export(
        self,
        output_dir: str,
        filename_prefix: str = "cluster_export",
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write JSON and CSV export artifacts to disk."""
        report = self.build_report(limit=limit)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        json_path = output_path / f"{filename_prefix}_{timestamp}.json"
        csv_path = output_path / f"{filename_prefix}_{timestamp}.csv"

        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self._write_csv(csv_path, report["clusters"])

        return {
            "json": str(json_path),
            "csv": str(csv_path),
            "clusters_exported": len(report["clusters"]),
        }

    def _load_clusters(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load stored cluster documents and normalize them for export."""
        if not self.db.has_collection(self.cluster_collection):
            return []

        limit_clause = "LIMIT @limit" if limit is not None else ""
        query = f"""
        FOR c IN @@cluster_collection
            SORT (c.size != null ? c.size : LENGTH(c.members)) DESC, c._key
            {limit_clause}
            RETURN c
        """
        bind_vars: dict = {"@cluster_collection": self.cluster_collection}
        if limit is not None:
            bind_vars["limit"] = int(limit)
        cursor = self.db.aql.execute(query, bind_vars=bind_vars)

        clusters: List[Dict[str, Any]] = []
        for raw in cursor:
            members = list(raw.get("members") or [])
            member_keys = list(raw.get("member_keys") or raw.get("memberKeys") or [])
            if not member_keys and members:
                member_keys = [str(member).split("/")[-1] for member in members]

            size = raw.get("size")
            if size is None:
                size = len(member_keys or members)

            clusters.append(
                {
                    "cluster_id": raw.get("cluster_id") or raw.get("_key"),
                    "representative": raw.get("representative"),
                    "size": size,
                    "members": members,
                    "member_keys": member_keys,
                    "edge_count": raw.get("edge_count"),
                    "average_similarity": raw.get("average_similarity"),
                    "min_similarity": raw.get("min_similarity"),
                    "max_similarity": raw.get("max_similarity"),
                    "density": raw.get("density"),
                    "quality_score": raw.get("quality_score"),
                }
            )

        return clusters

    def _artifact_counts(self) -> Dict[str, int]:
        """Return counts for downstream persistence artifacts when present."""
        counts = {
            "golden_records": 0,
            "resolved_edges": 0,
        }
        if self.db.has_collection(self.golden_collection):
            counts["golden_records"] = self.db.collection(self.golden_collection).count()
        if self.db.has_collection(self.resolved_edge_collection):
            counts["resolved_edges"] = self.db.collection(self.resolved_edge_collection).count()
        return counts

    @staticmethod
    def _quality_summary(clusters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate quality-oriented rollups for exported clusters."""
        quality_scores = [
            float(cluster["quality_score"])
            for cluster in clusters
            if isinstance(cluster.get("quality_score"), (int, float))
        ]
        avg_similarities = [
            float(cluster["average_similarity"])
            for cluster in clusters
            if isinstance(cluster.get("average_similarity"), (int, float))
        ]

        return {
            "clusters_with_quality": len(quality_scores),
            "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 4)
            if quality_scores
            else None,
            "min_quality_score": round(min(quality_scores), 4) if quality_scores else None,
            "max_quality_score": round(max(quality_scores), 4) if quality_scores else None,
            "avg_cluster_similarity": round(sum(avg_similarities) / len(avg_similarities), 4)
            if avg_similarities
            else None,
        }

    @staticmethod
    def _write_csv(path: Path, clusters: List[Dict[str, Any]]) -> None:
        """Write a flat cluster summary CSV."""
        fieldnames = [
            "cluster_id",
            "size",
            "representative",
            "edge_count",
            "average_similarity",
            "min_similarity",
            "max_similarity",
            "density",
            "quality_score",
            "member_keys",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for cluster in clusters:
                row = dict(cluster)
                row["member_keys"] = "|".join(cluster.get("member_keys") or [])
                writer.writerow({key: row.get(key) for key in fieldnames})

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from entity_resolution.services.cluster_export_service import ClusterExportService


class FakeCursor(list):
    pass


@dataclass
class FakeAQL:
    dispatch: Any
    calls: List[Dict[str, Any]] = field(default_factory=list)

    def execute(self, query: str, bind_vars: Optional[Dict[str, Any]] = None, **kwargs: Any) -> FakeCursor:
        self.calls.append({"query": query, "bind_vars": bind_vars})
        return FakeCursor(self.dispatch(query, bind_vars))


@dataclass
class FakeCollection:
    count_value: int

    def count(self) -> int:
        return self.count_value


@dataclass
class FakeDB:
    collections: Dict[str, FakeCollection]
    aql: FakeAQL

    def has_collection(self, name: str) -> bool:
        return name in self.collections

    def collection(self, name: str) -> FakeCollection:
        return self.collections[name]


def test_build_report_includes_stats_quality_and_artifact_counts(monkeypatch) -> None:
    def dispatch(query: str, bind_vars: Optional[Dict[str, Any]]) -> Iterable[Any]:
        if "RETURN c" in query:
            return [
                {
                    "_key": "cluster_1",
                    "size": 2,
                    "members": ["companies/a1", "companies/b1"],
                    "representative": "companies/a1",
                    "edge_count": 1,
                    "average_similarity": 0.91,
                    "min_similarity": 0.91,
                    "max_similarity": 0.91,
                    "density": 1.0,
                    "quality_score": 0.95,
                }
            ]
        return []

    db = FakeDB(
        collections={
            "companies": FakeCollection(10),
            "companies_clusters": FakeCollection(1),
            "companies_similarity_edges": FakeCollection(5),
            "golden_records": FakeCollection(1),
            "resolvedTo": FakeCollection(2),
        },
        aql=FakeAQL(dispatch=dispatch),
    )

    monkeypatch.setattr(
        "entity_resolution.services.cluster_export_service.get_pipeline_statistics",
        lambda *args, **kwargs: {"entities": {"total": 10}, "clusters": {"total": 1}, "timestamp": "t"},
    )

    service = ClusterExportService(db=db, source_collection="companies")
    report = service.build_report()

    assert report["metadata"]["cluster_collection"] == "companies_clusters"
    assert report["stats"]["artifacts"]["golden_records"] == 1
    assert report["stats"]["artifacts"]["resolved_edges"] == 2
    assert report["stats"]["quality"]["clusters_with_quality"] == 1
    assert report["clusters"][0]["member_keys"] == ["a1", "b1"]


def test_export_writes_json_and_csv(tmp_path: Path, monkeypatch) -> None:
    db = FakeDB(
        collections={"companies": FakeCollection(1), "companies_clusters": FakeCollection(1)},
        aql=FakeAQL(dispatch=lambda q, b: []),
    )
    monkeypatch.setattr(
        ClusterExportService,
        "build_report",
        lambda self, limit=None: {
            "metadata": {"source_collection": "companies"},
            "stats": {"clusters": {"total": 1}},
            "clusters": [
                {
                    "cluster_id": "cluster_1",
                    "size": 2,
                    "representative": "companies/a1",
                    "edge_count": 1,
                    "average_similarity": 0.91,
                    "min_similarity": 0.91,
                    "max_similarity": 0.91,
                    "density": 1.0,
                    "quality_score": 0.95,
                    "member_keys": ["a1", "b1"],
                }
            ],
        },
    )

    service = ClusterExportService(db=db, source_collection="companies")
    exported = service.export(output_dir=str(tmp_path), filename_prefix="clusters")

    json_path = Path(exported["json"])
    csv_path = Path(exported["csv"])
    assert json_path.exists()
    assert csv_path.exists()
    assert exported["clusters_exported"] == 1

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["metadata"]["source_collection"] == "companies"

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["cluster_id"] == "cluster_1"
    assert rows[0]["member_keys"] == "a1|b1"

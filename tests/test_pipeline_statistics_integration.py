"""get_pipeline_statistics against a real ArangoDB.

``FOR cluster IN c RETURN SUM(cluster.size)`` applied SUM to one scalar per row
and the code read the first row, so clustered entities came back as 0 and
clustering_rate as 0.0. A recording fake cannot catch that, because the defect
is in what the AQL means, so this runs against a real server.
"""

from __future__ import annotations

import pytest

from entity_resolution.utils.pipeline_utils import get_pipeline_statistics

pytestmark = pytest.mark.integration


@pytest.fixture
def populated(db_connection):
    db = db_connection
    for name in ("pst_people", "pst_clusters"):
        if db.has_collection(name):
            db.delete_collection(name)
    db.create_collection("pst_people").insert_many([{"_key": str(i)} for i in range(10)])
    db.create_collection("pst_clusters").insert_many([{"size": 2}, {"size": 3}])
    yield db
    for name in ("pst_people", "pst_clusters"):
        db.delete_collection(name)


def test_clustered_entities_are_summed_across_clusters(populated) -> None:
    stats = get_pipeline_statistics(populated, "pst_people", cluster_collection="pst_clusters")
    assert stats["entities"]["clustered"] == 5
    assert stats["entities"]["unclustered"] == 5
    assert stats["entities"]["clustering_rate"] == pytest.approx(0.5)
    assert stats["clusters"]["size_distribution"] == {"2": 1, "3": 1}

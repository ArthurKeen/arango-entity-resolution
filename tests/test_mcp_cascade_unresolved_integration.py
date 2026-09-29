"""The cascade's "still unresolved" set must ignore steward-suppressed edges.

A suppressed edge is a rejected match. ``_get_unresolved_doc_ids`` counted it as
a link, so a record whose only edge a steward had rejected looked resolved and
was skipped by every later cascade stage, the one place it could have found its
real match. Every clustering backend already filters ``suppressed != true``;
this path was the sibling without the guard.
"""

from __future__ import annotations

import pytest

from entity_resolution.mcp.tools.pipeline import _get_unresolved_doc_ids

pytestmark = pytest.mark.integration

DOCS = "cascade_it_people"
EDGES = "cascade_it_people_edges"


@pytest.fixture
def graph(db_connection):
    db = db_connection
    for name in (EDGES, DOCS):
        if db.has_collection(name):
            db.delete_collection(name)
    db.create_collection(DOCS).insert_many([{"_key": k} for k in ("a", "b", "c", "d", "e")])
    db.create_collection(EDGES, edge=True).insert_many([
        {"_from": f"{DOCS}/a", "_to": f"{DOCS}/b", "suppressed": True},
        {"_from": f"{DOCS}/c", "_to": f"{DOCS}/d"},
        {"_from": f"{DOCS}/d", "_to": f"{DOCS}/e", "suppressed": False},
    ])
    yield db
    db.delete_collection(EDGES)
    db.delete_collection(DOCS)


def test_suppressed_edges_do_not_resolve_a_record(graph) -> None:
    unresolved = _get_unresolved_doc_ids(graph, DOCS, EDGES)
    assert unresolved == {f"{DOCS}/a", f"{DOCS}/b"}


class _RecordingDB:
    """Captures the AQL sent, so the guard is also checked in the unit run."""

    def __init__(self):
        self.queries = []
        self.aql = self

    def has_collection(self, name):
        return True

    def execute(self, query, bind_vars=None):
        self.queries.append(query)
        return iter([])


@pytest.mark.unit
def test_unresolved_query_filters_suppressed_edges_unit() -> None:
    # CI runs only the unit marker; this keeps the guard gating there too.
    db = _RecordingDB()
    _get_unresolved_doc_ids(db, DOCS, EDGES)
    (query,) = db.queries
    assert "e.suppressed != true" in query

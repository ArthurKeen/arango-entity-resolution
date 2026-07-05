"""Integration test for the Phase 2.4 profile route against a real ArangoDB."""

from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient

from entity_resolution.ui.app import create_app


@pytest.fixture
def profile_app(db_connection):
    suffix = uuid.uuid4().hex[:8]
    coll = f"itp_person_{suffix}"
    db = db_connection
    db.create_collection(coll)
    db.collection(coll).insert_many([
        {"_key": f"k{i}", "name": f"Person {i}", "email": f"p{i}@example.com",
         "city": "NYC"}
        for i in range(12)
    ])
    client = TestClient(create_app(db=db))
    yield coll, client
    if db.has_collection(coll):
        db.delete_collection(coll)


def test_profile_route_detects_fields_and_samples(profile_app):
    coll, client = profile_app
    resp = client.get(f"/api/profile/{coll}?emit_config=true")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["collection"] == coll
    assert data["sampled_docs"] == 12
    fields = data["fields"]
    assert "email" in fields and fields["email"]["type"] == "email"
    assert "_key" not in fields  # system fields excluded
    # Sample values are surfaced for the UI.
    assert len(fields["email"]["samples"]) > 0
    # emit_config attaches a normalized similarity block.
    assert "config" in data
    weights = data["config"]["similarity"]["field_weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-6

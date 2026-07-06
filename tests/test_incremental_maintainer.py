"""Unit tests for IncrementalMaintainer (plan 3.3)."""

from __future__ import annotations

from entity_resolution.core.incremental_maintainer import IncrementalMaintainer
from entity_resolution.services.feedback_application_service import FeedbackApplicationService


def test_edge_key_matches_feedback_service_and_is_order_independent():
    a, b = "Person/x", "Person/y"
    # Must equal FeedbackApplicationService's key so a human suppression collides
    # with (and is preserved through) an incremental upsert.
    assert IncrementalMaintainer._edge_key(a, b) == FeedbackApplicationService._edge_key(a, b)
    assert IncrementalMaintainer._edge_key(a, b) == IncrementalMaintainer._edge_key(b, a)

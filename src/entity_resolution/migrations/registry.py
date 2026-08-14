"""Ordered registry of schema migrations.

Add new migrations here with the next integer id and an idempotent ``apply``.
Migrations operate on collections the ER system owns (versioned schema), not on
user data — one-off data repairs that need deployment-specific collection names
(e.g. the GraphRAG self-loop edge fix in
``scripts/migrations/001_fix_graphrag_self_loop_edges.py``) stay as standalone,
parameterized scripts rather than auto-run migrations.
"""

from __future__ import annotations

from typing import Any, List

from .runner import Migration


def _baseline(db: Any) -> None:
    """v3.6 baseline — no schema objects yet; establishes the version anchor.

    Phase 0 added only schemaless document fields (verdict flags on edges,
    staleness fields on golden records) and the runtime-created ``er_locks``
    collection, so there is nothing to create here. Later migrations
    (er_model_params, er_term_frequencies, er_audit_log) build on this anchor.
    """
    return None


def _create_collection(name: str):
    def apply(db) -> None:
        if not db.has_collection(name):
            db.create_collection(name)
    return apply


def _add_persistent_index(collection: str, fields: List[str], name: str):
    """Idempotently add a persistent index.

    ``add_persistent_index`` is itself idempotent for an identical definition,
    but the collection is checked first so a migration cannot fail on a
    deployment where an earlier step was skipped.
    """
    def apply(db) -> None:
        if not db.has_collection(collection):
            db.create_collection(collection)
        db.collection(collection).add_persistent_index(
            fields=fields, name=name, sparse=False, unique=False
        )
    return apply


MIGRATIONS: List[Migration] = [
    Migration(
        id=1,
        name="baseline_v3_6",
        description="Establish schema-version baseline (no schema objects to create).",
        apply=_baseline,
    ),
    Migration(
        id=2,
        name="create_er_model_params",
        description="Collection for EM-learned m/u/lambda model parameters (plan 1.1).",
        apply=_create_collection("er_model_params"),
    ),
    Migration(
        id=3,
        name="create_er_term_frequencies",
        description="Collection for per-field term-frequency tables (plan 1.1).",
        apply=_create_collection("er_term_frequencies"),
    ),
    Migration(
        id=4,
        name="create_er_repair_queue",
        description="Collection for clusters flagged for human review by cluster repair (plan 1.3).",
        apply=_create_collection("er_repair_queue"),
    ),
    Migration(
        id=5,
        name="create_er_audit_log",
        description="Audit trail for steward curation actions (plan 2.0).",
        apply=_create_collection("er_audit_log"),
    ),
    Migration(
        id=6,
        name="index_er_audit_log_history",
        description=(
            "Index (collection, entity_key, ts) on er_audit_log so per-entity "
            "history is an index lookup rather than a full scan."
        ),
        apply=_add_persistent_index(
            "er_audit_log",
            ["collection", "entity_key", "ts"],
            "idx_audit_history",
        ),
    ),
]

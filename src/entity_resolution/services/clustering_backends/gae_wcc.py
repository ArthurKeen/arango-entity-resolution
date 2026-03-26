"""ArangoDB Graph Analytics Engine (GAE) WCC clustering backend.

Uses the GRAL engine API for large-scale WCC computation:

1. Deploy / reuse a GAE engine (k8s pod spin-up with readiness polling).
2. Load vertex + edge collections into the engine via ``v1/loaddata``.
3. Run WCC via ``v1/wcc`` and poll for job completion.
4. Store results back via ``v1/storeresults`` and read component labels.
5. Optionally stop the engine on cleanup.

Supports two deployment modes (routed by ``TEST_DEPLOYMENT_MODE``):

* **self_managed_platform** -- JWT auth, ``/gen-ai/`` + ``/gral/<id>/`` APIs.
* **managed_platform** -- oasisctl token, AMP management + engine APIs.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ...config.er_config import GAEClusteringConfig

logger = logging.getLogger(__name__)


class GAEWCCBackend:
    """WCC clustering via ArangoDB Graph Analytics Engine.

    The engine is a Kubernetes pod that needs time to spin up.  The
    ``deploy_engine`` + ``wait_for_engine_ready`` sequence handles the
    readiness polling with consecutive-OK probes before issuing any
    algorithm calls.
    """

    def __init__(
        self,
        db,
        edge_collection_name: str,
        vertex_collection: Optional[str] = None,
        gae_config: Optional["GAEClusteringConfig"] = None,
    ):
        self.db = db
        self.edge_collection_name = edge_collection_name
        self.vertex_collection = vertex_collection

        if gae_config is None:
            from ...config.er_config import GAEClusteringConfig
            gae_config = GAEClusteringConfig()
        self.gae_config = gae_config

        self._connection = None
        self.gae_job_id: Optional[str] = None
        self.gae_runtime_seconds: Optional[float] = None

    # ── Connection ───────────────────────────────────────────────────

    def _get_connection(self):
        if self._connection is None:
            from .gae_connection import get_gae_connection
            self._connection = get_gae_connection()
        return self._connection

    # ── Capability probe ─────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if GAE is accessible on the connected platform.

        For self-managed: verifies JWT auth + ``/gen-ai/v1/list_services``.
        For AMP: verifies oasisctl token + management API.
        """
        try:
            conn = self._get_connection()
            conn.deploy_engine(reuse_existing=True)
            conn.wait_for_engine_ready(max_retries=15, retry_interval=2)
            return True
        except Exception as exc:
            logger.debug("GAE availability check failed: %s", exc)
            return False

    # ── Clustering ───────────────────────────────────────────────────

    def cluster(self) -> List[List[str]]:
        conn = self._get_connection()

        start = time.time()
        try:
            # 1. Deploy / reuse engine and wait for readiness
            logger.info("Deploying GAE engine (reuse_existing=True)...")
            conn.deploy_engine(reuse_existing=True)
            conn.wait_for_engine_ready(max_retries=60, retry_interval=2)

            # 2. Resolve vertex collections from edges if needed
            vertex_collections = self._resolve_vertex_collections()
            database = self._resolve_database()

            # 3. Load graph into engine
            logger.info(
                "Loading graph into GAE: vertices=%s, edges=[%s], db=%s",
                vertex_collections, self.edge_collection_name, database,
            )
            load_job = conn.load_graph(
                database=database,
                vertex_collections=vertex_collections,
                edge_collections=[self.edge_collection_name],
            )
            load_job_id = load_job.get("id") or load_job.get("job_id")
            graph_id = load_job.get("graph_id")
            logger.info("Load data submitted: job_id=%s, graph_id=%s", load_job_id, graph_id)

            if load_job_id:
                conn.wait_for_job(load_job_id, timeout=self.gae_config.timeout_seconds)
                logger.info("Graph loaded successfully")

            # 4. Run WCC
            if not graph_id:
                raise RuntimeError("No graph_id returned from loaddata")

            wcc_job = conn.run_wcc(graph_id)
            wcc_job_id = wcc_job.get("id") or wcc_job.get("job_id")
            self.gae_job_id = str(wcc_job_id)
            logger.info("WCC job submitted: %s", wcc_job_id)

            conn.wait_for_job(wcc_job_id, timeout=self.gae_config.timeout_seconds)
            logger.info("WCC completed")

            # 5. Store WCC component labels back into vertex documents
            target_collection = vertex_collections[0]
            store_job = conn.store_results(
                target_collection=target_collection,
                job_ids=[wcc_job_id],
                attribute_names=["wcc_component"],
                database=database,
            )
            store_job_id = store_job.get("id") or store_job.get("job_id")
            logger.info("Store results submitted: %s (target=%s)", store_job_id, target_collection)

            if store_job_id:
                conn.wait_for_job(store_job_id, timeout=self.gae_config.timeout_seconds)
                logger.info("Results stored to %s", target_collection)

            # 6. Read component labels from vertex documents
            clusters = self._read_wcc_results(target_collection)

        finally:
            self.gae_runtime_seconds = round(time.time() - start, 2)
            if self.gae_config.auto_cleanup:
                self._cleanup(conn)

        logger.info(
            "GAE WCC completed: %d clusters in %.1fs (job=%s)",
            len(clusters), self.gae_runtime_seconds, self.gae_job_id,
        )
        return clusters

    def backend_name(self) -> str:
        return "gae_wcc"

    # ── Internal helpers ─────────────────────────────────────────────

    def _resolve_database(self) -> str:
        """Get the database name from the ArangoDB connection."""
        if hasattr(self.db, 'name'):
            return self.db.name
        if hasattr(self.db, 'db_name'):
            return self.db.db_name
        import os
        return os.getenv("ARANGO_DATABASE", "_system")

    def _resolve_vertex_collections(self) -> List[str]:
        """Determine vertex collections from edges or config."""
        if self.vertex_collection:
            return [self.vertex_collection]

        edge_coll = self.db.collection(self.edge_collection_name)
        sample = list(edge_coll.all(limit=10))
        seen: set = set()
        for e in sample:
            for field in ("_from", "_to"):
                vid = e.get(field, "")
                if "/" in vid:
                    seen.add(vid.split("/")[0])
        if seen:
            return sorted(seen)

        raise ValueError(
            f"Could not determine vertex collections from edges in "
            f"{self.edge_collection_name}. Provide vertex_collection explicitly."
        )

    def _read_wcc_results(self, vertex_collection: str) -> List[List[str]]:
        """Read WCC component labels from GAE result documents.

        GAE ``storeresults`` inserts *new* documents into the target collection
        with fields ``id`` (original vertex ID, e.g. ``coll/key``) and
        ``wcc_component`` (the component representative vertex ID).  The write
        is asynchronous, so we poll until results appear (up to 30s).
        """
        deadline = time.time() + 30
        poll_interval = 1.0

        while time.time() < deadline:
            check_query = f"""
            FOR doc IN `{vertex_collection}`
                FILTER doc.wcc_component != null AND doc.id != null
                LIMIT 1
                RETURN 1
            """
            cursor = self.db.aql.execute(check_query)
            if list(cursor):
                break
            logger.debug("GAE result docs not yet in %s, waiting...", vertex_collection)
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 5.0)

        query = f"""
        FOR doc IN `{vertex_collection}`
            FILTER doc.wcc_component != null AND doc.id != null
            LET vertex_key = LAST(SPLIT(doc.id, '/'))
            COLLECT component = doc.wcc_component INTO members
            RETURN members[*].vertex_key
        """
        cursor = self.db.aql.execute(query)
        clusters: List[List[str]] = []
        for members in cursor:
            keys = [k for k in members if k]
            if keys:
                clusters.append(sorted(keys))
        return clusters

    def _cleanup(self, conn) -> None:
        """Optionally stop the engine on completion."""
        try:
            if self.gae_config.auto_cleanup and self.gae_config.deployment_mode == "auto":
                conn.stop_engine()
                logger.info("GAE engine stopped (auto_cleanup)")
        except Exception as exc:
            logger.warning("Failed to stop GAE engine: %s", exc)

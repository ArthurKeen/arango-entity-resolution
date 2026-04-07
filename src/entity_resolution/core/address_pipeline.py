"""
AddressERPipeline: First-class YAML-driven address resolution pipeline.

Wraps :class:`AddressERService` with :class:`ConfigurableERPipeline`-style
configuration, CLI integration, and progress reporting.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from arango.database import StandardDatabase

from ..services.address_er_service import AddressERService

logger = logging.getLogger(__name__)


class AddressERPipeline:
    """Config-driven address entity resolution pipeline.

    This class wraps :class:`AddressERService` and adds:

    * YAML/dict-driven configuration
    * Progress callbacks
    * Structured result metadata
    * CLI integration (via ``arango-er address-resolve``)

    Parameters
    ----------
    db:
        ArangoDB database connection.
    config:
        Configuration dict.  Required keys: ``collection``,
        ``field_mapping``.  Optional: ``edge_collection``,
        ``max_block_size``, ``cluster``, ``create_edges``,
        ``clustering_backend``.

    Example
    -------
    ::

        config = {
            "collection": "addresses",
            "field_mapping": {
                "street": "ADDRESS_LINE_1",
                "city": "PRIMARY_TOWN",
                "state": "TERRITORY_CODE",
                "postal_code": "POSTAL_CODE",
            },
            "edge_collection": "address_sameAs",
            "max_block_size": 100,
            "cluster": True,
            "create_edges": True,
        }
        pipeline = AddressERPipeline(db, config)
        results = pipeline.run()
    """

    def __init__(self, db: StandardDatabase, config: Dict[str, Any]) -> None:
        self.db = db
        self.config = config
        self._results: Dict[str, Any] = {}

        required = ["collection", "field_mapping"]
        for key in required:
            if key not in config:
                raise ValueError(f"Missing required config key: '{key}'")

        service_config = {
            "max_block_size": config.get("max_block_size", 100),
            "blocking_mode": config.get("blocking_mode", "single_query"),
            "shard_key_field": config.get("shard_key_field"),
            "shard_key_prefix_length": config.get("shard_key_prefix_length", 3),
            "edge_loading_method": config.get("edge_loading_method", "auto"),
            "edge_count_threshold_for_csv": config.get("edge_count_threshold_for_csv", 100_000),
            "min_bm25_score": config.get("min_bm25_score", 2.0),
            "batch_size": config.get("batch_size", 5000),
        }

        self.service = AddressERService(
            db=db,
            collection=config["collection"],
            field_mapping=config["field_mapping"],
            edge_collection=config.get("edge_collection", "address_sameAs"),
            config=service_config,
        )

    @classmethod
    def from_yaml(cls, db: StandardDatabase, yaml_path: str) -> "AddressERPipeline":
        """Create a pipeline from a YAML config file."""
        import yaml

        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        addr_config = config.get("address_resolution", config)
        return cls(db, addr_config)

    def run(
        self,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute the full address resolution pipeline.

        Steps:
        1. Setup infrastructure (analyzers, views)
        2. Run blocking and edge creation
        3. Optional WCC clustering
        4. Collect and return results

        Parameters
        ----------
        progress_callback:
            Optional callable ``(step_name, pct)`` for progress updates.

        Returns
        -------
        dict
            Pipeline results including ``edges_created``, ``clusters``,
            ``execution_time_seconds``, and per-step timings.
        """
        start = time.time()
        results: Dict[str, Any] = {
            "collection": self.config["collection"],
            "steps": [],
        }

        def _report(step: str, pct: float):
            if progress_callback:
                progress_callback(step, pct)
            logger.info("Step: %s (%.0f%%)", step, pct * 100)

        # Step 1: Infrastructure
        _report("setup_infrastructure", 0.1)
        step_start = time.time()
        self.service.setup_infrastructure()
        results["steps"].append({
            "name": "setup_infrastructure",
            "elapsed_seconds": round(time.time() - step_start, 3),
        })

        # Step 2: Run ER
        _report("run_entity_resolution", 0.3)
        step_start = time.time()
        er_results = self.service.run(
            max_block_size=self.config.get("max_block_size", 100),
            create_edges=self.config.get("create_edges", True),
            cluster=self.config.get("cluster", True),
        )
        results["steps"].append({
            "name": "entity_resolution",
            "elapsed_seconds": round(time.time() - step_start, 3),
        })

        results.update({
            "edges_created": er_results.get("edges_created", 0),
            "total_pairs": er_results.get("total_pairs", 0),
            "clusters": er_results.get("clusters", []),
            "cluster_count": len(er_results.get("clusters", [])),
        })

        _report("complete", 1.0)
        results["execution_time_seconds"] = round(time.time() - start, 3)

        self._results = results
        return results

    def get_results(self) -> Dict[str, Any]:
        """Return results from the most recent run."""
        return self._results.copy()

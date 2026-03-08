"""
Configuration-driven ER pipeline.

Runs complete entity resolution pipelines from YAML/JSON configuration files.
"""

from typing import Dict, Any, Optional, Union
from pathlib import Path
from arango.database import StandardDatabase
import logging
import time

from ..config.er_config import ERPipelineConfig
from ..services.batch_similarity_service import BatchSimilarityService
from ..services.similarity_edge_service import SimilarityEdgeService
from ..services.wcc_clustering_service import WCCClusteringService
from ..services.address_er_service import AddressERService
from ..strategies import CollectBlockingStrategy, BM25BlockingStrategy


class ConfigurableERPipeline:
    """
    ER pipeline that runs from configuration.
    
    This class orchestrates a complete ER pipeline based on configuration,
    automatically instantiating and configuring services.
    
    Example:
        ```python
        from entity_resolution.core import ConfigurableERPipeline
        
        pipeline = ConfigurableERPipeline(
            db=db,
            config_path='er_config.yaml'
        )
        
        results = pipeline.run()
        
        print(f"Blocks: {results['blocking']['blocks_found']}")
        print(f"Matches: {results['similarity']['matches_found']}")
        print(f"Clusters: {results['clustering']['clusters_found']}")
        ```
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        config: Optional[ERPipelineConfig] = None,
        config_path: Optional[Union[str, Path]] = None
    ):
        """
        Initialize configurable ER pipeline.
        
        Args:
            db: ArangoDB database connection
            config: ERPipelineConfig instance (if provided, config_path is ignored)
            config_path: Path to YAML/JSON configuration file
        
        Raises:
            ValueError: If neither config nor config_path provided
            FileNotFoundError: If config_path doesn't exist
        """
        if config is None and config_path is None:
            raise ValueError("Either config or config_path must be provided")
        
        self.db = db
        
        # Load configuration
        if config is not None:
            self.config = config
        else:
            config_path = Path(config_path)
            if config_path.suffix.lower() == '.json':
                self.config = ERPipelineConfig.from_json(config_path)
            else:
                self.config = ERPipelineConfig.from_yaml(config_path)
        
        # Validate configuration
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
        
        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._active_learning_stats: Dict[str, Any] = {
            'enabled': bool(getattr(self.config, 'active_learning', None) and self.config.active_learning.enabled),
            'pairs_reviewed': 0,
            'llm_calls': 0,
            'score_overrides': 0,
            'feedback_collection': None,
        }
    
    def run(self) -> Dict[str, Any]:
        """
        Run complete ER pipeline based on configuration.
        
        Pipeline phases:
        1. Setup (if needed, e.g., for address ER)
        2. Blocking (based on config.blocking)
        3. Similarity (based on config.similarity)
        4. Edge creation (based on config.edges)
        5. Clustering (based on config.clustering)
        
        Returns:
            Results dictionary with metrics for each phase:
            {
                'blocking': {
                    'blocks_found': int,
                    'candidate_pairs': int,
                    'runtime_seconds': float
                },
                'similarity': {
                    'matches_found': int,
                    'pairs_processed': int,
                    'runtime_seconds': float
                },
                'edges': {
                    'edges_created': int,
                    'runtime_seconds': float
                },
                'clustering': {
                    'clusters_found': int,
                    'runtime_seconds': float
                },
                'total_runtime_seconds': float
            }
        """
        start_time = time.time()
        results = {
            'blocking': {},
            'similarity': {},
            'edges': {},
            'clustering': {},
            'total_runtime_seconds': 0.0
        }
        
        self.logger.info("=" * 80)
        self.logger.info("CONFIGURABLE ER PIPELINE")
        self.logger.info("=" * 80)
        self.logger.info(f"Entity Type: {self.config.entity_type}")
        self.logger.info(f"Collection: {self.config.collection_name}")
        self.logger.info("")
        
        # Special handling for address ER
        if self.config.entity_type == 'address':
            return self._run_address_er(results, start_time)
        
        # Standard ER pipeline
        # Phase 1: Blocking
        self.logger.info("Phase 1: Blocking...")
        blocking_start = time.time()
        candidate_pairs = self._run_blocking()
        blocking_time = time.time() - blocking_start
        
        results['blocking'] = {
            'candidate_pairs': len(candidate_pairs),
            'runtime_seconds': round(blocking_time, 2)
        }
        self.logger.info(f"[OK] Found {len(candidate_pairs):,} candidate pairs")
        
        # Phase 2: Similarity
        if candidate_pairs and self.config.similarity:
            self.logger.info("Phase 2: Similarity computation...")
            similarity_start = time.time()
            matches = self._run_similarity(candidate_pairs)
            similarity_time = time.time() - similarity_start
            
            results['similarity'] = {
                'matches_found': len(matches),
                'pairs_processed': len(candidate_pairs),
                'runtime_seconds': round(similarity_time, 2),
                'active_learning': self._active_learning_stats.copy(),
            }
            self.logger.info(f"[OK] Found {len(matches):,} matches")
        else:
            matches = []
            results['similarity'] = {
                'matches_found': 0,
                'pairs_processed': 0,
                'runtime_seconds': 0.0,
                'active_learning': self._active_learning_stats.copy(),
            }
        
        # Phase 3: Edge Creation
        if matches:
            self.logger.info("Phase 3: Edge creation...")
            edge_start = time.time()
            edges_created = self._run_edge_creation(matches)
            edge_time = time.time() - edge_start
            
            results['edges'] = {
                'edges_created': edges_created,
                'runtime_seconds': round(edge_time, 2)
            }
            self.logger.info(f"[OK] Created {edges_created:,} edges")
        else:
            results['edges'] = {
                'edges_created': 0,
                'runtime_seconds': 0.0
            }

        # Phase 4: Clustering — only run when edges actually exist
        edges_created = results.get('edges', {}).get('edges_created', 0)
        if self.config.clustering.store_results and edges_created > 0:
            self.logger.info("Phase 4: Clustering...")
            cluster_start = time.time()
            clusters = self._run_clustering()
            cluster_time = time.time() - cluster_start

            results['clustering'] = {
                'clusters_found': len(clusters),
                'runtime_seconds': round(cluster_time, 2)
            }
            self.logger.info(f"[OK] Found {len(clusters):,} clusters")
        else:
            results['clustering'] = {
                'clusters_found': 0,
                'runtime_seconds': 0.0
            }
        
        results['total_runtime_seconds'] = round(time.time() - start_time, 2)
        
        # Summary
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"Candidate Pairs: {results['blocking']['candidate_pairs']:,}")
        self.logger.info(f"Matches Found: {results['similarity']['matches_found']:,}")
        self.logger.info(f"Edges Created: {results['edges']['edges_created']:,}")
        self.logger.info(f"Clusters Found: {results['clustering']['clusters_found']:,}")
        self.logger.info(f"Total Runtime: {results['total_runtime_seconds']:.2f}s")
        
        return results
    
    def _run_address_er(
        self,
        results: Dict[str, Any],
        start_time: float
    ) -> Dict[str, Any]:
        """Run address-specific ER pipeline."""
        # Use AddressERService for address ER
        address_service = AddressERService(
            db=self.db,
            collection=self.config.collection_name,
            edge_collection=self.config.edge_collection,
            config={
                'max_block_size': self.config.blocking.max_block_size,
                'min_bm25_score': 2.0,
                'batch_size': self.config.similarity.batch_size
            }
        )
        
        # Setup infrastructure
        address_service.setup_infrastructure()
        
        # Run address ER
        address_results = address_service.run(
            max_block_size=self.config.blocking.max_block_size,
            create_edges=True,
            cluster=self.config.clustering.store_results,
            min_cluster_size=self.config.clustering.min_cluster_size
        )
        
        # Map results to standard format
        results['blocking'] = {
            'blocks_found': address_results['blocks_found'],
            'addresses_matched': address_results['addresses_matched'],
            'runtime_seconds': 0.0  # Included in total
        }
        results['similarity'] = {
            'matches_found': address_results['addresses_matched'],
            'runtime_seconds': 0.0
        }
        results['edges'] = {
            'edges_created': address_results['edges_created'],
            'runtime_seconds': 0.0
        }
        results['clustering'] = {
            'clusters_found': address_results.get('clusters_found', 0),
            'runtime_seconds': 0.0
        }
        results['total_runtime_seconds'] = address_results['runtime_seconds']
        
        return results
    
    def _run_blocking(self) -> list:
        """Run blocking phase based on configuration."""
        strategy = self.config.blocking.strategy
        
        if strategy == 'exact':
            # Use CollectBlockingStrategy
            blocking_fields, computed_fields = self._get_blocking_fields()
            blocking_strategy = CollectBlockingStrategy(
                db=self.db,
                collection=self.config.collection_name,
                blocking_fields=blocking_fields,
                max_block_size=self.config.blocking.max_block_size,
                min_block_size=self.config.blocking.min_block_size,
                computed_fields=computed_fields or None,
            )
            return list(blocking_strategy.generate_candidates())
        
        elif strategy in ('bm25', 'arangosearch'):
            # Note: 'arangosearch' is a deprecated alias for 'bm25'.
            # Resolve search_field and blocking_field from config.
            # Explicit attributes on BlockingConfig take precedence; fall back to
            # the first two entries in the generic `fields` list so callers that
            # don't know about the BM25-specific keys still work.
            generic_fields, _ = self._get_blocking_fields()

            search_field = (
                self.config.blocking.search_field
                or (generic_fields[0] if generic_fields else None)
            )
            blocking_field = (
                self.config.blocking.blocking_field
                if self.config.blocking.blocking_field is not None
                else (generic_fields[1] if len(generic_fields) > 1 else None)
            )

            if not search_field:
                raise ValueError(
                    "BM25 blocking strategy requires a search_field. "
                    "Set blocking.search_field in your config, or provide at least "
                    "one entry in blocking.fields."
                )

            blocking_strategy = BM25BlockingStrategy(
                db=self.db,
                collection=self.config.collection_name,
                search_view=f"{self.config.collection_name}_search",
                search_field=search_field,
                blocking_field=blocking_field,
            )
            return list(blocking_strategy.generate_candidates())
        
        else:
            self.logger.warning(f"Unknown blocking strategy: {strategy}")
            return []


    def _get_blocking_fields(self) -> tuple[list, dict]:
        """
        Extract blocking field names (and optional computed fields) from config.

        Delegates to ``BlockingConfig.parse_fields()`` (H3 — single canonical
        implementation shared with ERPipelineConfig; no local duplication).

        Returns:
            (field_names, computed_fields)
        """
        return self.config.blocking.parse_fields()

    
    def _run_similarity(self, candidate_pairs: list) -> list:
        """Run similarity phase based on configuration."""
        if not candidate_pairs:
            return []

        # Derive field weights: use configured weights, or fall back to equal
        # weights across every blocking field so BatchSimilarityService does not
        # reject an empty dict.
        field_weights = self.config.similarity.field_weights
        if not field_weights:
            blocking_field_names, _ = self.config.blocking.parse_fields()
            if blocking_field_names:
                weight = 1.0 / len(blocking_field_names)
                field_weights = {f: weight for f in blocking_field_names}

        similarity_service = BatchSimilarityService(
            db=self.db,
            collection=self.config.collection_name,
            field_weights=field_weights,
            similarity_algorithm=self.config.similarity.algorithm,
            batch_size=self.config.similarity.batch_size,
            field_transformers=getattr(self.config.similarity, "transformers", {}),
        )

        # BatchSimilarityService.compute_similarities expects (key1, key2) tuples;
        # blocking strategies return rich dicts — normalise at the boundary.
        if candidate_pairs and isinstance(candidate_pairs[0], dict):
            pair_tuples = [(p["doc1_key"], p["doc2_key"]) for p in candidate_pairs]
        else:
            pair_tuples = candidate_pairs

        active_learning_cfg = getattr(self.config, 'active_learning', None)
        if active_learning_cfg and active_learning_cfg.enabled:
            return self._run_similarity_with_active_learning(similarity_service, pair_tuples)

        matches = similarity_service.compute_similarities(
            candidate_pairs=pair_tuples,
            threshold=self.config.similarity.threshold
        )

        return matches

    def _run_similarity_with_active_learning(
        self,
        similarity_service: BatchSimilarityService,
        pair_tuples: list[tuple[str, str]],
    ) -> list:
        """Run similarity plus optional LLM verification for uncertain pairs."""
        verifier = self._build_active_learning_verifier()
        active_cfg = self.config.active_learning
        threshold = min(self.config.similarity.threshold, active_cfg.low_threshold)
        detailed_matches = similarity_service.compute_similarities_detailed(
            candidate_pairs=pair_tuples,
            threshold=threshold,
        )

        doc_cache = similarity_service._batch_fetch_documents(  # noqa: SLF001 - intentional reuse
            list({key for pair in pair_tuples for key in pair})
        )

        matches = []
        self._active_learning_stats = {
            'enabled': True,
            'pairs_reviewed': 0,
            'llm_calls': 0,
            'score_overrides': 0,
            'feedback_collection': verifier.store.collection,
        }

        for item in detailed_matches:
            score = item['weighted_score']
            final_score = score
            self._active_learning_stats['pairs_reviewed'] += 1

            if verifier._verifier.needs_verification(score):  # noqa: SLF001 - narrow pipeline integration
                field_scores = self._format_field_scores_for_llm(item['field_scores'])
                result = verifier.verify(
                    doc_cache.get(item['doc1_key'], {'_key': item['doc1_key']}),
                    doc_cache.get(item['doc2_key'], {'_key': item['doc2_key']}),
                    score=score,
                    field_scores=field_scores,
                )
                if result.get('llm_called'):
                    self._active_learning_stats['llm_calls'] += 1
                if result.get('score_override') is not None:
                    final_score = result['score_override']
                    self._active_learning_stats['score_overrides'] += 1

            if final_score >= self.config.similarity.threshold:
                matches.append((item['doc1_key'], item['doc2_key'], round(final_score, 4)))

        matches.sort(key=lambda x: x[2], reverse=True)
        return matches

    def _build_active_learning_verifier(self):
        """Construct the active learning verifier for this pipeline run."""
        from entity_resolution.reasoning.feedback import AdaptiveLLMVerifier, FeedbackStore

        cfg = self.config.active_learning
        feedback_collection = cfg.feedback_collection or f"{self.config.collection_name}_llm_feedback"
        store = FeedbackStore(self.db, collection=feedback_collection)
        return AdaptiveLLMVerifier(
            feedback_store=store,
            refresh_every=cfg.refresh_every,
            model=cfg.model,
            low_threshold=cfg.low_threshold,
            high_threshold=cfg.high_threshold,
            entity_type=self.config.entity_type,
            optimizer_target_precision=cfg.optimizer_target_precision,
            optimizer_min_samples=cfg.optimizer_min_samples,
        )

    def _format_field_scores_for_llm(self, field_scores: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """Convert plain per-field scores into the structure expected by LLM prompts."""
        return {
            field: {
                'score': score,
                'method': self.config.similarity.algorithm,
            }
            for field, score in field_scores.items()
        }


    def _run_edge_creation(self, matches: list) -> int:
        """Run edge creation phase."""
        if not matches:
            return 0
        
        edge_service = SimilarityEdgeService(
            db=self.db,
            edge_collection=self.config.edge_collection,
            batch_size=1000
        )
        
        edges_created = edge_service.create_edges(
            matches=matches,
            metadata={
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'method': 'configurable_pipeline'
            }
        )
        
        return edges_created
    
    def _run_clustering(self) -> list:
        """Run clustering phase based on configuration."""
        clustering_service = WCCClusteringService(
            db=self.db,
            edge_collection=self.config.edge_collection,
            cluster_collection=self.config.cluster_collection,
            min_cluster_size=self.config.clustering.min_cluster_size
        )
        
        clusters = clustering_service.cluster(
            store_results=self.config.clustering.store_results
        )
        
        return clusters
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"ConfigurableERPipeline("
                f"entity_type='{self.config.entity_type}', "
                f"collection='{self.config.collection_name}')")


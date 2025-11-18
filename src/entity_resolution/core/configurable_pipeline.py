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
from ..services.blocking_service import BlockingService
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
        self.logger.info(f"✓ Found {len(candidate_pairs):,} candidate pairs")
        
        # Phase 2: Similarity
        if candidate_pairs and self.config.similarity:
            self.logger.info("Phase 2: Similarity computation...")
            similarity_start = time.time()
            matches = self._run_similarity(candidate_pairs)
            similarity_time = time.time() - similarity_start
            
            results['similarity'] = {
                'matches_found': len(matches),
                'pairs_processed': len(candidate_pairs),
                'runtime_seconds': round(similarity_time, 2)
            }
            self.logger.info(f"✓ Found {len(matches):,} matches")
        else:
            matches = []
            results['similarity'] = {
                'matches_found': 0,
                'pairs_processed': 0,
                'runtime_seconds': 0.0
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
            self.logger.info(f"✓ Created {edges_created:,} edges")
        else:
            results['edges'] = {
                'edges_created': 0,
                'runtime_seconds': 0.0
            }
        
        # Phase 4: Clustering
        if self.config.clustering.store_results:
            self.logger.info("Phase 4: Clustering...")
            cluster_start = time.time()
            clusters = self._run_clustering()
            cluster_time = time.time() - cluster_start
            
            results['clustering'] = {
                'clusters_found': len(clusters),
                'runtime_seconds': round(cluster_time, 2)
            }
            self.logger.info(f"✓ Found {len(clusters):,} clusters")
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
            # Note: This is a simplified example - actual implementation
            # would need field configuration from config.blocking.fields
            blocking_strategy = CollectBlockingStrategy(
                db=self.db,
                collection=self.config.collection_name,
                blocking_fields=[],  # Would come from config
                max_block_size=self.config.blocking.max_block_size
            )
            return list(blocking_strategy.generate_candidates())
        
        elif strategy == 'bm25':
            # Use BM25BlockingStrategy
            # Note: Requires search view configuration
            blocking_strategy = BM25BlockingStrategy(
                db=self.db,
                collection=self.config.collection_name,
                search_view=f"{self.config.collection_name}_search",
                search_field='name',  # Would come from config
                blocking_field='state'  # Would come from config
            )
            return list(blocking_strategy.generate_candidates())
        
        else:
            self.logger.warning(f"Unknown blocking strategy: {strategy}")
            return []
    
    def _run_similarity(self, candidate_pairs: list) -> list:
        """Run similarity phase based on configuration."""
        if not candidate_pairs:
            return []
        
        similarity_service = BatchSimilarityService(
            db=self.db,
            collection=self.config.collection_name,
            field_weights=self.config.similarity.field_weights,
            similarity_algorithm=self.config.similarity.algorithm,
            batch_size=self.config.similarity.batch_size
        )
        
        matches = similarity_service.compute_similarities(
            candidate_pairs=candidate_pairs,
            threshold=self.config.similarity.threshold
        )
        
        return matches
    
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
            min_cluster_size=self.config.clustering.min_cluster_size,
            algorithm=self.config.clustering.wcc_algorithm
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


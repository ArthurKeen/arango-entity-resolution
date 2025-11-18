"""
Address Entity Resolution Service

Complete address deduplication pipeline using ArangoDB analyzers and
ArangoSearch views. Handles address normalization, blocking, and edge creation.
"""

from typing import Dict, List, Any, Optional, Tuple
from arango.database import StandardDatabase
from arango.collection import EdgeCollection, StandardCollection
import time
from datetime import datetime
import logging

from .wcc_clustering_service import WCCClusteringService
from ..utils.validation import validate_collection_name, validate_field_name


class AddressERService:
    """
    Complete address entity resolution pipeline.
    
    This service provides a complete end-to-end address deduplication solution:
    - Custom analyzer setup for address normalization
    - ArangoSearch view creation
    - Blocking with registered agent handling
    - Edge creation
    - Optional clustering
    
    Features:
    - Configurable field mapping (works with any address schema)
    - Max block size limit (prevents edge explosion from registered agents)
    - Bulk edge creation
    - Integration with WCC clustering
    
    Example:
        ```python
        service = AddressERService(
            db=db,
            collection='addresses',
            field_mapping={
                'street': 'ADDRESS_LINE_1',
                'city': 'PRIMARY_TOWN',
                'state': 'TERRITORY_CODE',
                'postal_code': 'POSTAL_CODE'
            },
            edge_collection='address_sameAs'
        )
        
        # Setup infrastructure (once)
        service.setup_infrastructure()
        
        # Run ER
        results = service.run(
            max_block_size=100,
            create_edges=True,
            cluster=True
        )
        ```
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str = "addresses",
        field_mapping: Optional[Dict[str, str]] = None,
        edge_collection: str = "address_sameAs",
        search_view_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize address ER service.
        
        Args:
            db: ArangoDB database connection
            collection: Address collection name
            field_mapping: Dictionary mapping logical field names to actual
                collection field names:
                {
                    'street': 'ADDRESS_LINE_1',
                    'city': 'PRIMARY_TOWN',
                    'state': 'TERRITORY_CODE',
                    'postal_code': 'POSTAL_CODE'
                }
                If None, uses default mapping.
            edge_collection: Name of edge collection for sameAs relationships
            search_view_name: Name of ArangoSearch view (auto-generated if None)
            config: Additional configuration dictionary:
                {
                    'max_block_size': 100,
                    'min_bm25_score': 2.0,
                    'batch_size': 5000
                }
        """
        self.db = db
        # Validate collection names to prevent AQL injection
        self.collection = validate_collection_name(collection)
        self.edge_collection = validate_collection_name(edge_collection)
        self.search_view_name = search_view_name or f"{collection}_search"
        
        # Default field mapping
        self.field_mapping = field_mapping or {
            'street': 'ADDRESS_LINE_1',
            'city': 'PRIMARY_TOWN',
            'state': 'TERRITORY_CODE',
            'postal_code': 'POSTAL_CODE'
        }
        # Validate all field names in mapping to prevent AQL injection
        for logical_field, actual_field in self.field_mapping.items():
            validate_field_name(logical_field)
            validate_field_name(actual_field)
        
        # Configuration
        self.config = config or {}
        self.max_block_size = self.config.get('max_block_size', 100)
        self.min_bm25_score = self.config.get('min_bm25_score', 2.0)
        self.batch_size = self.config.get('batch_size', 5000)
        
        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Get actual field names from mapping
        self.street_field = self.field_mapping['street']
        self.city_field = self.field_mapping['city']
        self.state_field = self.field_mapping['state']
        self.postal_code_field = self.field_mapping.get('postal_code', 'POSTAL_CODE')
    
    def setup_infrastructure(self) -> Dict[str, Any]:
        """
        Set up analyzers and search views.
        
        Creates:
        - address_normalizer: Pipeline analyzer for street addresses
        - text_normalizer: Simple normalizer for city/state
        - ArangoSearch view with proper field mappings
        
        Returns:
            Dictionary with setup results:
            {
                'analyzers_created': ['address_normalizer', 'text_normalizer'],
                'view_created': 'addresses_search',
                'view_build_wait_seconds': 10
            }
        """
        self.logger.info("Setting up address ER infrastructure...")
        
        results = {
            'analyzers_created': [],
            'view_created': None,
            'view_build_wait_seconds': 10
        }
        
        # Setup analyzers
        analyzers_created = self._setup_analyzers()
        results['analyzers_created'] = analyzers_created
        
        # Setup search view
        view_created = self._setup_search_view()
        results['view_created'] = view_created
        
        if view_created:
            self.logger.info(f"  Waiting {results['view_build_wait_seconds']}s for view to build indices...")
            time.sleep(results['view_build_wait_seconds'])
        
        self.logger.info("✓ Infrastructure setup complete")
        
        return results
    
    def run(
        self,
        max_block_size: Optional[int] = None,
        create_edges: bool = True,
        cluster: bool = False,
        min_cluster_size: int = 2
    ) -> Dict[str, Any]:
        """
        Run complete address ER pipeline.
        
        Args:
            max_block_size: Override max block size (default from config)
            create_edges: Whether to create sameAs edges. Default True.
            cluster: Whether to run WCC clustering. Default False.
            min_cluster_size: Minimum cluster size for clustering. Default 2.
        
        Returns:
            Results dictionary:
            {
                'blocks_found': int,
                'addresses_matched': int,
                'edges_created': int,
                'clusters_found': Optional[int],
                'runtime_seconds': float
            }
        """
        start_time = time.time()
        
        # Use provided max_block_size or config default
        effective_max_block_size = max_block_size or self.max_block_size
        
        self.logger.info("=" * 80)
        self.logger.info("ADDRESS ENTITY RESOLUTION PIPELINE")
        self.logger.info("=" * 80)
        self.logger.info(f"Collection: {self.collection}")
        self.logger.info(f"Max block size: {effective_max_block_size}")
        self.logger.info("")
        
        results = {}
        
        # Phase 1: Blocking
        self.logger.info("Phase 1: Finding duplicate addresses...")
        blocks, total_addresses = self._find_duplicate_addresses(effective_max_block_size)
        results['blocks_found'] = len(blocks)
        results['addresses_matched'] = total_addresses
        
        # Phase 2: Edge Creation
        edges_created = 0
        if create_edges:
            self.logger.info("Phase 2: Creating sameAs edges...")
            edges_created = self._create_edges(blocks)
            results['edges_created'] = edges_created
        else:
            results['edges_created'] = 0
        
        # Phase 3: Clustering (optional)
        clusters_found = None
        if cluster:
            self.logger.info("Phase 3: Clustering addresses...")
            clusters = self._cluster_addresses(min_cluster_size)
            clusters_found = len(clusters)
            results['clusters_found'] = clusters_found
        else:
            results['clusters_found'] = None
        
        results['runtime_seconds'] = round(time.time() - start_time, 2)
        
        # Summary
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"Blocks found: {results['blocks_found']:,}")
        self.logger.info(f"Addresses matched: {results['addresses_matched']:,}")
        self.logger.info(f"Edges created: {results['edges_created']:,}")
        if clusters_found is not None:
            self.logger.info(f"Clusters found: {clusters_found:,}")
        self.logger.info(f"Runtime: {results['runtime_seconds']:.2f}s")
        
        return results
    
    def _setup_analyzers(self) -> List[str]:
        """
        Create custom analyzers for address normalization.
        
        Returns:
            List of analyzer names that were created
        """
        self.logger.info("Setting up custom analyzers...")
        
        analyzers_to_create = [
            {
                "name": "address_normalizer",
                "type": "pipeline",
                "properties": {
                    "pipeline": [
                        {
                            "type": "norm",
                            "properties": {
                                "locale": "en",
                                "case": "lower",
                                "accent": False
                            }
                        },
                        {
                            "type": "delimiter",
                            "properties": {
                                "delimiter": ".,-()"
                            }
                        },
                        {
                            "type": "stem",
                            "properties": {
                                "locale": "en"
                            }
                        }
                    ]
                }
            },
            {
                "name": "text_normalizer",
                "type": "norm",
                "properties": {
                    "locale": "en",
                    "case": "lower",
                    "accent": False
                }
            }
        ]
        
        # Get existing analyzers
        existing = {a['name'] for a in self.db.analyzers()}
        created = []
        
        for analyzer_def in analyzers_to_create:
            name = analyzer_def['name']
            if name not in existing:
                try:
                    self.db.create_analyzer(
                        name=name,
                        analyzer_type=analyzer_def['type'],
                        properties=analyzer_def['properties']
                    )
                    self.logger.info(f"  ✓ Created analyzer: {name}")
                    created.append(name)
                except Exception as e:
                    if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                        self.logger.info(f"  - Analyzer exists: {name}")
                    else:
                        self.logger.warning(f"  ! Could not create {name}: {e}")
            else:
                self.logger.info(f"  - Analyzer exists: {name}")
        
        return created
    
    def _setup_search_view(self) -> Optional[str]:
        """
        Create ArangoSearch view for address matching.
        
        Returns:
            View name if created, None otherwise
        """
        self.logger.info(f"Setting up ArangoSearch view: {self.search_view_name}...")
        
        # Check if view exists
        existing_views = {v['name'] for v in self.db.views()}
        
        if self.search_view_name in existing_views:
            self.logger.info(f"  - View exists: {self.search_view_name}")
            self.logger.info("  - Dropping and recreating to ensure correct configuration...")
            try:
                self.db.delete_view(self.search_view_name)
            except Exception as e:
                self.logger.warning(f"  ! Could not delete view: {e}")
        
        # Create view
        try:
            self.db.create_arangosearch_view(
                name=self.search_view_name,
                properties={
                    'links': {
                        self.collection: {
                            'includeAllFields': False,
                            'fields': {
                                self.street_field: {
                                    'analyzers': ['address_normalizer', 'text_en']
                                },
                                self.city_field: {
                                    'analyzers': ['text_normalizer']
                                },
                                self.state_field: {
                                    'analyzers': ['identity']
                                },
                                self.postal_code_field: {
                                    'analyzers': ['identity']
                                }
                            }
                        }
                    }
                }
            )
            self.logger.info(f"  ✓ Created view: {self.search_view_name}")
            return self.search_view_name
        except Exception as e:
            self.logger.error(f"  ✗ Failed to create view: {e}")
            return None
    
    def _find_duplicate_addresses(
        self,
        max_block_size: int
    ) -> Tuple[Dict[str, List[str]], int]:
        """
        Find duplicate addresses using normalized blocking.
        
        Strategy:
        - Normalize street, city, state, zip5
        - Group by normalized address
        - Skip blocks > max_block_size (registered agents)
        - Create address groups
        
        Args:
            max_block_size: Maximum addresses per block
        
        Returns:
            Tuple of (blocks dict, total addresses matched)
        """
        self.logger.info("Finding duplicate addresses using normalized blocking...")
        
        query = f"""
        FOR addr IN {self.collection}
            FILTER addr.{self.street_field} != null AND addr.{self.street_field} != 'NULL'
            FILTER addr.{self.city_field} != null
            FILTER addr.{self.state_field} != null
            
            // Normalize address components
            LET norm_street = UPPER(REGEX_REPLACE(TRIM(addr.{self.street_field}), '[^A-Z0-9\\s]', ''))
            LET norm_city = UPPER(TRIM(addr.{self.city_field}))
            LET state = UPPER(TRIM(addr.{self.state_field}))
            LET zip5 = SUBSTRING(REGEX_REPLACE(addr.{self.postal_code_field}, '[^0-9]', ''), 0, 5)
            
            FILTER LENGTH(norm_street) > 0 AND LENGTH(norm_city) > 0 AND LENGTH(state) > 0
            
            LET block_key = CONCAT_SEPARATOR('|', norm_street, norm_city, state, zip5)
            
            COLLECT block = block_key INTO group = addr._id
            
            LET block_size = LENGTH(group)
            
            // Only blocks with 2-max_block_size addresses (skip registered agents)
            FILTER block_size >= 2 AND block_size <= @max_block_size
            
            RETURN {{
                block_key: block,
                addresses: group,
                size: block_size
            }}
        """
        
        cursor = self.db.aql.execute(
            query,
            bind_vars={'max_block_size': max_block_size},
            batch_size=self.batch_size,
            stream=True
        )
        
        blocks = {}
        total_addresses = 0
        
        for result in cursor:
            block_key = result['block_key']
            addresses = result['addresses']
            size = result['size']
            
            blocks[block_key] = addresses
            total_addresses += size
        
        self.logger.info(f"✓ Found {len(blocks):,} duplicate address groups")
        self.logger.info(f"✓ Total addresses in groups: {total_addresses:,}")
        
        return blocks, total_addresses
    
    def _create_edges(self, blocks: Dict[str, List[str]]) -> int:
        """
        Create sameAs edges for duplicate addresses.
        
        Args:
            blocks: Dictionary mapping block keys to lists of address IDs
        
        Returns:
            Number of edges created
        """
        # Ensure edge collection exists
        if not self.db.has_collection(self.edge_collection):
            self.logger.info(f"Creating {self.edge_collection} edge collection...")
            self.db.create_collection(self.edge_collection, edge=True)
        else:
            self.logger.info(f"Truncating existing {self.edge_collection} collection...")
            self.db.collection(self.edge_collection).truncate()
        
        # Calculate total edges (each block of n addresses creates n*(n-1)/2 edges)
        total_edges = sum(
            (len(addrs) * (len(addrs) - 1)) // 2
            for addrs in blocks.values()
        )
        
        self.logger.info(f"Will create ~{total_edges:,} edges from {len(blocks):,} blocks")
        
        # Create edges in batches
        edge_collection: EdgeCollection = self.db.collection(self.edge_collection)
        edges_created = 0
        
        for block_key, addresses in blocks.items():
            # Create edges between all pairs in the block
            edge_docs = []
            
            for i, addr1_id in enumerate(addresses):
                for addr2_id in addresses[i + 1:]:
                    edge_docs.append({
                        '_from': addr1_id,
                        '_to': addr2_id,
                        'block_key': block_key,
                        'timestamp': datetime.now().isoformat(),
                        'type': 'address_sameAs'
                    })
            
            # Insert batch
            if edge_docs:
                edge_collection.insert_many(edge_docs)
                edges_created += len(edge_docs)
        
        self.logger.info(f"✓ Created {edges_created:,} sameAs edges")
        
        return edges_created
    
    def _cluster_addresses(self, min_cluster_size: int) -> List[List[str]]:
        """
        Cluster addresses using WCC clustering.
        
        Args:
            min_cluster_size: Minimum cluster size
        
        Returns:
            List of clusters
        """
        clustering_service = WCCClusteringService(
            db=self.db,
            edge_collection=self.edge_collection,
            cluster_collection=f'{self.collection}_clusters',
            min_cluster_size=min_cluster_size,
            algorithm='python_dfs'  # Use Python DFS for reliability
        )
        
        clusters = clustering_service.cluster(store_results=True)
        
        return clusters
    
    def __repr__(self) -> str:
        """String representation."""
        return (f"AddressERService("
                f"collection='{self.collection}', "
                f"edge_collection='{self.edge_collection}')")


"""
Address Entity Resolution Service

Complete address deduplication pipeline using ArangoDB analyzers and
ArangoSearch views. Handles address normalization, blocking, and edge creation.
"""

from typing import Dict, List, Any, Optional, Tuple
from arango.database import StandardDatabase
from arango.collection import EdgeCollection, StandardCollection
import shutil
import time
from datetime import datetime
import logging

from .wcc_clustering_service import WCCClusteringService
from ..utils.validation import validate_collection_name, validate_field_name, sanitize_string_for_display
from ..utils.constants import DEFAULT_BATCH_SIZE, DEFAULT_EDGE_BATCH_SIZE, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USERNAME


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
        # Standard usage (API method - good for <100K edges)
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
        
        # Run ER with API method (default)
        results = service.run(
            max_block_size=100,
            create_edges=True,
            cluster=True
        )
        
        # For large datasets (>100K edges), use CSV method for 10-20x faster loading
        service_csv = AddressERService(
            db=db,
            collection='addresses',
            config={
                'edge_loading_method': 'csv',  # Use CSV + arangoimport
                'csv_path': '/tmp/edges.csv'  # Optional: specify path
            }
        )
        
        results = service_csv.run(create_edges=True)
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
                    'batch_size': DEFAULT_BATCH_SIZE,
                    'edge_loading_method': 'auto',  # 'auto', 'api', or 'csv'
                    'edge_count_threshold_for_csv': 100_000,
                    'edge_batch_size': DEFAULT_EDGE_BATCH_SIZE,
                    'csv_path': None,
                    'blocking_mode': 'single_query',  # 'single_query' or 'shard_parallel'
                    'shard_key_field': None,  # defaults to postal_code field
                    'shard_key_prefix_length': 3,
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
        self.batch_size = self.config.get('batch_size', DEFAULT_BATCH_SIZE)
        self.edge_loading_method = self.config.get('edge_loading_method', 'auto')
        self.edge_count_threshold_for_csv = self.config.get('edge_count_threshold_for_csv', 100_000)
        self.edge_batch_size = self.config.get('edge_batch_size', DEFAULT_EDGE_BATCH_SIZE)
        self.csv_path = self.config.get('csv_path', None)
        self.blocking_mode = self.config.get('blocking_mode', 'single_query')
        self.shard_key_field = self.config.get('shard_key_field')
        self.shard_key_prefix_length = self.config.get('shard_key_prefix_length', 3)
        
        # Initialize logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        self._arangoimport_available = shutil.which('arangoimport') is not None
        
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
        
        self.logger.info("[OK] Infrastructure setup complete")
        
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
        
        Edge Loading Methods:
            The method used for edge creation is controlled by config['edge_loading_method']:
            - 'api' (default): Optimized API batching - good for <100K edges
            - 'csv': CSV export + arangoimport - 10-20x faster for >100K edges
            
            For large datasets (>100K edges), use 'csv' method for best performance.
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
        blocks, total_addresses, skip_stats = self._find_duplicate_addresses(effective_max_block_size)
        results['blocks_found'] = len(blocks)
        results['addresses_matched'] = total_addresses
        results['blocks_skipped_max_size'] = skip_stats['blocks_skipped_max_size']
        results['largest_skipped_block_size'] = skip_stats['largest_skipped_block_size']
        results['skipped_block_samples'] = skip_stats['skipped_block_samples']
        
        # Phase 2: Edge Creation
        edges_created = 0
        estimated_edges = sum(
            (len(addrs) * (len(addrs) - 1)) // 2
            for addrs in blocks.values()
        )
        
        if create_edges:
            self.logger.info("Phase 2: Creating sameAs edges...")

            loading_method = self.edge_loading_method
            if loading_method == 'auto':
                if estimated_edges > self.edge_count_threshold_for_csv and self._arangoimport_available:
                    loading_method = 'csv'
                    self.logger.info(
                        f"  Auto-selected CSV loading: {estimated_edges:,} estimated edges "
                        f"> threshold {self.edge_count_threshold_for_csv:,} and arangoimport is available"
                    )
                else:
                    loading_method = 'api'
                    reason = (
                        f"{estimated_edges:,} estimated edges <= threshold {self.edge_count_threshold_for_csv:,}"
                        if estimated_edges <= self.edge_count_threshold_for_csv
                        else "arangoimport not found on PATH"
                    )
                    self.logger.info(f"  Auto-selected API loading: {reason}")

            if loading_method == 'api' and estimated_edges > self.edge_count_threshold_for_csv:
                self.logger.warning(
                    f"API edge loading with {estimated_edges:,} estimated edges may be slow. "
                    "Consider edge_loading_method='csv' or 'auto' for large datasets."
                )

            self.logger.info(f"  Using edge loading method: {loading_method}")

            if loading_method == 'csv':
                edges_created = self._create_edges_via_csv(blocks, csv_path=self.csv_path)
            else:
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
        if results['blocks_skipped_max_size']:
            self.logger.info(f"Blocks skipped (exceeded max size): {results['blocks_skipped_max_size']:,}")
            self.logger.info(f"Largest skipped block: {results['largest_skipped_block_size']:,}")
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
                    self.logger.info(f"  [OK] Created analyzer: {name}")
                    created.append(name)
                except Exception as e:
                    if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
                        self.logger.info(f"  - Analyzer exists: {name}")
                    else:
                        self.logger.warning(f"  ! Could not create {name}: {e}")
            else:
                self.logger.info(f"  - Analyzer exists: {name}")
        
        return created
    
    def _resolve_analyzer_name(self, analyzer_name: str) -> str:
        """
        Resolve analyzer name, checking for database-prefixed versions.
        
        In ArangoDB, analyzers may be stored with a database prefix
        (e.g., 'database_name::analyzer_name'). This method finds the
        actual analyzer name that exists in the database.
        
        Args:
            analyzer_name: Base analyzer name (e.g., 'address_normalizer')
        
        Returns:
            Actual analyzer name (with prefix if present, otherwise original)
        """
        # Get all existing analyzers
        existing_analyzers = {a['name'] for a in self.db.analyzers()}
        
        # Check if analyzer exists as-is (no prefix)
        if analyzer_name in existing_analyzers:
            return analyzer_name
        
        # Try to get database name and check for prefixed version
        db_name = None
        try:
            # Try to get database name from properties
            props = self.db.properties()
            db_name = props.get('name')
        except (AttributeError, Exception):
            try:
                # Try direct attribute access
                db_name = self.db.name
            except (AttributeError, Exception):
                pass
        
        # Check if analyzer exists with database prefix
        if db_name:
            prefixed_name = f"{db_name}::{analyzer_name}"
            if prefixed_name in existing_analyzers:
                self.logger.debug(f"Using database-prefixed analyzer: {prefixed_name}")
                return prefixed_name
        
        # Fallback: search for any analyzer ending with ::analyzer_name
        for existing_name in existing_analyzers:
            if existing_name.endswith(f"::{analyzer_name}"):
                self.logger.debug(f"Found prefixed analyzer: {existing_name}")
                return existing_name
        
        # If not found, return original (will fail during view creation if truly missing)
        # This allows built-in analyzers like 'text_en' and 'identity' to work
        return analyzer_name
    
    def _setup_search_view(self) -> Optional[str]:
        """
        Create ArangoSearch view for address matching.
        
        Detects and uses database-prefixed analyzer names when present.
        
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
        
        # Resolve analyzer names (check for database prefixes)
        address_normalizer = self._resolve_analyzer_name('address_normalizer')
        text_normalizer = self._resolve_analyzer_name('text_normalizer')
        text_en = self._resolve_analyzer_name('text_en')
        identity = self._resolve_analyzer_name('identity')
        
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
                                    'analyzers': [address_normalizer, text_en]
                                },
                                self.city_field: {
                                    'analyzers': [text_normalizer]
                                },
                                self.state_field: {
                                    'analyzers': [identity]
                                },
                                self.postal_code_field: {
                                    'analyzers': [identity]
                                }
                            }
                        }
                    }
                }
            )
            self.logger.info(f"  [OK] Created view: {self.search_view_name}")
            return self.search_view_name
        except Exception as e:
            self.logger.error(f"  [X] Failed to create view: {e}")
            return None
    
    def _find_duplicate_addresses(
        self,
        max_block_size: int
    ) -> Tuple[Dict[str, List[str]], int, Dict[str, Any]]:
        """
        Find duplicate addresses using normalized blocking.
        
        Dispatches to single-query or shard-parallel blocking based on
        ``self.blocking_mode``.
        
        Args:
            max_block_size: Maximum addresses per block
        
        Returns:
            Tuple of (blocks dict, total addresses matched, skip_stats dict)
        """
        if self.blocking_mode == 'shard_parallel':
            return self._find_duplicate_addresses_shard_parallel(max_block_size)
        return self._find_duplicate_addresses_single_query(max_block_size)

    def _partition_blocks(
        self,
        cursor,
        max_block_size: int,
    ) -> Tuple[Dict[str, List[str]], int, Dict[str, Any]]:
        """Consume a blocking-query cursor and split results into kept / skipped."""
        blocks: Dict[str, List[str]] = {}
        total_addresses = 0
        blocks_skipped_max_size = 0
        largest_skipped_block_size = 0
        skipped_block_samples: List[Dict[str, Any]] = []

        for result in cursor:
            block_key = result['block_key']
            addresses = result['addresses']
            size = result['size']

            if size > max_block_size:
                blocks_skipped_max_size += 1
                if size > largest_skipped_block_size:
                    largest_skipped_block_size = size
                if len(skipped_block_samples) < 5:
                    skipped_block_samples.append({'block_key': block_key, 'size': size})
                else:
                    smallest_sample = min(skipped_block_samples, key=lambda s: s['size'])
                    if size > smallest_sample['size']:
                        skipped_block_samples.remove(smallest_sample)
                        skipped_block_samples.append({'block_key': block_key, 'size': size})
            else:
                blocks[block_key] = addresses
                total_addresses += size

        skipped_block_samples.sort(key=lambda s: s['size'], reverse=True)

        skip_stats: Dict[str, Any] = {
            'blocks_skipped_max_size': blocks_skipped_max_size,
            'largest_skipped_block_size': largest_skipped_block_size,
            'skipped_block_samples': skipped_block_samples,
        }

        self.logger.info(f"[OK] Found {len(blocks):,} duplicate address groups")
        self.logger.info(f"[OK] Total addresses in groups: {total_addresses:,}")
        if blocks_skipped_max_size:
            self.logger.info(
                f"Skipped {blocks_skipped_max_size:,} blocks exceeding max size {max_block_size} "
                f"(largest: {largest_skipped_block_size:,})"
            )
            for sample in skipped_block_samples[:5]:
                self.logger.info(f"  skipped block: {sample['block_key']!r} (size={sample['size']:,})")

        return blocks, total_addresses, skip_stats

    def _find_duplicate_addresses_single_query(
        self,
        max_block_size: int,
    ) -> Tuple[Dict[str, List[str]], int, Dict[str, Any]]:
        """Single-query blocking across the entire collection."""
        self.logger.info("Finding duplicate addresses using normalized blocking (single_query)...")

        query = f"""
        FOR addr IN {self.collection}
            FILTER addr.{self.street_field} != null AND addr.{self.street_field} != 'NULL'
            FILTER addr.{self.city_field} != null
            FILTER addr.{self.state_field} != null

            LET norm_street = UPPER(REGEX_REPLACE(TRIM(addr.{self.street_field}), '[^A-Z0-9\\s]', ''))
            LET norm_city = UPPER(TRIM(addr.{self.city_field}))
            LET state = UPPER(TRIM(addr.{self.state_field}))
            LET zip5 = SUBSTRING(REGEX_REPLACE(addr.{self.postal_code_field}, '[^0-9]', ''), 0, 5)

            FILTER LENGTH(norm_street) > 0 AND LENGTH(norm_city) > 0 AND LENGTH(state) > 0

            LET block_key = CONCAT_SEPARATOR('|', norm_street, norm_city, state, zip5)

            COLLECT block = block_key INTO group = addr._id

            LET block_size = LENGTH(group)

            FILTER block_size >= 2

            RETURN {{
                block_key: block,
                addresses: group,
                size: block_size
            }}
        """

        cursor = self.db.aql.execute(
            query,
            batch_size=self.batch_size,
            stream=True,
        )

        return self._partition_blocks(cursor, max_block_size)

    def _find_duplicate_addresses_shard_parallel(
        self,
        max_block_size: int,
    ) -> Tuple[Dict[str, List[str]], int, Dict[str, Any]]:
        """Shard-parallel blocking: one query per shard-key prefix value.

        Enumerates distinct prefix values (e.g. ZIP3) then runs one blocking
        query per prefix so the ArangoDB optimizer routes each sub-query to a
        single shard instead of doing scatter-gather.
        """
        shard_field = self.shard_key_field or self.postal_code_field
        prefix_len = self.shard_key_prefix_length

        self.logger.info(
            "Finding duplicate addresses using shard-parallel blocking "
            f"(field={shard_field}, prefix_len={prefix_len})..."
        )

        prefix_query = """
        FOR d IN @@collection
            COLLECT prefix = SUBSTRING(d.@field, 0, @len)
            RETURN prefix
        """
        prefix_cursor = self.db.aql.execute(
            prefix_query,
            bind_vars={
                '@collection': self.collection,
                'field': shard_field,
                'len': prefix_len,
            },
        )
        prefixes = [p for p in prefix_cursor if p is not None]
        self.logger.info(f"Found {len(prefixes):,} distinct shard-key prefix values")

        all_blocks: Dict[str, List[str]] = {}
        total_addresses = 0
        total_skipped = 0
        largest_skipped = 0
        all_skipped_samples: List[Dict[str, Any]] = []

        for idx, prefix in enumerate(prefixes, 1):
            query = f"""
            FOR addr IN {self.collection}
                FILTER SUBSTRING(addr.{self.postal_code_field}, 0, @prefix_len) == @prefix
                FILTER addr.{self.street_field} != null AND addr.{self.street_field} != 'NULL'
                FILTER addr.{self.city_field} != null
                FILTER addr.{self.state_field} != null

                LET norm_street = UPPER(REGEX_REPLACE(TRIM(addr.{self.street_field}), '[^A-Z0-9\\s]', ''))
                LET norm_city = UPPER(TRIM(addr.{self.city_field}))
                LET state = UPPER(TRIM(addr.{self.state_field}))
                LET zip5 = SUBSTRING(REGEX_REPLACE(addr.{self.postal_code_field}, '[^0-9]', ''), 0, 5)

                FILTER LENGTH(norm_street) > 0 AND LENGTH(norm_city) > 0 AND LENGTH(state) > 0

                LET block_key = CONCAT_SEPARATOR('|', norm_street, norm_city, state, zip5)

                COLLECT block = block_key INTO group = addr._id

                LET block_size = LENGTH(group)

                FILTER block_size >= 2

                RETURN {{
                    block_key: block,
                    addresses: group,
                    size: block_size
                }}
            """

            cursor = self.db.aql.execute(
                query,
                bind_vars={'prefix': prefix, 'prefix_len': prefix_len},
                batch_size=self.batch_size,
                stream=True,
            )

            blocks, addrs, skip_stats = self._partition_blocks(cursor, max_block_size)
            all_blocks.update(blocks)
            total_addresses += addrs
            total_skipped += skip_stats['blocks_skipped_max_size']
            if skip_stats['largest_skipped_block_size'] > largest_skipped:
                largest_skipped = skip_stats['largest_skipped_block_size']
            all_skipped_samples.extend(skip_stats['skipped_block_samples'])

            if idx % 25 == 0 or idx == len(prefixes):
                self.logger.info(
                    f"  Shard-parallel progress: {idx}/{len(prefixes)} prefixes, "
                    f"{len(all_blocks):,} blocks so far"
                )

        all_skipped_samples.sort(key=lambda s: s['size'], reverse=True)
        combined_skip_stats: Dict[str, Any] = {
            'blocks_skipped_max_size': total_skipped,
            'largest_skipped_block_size': largest_skipped,
            'skipped_block_samples': all_skipped_samples[:5],
        }

        self.logger.info(f"[OK] Shard-parallel complete: {len(all_blocks):,} blocks, {total_addresses:,} addresses")
        if total_skipped:
            self.logger.info(
                f"Skipped {total_skipped:,} blocks exceeding max size {max_block_size} "
                f"(largest: {largest_skipped:,})"
            )
            for sample in combined_skip_stats['skipped_block_samples']:
                self.logger.info(f"  skipped block: {sample['block_key']!r} (size={sample['size']:,})")

        return all_blocks, total_addresses, combined_skip_stats
    
    def _create_edges(self, blocks: Dict[str, List[str]]) -> int:
        """
        Create sameAs edges for duplicate addresses using optimized API batching.
        
        Optimized version that batches edges across blocks to reduce API calls.
        Much faster than per-block insertion for large datasets.
        
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
        self.logger.info(f"Using optimized batching (batch size: {self.edge_batch_size:,})")
        
        # Create edges in larger batches (across blocks)
        edge_collection: EdgeCollection = self.db.collection(self.edge_collection)
        edges_created = 0
        batch = []
        timestamp = datetime.now().isoformat()
        
        for block_key, addresses in blocks.items():
            # Generate all pairs for this block
            for i, addr1_id in enumerate(addresses):
                for addr2_id in addresses[i + 1:]:
                    batch.append({
                        '_from': addr1_id,
                        '_to': addr2_id,
                        'block_key': block_key,
                        'timestamp': timestamp,
                        'type': 'address_sameAs'
                    })
                    
                    # Insert when batch is full
                    if len(batch) >= self.edge_batch_size:
                        try:
                            edge_collection.insert_many(batch)
                            edges_created += len(batch)
                            batch = []
                            
                            # Progress logging
                            if edges_created % 100000 == 0:
                                self.logger.info(f"  Created {edges_created:,} edges...")
                        except Exception as e:
                            self.logger.error(f"Failed to insert edge batch: {e}", exc_info=True)
                            # Continue with next batch
        
        # Insert remaining edges
        if batch:
            try:
                edge_collection.insert_many(batch)
                edges_created += len(batch)
            except Exception as e:
                self.logger.error(f"Failed to insert final edge batch: {e}", exc_info=True)
        
        self.logger.info(f"[OK] Created {edges_created:,} sameAs edges")
        
        return edges_created
    
    def _create_edges_via_csv(
        self, 
        blocks: Dict[str, List[str]], 
        csv_path: Optional[str] = None
    ) -> int:
        """
        Create sameAs edges by exporting to CSV and using arangoimport.
        
        Much faster for large edge sets (>100K edges). Uses ArangoDB's native
        bulk import tool for optimal performance.
        
        Args:
            blocks: Dictionary mapping block keys to lists of address IDs
            csv_path: Path to CSV file (auto-generated if None)
        
        Returns:
            Number of edges created
        
        Raises:
            FileNotFoundError: If arangoimport is not available
            subprocess.CalledProcessError: If arangoimport fails
        """
        import csv
        import tempfile
        import subprocess
        import os
        
        # Generate CSV path
        if csv_path is None:
            csv_path = tempfile.mktemp(suffix='.csv', prefix='address_edges_')
            cleanup_csv = True
        else:
            cleanup_csv = False
        
        self.logger.info(f"Exporting edges to CSV: {csv_path}")
        
        # Calculate total edges
        total_edges = sum(
            (len(addrs) * (len(addrs) - 1)) // 2
            for addrs in blocks.values()
        )
        
        self.logger.info(f"Will export ~{total_edges:,} edges to CSV")
        
        # Ensure edge collection exists
        if not self.db.has_collection(self.edge_collection):
            self.logger.info(f"Creating {self.edge_collection} edge collection...")
            self.db.create_collection(self.edge_collection, edge=True)
        else:
            self.logger.info(f"Truncating existing {self.edge_collection} collection...")
            self.db.collection(self.edge_collection).truncate()
        
        # Export to CSV
        edges_written = 0
        timestamp = datetime.now().isoformat()
        
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['_from', '_to', 'block_key', 'timestamp', 'type'])
                
                # Write edges
                for block_key, addresses in blocks.items():
                    for i, addr1_id in enumerate(addresses):
                        for addr2_id in addresses[i + 1:]:
                            writer.writerow([
                                addr1_id,
                                addr2_id,
                                block_key,
                                timestamp,
                                'address_sameAs'
                            ])
                            edges_written += 1
                            
                            # Progress logging
                            if edges_written % 100000 == 0:
                                self.logger.info(f"  Exported {edges_written:,} edges...")
            
            self.logger.info(f"[OK] Exported {edges_written:,} edges to CSV")
            
        except Exception as e:
            self.logger.error(f"Failed to write CSV file: {e}", exc_info=True)
            if cleanup_csv and os.path.exists(csv_path):
                os.remove(csv_path)
            raise
        
        # Import using arangoimport
        self.logger.info("Importing edges using arangoimport...")
        
        # Get database connection info
        try:
            # Try to get connection info from database object
            db_name = self.db.name
            
            # Get connection details - try multiple approaches
            host = DEFAULT_HOST
            port = DEFAULT_PORT
            username = DEFAULT_USERNAME
            password = ''
            
            # Try to extract from connection if available
            try:
                if hasattr(self.db, 'connection'):
                    conn = self.db.connection
                    if hasattr(conn, 'host'):
                        host = conn.host
                    if hasattr(conn, 'port'):
                        port = conn.port
                    if hasattr(conn, 'username'):
                        username = conn.username
                    if hasattr(conn, 'password'):
                        password = conn.password
            except Exception as e:
                self.logger.debug("Could not extract connection info from db object: %s", e)
            
            # Try to get from environment variables
            import os
            host = os.getenv('ARANGO_HOST', os.getenv('ARANGO_DB_HOST', host))
            port = int(os.getenv('ARANGO_PORT', os.getenv('ARANGO_DB_PORT', str(port))))
            username = os.getenv('ARANGO_USERNAME', os.getenv('ARANGO_ROOT_USERNAME', username))
            password = os.getenv('ARANGO_PASSWORD', os.getenv('ARANGO_ROOT_PASSWORD', password))
            
            # Validate we have required info
            if not db_name:
                raise ValueError("Database name not available")
                
        except Exception as e:
            self.logger.warning(f"Could not determine database connection info: {e}")
            self.logger.info("Falling back to standard insert_many method...")
            return self._create_edges(blocks)  # Fallback
        
        # Build arangoimport command
        # NOTE: arangoimport accepts passwords via argv. This can be visible in process lists
        # on some systems. We avoid logging the full command and redact any captured output.
        cmd = [
            'arangoimport',
            '--server.endpoint', f'http://{host}:{port}',
            '--server.username', username,
            '--server.password', password,
            '--server.database', db_name,
            '--collection', self.edge_collection,
            '--type', 'csv',
            '--file', csv_path,
            '--create-collection', 'false',
            '--create-collection-type', 'edge'
        ]
        
        # Run arangoimport
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Parse output to get number imported
            # arangoimport outputs: "created: 3973489"
            import re
            match = re.search(r'created:\s*(\d+)', result.stdout)
            if match:
                edges_imported = int(match.group(1))
            else:
                # Fallback: use written count
                edges_imported = edges_written
                self.logger.warning("Could not parse arangoimport output, using written count")
            
            self.logger.info(f"[OK] Imported {edges_imported:,} edges via arangoimport")
            
            # Clean up CSV file
            if cleanup_csv and os.path.exists(csv_path):
                os.remove(csv_path)
                self.logger.debug(f"Cleaned up temporary CSV: {csv_path}")
            
            return edges_imported
            
        except FileNotFoundError:
            self.logger.error("arangoimport not found. Install ArangoDB client tools.")
            self.logger.info("Falling back to standard insert_many method...")
            if cleanup_csv and os.path.exists(csv_path):
                os.remove(csv_path)
            return self._create_edges(blocks)  # Fallback
            
        except subprocess.TimeoutExpired:
            self.logger.error("arangoimport timed out after 1 hour")
            if cleanup_csv and os.path.exists(csv_path):
                # Keep CSV for manual retry
                self.logger.info(f"CSV file preserved at: {csv_path}")
            raise
            
        except subprocess.CalledProcessError as e:
            def _redact(value: Optional[str]) -> str:
                if not value:
                    return ""
                redacted = value.replace(password, "***") if password else value
                return sanitize_string_for_display(redacted, max_length=500)

            self.logger.error(
                "arangoimport failed (returncode=%s) endpoint=http://%s:%s db=%s collection=%s file=%s",
                e.returncode,
                host,
                port,
                db_name,
                self.edge_collection,
                csv_path,
            )
            stderr_snippet = _redact(getattr(e, "stderr", None))
            stdout_snippet = _redact(getattr(e, "stdout", None))
            if stderr_snippet:
                self.logger.error("arangoimport stderr (redacted, truncated): %s", stderr_snippet)
            if stdout_snippet:
                self.logger.debug("arangoimport stdout (redacted, truncated): %s", stdout_snippet)
            self.logger.info("Falling back to standard insert_many method...")
            if cleanup_csv and os.path.exists(csv_path):
                os.remove(csv_path)
            return self._create_edges(blocks)  # Fallback
    
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
    
    def run_canonical_etl(
        self,
        input_path: str,
        output_dir: str,
        header_path: Optional[str] = None,
        key_field: Optional[str] = None,
        source_lookup: Optional[Dict] = None,
        edge_extra_fields: Optional[List[str]] = None,
        hub_threshold: int = 50,
        hub_markers: Optional[Dict[str, str]] = None,
        from_collection: str = "regs",
        to_collection: str = "canonical_addresses",
    ) -> Dict[str, Any]:
        """Run ETL-time canonicalization as an alternative to post-load dedup.

        This pre-deduplicates addresses at ingest time using O(n) signature
        grouping, producing JSONL files suitable for ``arangoimport``.

        Args:
            input_path: Path to input TSV/CSV file.
            output_dir: Directory for output JSONL files.
            header_path: Separate header file (or ``None`` to use first row).
            key_field: Join-key column for source vertex lookup.
            source_lookup: ``{join_key: (shard_prefix, vertex_key)}`` mapping.
            edge_extra_fields: Extra input columns to include on edges.
            hub_threshold: In-degree threshold for hub classification.
            hub_markers: ``{column: value}`` markers for hubs.
            from_collection: Source vertex collection name.
            to_collection: Target canonical address collection name.

        Returns:
            Statistics dict from the resolver.
        """
        from pathlib import Path as _Path
        from ..etl import CanonicalResolver, AddressNormalizer

        resolver = CanonicalResolver(
            normalizer=AddressNormalizer(),
            signature_fields=["street", "city", "state", "postal"],
            field_mapping=dict(self.field_mapping),
            hub_threshold=hub_threshold,
            hub_markers=hub_markers or {},
        )

        resolver.process_file(
            input_path,
            header_path=header_path,
            key_field=key_field,
            source_lookup=source_lookup,
            edge_extra_fields=edge_extra_fields,
        )

        out = _Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        nodes_path = out / "canonical_addresses.jsonl"
        edges_path = out / "hasAddress.jsonl"

        resolver.write_nodes(str(nodes_path))
        resolver.write_edges(str(edges_path), from_collection, to_collection)

        self.logger.info("Canonical ETL complete: %s", resolver.stats)
        return resolver.stats

    def __repr__(self) -> str:
        """String representation."""
        return (f"AddressERService("
                f"collection='{self.collection}', "
                f"edge_collection='{self.edge_collection}')")


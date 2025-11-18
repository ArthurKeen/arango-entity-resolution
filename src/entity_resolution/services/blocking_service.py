"""
Blocking Service for Entity Resolution (v1.x Legacy)

⚠️  DEPRECATED: This service is deprecated and will be removed in v3.0.
Use the v2.0 strategy pattern instead:
- CollectBlockingStrategy for composite key blocking (99% test coverage)
- BM25BlockingStrategy for fuzzy text matching (85% test coverage)

This service provides:
- ArangoSearch views and analyzers
- Multi-strategy blocking (n-gram, exact, phonetic)
- Python-based implementation
"""

import warnings
import requests
from typing import Dict, List, Any, Optional
from .base_service import BaseEntityResolutionService, Config
from ..utils.algorithms import soundex


class BlockingService(BaseEntityResolutionService):
    """
    Record blocking service that generates candidate pairs (v1.x legacy).
    
    ⚠️  DEPRECATED: Use CollectBlockingStrategy or BM25BlockingStrategy instead.
    This service will be removed in v3.0.
    
    For v2.0+, prefer using CollectBlockingStrategy or BM25BlockingStrategy
    from the strategies package for better performance and cleaner API.
    
    This service uses Python-based ArangoDB operations.
    """
    
    def __init__(self, config: Optional[Config] = None):
        warnings.warn(
            "BlockingService is deprecated and will be removed in v3.0. "
            "Use CollectBlockingStrategy (99% coverage) or BM25BlockingStrategy (85% coverage) instead. "
            "See docs/guides/MIGRATION_GUIDE_V3.md for migration instructions.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config)
        
    def _get_service_name(self) -> str:
        return "blocking"
    
    def setup_for_collections(self, collections: List[str]) -> Dict[str, Any]:
        """
        Set up analyzers and views for blocking
        
        Args:
            collections: List of collection names to set up
            
        Returns:
            Setup results
        """
        # v2.0: Python-only implementation
        return self._setup_via_python(collections)
    
    def generate_candidates(self, collection: str, target_record_id: str,
                          strategies: Optional[List[str]] = None,
                          limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate candidate pairs for a target record
        
        Args:
            collection: Source collection name
            target_record_id: ID of the target record
            strategies: Blocking strategies to use
            limit: Maximum candidates to return
            
        Returns:
            Candidate generation results
        """
        strategies = strategies or ["ngram", "exact"]
        limit = limit or self.config.er.max_candidates_per_record
        
        # v2.0: Python-only implementation
        return self._generate_candidates_via_python(collection, target_record_id, strategies, limit)
    
    def _setup_via_foxx(self, collections: List[str]) -> Dict[str, Any]:
        """Set up analyzers and views via Foxx service"""
        try:
            # Create analyzers
            analyzers_url = self.config.get_foxx_service_url("setup/analyzers")
            analyzer_response = requests.post(
                analyzers_url,
                auth=self.config.get_auth_tuple(),
                json={},
                timeout=self.config.er.foxx_timeout
            )
            
            if analyzer_response.status_code != 200:
                return {"success": False, "error": "Failed to create analyzers via Foxx service"}
            
            # Create views
            views_url = self.config.get_foxx_service_url("setup/views")
            views_response = requests.post(
                views_url,
                auth=self.config.get_auth_tuple(),
                json={"collections": collections},
                timeout=self.config.er.foxx_timeout
            )
            
            if views_response.status_code != 200:
                return {"success": False, "error": "Failed to create views via Foxx service"}
            
            self.logger.info("Setup completed via Foxx services")
            
            return {
                "success": True,
                "method": "foxx",
                "analyzers": analyzer_response.json(),
                "views": views_response.json()
            }
            
        except Exception as e:
            self.logger.error(f"Foxx setup failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _setup_via_python(self, collections: List[str]) -> Dict[str, Any]:
        """Set up analyzers and views via Python (fallback)"""
        try:
            from arango import ArangoClient
            
            # Create ArangoDB client
            client = ArangoClient(hosts=f"http://{self.config.db.host}:{self.config.db.port}")
            db = client.db(self.config.db.database, username=self.config.db.username, 
                          password=self.config.db.password)
            
            setup_results = {
                "analyzers": {},
                "views": {},
                "errors": []
            }
            
            # Create custom analyzers for blocking
            analyzers_to_create = self._get_blocking_analyzers()
            
            for analyzer_name, analyzer_config in analyzers_to_create.items():
                try:
                    # Check if analyzer exists
                    existing_analyzers = db.analyzers()
                    if not any(a['name'] == analyzer_name for a in existing_analyzers):
                        db.create_analyzer(
                            name=analyzer_name,
                            analyzer_type=analyzer_config['type'],
                            properties=analyzer_config.get('properties', {}),
                            features=analyzer_config.get('features', ['frequency', 'norm', 'position'])
                        )
                        setup_results["analyzers"][analyzer_name] = "created"
                        self.logger.info(f"Created analyzer: {analyzer_name}")
                    else:
                        setup_results["analyzers"][analyzer_name] = "exists"
                        
                except Exception as e:
                    self.logger.warning(f"Failed to create analyzer {analyzer_name}: {e}")
                    setup_results["errors"].append(f"Analyzer {analyzer_name}: {str(e)}")
            
            # Create ArangoSearch views for collections
            for collection in collections:
                view_name = f"{collection}_blocking_view"
                try:
                    # Check if view exists
                    if not db.has_view(view_name):
                        view_config = self._get_blocking_view_config(collection)
                        db.create_arangosearch_view(view_name, view_config)
                        setup_results["views"][view_name] = "created"
                        self.logger.info(f"Created blocking view: {view_name}")
                    else:
                        setup_results["views"][view_name] = "exists"
                        
                except Exception as e:
                    self.logger.warning(f"Failed to create view {view_name}: {e}")
                    setup_results["errors"].append(f"View {view_name}: {str(e)}")
            
            self.logger.info("Setup completed via Python implementation")
            
            return {
                "success": True,
                "method": "python",
                "analyzers": setup_results["analyzers"],
                "views": setup_results["views"],
                "errors": setup_results["errors"] if setup_results["errors"] else None
            }
            
        except Exception as e:
            self.logger.error(f"Python setup failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_blocking_analyzers(self) -> Dict[str, Dict[str, Any]]:
        """Get analyzer configurations for blocking"""
        return {
            "blocking_ngram": {
                "type": "ngram",
                "properties": {
                    "min": 2,
                    "max": 4,
                    "preserveOriginal": False,
                    "streamType": "utf8"
                },
                "features": ["frequency", "norm", "position"]
            },
            "blocking_text": {
                "type": "text",
                "properties": {
                    "locale": "en.utf-8",
                    "case": "lower",
                    "stopwords": [],
                    "accent": False,
                    "stemming": False
                },
                "features": ["frequency", "norm", "position"]
            },
            "blocking_identity": {
                "type": "identity",
                "properties": {},
                "features": ["frequency", "norm"]
            }
        }
    
    def _get_blocking_view_config(self, collection: str) -> Dict[str, Any]:
        """Get ArangoSearch view configuration for blocking"""
        return {
            "links": {
                collection: {
                    "analyzers": ["blocking_ngram", "blocking_text", "blocking_identity"],
                    "fields": {
                        "first_name": {
                            "analyzers": ["blocking_ngram", "blocking_text"]
                        },
                        "last_name": {
                            "analyzers": ["blocking_ngram", "blocking_text"]
                        },
                        "email": {
                            "analyzers": ["blocking_identity", "blocking_text"]
                        },
                        "phone": {
                            "analyzers": ["blocking_identity"]
                        },
                        "address": {
                            "analyzers": ["blocking_ngram", "blocking_text"]
                        },
                        "city": {
                            "analyzers": ["blocking_ngram", "blocking_text"]
                        },
                        "company": {
                            "analyzers": ["blocking_ngram", "blocking_text"]
                        }
                    },
                    "includeAllFields": False,
                    "storeValues": "none",
                    "trackListPositions": False
                }
            },
            "primarySort": [
                {"field": "first_name", "direction": "asc"},
                {"field": "last_name", "direction": "asc"}
            ]
        }
    
    def _generate_candidates_via_foxx(self, collection: str, target_record_id: str,
                                    strategies: List[str], limit: int) -> Dict[str, Any]:
        """Generate candidates via Foxx service"""
        try:
            url = self.config.get_foxx_service_url("blocking/candidates")
            
            payload = {
                "collection": collection,
                "targetDocId": target_record_id,
                "strategies": strategies,
                "limit": limit
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                self.logger.debug(f"Generated {len(result.get('candidates', []))} candidates via Foxx")
                return result
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx candidate generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_candidates_via_python(self, collection: str, target_record_id: str,
                                      strategies: List[str], limit: int) -> Dict[str, Any]:
        """Generate candidates via Python implementation using AQL queries"""
        try:
            from arango import ArangoClient
            import time
            
            start_time = time.time()
            
            # Create ArangoDB client
            client = ArangoClient(hosts=f"http://{self.config.db.host}:{self.config.db.port}")
            db = client.db(self.config.db.database, username=self.config.db.username, 
                          password=self.config.db.password)
            
            # Get target record
            target_record = db.collection(collection).get(target_record_id)
            if not target_record:
                return {"success": False, "error": f"Target record {target_record_id} not found"}
            
            all_candidates = set()
            strategy_results = {}
            
            # Apply each blocking strategy
            for strategy in strategies:
                strategy_candidates = self._apply_blocking_strategy(
                    db, collection, target_record, strategy, limit)
                
                if strategy_candidates:
                    strategy_results[strategy] = len(strategy_candidates)
                    all_candidates.update(strategy_candidates)
            
            # Convert to list and limit results
            final_candidates = list(all_candidates)[:limit]
            
            # Fetch full candidate records
            candidate_records = []
            for candidate_id in final_candidates:
                try:
                    candidate_doc = db.collection(collection).get(candidate_id)
                    if candidate_doc and candidate_doc['_id'] != target_record_id:
                        candidate_records.append({
                            "_id": candidate_doc['_id'],
                            "document": candidate_doc,
                            "blocking_strategy": "multi"  # Multiple strategies may have found this
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to fetch candidate {candidate_id}: {e}")
            
            execution_time = time.time() - start_time
            
            self.logger.info(f"Generated {len(candidate_records)} candidates using {len(strategies)} strategies")
            
            return {
                "success": True,
                "method": "python",
                "collection": collection,
                "target_record_id": target_record_id,
                "strategies": strategies,
                "candidates": candidate_records,
                "statistics": {
                    "total_candidates": len(candidate_records),
                    "unique_candidates": len(all_candidates),
                    "strategies_used": len(strategies),
                    "strategy_results": strategy_results,
                    "execution_time": execution_time
                }
            }
            
        except Exception as e:
            self.logger.error(f"Python candidate generation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _apply_blocking_strategy(self, db, collection: str, target_record: Dict[str, Any], 
                               strategy: str, limit: int) -> List[str]:
        """Apply a specific blocking strategy to find candidates"""
        try:
            if strategy == "ngram":
                return self._ngram_blocking(db, collection, target_record, limit)
            elif strategy == "exact":
                return self._exact_blocking(db, collection, target_record, limit)
            elif strategy == "phonetic":
                return self._phonetic_blocking(db, collection, target_record, limit)
            elif strategy == "sorted_neighborhood":
                return self._sorted_neighborhood_blocking(db, collection, target_record, limit)
            else:
                self.logger.warning(f"Unknown blocking strategy: {strategy}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error applying blocking strategy {strategy}: {e}")
            return []
    
    def _exact_blocking(self, db, collection: str, target_record: Dict[str, Any], 
                       limit: int) -> List[str]:
        """Exact match blocking on key fields"""
        try:
            candidates = set()
            
            # Exact match on email
            if 'email' in target_record and target_record['email']:
                aql = f"""
                FOR doc IN {collection}
                FILTER doc.email == @email AND doc._id != @target_id
                LIMIT {limit}
                RETURN doc._id
                """
                cursor = db.aql.execute(aql, bind_vars={
                    "email": target_record['email'],
                    "target_id": target_record['_id']
                })
                candidates.update(doc for doc in cursor)
            
            # Exact match on phone
            if 'phone' in target_record and target_record['phone']:
                aql = f"""
                FOR doc IN {collection}
                FILTER doc.phone == @phone AND doc._id != @target_id
                LIMIT {limit}
                RETURN doc._id
                """
                cursor = db.aql.execute(aql, bind_vars={
                    "phone": target_record['phone'],
                    "target_id": target_record['_id']
                })
                candidates.update(doc for doc in cursor)
            
            # Exact match on last name + first initial
            if 'last_name' in target_record and 'first_name' in target_record:
                if target_record['last_name'] and target_record['first_name']:
                    first_initial = target_record['first_name'][0].upper()
                    aql = f"""
                    FOR doc IN {collection}
                    FILTER doc.last_name == @last_name 
                           AND UPPER(LEFT(doc.first_name, 1)) == @first_initial 
                           AND doc._id != @target_id
                    LIMIT {limit}
                    RETURN doc._id
                    """
                    cursor = db.aql.execute(aql, bind_vars={
                        "last_name": target_record['last_name'],
                        "first_initial": first_initial,
                        "target_id": target_record['_id']
                    })
                    candidates.update(doc for doc in cursor)
            
            return list(candidates)[:limit]
            
        except Exception as e:
            self.logger.error(f"Exact blocking failed: {e}")
            return []
    
    def _ngram_blocking(self, db, collection: str, target_record: Dict[str, Any], 
                       limit: int) -> List[str]:
        """N-gram based blocking with fallback to simple matching"""
        try:
            # Simple approach: match on partial names
            candidates = set()
            
            if 'last_name' in target_record and target_record['last_name']:
                last_name = target_record['last_name']
                # Match records with similar last names (first 3 characters)
                if len(last_name) >= 3:
                    prefix = last_name[:3].upper()
                    aql = f"""
                    FOR doc IN {collection}
                    FILTER UPPER(LEFT(doc.last_name, 3)) == @prefix AND doc._id != @target_id
                    LIMIT {limit}
                    RETURN doc._id
                    """
                    cursor = db.aql.execute(aql, bind_vars={
                        "prefix": prefix,
                        "target_id": target_record['_id']
                    })
                    candidates.update(doc for doc in cursor)
            
            # Similar approach for first name
            if 'first_name' in target_record and target_record['first_name']:
                first_name = target_record['first_name']
                if len(first_name) >= 3:
                    prefix = first_name[:3].upper()
                    aql = f"""
                    FOR doc IN {collection}
                    FILTER UPPER(LEFT(doc.first_name, 3)) == @prefix AND doc._id != @target_id
                    LIMIT {limit}
                    RETURN doc._id
                    """
                    cursor = db.aql.execute(aql, bind_vars={
                        "prefix": prefix,
                        "target_id": target_record['_id']
                    })
                    candidates.update(doc for doc in cursor)
            
            return list(candidates)[:limit]
            
        except Exception as e:
            self.logger.error(f"N-gram blocking failed: {e}")
            return []
    
    def _phonetic_blocking(self, db, collection: str, target_record: Dict[str, Any], 
                          limit: int) -> List[str]:
        """Phonetic blocking using Soundex codes"""
        try:
            candidates = set()
            
            # Generate Soundex codes for names
            if 'first_name' in target_record and target_record['first_name']:
                first_soundex = soundex(target_record['first_name'])
                if first_soundex:
                    aql = f"""
                    FOR doc IN {collection}
                    FILTER SOUNDEX(doc.first_name) == @soundex AND doc._id != @target_id
                    LIMIT {limit}
                    RETURN doc._id
                    """
                    cursor = db.aql.execute(aql, bind_vars={
                        "soundex": first_soundex,
                        "target_id": target_record['_id']
                    })
                    candidates.update(doc for doc in cursor)
            
            if 'last_name' in target_record and target_record['last_name']:
                last_soundex = soundex(target_record['last_name'])
                if last_soundex:
                    aql = f"""
                    FOR doc IN {collection}
                    FILTER SOUNDEX(doc.last_name) == @soundex AND doc._id != @target_id
                    LIMIT {limit}
                    RETURN doc._id
                    """
                    cursor = db.aql.execute(aql, bind_vars={
                        "soundex": last_soundex,
                        "target_id": target_record['_id']
                    })
                    candidates.update(doc for doc in cursor)
            
            return list(candidates)[:limit]
            
        except Exception as e:
            self.logger.error(f"Phonetic blocking failed: {e}")
            return []
    
    def _sorted_neighborhood_blocking(self, db, collection: str, target_record: Dict[str, Any], 
                                    limit: int) -> List[str]:
        """Sorted neighborhood blocking"""
        try:
            candidates = set()
            
            # Create sorting key from name
            sort_key = ""
            if 'last_name' in target_record and target_record['last_name']:
                sort_key += target_record['last_name'].upper()
            if 'first_name' in target_record and target_record['first_name']:
                sort_key += target_record['first_name'].upper()
            
            if not sort_key:
                return []
            
            # Find records in sorted neighborhood (window size = limit)
            window_size = min(limit, 50)
            
            aql = f"""
            LET target_key = @sort_key
            FOR doc IN {collection}
            LET doc_key = UPPER(CONCAT(doc.last_name || "", doc.first_name || ""))
            FILTER doc._id != @target_id AND doc_key != ""
            SORT doc_key
            LIMIT {window_size * 2}
            RETURN {{
                _id: doc._id,
                sort_key: doc_key,
                distance: ABS(LENGTH(doc_key) - LENGTH(target_key))
            }}
            """
            
            cursor = db.aql.execute(aql, bind_vars={
                "sort_key": sort_key,
                "target_id": target_record['_id']
            })
            
            # Sort by distance and take closest records
            results = list(cursor)
            results.sort(key=lambda x: x['distance'])
            candidates.update(doc['_id'] for doc in results[:limit])
            
            return list(candidates)[:limit]
            
        except Exception as e:
            self.logger.error(f"Sorted neighborhood blocking failed: {e}")
            return []
    
    
    def get_blocking_stats(self, collection: str) -> Dict[str, Any]:
        """Get blocking performance statistics"""
        # v2.0: Python-only implementation
        return self._get_stats_via_python(collection)
    
    def _get_stats_via_foxx(self, collection: str) -> Dict[str, Any]:
        """Get stats via Foxx service"""
        try:
            url = self.config.get_foxx_service_url(f"blocking/stats/{collection}")
            
            response = requests.get(
                url,
                auth=self.config.get_auth_tuple(),
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Failed to get Foxx stats: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_stats_via_python(self, collection: str) -> Dict[str, Any]:
        """Get stats via Python implementation"""
        return {
            "success": True,
            "method": "python",
            "collection": collection,
            "stats": {
                "total_records": "unknown",
                "blocking_efficiency": "unknown",
                "note": "Limited stats in Python fallback mode"
            }
        }

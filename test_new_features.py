#!/usr/bin/env python3
"""
Functional tests for new library features.

Tests the newly added cross-collection matching, hybrid blocking,
geographic blocking, and graph traversal features against a real
ArangoDB instance.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set up database credentials for dedicated test container
os.environ['ARANGO_ROOT_PASSWORD'] = 'test_er_password_2025'
os.environ['ARANGO_HOST'] = 'localhost'
os.environ['ARANGO_PORT'] = '8532'  # Dedicated test container port

def test_imports():
    """Test that all new modules can be imported."""
    print("=" * 80)
    print("TEST 1: Module Imports")
    print("=" * 80)
    
    try:
        from entity_resolution import (
            CrossCollectionMatchingService,
            HybridBlockingStrategy,
            GeographicBlockingStrategy,
            GraphTraversalBlockingStrategy,
            clean_er_results,
            count_inferred_edges,
            validate_edge_quality,
            get_pipeline_statistics
        )
        print("✅ All new modules import successfully from main package")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test database connection."""
    print("\n" + "=" * 80)
    print("TEST 2: Database Connection")
    print("=" * 80)
    
    try:
        from entity_resolution.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        
        # Get database info
        db = db_manager.get_database()
        print(f"✅ Connected to database: {db.name}")
        print(f"   Server version: {db.version()}")
        
        # List collections
        collections = db.collections()
        print(f"   Collections available: {len(collections)}")
        
        db_manager.close_connections()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cross_collection_service_initialization():
    """Test CrossCollectionMatchingService can be initialized."""
    print("\n" + "=" * 80)
    print("TEST 3: CrossCollectionMatchingService Initialization")
    print("=" * 80)
    
    try:
        from entity_resolution import CrossCollectionMatchingService
        from entity_resolution.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        db = db_manager.get_database()
        
        # Create service (with mock collections)
        service = CrossCollectionMatchingService(
            db=db,
            source_collection="test_source",
            target_collection="test_target",
            edge_collection="test_edges",
            auto_create_edge_collection=False
        )
        
        print("✅ CrossCollectionMatchingService initialized successfully")
        print(f"   Source collection: {service.source_collection_name}")
        print(f"   Target collection: {service.target_collection_name}")
        print(f"   Edge collection: {service.edge_collection_name}")
        
        # Test configuration
        service.configure_matching(
            source_fields={"name": "src_name", "address": "src_addr"},
            target_fields={"name": "tgt_name", "address": "tgt_addr"},
            field_weights={"name": 0.7, "address": 0.3},
            blocking_fields=["state"]
        )
        
        print("✅ Service configuration successful")
        print(f"   Field weights: {service.field_weights}")
        print(f"   Blocking fields: {service.blocking_fields}")
        
        db_manager.close_connections()
        return True
        
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hybrid_blocking_strategy():
    """Test HybridBlockingStrategy initialization."""
    print("\n" + "=" * 80)
    print("TEST 4: HybridBlockingStrategy Initialization")
    print("=" * 80)
    
    try:
        from entity_resolution import HybridBlockingStrategy
        from entity_resolution.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        db = db_manager.get_database()
        
        # Create strategy
        strategy = HybridBlockingStrategy(
            db=db,
            collection="test_collection",
            search_view="test_search_view",
            search_fields={"name": 0.6, "address": 0.4},
            levenshtein_threshold=0.85,
            bm25_threshold=2.0
        )
        
        print("✅ HybridBlockingStrategy initialized successfully")
        print(f"   Collection: {strategy.collection}")
        print(f"   Search view: {strategy.search_view}")
        print(f"   Search fields: {strategy.search_fields}")
        print(f"   Levenshtein threshold: {strategy.levenshtein_threshold}")
        print(f"   BM25 threshold: {strategy.bm25_threshold}")
        
        db_manager.close_connections()
        return True
        
    except Exception as e:
        print(f"❌ Strategy initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_geographic_blocking_strategy():
    """Test GeographicBlockingStrategy initialization."""
    print("\n" + "=" * 80)
    print("TEST 5: GeographicBlockingStrategy Initialization")
    print("=" * 80)
    
    try:
        from entity_resolution import GeographicBlockingStrategy
        from entity_resolution.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        db = db_manager.get_database()
        
        # Test different blocking types
        blocking_types = [
            ("state", {"state": "primary_state"}),
            ("city", {"city": "primary_city"}),
            ("city_state", {"city": "primary_city", "state": "primary_state"}),
            ("zip_range", {"zip": "postal_code"}),
        ]
        
        for blocking_type, geo_fields in blocking_types:
            if blocking_type == "zip_range":
                strategy = GeographicBlockingStrategy(
                    db=db,
                    collection="test_collection",
                    blocking_type=blocking_type,
                    geographic_fields=geo_fields,
                    zip_ranges=[("570", "577")]
                )
            else:
                strategy = GeographicBlockingStrategy(
                    db=db,
                    collection="test_collection",
                    blocking_type=blocking_type,
                    geographic_fields=geo_fields
                )
            
            print(f"✅ {blocking_type} blocking strategy initialized")
        
        db_manager.close_connections()
        return True
        
    except Exception as e:
        print(f"❌ Strategy initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_traversal_strategy():
    """Test GraphTraversalBlockingStrategy initialization."""
    print("\n" + "=" * 80)
    print("TEST 6: GraphTraversalBlockingStrategy Initialization")
    print("=" * 80)
    
    try:
        from entity_resolution import GraphTraversalBlockingStrategy
        from entity_resolution.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        db = db_manager.get_database()
        
        # Create strategy
        strategy = GraphTraversalBlockingStrategy(
            db=db,
            collection="test_entities",
            edge_collection="test_edges",
            intermediate_collection="test_shared_resources",
            direction="INBOUND"
        )
        
        print("✅ GraphTraversalBlockingStrategy initialized successfully")
        print(f"   Collection: {strategy.collection}")
        print(f"   Edge collection: {strategy.edge_collection}")
        print(f"   Intermediate collection: {strategy.intermediate_collection}")
        print(f"   Direction: {strategy.direction}")
        
        db_manager.close_connections()
        return True
        
    except Exception as e:
        print(f"❌ Strategy initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_utilities():
    """Test pipeline utility functions."""
    print("\n" + "=" * 80)
    print("TEST 7: Pipeline Utilities")
    print("=" * 80)
    
    try:
        from entity_resolution import (
            clean_er_results,
            count_inferred_edges,
            validate_edge_quality,
            get_pipeline_statistics
        )
        from entity_resolution.utils.database import DatabaseManager
        
        db_manager = DatabaseManager()
        db = db_manager.get_database()
        
        print("✅ All utility functions imported successfully")
        print("   - clean_er_results")
        print("   - count_inferred_edges")
        print("   - validate_edge_quality")
        print("   - get_pipeline_statistics")
        
        # Test that functions are callable
        assert callable(clean_er_results), "clean_er_results should be callable"
        assert callable(count_inferred_edges), "count_inferred_edges should be callable"
        assert callable(validate_edge_quality), "validate_edge_quality should be callable"
        assert callable(get_pipeline_statistics), "get_pipeline_statistics should be callable"
        
        print("✅ All utility functions are callable")
        
        db_manager.close_connections()
        return True
        
    except Exception as e:
        print(f"❌ Utility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("FUNCTIONAL TESTS FOR NEW LIBRARY FEATURES")
    print("=" * 80)
    print("\nTesting against local Docker ArangoDB instance")
    print("Default password: testpassword123")
    print("=" * 80)
    
    tests = [
        ("Module Imports", test_imports),
        ("Database Connection", test_database_connection),
        ("CrossCollectionMatchingService", test_cross_collection_service_initialization),
        ("HybridBlockingStrategy", test_hybrid_blocking_strategy),
        ("GeographicBlockingStrategy", test_geographic_blocking_strategy),
        ("GraphTraversalBlockingStrategy", test_graph_traversal_strategy),
        ("Pipeline Utilities", test_pipeline_utilities),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 80)
    print(f"Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())


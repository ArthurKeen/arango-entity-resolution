"""
Tests for deterministic edge key generation in SimilarityEdgeService.

These tests verify that:
1. Same vertex pairs generate the same edge key (deterministic)
2. Edge creation is idempotent (no duplicates)
3. Works for both SmartGraph and non-SmartGraph deployments
4. Order-independent (A,B) == (B,A)
"""

import pytest
from entity_resolution.services.similarity_edge_service import SimilarityEdgeService


class TestDeterministicEdgeKeys:
    """Test deterministic edge key generation."""
    
    @pytest.fixture
    def db(self, arango_db):
        """Get database connection."""
        return arango_db
    
    @pytest.fixture
    def edge_collection(self, db):
        """Create test edge collection."""
        coll_name = "test_det_edges"
        
        # Clean up if exists
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
        
        # Create fresh collection
        db.create_collection(coll_name, edge=True)
        
        yield coll_name
        
        # Cleanup
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
    
    @pytest.fixture
    def vertex_collection(self, db):
        """Create test vertex collection."""
        coll_name = "test_det_vertices"
        
        # Clean up if exists
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
        
        # Create and populate with test data
        coll = db.create_collection(coll_name)
        coll.insert_many([
            {'_key': '123', 'name': 'Entity A'},
            {'_key': '456', 'name': 'Entity B'},
            {'_key': '789', 'name': 'Entity C'},
        ])
        
        yield coll_name
        
        # Cleanup
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
    
    def test_deterministic_keys_enabled_by_default(self, db, edge_collection, vertex_collection):
        """Test that deterministic keys are enabled by default."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection
        )
        
        assert service.use_deterministic_keys is True
    
    def test_same_pair_generates_same_key(self, db, edge_collection, vertex_collection):
        """Test that the same vertex pair always generates the same edge key."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        # Create edge
        matches = [("123", "456", 0.9)]
        service.create_edges(matches)
        
        # Get the edge
        edges = list(db.aql.execute(f"FOR e IN {edge_collection} RETURN e"))
        assert len(edges) == 1
        first_key = edges[0]['_key']
        
        # Create same edge again
        service.create_edges(matches)
        
        # Should still have only 1 edge with same key
        edges = list(db.aql.execute(f"FOR e IN {edge_collection} RETURN e"))
        assert len(edges) == 1
        assert edges[0]['_key'] == first_key
    
    def test_idempotent_edge_creation(self, db, edge_collection, vertex_collection):
        """Test that edge creation is idempotent with deterministic keys."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        matches = [
            ("123", "456", 0.9),
            ("456", "789", 0.85)
        ]
        
        # Create edges multiple times
        service.create_edges(matches)
        service.create_edges(matches)
        service.create_edges(matches)
        
        # Should have exactly 2 edges (no duplicates)
        edge_count = db.aql.execute(f"RETURN LENGTH({edge_collection})").next()
        assert edge_count == 2
    
    def test_order_independent_keys(self, db, edge_collection, vertex_collection):
        """Test that (A,B) and (B,A) generate the same edge key."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        # Create edge A -> B
        service.create_edges([("123", "456", 0.9)])
        edges = list(db.aql.execute(f"FOR e IN {edge_collection} RETURN e"))
        assert len(edges) == 1
        key_ab = edges[0]['_key']
        
        # Try to create edge B -> A
        service.create_edges([("456", "123", 0.9)])
        
        # Should still have 1 edge with same key
        edges = list(db.aql.execute(f"FOR e IN {edge_collection} RETURN e"))
        assert len(edges) == 1
        assert edges[0]['_key'] == key_ab
    
    def test_different_pairs_generate_different_keys(self, db, edge_collection, vertex_collection):
        """Test that different vertex pairs generate different edge keys."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        matches = [
            ("123", "456", 0.9),
            ("123", "789", 0.85),
            ("456", "789", 0.92)
        ]
        
        service.create_edges(matches)
        
        # Get all edge keys
        edges = list(db.aql.execute(f"FOR e IN {edge_collection} RETURN e._key"))
        assert len(edges) == 3
        assert len(set(edges)) == 3  # All unique
    
    def test_without_deterministic_keys(self, db, edge_collection, vertex_collection):
        """Test that without deterministic keys, duplicates can be created."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=False
        )
        
        matches = [("123", "456", 0.9)]
        
        # Create same edge twice
        service.create_edges(matches)
        service.create_edges(matches)
        
        # Should have 2 edges (duplicates allowed)
        edge_count = db.aql.execute(f"RETURN LENGTH({edge_collection})").next()
        assert edge_count == 2
    
    def test_deterministic_with_detailed_edges(self, db, edge_collection, vertex_collection):
        """Test deterministic keys with create_edges_detailed method."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        matches = [
            {
                'doc1_key': '123',
                'doc2_key': '456',
                'similarity': 0.92,
                'method': 'test',
                'field_scores': {'name': 0.95, 'address': 0.89}
            }
        ]
        
        # Create twice
        service.create_edges_detailed(matches)
        service.create_edges_detailed(matches)
        
        # Should have only 1 edge
        edge_count = db.aql.execute(f"RETURN LENGTH({edge_collection})").next()
        assert edge_count == 1
        
        # Verify metadata preserved
        edge = db.aql.execute(f"FOR e IN {edge_collection} RETURN e").next()
        assert edge['method'] == 'test'
        assert edge['field_scores']['name'] == 0.95
    
    def test_bidirectional_edges_with_deterministic_keys(self, db, edge_collection, vertex_collection):
        """Test that bidirectional edges generate different keys for forward/reverse."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        matches = [("123", "456", 0.9)]
        
        # Create bidirectional edges
        service.create_edges(matches, bidirectional=True)
        
        # Should have 2 edges (forward and reverse)
        edges = list(db.aql.execute(f"FOR e IN {edge_collection} RETURN e"))
        assert len(edges) == 2
        
        # But both should have the same _key (order-independent)
        keys = [e['_key'] for e in edges]
        assert keys[0] == keys[1]
        
        # Verify directions
        from_tos = [(e['_from'], e['_to']) for e in edges]
        assert (f"{vertex_collection}/123", f"{vertex_collection}/456") in from_tos
        assert (f"{vertex_collection}/456", f"{vertex_collection}/123") in from_tos


class TestDeterministicKeysSmartGraph:
    """Test deterministic keys with SmartGraph-style vertex keys."""
    
    @pytest.fixture
    def db(self, arango_db):
        """Get database connection."""
        return arango_db
    
    @pytest.fixture
    def edge_collection(self, db):
        """Create test edge collection."""
        coll_name = "test_smart_det_edges"
        
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
        
        db.create_collection(coll_name, edge=True)
        
        yield coll_name
        
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
    
    @pytest.fixture
    def vertex_collection(self, db):
        """Create test vertex collection with SmartGraph-style keys."""
        coll_name = "test_smart_vertices"
        
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
        
        # Create with SmartGraph-style keys (shard:natural_key format)
        coll = db.create_collection(coll_name)
        coll.insert_many([
            {'_key': '570:123', 'name': 'Entity A', 'zip3': '570'},
            {'_key': '570:456', 'name': 'Entity B', 'zip3': '570'},
            {'_key': '571:789', 'name': 'Entity C', 'zip3': '571'},
        ])
        
        yield coll_name
        
        if db.has_collection(coll_name):
            db.delete_collection(coll_name)
    
    def test_smartgraph_keys_generate_deterministic_edges(self, db, edge_collection, vertex_collection):
        """Test that SmartGraph-style vertex keys work with deterministic edge keys."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        # Use SmartGraph-style keys
        matches = [("570:123", "570:456", 0.9)]
        
        # Create twice
        service.create_edges(matches)
        service.create_edges(matches)
        
        # Should have only 1 edge
        edge_count = db.aql.execute(f"RETURN LENGTH({edge_collection})").next()
        assert edge_count == 1
    
    def test_smartgraph_edge_key_no_shard_prefix(self, db, edge_collection, vertex_collection):
        """Test that edge _key does NOT contain shard prefix (verified from dnb_er code)."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        matches = [("570:123", "570:456", 0.9)]
        service.create_edges(matches)
        
        # Get edge
        edge = db.aql.execute(f"FOR e IN {edge_collection} RETURN e").next()
        
        # Edge _key should NOT start with shard prefix "570:"
        # It's just a hash of the full _id values
        assert not edge['_key'].startswith('570:')
        
        # But _from and _to should have the full IDs with shard prefix
        assert edge['_from'] == f"{vertex_collection}/570:123"
        assert edge['_to'] == f"{vertex_collection}/570:456"
    
    def test_cross_shard_edges(self, db, edge_collection, vertex_collection):
        """Test edges between vertices in different shards."""
        service = SimilarityEdgeService(
            db=db,
            edge_collection=edge_collection,
            vertex_collection=vertex_collection,
            use_deterministic_keys=True
        )
        
        # Create edge between different shards
        matches = [("570:123", "571:789", 0.85)]
        
        # Create twice
        service.create_edges(matches)
        service.create_edges(matches)
        
        # Should have only 1 edge
        edge_count = db.aql.execute(f"RETURN LENGTH({edge_collection})").next()
        assert edge_count == 1


class TestEdgeKeyGeneration:
    """Test the _generate_deterministic_key method directly."""
    
    def test_key_generation_order_independence(self):
        """Test that key generation is order-independent."""
        from entity_resolution.services.similarity_edge_service import SimilarityEdgeService
        
        # Create service instance (we'll test the method directly)
        service = SimilarityEdgeService.__new__(SimilarityEdgeService)
        
        # Test non-SmartGraph IDs
        key1 = service._generate_deterministic_key("collection/123", "collection/456")
        key2 = service._generate_deterministic_key("collection/456", "collection/123")
        assert key1 == key2
        
        # Test SmartGraph IDs
        key3 = service._generate_deterministic_key("collection/570:123", "collection/570:456")
        key4 = service._generate_deterministic_key("collection/570:456", "collection/570:123")
        assert key3 == key4
    
    def test_different_ids_generate_different_keys(self):
        """Test that different IDs generate different keys."""
        from entity_resolution.services.similarity_edge_service import SimilarityEdgeService
        
        service = SimilarityEdgeService.__new__(SimilarityEdgeService)
        
        key1 = service._generate_deterministic_key("collection/123", "collection/456")
        key2 = service._generate_deterministic_key("collection/123", "collection/789")
        key3 = service._generate_deterministic_key("collection/456", "collection/789")
        
        # All should be different
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3
    
    def test_key_is_md5_hash(self):
        """Test that generated key is a valid MD5 hash."""
        from entity_resolution.services.similarity_edge_service import SimilarityEdgeService
        import re
        
        service = SimilarityEdgeService.__new__(SimilarityEdgeService)
        
        key = service._generate_deterministic_key("collection/123", "collection/456")
        
        # MD5 hash should be 32 hexadecimal characters
        assert len(key) == 32
        assert re.match(r'^[a-f0-9]{32}$', key)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


"""
Unit Tests for IC Enrichment Pack

Comprehensive test suite validating all components with domain-agnostic data.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from entity_resolution.enrichments import (
    HierarchicalContextResolver,
    TypeCompatibilityFilter,
    AcronymExpansionHandler,
    RelationshipProvenanceSweeper
)


class TestHierarchicalContextResolver:
    """Test suite for context-based resolution."""
    
    def test_initialization(self):
        """Test resolver initialization with various parameters."""
        resolver = HierarchicalContextResolver()
        assert resolver.context_weight == 0.3
        assert resolver.base_weight == 0.7
        
        # Test weight validation
        with pytest.raises(ValueError):
            HierarchicalContextResolver(context_weight=1.5)
        
        with pytest.raises(ValueError):
            HierarchicalContextResolver(context_weight=0.5, base_weight=0.6)
    
    def test_token_overlap_calculation(self):
        """Test token overlap with various inputs."""
        resolver = HierarchicalContextResolver()
        
        # Perfect overlap
        overlap = resolver.calculate_token_overlap("exception status", "exception status")
        assert overlap == 1.0
        
        # Partial overlap
        overlap = resolver.calculate_token_overlap(
            "exception status register",
            "register stores status"
        )
        assert 0.5 < overlap < 1.0
        
        # No overlap
        overlap = resolver.calculate_token_overlap("exception", "memory")
        assert overlap == 0.0
        
        # Empty strings
        overlap = resolver.calculate_token_overlap("", "test")
        assert overlap == 0.0
    
    def test_stop_words_filtering(self):
        """Test that stop words are properly filtered."""
        resolver = HierarchicalContextResolver()
        
        # With stop words
        overlap1 = resolver.calculate_token_overlap(
            "the exception is critical",
            "exception handling"
        )
        
        # Without stop words (manual check)
        tokens1 = {'exception', 'critical'}
        tokens2 = {'exception', 'handling'}
        expected = len(tokens1.intersection(tokens2)) / min(len(tokens1), len(tokens2))
        
        assert abs(overlap1 - expected) < 0.01
    
    def test_resolve_without_context(self):
        """Test resolution without parent context."""
        resolver = HierarchicalContextResolver()
        
        def dummy_similarity(cand):
            return 0.8
        
        candidates = [
            {'name': 'Entity A', 'description': 'First entity'},
            {'name': 'Entity B', 'description': 'Second entity'}
        ]
        
        results = resolver.resolve_with_context(
            item={'name': 'test'},
            candidates=candidates,
            parent_context="",  # No context
            base_similarity_fn=dummy_similarity
        )
        
        assert len(results) == 2
        assert all(r['final_score'] == r['base_score'] for r in results)
    
    def test_resolve_with_context_boost(self):
        """Test that context affects candidate scoring."""
        resolver = HierarchicalContextResolver()
        
        def dummy_similarity(cand):
            return 0.7
        
        candidates = [
            {'name': 'ESR', 'description': 'Exception Status Register handles errors'},
            {'name': 'TMR', 'description': 'Timer control register'}
        ]
        
        results = resolver.resolve_with_context(
            item={'name': 'esr'},
            candidates=candidates,
            parent_context='exception error handling and status reporting',
            base_similarity_fn=dummy_similarity
        )
        
        # Find ESR and TMR in results
        esr_result = [r for r in results if r['name'] == 'ESR'][0]
        tmr_result = [r for r in results if r['name'] == 'TMR'][0]
        
        # ESR should have higher context overlap due to exception/error/handling/status terms
        assert esr_result['context_score'] > tmr_result['context_score']
        
        # Both should have context scores populated
        assert esr_result['context_score'] > 0
        assert 'base_score' in esr_result
        assert 'final_score' in esr_result


class TestTypeCompatibilityFilter:
    """Test suite for type-based filtering."""
    
    def test_initialization(self):
        """Test filter initialization."""
        compatibility = {
            'signal': {'register', 'signal'},
            'module': {'component', 'interface'}
        }
        filter = TypeCompatibilityFilter(compatibility)
        
        assert 'signal' in filter.compatibility_matrix
        assert 'register' in filter.compatibility_matrix['signal']
    
    def test_is_compatible(self):
        """Test type compatibility checking."""
        filter = TypeCompatibilityFilter({
            'signal': {'register', 'signal'},
            'module': {'component'}
        })
        
        # Compatible types
        assert filter.is_compatible('signal', 'register') == True
        assert filter.is_compatible('signal', 'signal') == True
        
        # Incompatible types
        assert filter.is_compatible('signal', 'component') == False
        
        # Unknown source type (permissive mode)
        assert filter.is_compatible('unknown', 'register') == True
    
    def test_strict_mode(self):
        """Test strict mode behavior."""
        filter = TypeCompatibilityFilter(
            {'signal': {'register'}},
            strict_mode=True
        )
        
        # Unknown types rejected in strict mode
        assert filter.is_compatible('unknown', 'register') == False
        assert filter.is_compatible('signal', 'UNKNOWN') == False
    
    def test_filter_candidates(self):
        """Test candidate filtering."""
        filter = TypeCompatibilityFilter({
            'signal': {'register', 'signal'}
        })
        
        candidates = [
            {'name': 'A', 'type': 'register'},
            {'name': 'B', 'type': 'instruction'},
            {'name': 'C', 'type': 'signal'}
        ]
        
        filtered = filter.filter_candidates('signal', candidates)
        
        assert len(filtered) == 2
        assert all(c['type'] in {'register', 'signal'} for c in filtered)
    
    def test_get_compatible_types(self):
        """Test retrieving compatible types."""
        filter = TypeCompatibilityFilter({
            'signal': {'register', 'signal', 'feature'}
        })
        
        types = filter.get_compatible_types('signal')
        assert types == {'register', 'signal', 'feature'}


class TestAcronymExpansionHandler:
    """Test suite for acronym expansion."""
    
    def test_initialization(self):
        """Test handler initialization."""
        handler = AcronymExpansionHandler({
            'ESR': 'Exception Status Register',
            'ALU': ['Arithmetic Logic Unit']
        })
        
        assert 'ESR' in handler.acronym_dict
        assert isinstance(handler.acronym_dict['ESR'], list)
    
    def test_case_insensitive_matching(self):
        """Test case-insensitive acronym matching."""
        handler = AcronymExpansionHandler(
            {'ESR': 'Exception Status Register'},
            case_sensitive=False
        )
        
        assert handler.is_acronym('ESR') == True
        assert handler.is_acronym('esr') == True
        assert handler.is_acronym('EsR') == True
    
    def test_case_sensitive_matching(self):
        """Test case-sensitive acronym matching."""
        handler = AcronymExpansionHandler(
            {'ESR': 'Exception Status Register'},
            case_sensitive=True
        )
        
        assert handler.is_acronym('ESR') == True
        assert handler.is_acronym('esr') == False
    
    def test_expand_search_terms(self):
        """Test search term expansion."""
        handler = AcronymExpansionHandler({
            'ESR': ['Exception Status Register', 'Exception State Register']
        })
        
        # Acronym expansion
        terms = handler.expand_search_terms('ESR')
        assert len(terms) == 3  # Original + 2 expansions
        assert 'ESR' in terms
        assert 'Exception Status Register' in terms
        
        # Non-acronym
        terms = handler.expand_search_terms('UNKNOWN')
        assert terms == ['UNKNOWN']
    
    def test_add_remove_acronym(self):
        """Test adding and removing acronyms."""
        handler = AcronymExpansionHandler({})
        
        # Add acronym
        handler.add_acronym('CPU', 'Central Processing Unit')
        assert handler.is_acronym('CPU') == True
        
        # Remove acronym
        removed = handler.remove_acronym('CPU')
        assert removed == True
        assert handler.is_acronym('CPU') == False
        
        # Remove non-existent
        removed = handler.remove_acronym('NOTFOUND')
        assert removed == False
    
    def test_statistics(self):
        """Test statistics generation."""
        handler = AcronymExpansionHandler({
            'ESR': ['Exception Status Register', 'Exception State Register'],
            'ALU': ['Arithmetic Logic Unit'],
            'MMU': ['Memory Management Unit']
        })
        
        stats = handler.get_statistics()
        assert stats['total_acronyms'] == 3
        assert stats['total_expansions'] == 4
        assert stats['multi_expansion_count'] == 1  # ESR has 2 expansions


class TestRelationshipProvenanceSweeper:
    """Test suite for relationship sweeping."""
    
    def test_initialization(self):
        """Test sweeper initialization."""
        sweeper = RelationshipProvenanceSweeper()
        assert sweeper.track_provenance == True
        assert sweeper.deduplicate_edges == True
    
    def test_sweep_without_remapping(self):
        """Test sweeping when entity IDs don't change."""
        sweeper = RelationshipProvenanceSweeper(track_provenance=False)
        
        # Empty mapping means no remapping
        relationships = [
            {'_from': 'A', '_to': 'B', 'type': 'RELATED'}
        ]
        
        result = sweeper.sweep_relationships({}, relationships)
        # With track_provenance=False and no remapping, should skip
        assert len(result) == 0
    
    def test_sweep_with_deduplication(self):
        """Test edge deduplication."""
        sweeper = RelationshipProvenanceSweeper(deduplicate_edges=True)
        
        entity_mapping = {
            'ent_a1': 'golden_a',
            'ent_a2': 'golden_a'  # Duplicate
        }
        
        relationships = [
            {'_id': 'rel_1', '_from': 'ent_a1', '_to': 'ent_b', 'type': 'KNOWS'},
            {'_id': 'rel_2', '_from': 'ent_a2', '_to': 'ent_b', 'type': 'KNOWS'}
        ]
        
        result = sweeper.sweep_relationships(entity_mapping, relationships)
        
        # Should deduplicate to 1 edge
        assert len(result) == 1
        assert result[0]['_from'] == 'golden_a'
        
        # Should track provenance
        assert len(result[0]['provenance']) == 2
    
    def test_sweep_without_deduplication(self):
        """Test keeping duplicate edges."""
        sweeper = RelationshipProvenanceSweeper(deduplicate_edges=False)
        
        entity_mapping = {
            'ent_a1': 'golden_a',
            'ent_a2': 'golden_a'
        }
        
        relationships = [
            {'_id': 'rel_1', '_from': 'ent_a1', '_to': 'ent_b', 'type': 'KNOWS'},
            {'_id': 'rel_2', '_from': 'ent_a2', '_to': 'ent_b', 'type': 'KNOWS'}
        ]
        
        result = sweeper.sweep_relationships(entity_mapping, relationships)
        
        # Should keep both edges
        assert len(result) == 2
    
    def test_statistics(self):
        """Test statistics calculation."""
        sweeper = RelationshipProvenanceSweeper()
        
        original = [
            {'_id': '1', '_from': 'a', '_to': 'b', 'type': 'X'},
            {'_id': '2', '_from': 'a', '_to': 'b', 'type': 'X'},
            {'_id': '3', '_from': 'a', '_to': 'b', 'type': 'X'}
        ]
        
        golden = [
            {'_id': 'g1', '_from': 'golden_a', '_to': 'golden_b', 'type': 'X',
             'provenance': [{'source_id': '1'}, {'source_id': '2'}, {'source_id': '3'}]}
        ]
        
        stats = sweeper.get_statistics(original, golden)
        
        assert stats['original_relationship_count'] == 3
        assert stats['golden_relationship_count'] == 1
        assert stats['relationships_merged'] == 2
        assert stats['deduplication_percentage'] == pytest.approx(66.67, rel=0.1)
    
    def test_validation(self):
        """Test entity mapping validation."""
        sweeper = RelationshipProvenanceSweeper()
        
        # Valid mapping
        entity_mapping = {'ent_1': 'golden_1'}
        golden_entities = [{'_id': 'golden_1'}]
        
        is_valid, errors = sweeper.validate_mapping(entity_mapping, golden_entities)
        assert is_valid == True
        assert len(errors) == 0
        
        # Invalid mapping (target doesn't exist)
        entity_mapping = {'ent_1': 'non_existent'}
        is_valid, errors = sweeper.validate_mapping(entity_mapping, golden_entities)
        assert is_valid == False
        assert len(errors) > 0


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, '-v'])


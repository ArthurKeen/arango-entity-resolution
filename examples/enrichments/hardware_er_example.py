"""
Hardware Entity Resolution Example

Demonstrates using the IC Enrichment Pack for hardware entity resolution.
This example shows how the OR1200 Knowledge Graph project uses these components.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ic_enrichment import (
    HierarchicalContextResolver,
    TypeCompatibilityFilter,
    AcronymExpansionHandler,
    RelationshipProvenanceSweeper
)


def hardware_er_example():
    """
    Complete example of hardware entity resolution workflow.
    """
    print("IC Design Entity Resolution Example")
    print("=" * 60)
    
    # 1. Set up Type Compatibility
    print("\n1. Setting up Type Compatibility Filter...")
    type_filter = TypeCompatibilityFilter({
        'signal': {'register', 'signal', 'architecture_feature', 'UNKNOWN'},
        'module': {'processor_component', 'memory_unit', 'hardware_interface', 'UNKNOWN'},
        'port': {'register', 'signal', 'hardware_interface', 'architecture_feature', 'UNKNOWN'},
        'logic': {'instruction', 'architecture_feature', 'configuration', 'exception_type', 'UNKNOWN'}
    })
    
    # 2. Set up Acronym Expansion
    print("2. Setting up Acronym Handler...")
    acronym_handler = AcronymExpansionHandler({
        'ESR': ['Exception Status Register', 'Exception State Register'],
        'ALU': ['Arithmetic Logic Unit'],
        'MMU': ['Memory Management Unit'],
        'PC': ['Program Counter'],
        'SPR': ['Special Purpose Register']
    })
    
    # 3. Set up Context Resolver
    print("3. Setting up Hierarchical Context Resolver...")
    context_resolver = HierarchicalContextResolver(
        parent_field='module_name',
        context_field='description',
        context_weight=0.3
    )
    
    print("\n" + "=" * 60)
    print("Example Workflow: Resolving Signal 'esr'")
    print("=" * 60)
    
    # Sample data
    signal_item = {
        'name': 'esr',
        'type': 'signal',
        'module_name': 'or1200_except'
    }
    
    module_context = "Exception handling module. Manages processor exceptions and interrupts."
    
    candidates = [
        {
            'name': 'ESR Register',
            'type': 'register',
            'description': 'Exception Status Register holds processor state during exception'
        },
        {
            'name': 'ESR',
            'type': 'register',
            'description': 'Register used to save processor state'
        },
        {
            'name': 'ADD Instruction',
            'type': 'instruction',
            'description': 'Arithmetic addition instruction'
        },
        {
            'name': 'Error Signal',
            'type': 'signal',
            'description': 'General error signaling'
        }
    ]
    
    print(f"\nSignal to resolve: {signal_item['name']}")
    print(f"Module context: {module_context}")
    print(f"\nCandidates before filtering: {len(candidates)}")
    
    # Step 1: Expand acronym
    search_terms = acronym_handler.expand_search_terms('esr')
    print(f"\nAcronym expansion:")
    print(f"  Original: 'esr'")
    print(f"  Expanded: {search_terms}")
    
    # Step 2: Filter by type
    type_filtered = type_filter.filter_candidates(signal_item['type'], candidates)
    print(f"\nAfter type filtering: {len(type_filtered)} candidates")
    for cand in type_filtered:
        print(f"  - {cand['name']} ({cand['type']})")
    
    # Step 3: Resolve with context
    def dummy_similarity(cand):
        # In real usage, this would be your similarity function
        name_lower = cand['name'].lower()
        if 'esr' in name_lower or 'exception' in name_lower:
            return 0.85
        return 0.5
    
    matches = context_resolver.resolve_with_context(
        item=signal_item,
        candidates=type_filtered,
        parent_context=module_context,
        base_similarity_fn=dummy_similarity,
        threshold=0.6
    )
    
    print(f"\nFinal matches (with context boost):")
    for i, match in enumerate(matches, 1):
        print(f"  {i}. {match['name']}")
        print(f"     Base score: {match['base_score']:.3f}")
        print(f"     Context score: {match['context_score']:.3f}")
        print(f"     Final score: {match['final_score']:.3f}")
    
    # Step 4: Demonstrate relationship sweeping
    print("\n" + "=" * 60)
    print("Example: Relationship Sweeping After Consolidation")
    print("=" * 60)
    
    sweeper = RelationshipProvenanceSweeper(track_provenance=True)
    
    # Simulate entity consolidation
    entity_mapping = {
        'ESR_Register_1': 'Golden_ESR',
        'ESR_Register_2': 'Golden_ESR',  # Duplicate
        'ESR_3': 'Golden_ESR',  # Another duplicate
        'ALU_Entity': 'Golden_ALU'
    }
    
    relationships = [
        {'_id': 'rel_1', '_from': 'ESR_Register_1', '_to': 'ALU_Entity', 'type': 'RELATED_TO'},
        {'_id': 'rel_2', '_from': 'ESR_Register_2', '_to': 'ALU_Entity', 'type': 'RELATED_TO'},
        {'_id': 'rel_3', '_from': 'ESR_3', '_to': 'ALU_Entity', 'type': 'DEPENDS_ON'}
    ]
    
    print(f"\nOriginal relationships: {len(relationships)}")
    
    golden_relations = sweeper.sweep_relationships(entity_mapping, relationships)
    
    print(f"Golden relationships: {len(golden_relations)}")
    print("\nConsolidated relationships:")
    for rel in golden_relations:
        print(f"  {rel['_from']} -> {rel['_to']} ({rel['type']})")
        if 'provenance' in rel:
            print(f"    Sources: {[p['source_id'] for p in rel['provenance']]}")
    
    stats = sweeper.get_statistics(relationships, golden_relations)
    print(f"\nDeduplication: {stats['deduplication_percentage']:.1f}% reduction")
    
    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    hardware_er_example()


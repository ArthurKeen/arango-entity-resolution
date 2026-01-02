"""
Domain-Agnostic Examples for IC Enrichment Pack

Demonstrates applicability across medical, legal, organizational, and retail domains.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# ==============================================================================
# Example 1: Medical Records - Clinical Entity Resolution
# ==============================================================================

from ic_enrichment import (
    HierarchicalContextResolver,
    TypeCompatibilityFilter,
    AcronymExpansionHandler,
    RelationshipProvenanceSweeper
)


def medical_entity_resolution():
    """
    Scenario: Resolving clinical terms from multiple hospitals into a unified
    patient record system. Each hospital uses different terminology and acronyms.
    """
    
    # Medical acronyms - many have multiple meanings
    medical_acronyms = AcronymExpansionHandler({
        'MI': ['Myocardial Infarction', 'Mitral Insufficiency'],
        'CHF': ['Congestive Heart Failure'],
        'COPD': ['Chronic Obstructive Pulmonary Disease'],
        'MS': ['Multiple Sclerosis', 'Mitral Stenosis'],
        'RA': ['Rheumatoid Arthritis', 'Right Atrium'],
        'DM': ['Diabetes Mellitus'],
        'HTN': ['Hypertension']
    })
    
    # Medical type constraints - prevent nonsensical matches
    medical_types = TypeCompatibilityFilter({
        'condition': {'condition', 'syndrome', 'disorder', 'side_effect'},
        'medication': {'drug', 'treatment', 'therapy'},
        'procedure': {'surgery', 'test', 'examination', 'procedure'},
        'anatomy': {'organ', 'tissue', 'body_system'}
    })
    
    # Hierarchical context - organ system provides context
    medical_context = HierarchicalContextResolver(
        parent_field='organ_system',
        context_field='clinical_description'
    )
    
    # Example: Resolving "MI" in cardiology context
    item = {'name': 'MI', 'type': 'condition', 'department': 'Cardiology'}
    parent = {'name': 'Cardiovascular System', 'specialties': 'cardiology heart circulation'}
    
    candidates = [
        {'name': 'Myocardial Infarction', 'type': 'condition', 
         'clinical_description': 'heart attack due to blocked coronary arteries'},
        {'name': 'Mitral Insufficiency', 'type': 'condition',
         'clinical_description': 'heart valve regurgitation mitral valve'},
        {'name': 'Medical Imaging', 'type': 'procedure',  # Wrong type
         'clinical_description': 'diagnostic imaging techniques'}
    ]
    
    # Step 1: Expand acronym
    search_terms = medical_acronyms.expand_search_terms('MI')
    print(f"Search terms: {search_terms}")
    # Output: ['MI', 'Myocardial Infarction', 'Mitral Insufficiency']
    
    # Step 2: Filter by type compatibility
    compatible = medical_types.filter_candidates(
        source_type='condition',
        candidates=candidates,
        type_field='type'
    )
    print(f"Type-compatible candidates: {len(compatible)}/3")
    # Output: 2/3 (Medical Imaging filtered out)
    
    # Step 3: Resolve with context
    def dummy_similarity(cand):
        return 0.85
    
    results = medical_context.resolve_with_context(
        item=item,
        candidates=compatible,
        parent_context=parent.get('specialties', ''),
        base_similarity_fn=dummy_similarity
    )
    
    print("\nScored Results:")
    for r in results:
        print(f"  {r['name']}: {r['final_score']:.2f} (context: {r['context_score']:.2f})")
    
    return results


# ==============================================================================
# Example 2: Legal Document Analysis - Contract Clause Resolution
# ==============================================================================

def legal_entity_resolution():
    """
    Scenario: Standardizing contract clauses across multiple legal documents
    from different jurisdictions and time periods.
    """
    
    # Legal acronyms
    legal_acronyms = AcronymExpansionHandler({
        'SLA': ['Service Level Agreement'],
        'NDA': ['Non-Disclosure Agreement'],
        'ToS': ['Terms of Service'],
        'IP': ['Intellectual Property'],
        'PII': ['Personally Identifiable Information'],
        'GDPR': ['General Data Protection Regulation']
    })
    
    # Legal type constraints
    legal_types = TypeCompatibilityFilter({
        'obligation': {'duty', 'requirement', 'covenant', 'obligation'},
        'right': {'privilege', 'entitlement', 'permission', 'right'},
        'definition': {'term', 'meaning', 'interpretation', 'definition'},
        'clause': {'provision', 'article', 'section', 'clause'},
        'party': {'entity', 'person', 'organization'}
    })
    
    # Hierarchical context - contract type provides context
    legal_context = HierarchicalContextResolver(
        parent_field='contract_type',
        context_field='legal_description'
    )
    
    # Example: Resolving "IP" clause in software licensing context
    item = {'name': 'IP Rights', 'type': 'clause'}
    parent = {'name': 'Software License Agreement', 
              'domain': 'intellectual property licensing software copyright patents'}
    
    candidates = [
        {'name': 'Intellectual Property Rights', 'type': 'clause',
         'legal_description': 'ownership and licensing of copyrights patents trademarks software'},
        {'name': 'Internet Protocol Configuration', 'type': 'definition',  # Wrong type
         'legal_description': 'network addressing and routing protocols'},
        {'name': 'Installation Procedures', 'type': 'obligation',  # Wrong type
         'legal_description': 'software deployment and setup requirements'}
    ]
    
    # Type filtering
    compatible = legal_types.filter_candidates(
        source_type='clause',
        candidates=candidates,
        type_field='type'
    )
    print(f"\nLegal Example - Type-compatible: {len(compatible)}/3")
    
    return compatible


# ==============================================================================
# Example 3: Organization Chart - Employee/Department Resolution
# ==============================================================================

def organizational_entity_resolution():
    """
    Scenario: Merging HR data from multiple subsidiaries after an acquisition.
    """
    
    # Organizational acronyms
    org_acronyms = AcronymExpansionHandler({
        'CEO': ['Chief Executive Officer'],
        'CFO': ['Chief Financial Officer'],
        'CTO': ['Chief Technology Officer'],
        'VP': ['Vice President'],
        'HR': ['Human Resources'],
        'IT': ['Information Technology'],
        'R&D': ['Research and Development']
    })
    
    # Organizational type constraints
    org_types = TypeCompatibilityFilter({
        'person': {'employee', 'contractor', 'executive', 'person'},
        'department': {'division', 'team', 'unit', 'department'},
        'role': {'position', 'title', 'job_function', 'role'},
        'location': {'office', 'site', 'region'}
    })
    
    # Hierarchical context - department provides context
    org_context = HierarchicalContextResolver(
        parent_field='department',
        context_field='responsibilities'
    )
    
    # Example: Resolving VP across different subsidiaries
    item = {'name': 'VP Engineering', 'type': 'role'}
    parent = {'name': 'Engineering Department', 
              'scope': 'software hardware systems architecture development'}
    
    candidates = [
        {'name': 'Vice President of Engineering', 'type': 'role',
         'responsibilities': 'engineering teams product development technical strategy'},
        {'name': 'VP Sales Engineering', 'type': 'role',
         'responsibilities': 'pre-sales technical customer solutions'},
        {'name': 'Validation Process', 'type': 'department',  # Wrong type
         'responsibilities': 'quality assurance testing verification'}
    ]
    
    compatible = org_types.filter_candidates(
        source_type='role',
        candidates=candidates,
        type_field='type'
    )
    
    def dummy_similarity(cand):
        return 0.80
    
    results = org_context.resolve_with_context(
        item=item,
        candidates=compatible,
        parent_context=parent.get('scope', ''),
        base_similarity_fn=dummy_similarity
    )
    
    print("\nOrganizational Example:")
    for r in results:
        print(f"  {r['name']}: {r['final_score']:.2f}")
    
    return results


# ==============================================================================
# Example 4: E-Commerce - Product Catalog Consolidation
# ==============================================================================

def retail_entity_resolution():
    """
    Scenario: Merging product catalogs from multiple vendors with inconsistent
    naming and categorization.
    """
    
    # Retail acronyms
    retail_acronyms = AcronymExpansionHandler({
        'SKU': ['Stock Keeping Unit'],
        'UPC': ['Universal Product Code'],
        'ISBN': ['International Standard Book Number'],
        'MSRP': ['Manufacturer Suggested Retail Price'],
        'EAN': ['European Article Number']
    })
    
    # Retail type constraints
    retail_types = TypeCompatibilityFilter({
        'product': {'item', 'sku', 'merchandise', 'product'},
        'category': {'group', 'department', 'classification', 'category'},
        'brand': {'manufacturer', 'vendor', 'supplier'},
        'attribute': {'specification', 'feature', 'property'}
    })
    
    # Example: Resolving product identifiers
    item = {'name': 'SKU-12345', 'type': 'product', 'category': 'electronics'}
    
    candidates = [
        {'name': 'Wireless Mouse', 'type': 'product',
         'category': 'electronics', 'vendor': 'TechCorp'},
        {'name': 'Skeleton Key', 'type': 'product',  # SKU mismatch
         'category': 'hardware', 'vendor': 'LockCo'},
        {'name': 'Electronics', 'type': 'category',  # Wrong type
         'category': 'top-level'}
    ]
    
    compatible = retail_types.filter_candidates(
        source_type='product',
        candidates=candidates,
        type_field='type'
    )
    print(f"\nRetail Example - Type-compatible: {len(compatible)}/3")
    
    return compatible


# ==============================================================================
# Example 5: Relationship Sweeping After Entity Consolidation
# ==============================================================================

def demonstrate_relationship_sweeping():
    """
    Scenario: After merging duplicate entities, remap all relationships to
    the golden records and track provenance.
    """
    
    sweeper = RelationshipProvenanceSweeper(
        track_provenance=True,
        deduplicate_edges=True
    )
    
    # Simulated entity consolidation from medical example
    # Multiple hospital records merged into canonical patient record
    entity_mapping = {
        'patient_hospital_a_123': 'patient_canonical_001',
        'patient_clinic_b_456': 'patient_canonical_001',  # Same patient
        'condition_code_mi_v1': 'condition_myocardial_infarction',
        'condition_heart_attack': 'condition_myocardial_infarction'  # Same condition
    }
    
    # Original relationships from different sources
    original_relationships = [
        {'_id': 'rel_1', '_from': 'patient_hospital_a_123', 
         '_to': 'condition_code_mi_v1', 'type': 'HAS_CONDITION'},
        {'_id': 'rel_2', '_from': 'patient_clinic_b_456',
         '_to': 'condition_heart_attack', 'type': 'HAS_CONDITION'},  # Duplicate
        {'_id': 'rel_3', '_from': 'patient_hospital_a_123',
         '_to': 'medication_aspirin', 'type': 'PRESCRIBED'}
    ]
    
    # Sweep relationships
    golden_relationships = sweeper.sweep_relationships(
        entity_mapping,  # First positional arg
        original_relationships  # Second positional arg
    )
    
    print("\nRelationship Sweeping Example:")
    print(f"Original relationships: {len(original_relationships)}")
    print(f"Golden relationships: {len(golden_relationships)}")
    
    for rel in golden_relationships:
        print(f"\n{rel['_from']} --[{rel['type']}]--> {rel['_to']}")
        print(f"  Provenance: {len(rel['provenance'])} source(s)")
    
    # Statistics
    stats = sweeper.get_statistics(original_relationships, golden_relationships)
    print(f"\nDeduplication: {stats['deduplication_percentage']:.1f}%")
    
    return golden_relationships


# ==============================================================================
# Main Execution
# ==============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("IC ENRICHMENT PACK - DOMAIN-AGNOSTIC EXAMPLES")
    print("=" * 80)
    
    print("\n[1/5] Medical Records Entity Resolution")
    print("-" * 80)
    medical_entity_resolution()
    
    print("\n[2/5] Legal Contract Analysis")
    print("-" * 80)
    legal_entity_resolution()
    
    print("\n[3/5] Organizational Chart Consolidation")
    print("-" * 80)
    organizational_entity_resolution()
    
    print("\n[4/5] Retail Product Catalog Merge")
    print("-" * 80)
    retail_entity_resolution()
    
    print("\n[5/5] Relationship Provenance Sweeping")
    print("-" * 80)
    demonstrate_relationship_sweeping()
    
    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)


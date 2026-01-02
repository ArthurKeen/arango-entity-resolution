"""
Relationship Provenance Sweeper

Remaps relationships after entity consolidation while preserving full provenance.
Critical for multi-source knowledge graph merging and maintaining data lineage
for compliance and debugging.

Use Cases:
- Knowledge graph merging from multiple sources
- Entity deduplication with relationship preservation
- Data lineage tracking for compliance/audit
- Quality analysis and debugging of ER process
"""

import hashlib
from typing import List, Dict, Any, Set, Optional, Tuple


class RelationshipProvenanceSweeper:
    """
    Remaps relationships through entity consolidation with provenance tracking.
    
    After entities are deduplicated/consolidated, their relationships need to be
    remapped to point to the canonical (golden) entities. This class handles that
    remapping while preserving full audit trail of where relationships came from.
    
    Attributes:
        track_provenance (bool): Whether to track source relationships
        deduplicate_edges (bool): Whether to merge duplicate remapped edges
        provenance_field (str): Field name for provenance information
    
    Example:
        >>> sweeper = RelationshipProvenanceSweeper(track_provenance=True)
        >>> 
        >>> # Entity mapping: duplicate -> canonical
        >>> entity_mapping = {
        ...     'entity_1': 'golden_entity_A',
        ...     'entity_2': 'golden_entity_A',  # Duplicate of A
        ...     'entity_3': 'golden_entity_B'
        ... }
        >>> 
        >>> # Original relationships
        >>> relationships = [
        ...     {'_from': 'entity_1', '_to': 'entity_3', 'type': 'RELATED_TO'},
        ...     {'_from': 'entity_2', '_to': 'entity_3', 'type': 'RELATED_TO'}  # Duplicate after mapping
        ... ]
        >>> 
        >>> # Sweep relationships
        >>> golden_relations = sweeper.sweep_relationships(entity_mapping, relationships)
        >>> len(golden_relations)  # Deduplicated
        1
    """
    
    def __init__(
        self,
        track_provenance: bool = True,
        deduplicate_edges: bool = True,
        provenance_field: str = 'provenance'
    ):
        """
        Initialize the Relationship Provenance Sweeper.
        
        Args:
            track_provenance: If True, track which original relationships contributed
            deduplicate_edges: If True, merge duplicate remapped edges
            provenance_field: Field name to store provenance information
        """
        self.track_provenance = track_provenance
        self.deduplicate_edges = deduplicate_edges
        self.provenance_field = provenance_field
    
    def _generate_edge_key(self, from_id: str, to_id: str, edge_type: str) -> str:
        """Generate a unique key for an edge."""
        # Use hash to create deterministic key
        key_string = f"{from_id}|{to_id}|{edge_type}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def sweep_relationships(
        self,
        entity_mapping: Dict[str, str],
        relationships: List[Dict[str, Any]],
        from_field: str = '_from',
        to_field: str = '_to',
        type_field: str = 'type',
        id_field: str = '_id'
    ) -> List[Dict[str, Any]]:
        """
        Remap relationships through entity consolidation.
        
        Args:
            entity_mapping: Maps original entity IDs to golden entity IDs
            relationships: List of original relationships to remap
            from_field: Field name for source entity
            to_field: Field name for target entity
            type_field: Field name for relationship type
            id_field: Field name for relationship ID
        
        Returns:
            List of remapped relationships with provenance
        
        Example:
            >>> entity_mapping = {
            ...     'ent_a1': 'golden_a',
            ...     'ent_a2': 'golden_a',  # Duplicate
            ...     'ent_b1': 'golden_b'
            ... }
            >>> relationships = [
            ...     {'_id': 'rel_1', '_from': 'ent_a1', '_to': 'ent_b1', 'type': 'KNOWS'},
            ...     {'_id': 'rel_2', '_from': 'ent_a2', '_to': 'ent_b1', 'type': 'KNOWS'}
            ... ]
            >>> golden_rels = sweeper.sweep_relationships(entity_mapping, relationships)
            >>> len(golden_rels)  # Deduplicated
            1
            >>> golden_rels[0]['provenance']  # Tracks both sources
            [{'source_id': 'rel_1', ...}, {'source_id': 'rel_2', ...}]
        """
        golden_relations = {}
        
        for rel in relationships:
            source = rel.get(from_field)
            target = rel.get(to_field)
            rel_type = rel.get(type_field, 'RELATED_TO')
            rel_id = rel.get(id_field, str(id(rel)))
            
            if not source or not target:
                continue
            
            # Remap source if it's a consolidated entity
            new_source = entity_mapping.get(source, source)
            
            # Remap target if it's a consolidated entity
            new_target = entity_mapping.get(target, target)
            
            # Skip if relationship didn't change (no remapping needed)
            if new_source == source and new_target == target and not self.track_provenance:
                continue
            
            # Create provenance record
            provenance_record = {
                'source_id': rel_id,
                'original_from': source,
                'original_to': target
            }
            
            # Add any additional metadata from original relationship
            for key, value in rel.items():
                if key not in (from_field, to_field, type_field, id_field):
                    provenance_record[key] = value
            
            # Generate key for deduplication
            rel_key = (new_source, new_target, rel_type)
            
            if self.deduplicate_edges:
                if rel_key not in golden_relations:
                    # First occurrence - create new golden relation
                    edge_key = self._generate_edge_key(new_source, new_target, rel_type)
                    
                    golden_relations[rel_key] = {
                        '_key': edge_key,
                        from_field: new_source,
                        to_field: new_target,
                        type_field: rel_type
                    }
                    
                    if self.track_provenance:
                        golden_relations[rel_key][self.provenance_field] = [provenance_record]
                else:
                    # Duplicate - add to provenance
                    if self.track_provenance:
                        golden_relations[rel_key][self.provenance_field].append(provenance_record)
            else:
                # Not deduplicating - create separate entry for each
                edge_key = self._generate_edge_key(new_source, new_target, rel_type) + f"_{len(golden_relations)}"
                
                golden_rel = {
                    '_key': edge_key,
                    from_field: new_source,
                    to_field: new_target,
                    type_field: rel_type
                }
                
                if self.track_provenance:
                    golden_rel[self.provenance_field] = [provenance_record]
                
                golden_relations[rel_key + (len(golden_relations),)] = golden_rel
        
        return list(golden_relations.values())
    
    def get_statistics(
        self,
        original_relationships: List[Dict[str, Any]],
        golden_relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get statistics about the sweeping process.
        
        Args:
            original_relationships: List of relationships before sweeping
            golden_relationships: List of relationships after sweeping
        
        Returns:
            Statistics dict with counts and ratios
        
        Example:
            >>> stats = sweeper.get_statistics(original_rels, golden_rels)
            >>> print(f"Reduction: {stats['deduplication_percentage']:.1f}%")
        """
        orig_count = len(original_relationships)
        golden_count = len(golden_relationships)
        
        # Count relationships with multiple provenance sources
        multi_source_count = 0
        max_sources = 0
        
        if self.track_provenance:
            for rel in golden_relationships:
                provenance = rel.get(self.provenance_field, [])
                prov_count = len(provenance)
                
                if prov_count > 1:
                    multi_source_count += 1
                
                max_sources = max(max_sources, prov_count)
        
        reduction = orig_count - golden_count
        
        return {
            'original_relationship_count': orig_count,
            'golden_relationship_count': golden_count,
            'relationships_merged': reduction,
            'deduplication_percentage': (reduction / orig_count * 100) if orig_count > 0 else 0,
            'multi_source_relationships': multi_source_count,
            'max_sources_per_relationship': max_sources,
            'average_sources_per_relationship': orig_count / golden_count if golden_count > 0 else 0
        }
    
    def extract_provenance_graph(
        self,
        golden_relationships: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Extract provenance graph showing which original relationships
        contributed to which golden relationships.
        
        Args:
            golden_relationships: List of golden relationships with provenance
        
        Returns:
            Dict mapping golden relationship IDs to lists of source relationship IDs
        
        Example:
            >>> prov_graph = sweeper.extract_provenance_graph(golden_rels)
            >>> for golden_id, sources in prov_graph.items():
            ...     print(f"{golden_id} came from: {sources}")
        """
        provenance_graph = {}
        
        for rel in golden_relationships:
            golden_id = rel.get('_key', rel.get('_id', str(id(rel))))
            
            if self.provenance_field in rel:
                source_ids = [
                    prov.get('source_id')
                    for prov in rel[self.provenance_field]
                    if 'source_id' in prov
                ]
                provenance_graph[golden_id] = source_ids
        
        return provenance_graph
    
    def validate_mapping(
        self,
        entity_mapping: Dict[str, str],
        golden_entities: List[Dict[str, Any]],
        id_field: str = '_id'
    ) -> Tuple[bool, List[str]]:
        """
        Validate that entity mapping is consistent.
        
        Args:
            entity_mapping: The entity mapping to validate
            golden_entities: List of golden entities
            id_field: Field name for entity ID
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        
        Example:
            >>> is_valid, errors = sweeper.validate_mapping(mapping, golden_entities)
            >>> if not is_valid:
            ...     for error in errors:
            ...         print(f"Validation error: {error}")
        """
        errors = []
        
        # Get set of golden entity IDs
        golden_ids = {entity.get(id_field) for entity in golden_entities}
        
        # Check that all mapped-to entities exist
        for source, target in entity_mapping.items():
            if target not in golden_ids and target not in entity_mapping:
                # Target should be a golden entity (not another source entity)
                if target not in golden_ids:
                    errors.append(
                        f"Entity mapping references non-existent golden entity: "
                        f"{source} -> {target}"
                    )
        
        # Check for cycles in mapping
        visited = set()
        for source in entity_mapping:
            path = []
            current = source
            
            while current in entity_mapping:
                if current in visited:
                    if current in path:
                        errors.append(f"Cycle detected in entity mapping: {' -> '.join(path + [current])}")
                    break
                
                path.append(current)
                current = entity_mapping[current]
                
                if len(path) > 100:  # Prevent infinite loops
                    errors.append(f"Mapping chain too long (possible cycle): {source}")
                    break
            
            visited.update(path)
        
        return (len(errors) == 0, errors)


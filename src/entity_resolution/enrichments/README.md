# Entity Resolution Enrichments

Four standalone components for entity resolution in technical and hierarchical domains.

## Installation

These enrichments are included with arango-entity-resolution but are **standalone modules** that don't require database configuration.

## Usage

```python
# Import directly from enrichments to avoid database config requirements
from entity_resolution.enrichments import (
TypeCompatibilityFilter,
HierarchicalContextResolver,
AcronymExpansionHandler,
RelationshipProvenanceSweeper
)
```

**Note:** If you get import errors about database configuration, the enrichments can be imported directly:

```python
import sys
sys.path.insert(0, 'src/entity_resolution/enrichments')

from type_constraints import TypeCompatibilityFilter
from context_resolver import HierarchicalContextResolver
from acronym_handler import AcronymExpansionHandler
from relationship_sweeper import RelationshipProvenanceSweeper
```

## Components

### 1. Type Compatibility Filter

Pre-filters candidates by type compatibility to prevent nonsensical matches.

```python
type_filter = TypeCompatibilityFilter({
'signal': {'register', 'signal', 'architecture_feature'},
'diagnosis': {'condition', 'disease', 'syndrome'}
})

valid_candidates = type_filter.filter_candidates('signal', all_candidates)
```

**Impact:** Hardware domain - eliminated all false positives (50% -> 100% precision)

### 2. Hierarchical Context Resolver

Uses parent entity context to improve child entity resolution.

```python
resolver = HierarchicalContextResolver(
parent_field='parent_id',
context_field='description',
context_weight=0.3
)

matches = resolver.resolve_with_context(
item=entity,
candidates=candidates,
parent_context=parent_description,
base_similarity_fn=your_similarity_function
)
```

**Impact:** Hardware domain - improved recall from 11% to 44%

### 3. Acronym Expansion Handler

Expands domain-specific abbreviations during search.

```python
acronym_handler = AcronymExpansionHandler({
'MI': ['Myocardial Infarction', 'Mitral Insufficiency'],
'ESR': ['Exception Status Register']
})

search_terms = acronym_handler.expand_search_terms('MI')
# Returns: ['MI', 'Myocardial Infarction', 'Mitral Insufficiency']
```

**Impact:** Medical domain - baseline had 0% recall without expansion, achieved 100% with it

### 4. Relationship Provenance Sweeper

Remaps relationships after entity consolidation with full audit trail.

```python
sweeper = RelationshipProvenanceSweeper(track_provenance=True)

golden_relations = sweeper.sweep_relationships(
entity_mapping={'old_id_1': 'golden_id', 'old_id_2': 'golden_id'},
relationships=original_relationships
)
```

**Impact:** 33% relationship deduplication with full lineage tracking

## Validation

Validated on ground truth datasets:
- **Hardware:** 15 labeled pairs - F1: 0.18 -> 0.62
- **Medical:** 12 labeled pairs - F1: 0.00 -> 0.94

See `docs/validation/` for full methodology and reproducible experiments.

## Examples

- `examples/enrichments/hardware_er_example.py` - IC design use case
- `examples/enrichments/domain_agnostic_examples.py` - Medical, legal, org, retail examples

## Testing

```bash
# Standalone test (no database required)
python3 test_enrichments_standalone.py

# Full test suite (requires database config)
pytest tests/enrichments/test_components.py -v
```

## Limitations

- Small validation samples (27 pairs total)
- Single labeler (no inter-rater reliability)
- Proof-of-concept level - not production validated
- See `docs/validation/validation_methodology.md` for full details

## License

MIT License (same as arango-entity-resolution)


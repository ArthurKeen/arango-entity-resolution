# Entity Resolution Enrichments

**Package:** `entity_resolution.enrichments`
**Status:** Integrated
**Documentation:** Specialized components for hierarchical and technical domain entity resolution

---

## Overview

The Enrichments package provides components that address common challenges in entity resolution for hierarchical knowledge graphs and technical domains:

1. **Type Compatibility Filter** - Pre-filters candidates by type to prevent nonsensical matches (e.g., preventing a 'Signal' from matching an 'Instruction').
2. **Hierarchical Context Resolver** - Uses parent entity context to disambiguate similar names by looking for token overlap in parent descriptions.
3. **Acronym Expansion Handler** - Expands domain-specific abbreviations during search to improve recall for abbreviated terms.
4. **Relationship Provenance Sweeper** - Remaps relationships after deduplication while maintaining an audit trail of the original sources.

---

## Validation Results

The components have been validated across different domains to ensure generalizability:

### Hardware Domain

| Metric | Baseline | Enhanced | Delta |
|--------|----------|----------|---|
| Precision | 0.50 | 1.00 | +0.50 |
| Recall | 0.11 | 0.44 | +0.33 |
| F1 | 0.18 | 0.62 | +0.43 |

**Key Finding:** Perfect precision (no false positives) was achieved by enforcing type compatibility.

### Medical Domain

| Metric | Baseline | Enhanced | Delta |
|--------|----------|----------|---|
| Precision | 0.00 | 0.89 | +0.89 |
| Recall | 0.00 | 1.00 | +1.00 |
| F1 | 0.00 | 0.94 | +0.94 |

**Key Finding:** Acronym expansion was critical for medical abbreviations where the baseline failed to find any matches.

---

## Technical Details

### Type Compatibility Filter

**What it does:** Pre-filters candidates using a compatibility matrix before similarity scoring.

**Example:**
```python
from entity_resolution.enrichments import TypeCompatibilityFilter

type_filter = TypeCompatibilityFilter({
    'diagnosis': {'condition', 'disease', 'syndrome'},
    'medication': {'drug', 'treatment'}
})

# diagnosis <-> medication will be blocked even if names are similar
is_ok = type_filter.is_compatible('diagnosis', 'medication') # False
```

### Hierarchical Context Resolver

**What it does:** Blends base similarity with token overlap between parent context and candidate description.

**Example:**
```python
from entity_resolution.enrichments import HierarchicalContextResolver

resolver = HierarchicalContextResolver(weight=0.3)
# Resolving an item within a specific parent context
matches = resolver.resolve_with_context(item, candidates, "cardiology department")
```

### Acronym Expansion Handler

**What it does:** Expands search terms using a domain-specific abbreviation dictionary.

**Example:**
```python
from entity_resolution.enrichments import AcronymExpansionHandler

handler = AcronymExpansionHandler({'MI': ['Myocardial Infarction']})
terms = handler.expand_search_terms('MI')
# Returns: ['MI', 'Myocardial Infarction']
```

### Relationship Provenance Sweeper

**What it does:** After entity deduplication, remaps relationships to golden entities with provenance tracking.

**Example:**
```python
from entity_resolution.enrichments import RelationshipProvenanceSweeper

sweeper = RelationshipProvenanceSweeper()
# Remap original relationships to the new golden entity
swept_results = sweeper.sweep(relationships, entity_remapping)
```

---

## Usage

All components are available in the `entity_resolution.enrichments` package.

```python
from entity_resolution.enrichments import (
    HierarchicalContextResolver,
    TypeCompatibilityFilter,
    AcronymExpansionHandler,
    RelationshipProvenanceSweeper
)
```

For a complete working example, see `examples/enrichments/domain_agnostic_examples.py`.

---

## Testing

All components include comprehensive unit tests:
```bash
pytest tests/enrichments/test_components.py -v
```

Validation metrics can be reproduced using:
```bash
python3 docs/validation/validate_metrics.py --domain hardware
python3 docs/validation/validate_metrics.py --domain medical
```

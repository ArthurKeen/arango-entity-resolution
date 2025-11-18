# Computed Fields Guide

## Overview

Computed fields allow you to derive blocking keys from existing data fields using AQL expressions. This is essential when your data format doesn't match exactly what you need for blocking.

**Version:** 2.0+  
**Feature:** `CollectBlockingStrategy` with `computed_fields` parameter

---

## Common Use Cases

### 1. ZIP5 from POSTAL_CODE

Extract the first 5 digits of a postal code:

```python
from entity_resolution.strategies import CollectBlockingStrategy

strategy = CollectBlockingStrategy(
    db=db,
    collection="companies",
    blocking_fields=["address", "zip5"],  # zip5 is computed
    computed_fields={
        "zip5": "LEFT(d.postal_code, 5)"
    },
    filters={
        "address": {"not_null": True, "min_length": 5},
        "zip5": {"not_null": True, "min_length": 5}
    },
    max_block_size=50,
    min_block_size=2
)

pairs = strategy.generate_candidates()
```

**Generated AQL:**
```aql
FOR d IN companies
    LET zip5 = LEFT(d.postal_code, 5)
    FILTER d.address != null
    FILTER LENGTH(d.address) >= 5
    FILTER zip5 != null
    FILTER LENGTH(zip5) >= 5
    COLLECT address = d.address, zip5 = zip5
    INTO group
    KEEP d
    LET doc_keys = group[*].d._key
    FILTER LENGTH(doc_keys) >= 2
    FILTER LENGTH(doc_keys) <= 50
    FOR i IN 0..LENGTH(doc_keys)-2
        FOR j IN (i+1)..LENGTH(doc_keys)-1
            RETURN {
                doc1_key: doc_keys[i],
                doc2_key: doc_keys[j],
                blocking_keys: {address: address, zip5: zip5},
                block_size: LENGTH(doc_keys),
                method: "collect_blocking"
            }
```

### 2. Normalized Phone from Various Formats

Normalize phone numbers to digits only:

```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="customers",
    blocking_fields=["phone_normalized", "state"],
    computed_fields={
        "phone_normalized": "REGEX_REPLACE(d.phone, '[^0-9]', '')"
    },
    filters={
        "phone_normalized": {
            "not_null": True,
            "min_length": 10,
            "not_equal": ["0000000000", "1111111111"]
        },
        "state": {"not_null": True}
    },
    max_block_size=100,
    min_block_size=2
)
```

### 3. Name Initials + Last Name

Create a blocking key from name components:

```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="persons",
    blocking_fields=["name_key", "zip5"],
    computed_fields={
        "name_key": "CONCAT(LEFT(d.first_name, 1), LEFT(d.middle_name, 1), '_', d.last_name)",
        "zip5": "LEFT(d.postal_code, 5)"
    },
    filters={
        "name_key": {"not_null": True, "min_length": 3}
    },
    max_block_size=50,
    min_block_size=2
)
```

### 4. Combined Address Components

Normalize and combine address fields:

```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="addresses",
    blocking_fields=["address_key", "zip5"],
    computed_fields={
        "address_key": "UPPER(CONCAT(d.street_number, '_', d.street_name))",
        "zip5": "LEFT(d.postal_code, 5)"
    },
    filters={
        "address_key": {"not_null": True},
        "zip5": {"not_null": True}
    },
    max_block_size=30,
    min_block_size=2
)
```

### 5. Year from Date Field

Extract year from a date for temporal blocking:

```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="events",
    blocking_fields=["event_year", "location"],
    computed_fields={
        "event_year": "DATE_YEAR(d.event_date)"
    },
    filters={
        "event_year": {"not_null": True},
        "location": {"not_null": True}
    },
    max_block_size=1000,
    min_block_size=2
)
```

---

## Syntax Rules

### Computed Field Expressions

1. **Reference document fields:** Always use `d.field_name` in the expression
   ```python
   # ✅ Correct
   computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
   
   # ❌ Wrong
   computed_fields={"zip5": "LEFT(postal_code, 5)"}
   ```

2. **Use AQL functions:** Any AQL function is valid
   ```python
   computed_fields={
       "upper_name": "UPPER(d.name)",
       "digits_only": "REGEX_REPLACE(d.phone, '[^0-9]', '')",
       "concat_key": "CONCAT(d.field1, '_', d.field2)",
       "substring": "SUBSTRING(d.text, 0, 10)",
       "year": "DATE_YEAR(d.date_field)"
   }
   ```

3. **Complex expressions:** Can combine multiple operations
   ```python
   computed_fields={
       "complex_key": "CONCAT(LEFT(UPPER(d.name), 3), '_', LEFT(d.zip, 5))"
   }
   ```

### Computed Field Names

1. **Alphanumeric + underscores only:**
   ```python
   # ✅ Valid names
   "zip5", "phone_normalized", "name_key", "address_key_1"
   
   # ❌ Invalid names
   "zip-5", "phone.normalized", "name key", "123_field"
   ```

2. **Cannot start with digit:**
   ```python
   # ✅ Correct
   "zip5", "field_123"
   
   # ❌ Wrong
   "5zip", "123_field"
   ```

### Using Computed Fields in Blocking

1. **Add to blocking_fields:** Use the computed field name
   ```python
   blocking_fields=["address", "zip5"]  # zip5 is the computed field name
   ```

2. **Filter on computed fields:** Reference by name, not by `d.name`
   ```python
   filters={
       "address": {"not_null": True},  # Regular field: filters on d.address
       "zip5": {"not_null": True}      # Computed field: filters on zip5 variable
   }
   ```

---

## Migration from Workarounds

### Before (with workaround)

```python
# ❌ Old workaround
# Treating POSTAL_CODE as collection (incorrect)
# Using fallback query directly

strategy = CollectBlockingStrategy(
    db=db,
    collection="companies",
    blocking_fields=["address", "POSTAL_CODE"],  # Fails: treated as collection
    # ... workaround code ...
)
```

### After (using computed fields)

```python
# ✅ New approach with arango-entity-resolution v2.0+
from entity_resolution.strategies import CollectBlockingStrategy

strategy = CollectBlockingStrategy(
    db=db,
    collection="companies",
    blocking_fields=["address", "zip5"],
    computed_fields={
        "zip5": "LEFT(d.POSTAL_CODE, 5)"  # POSTAL_CODE is your actual field name
    },
    filters={
        "address": {"not_null": True, "min_length": 5},
        "zip5": {"not_null": True, "min_length": 5}
    },
    max_block_size=50,
    min_block_size=2
)

pairs = strategy.generate_candidates()
```

---

## Advanced Patterns

### Multiple Computed Fields

```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="companies",
    blocking_fields=["name_norm", "phone_norm", "zip5", "state"],
    computed_fields={
        "name_norm": "UPPER(TRIM(d.company_name))",
        "phone_norm": "REGEX_REPLACE(d.phone, '[^0-9]', '')",
        "zip5": "LEFT(d.postal_code, 5)"
    },
    filters={
        "name_norm": {"not_null": True, "min_length": 3},
        "phone_norm": {"min_length": 10},
        "zip5": {"min_length": 5},
        "state": {"not_null": True}
    },
    max_block_size=50,
    min_block_size=2
)
```

### Conditional Logic

```python
computed_fields={
    # Use phone if available, otherwise email domain
    "contact_key": "d.phone != null ? d.phone : SPLIT(d.email, '@')[1]",
    
    # Handle null postal codes
    "zip5": "d.postal_code != null ? LEFT(d.postal_code, 5) : '00000'"
}
```

### Nested Field Access

```python
computed_fields={
    # Access nested document fields
    "street_name": "d.address.street",
    "city_state": "CONCAT(d.location.city, '_', d.location.state)"
}
```

---

## Performance Considerations

### 1. Computed Field Complexity

- **Simple operations** (LEFT, UPPER, CONCAT): Minimal overhead
- **Regex operations** (REGEX_REPLACE): Moderate overhead
- **Complex calculations**: Higher overhead

**Recommendation:** Keep expressions simple. Do heavy computation elsewhere if possible.

### 2. Filtering on Computed Fields

Filters on computed fields are evaluated **after** computation, so they don't impact the number of computations. However, they do reduce the size of blocks.

```python
# This computes zip5 for ALL documents, then filters
computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
filters={"zip5": {"min_length": 5}}

# Better: Filter postal_code BEFORE computation
filters={
    "postal_code": {"min_length": 5},  # Filter before computing
    "zip5": {"not_null": True}         # Sanity check after
}
```

### 3. Block Size Tuning

Computed fields can create different blocking distributions than raw fields. Monitor block sizes:

```python
strategy = CollectBlockingStrategy(
    db=db,
    collection="companies",
    blocking_fields=["zip5"],
    computed_fields={"zip5": "LEFT(d.postal_code, 5)"},
    max_block_size=100,  # Adjust based on your data
    min_block_size=2
)

pairs = strategy.generate_candidates()
stats = strategy.get_statistics()
print(f"Blocks processed: {stats['blocks_processed']}")
print(f"Avg block size: {stats['total_pairs'] / stats['blocks_processed']:.1f}")
```

---

## Troubleshooting

### Error: "Computed field name must be alphanumeric"

**Cause:** Field name contains invalid characters.

```python
# ❌ Wrong
computed_fields={"zip-5": "LEFT(d.postal_code, 5)"}

# ✅ Correct
computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
```

### Error: "Computed field name cannot start with a digit"

**Cause:** Field name starts with a number.

```python
# ❌ Wrong
computed_fields={"5zip": "LEFT(d.postal_code, 5)"}

# ✅ Correct
computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
```

### Error: AQL query execution failure

**Cause:** Invalid AQL expression.

```python
# ❌ Wrong: Missing 'd.' prefix
computed_fields={"zip5": "LEFT(postal_code, 5)"}

# ✅ Correct
computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
```

### No pairs generated

**Possible causes:**

1. **Computed field returns null:** Add null handling
   ```python
   computed_fields={
       "zip5": "d.postal_code != null ? LEFT(d.postal_code, 5) : null"
   }
   ```

2. **Filters too restrictive:** Loosen filters or check data
   ```python
   filters={
       "zip5": {"not_null": True, "min_length": 5}  # Might filter everything
   }
   ```

3. **Block sizes out of range:** Adjust min/max block size
   ```python
   max_block_size=100,  # Increase if blocks are too large
   min_block_size=2     # Decrease if not enough data
   ```

---

## API Reference

### CollectBlockingStrategy Constructor

```python
CollectBlockingStrategy(
    db: StandardDatabase,
    collection: str,
    blocking_fields: List[str],
    filters: Optional[Dict[str, Dict[str, Any]]] = None,
    max_block_size: int = 100,
    min_block_size: int = 2,
    computed_fields: Optional[Dict[str, str]] = None
)
```

**Parameters:**

- `computed_fields`: Dictionary mapping computed field names to AQL expressions
  - **Key:** Alphanumeric variable name (underscores allowed, cannot start with digit)
  - **Value:** AQL expression using `d.field_name` syntax
  - **Example:** `{"zip5": "LEFT(d.postal_code, 5)"}`

**Notes:**

- Computed field names can be used in `blocking_fields`
- Computed field names can be used in `filters`
- In expressions, always reference document fields as `d.field_name`
- In blocking_fields and filters, reference computed fields by name only (no `d.` prefix)

---

## Related Documentation

- [Blocking Strategies Guide](BLOCKING_STRATEGIES.md)
- [Performance Tuning Guide](PERFORMANCE_TUNING.md)
- [ArangoDB AQL Functions](https://www.arangodb.com/docs/stable/aql/functions.html)

---

## Support

For issues or questions about computed fields:
1. Check this guide and examples
2. Review test cases in `tests/test_blocking_strategies.py`
3. Open an issue on GitHub with a minimal reproducible example


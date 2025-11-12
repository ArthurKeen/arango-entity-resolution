# 🔒 Security Fixes Needed - Immediate Action

**Priority:** HIGH  
**Estimated Time:** 1-2 hours  
**Risk Level:** Medium

---

## Critical Issues to Fix Now

### 1. Remove Hardcoded Test Password ⚠️

**File:** `src/entity_resolution/utils/config.py:28-29`

**Current (UNSAFE):**
```python
if not password and os.getenv("USE_DEFAULT_PASSWORD") == "true":
    password = "testpassword123"  # Development/testing only
```

**Fix:**
```python
# Only allow test password in pytest context
if not password:
    if os.getenv("PYTEST_CURRENT_TEST"):
        password = "test_unsafe_only_for_pytest"
    else:
        raise ValueError(
            "Database password must be set via ARANGO_ROOT_PASSWORD or ARANGO_PASSWORD "
            "environment variable. For testing, run within pytest."
        )
```

---

### 2. Add Collection Name Validation 🛡️

**Files:** All strategies and services that accept collection names

**Add to `utils/validation.py` (NEW FILE):**
```python
"""Input validation utilities for security."""

import re
from typing import List

def validate_collection_name(name: str) -> str:
    """
    Validate collection name to prevent AQL injection.
    
    Args:
        name: Collection name to validate
        
    Returns:
        The validated name
        
    Raises:
        ValueError: If name contains invalid characters
    """
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(
            f"Invalid collection name: '{name}'. "
            "Only alphanumeric characters and underscores allowed."
        )
    if len(name) > 256:
        raise ValueError(f"Collection name too long: {len(name)} chars")
    return name

def validate_field_name(name: str) -> str:
    """
    Validate field name to prevent AQL injection.
    
    Allows dots for nested fields (e.g., 'address.city')
    """
    if not re.match(r'^[a-zA-Z0-9_\.]+$', name):
        raise ValueError(
            f"Invalid field name: '{name}'. "
            "Only alphanumeric, underscore, and dot allowed."
        )
    if len(name) > 256:
        raise ValueError(f"Field name too long: {len(name)} chars")
    return name

def validate_field_names(names: List[str]) -> List[str]:
    """Validate multiple field names."""
    return [validate_field_name(name) for name in names]
```

**Then update strategies:**
```python
# In BlockingStrategy.__init__()
from entity_resolution.utils.validation import validate_collection_name

def __init__(self, db, collection: str, ...):
    self.collection = validate_collection_name(collection)
    # ...
```

---

### 3. Replace Error Print Statements 📋

**Files:**
- `src/entity_resolution/services/similarity_edge_service.py:172, 261`
- `src/entity_resolution/services/wcc_clustering_service.py:367`

**Current (UNSAFE):**
```python
except Exception as e:
    print(f"Error inserting edge batch: {e}")
```

**Fix:**
```python
except Exception as e:
    self.logger.error(f"Failed to insert edge batch", exc_info=True)
    # Re-raise or track failures
    raise RuntimeError(f"Edge insertion failed") from e
```

---

### 4. Make Password Mandatory (Not Optional) 🔑

**Files:** `config.py`, `enhanced_config.py`

**Current:**
```python
password: str = ""  # Empty by default
```

**Fix:**
```python
password: Optional[str] = None  # Force explicit check

@classmethod  
def from_env(cls) -> 'DatabaseConfig':
    password = os.getenv("ARANGO_PASSWORD") or os.getenv("ARANGO_ROOT_PASSWORD")
    
    if not password:
        # Check if in test environment
        if os.getenv("PYTEST_CURRENT_TEST"):
            password = "test_only_unsafe"
        else:
            raise ValueError(
                "Database password is required. Set ARANGO_ROOT_PASSWORD environment variable."
            )
    
    return cls(password=password, ...)
```

---

## Quick Fix Script

Run this to apply all security fixes:

```bash
# 1. Create validation module
cat > src/entity_resolution/utils/validation.py << 'EOF'
# Copy validation.py content from above
EOF

# 2. Update imports in strategies
# Add to base_strategy.py, collect_blocking.py, bm25_blocking.py
grep -l "def __init__" src/entity_resolution/strategies/*.py | \
  xargs sed -i '' '1i\
from entity_resolution.utils.validation import validate_collection_name, validate_field_names
'

# 3. Fix print statements
find src -name "*.py" -exec sed -i '' \
  's/print(f"Error/logger.error(f"Error/g' {} \;

# 4. Update config files  
# Manual: Edit config.py and enhanced_config.py as shown above
```

---

## Testing After Fixes

```bash
# 1. Run security-focused tests
pytest tests/ -v -k "security or validation"

# 2. Test with invalid inputs
python << 'EOF'
from entity_resolution import CollectBlockingStrategy

# Should raise ValueError
try:
    strategy = CollectBlockingStrategy(
        db=db,
        collection="'; DROP TABLE companies; --",  # SQL injection attempt
        blocking_fields=["name"]
    )
    print("❌ FAILED: Should have raised ValueError")
except ValueError as e:
    print(f"✅ PASS: Caught invalid collection name: {e}")
EOF

# 3. Test password requirement
ARANGO_ROOT_PASSWORD="" python -c "
from entity_resolution import get_database
try:
    db = get_database()
    print('❌ FAILED: Should require password')
except ValueError as e:
    print(f'✅ PASS: Password required: {e}')
"
```

---

## Verification Checklist

After applying fixes, verify:

- [ ] No hardcoded passwords in code
- [ ] Collection names validated before use
- [ ] Field names validated before use  
- [ ] No `print()` in error handling
- [ ] Password required (not optional)
- [ ] All tests still pass
- [ ] Security tests added
- [ ] Code review completed

---

**Estimated Impact:**
- Security: HIGH improvement
- Breaking Changes: Minimal (adds validation)
- Test Updates: Minor (handle ValueError)
- Performance: Negligible (validation is fast)

---

**Next Steps:**
1. Review this document
2. Apply fixes in order (1-4)
3. Run tests
4. Commit with message: "Security: Add input validation and remove hardcoded credentials"


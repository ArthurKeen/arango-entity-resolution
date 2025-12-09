# Pre-Push Hook Issue - Import-Time Config Loading

**Date:** December 2, 2025  
**Status:** ⚠️ **KNOWN ISSUE** - Workaround in place  
**Impact:** Pre-push hook fails without database credentials

---

## Problem

The pre-push hook tries to import modules to verify they don't have syntax errors. However, several modules call `get_config()` during import, which requires database credentials.

**Error:**
```
Database password is required. Set one of:
  - ARANGO_ROOT_PASSWORD environment variable
  - ARANGO_PASSWORD environment variable
  - USE_DEFAULT_PASSWORD=true (local docker development only)
```

---

## Root Causes

### 1. `DatabaseManager.__init__()` (Line 36 in database.py)
```python
def __init__(self):
    if not hasattr(self, 'initialized'):
        self.config = get_config()  # ← Requires password!
```

### 2. `get_logger()` (Line 23 in logging.py)
```python
def setup_logging(...):
    config = get_config()  # ← Requires password!
    level = log_level or config.er.log_level
```

### 3. Service Classes
Many services call `get_config()` in `__init__()`:
- `SimilarityService`
- `BlockingService`
- `ClusteringService`
- `EntityResolutionPipeline`
- etc.

---

## Current Workaround

Use `SKIP_TESTS=1` to bypass the pre-push hook:

```bash
SKIP_TESTS=1 git push
```

**When to use:**
- After thorough manual testing (like we did for WCC fix: 5/5 tests passing)
- In emergency situations
- When you know the code is good

**When NOT to use:**
- Untested code
- Quick fixes without verification
- As a regular practice

---

## Proper Solution (Not Yet Implemented)

### Option 1: Lazy Config Loading ✅ RECOMMENDED

Make config loading lazy - only load when actually accessed, not at init:

```python
class DatabaseManager:
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self._config = None  # Don't load yet
            self.logger = get_logger(__name__)
            self._client = None
            self._databases = {}
            self.initialized = True
    
    @property
    def config(self) -> Config:
        """Get configuration, loading lazily on first access"""
        if self._config is None:
            self._config = get_config()
        return self._config
```

**Benefits:**
- Modules can be imported without credentials
- Config only loaded when actually needed
- Minimal code changes

**Risks:**
- Need to test thoroughly to ensure no breakage
- Config access pattern changes slightly

###Option 2: Make Pre-Push Hook Set Dummy Credentials

Modify `.git/hooks/pre-push` to set dummy credentials before testing:

```bash
# Set dummy credentials for import testing
export ARANGO_PASSWORD="dummy_test_password"
export ARANGO_DATABASE="test_db"

# Run tests...
```

**Benefits:**
- No code changes needed
- Simple fix

**Drawbacks:**
- Hook-specific fix
- Doesn't solve the underlying architectural issue

### Option 3: Skip Database Imports in Tests

Make the pre-push hook only test syntax, not imports:

```python
# Instead of:
from entity_resolution.services import SimilarityService

# Use:
python3 -m py_compile src/entity_resolution/services/similarity_service.py
```

**Benefits:**
- Simple
- Fast

**Drawbacks:**
- Misses import-time errors
- Less thorough testing

---

## Recommended Fix

**Option 1 (Lazy Config Loading)** is the best solution because:
1. ✅ Solves the architectural problem
2. ✅ Makes modules more testable
3. ✅ Follows best practices (don't do work at import time)
4. ✅ No workarounds needed

**Implementation Steps:**
1. Make `DatabaseManager.config` a lazy-loaded property
2. Make `get_logger()` handle missing config gracefully
3. Test all services to ensure they still work
4. Update tests to verify lazy loading
5. Remove need for `SKIP_TESTS=1`

**Estimated Effort:** 2-3 hours
**Risk:** Medium (need thorough testing)
**Priority:** Medium (workaround exists, but should fix properly)

---

## Testing After Fix

After implementing lazy config loading, verify:

```bash
# Should work without credentials:
python3 -c "from entity_resolution import WCCClusteringService; print('OK')"

# Should only require credentials when actually connecting:
python3 -c "
from entity_resolution import WCCClusteringService
import os
os.environ['ARANGO_PASSWORD'] = 'test'
service = WCCClusteringService(...)  # This should work
service.cluster()  # This needs real credentials
"
```

---

## Impact Analysis

**Current Impact:**
- ⚠️ Developers must use `SKIP_TESTS=1` or set credentials
- ⚠️ CI/CD pipelines need credentials for simple syntax checks
- ⚠️ Makes testing more complex

**After Fix:**
- ✅ Modules can be imported freely
- ✅ Tests run without database
- ✅ Credentials only needed for actual database operations
- ✅ Better separation of concerns

---

## Related Issues

- None currently tracked
- This issue was discovered during WCC performance fix commit

---

## Conclusion

**Status:** Known issue with workaround  
**Workaround:** `SKIP_TESTS=1 git push` (after thorough testing)  
**Proper Fix:** Lazy config loading (not yet implemented)  
**Priority:** Medium - should fix but not urgent  
**Next Steps:** Implement Option 1 (lazy config loading) when time permits

---

**Last Updated:** December 2, 2025  
**Discovered By:** Pre-push hook failure during WCC fix commit  
**Workaround Verified:** Yes - used successfully for WCC commit


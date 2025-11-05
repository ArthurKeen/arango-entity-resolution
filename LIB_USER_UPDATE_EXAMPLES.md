# Library User Update - Before & After Examples

This document shows side-by-side examples of how to update your code.

---

## Example 1: Basic Entity Resolution (No Changes Needed)

### Before (Still Works)
```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Your existing code works as-is
pipeline = EntityResolutionPipeline()

result = pipeline.resolve_entities(
    records=my_data,
    collection_name='customers'
)

print(f"Found {len(result['clusters'])} clusters")
```

### After (Recommended - Add Environment Variables)
```python
from dotenv import load_dotenv
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Add this at the start of your application
load_dotenv()

# Everything else stays the same
pipeline = EntityResolutionPipeline()

result = pipeline.resolve_entities(
    records=my_data,
    collection_name='customers'
)

print(f"Found {len(result['clusters'])} clusters")
```

**Changes:** Just add `load_dotenv()` at the start  
**Benefit:** More secure credential management

---

## Example 2: Batch Processing Large Datasets

### Before (Slow - 6 minutes for 300K records)
```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

pipeline = EntityResolutionPipeline()

# Process in batches (makes many API calls)
all_results = []
batch_size = 100

for i in range(0, len(large_dataset), batch_size):
    batch = large_dataset[i:i+batch_size]
    result = pipeline.resolve_entities(batch, 'customers')
    all_results.append(result)

# Total time: ~6 minutes for 300K records
```

### After (Fast - 2 minutes for 300K records)
```python
from dotenv import load_dotenv
from entity_resolution.services.bulk_blocking_service import BulkBlockingService

load_dotenv()

# Use new bulk processing (single query)
service = BulkBlockingService()
service.connect()

# Process entire collection at once
result = service.generate_all_pairs(
    collection_name='customers',
    strategies=['exact', 'ngram'],
    limit=0  # 0 = no limit
)

print(f"Found {result['statistics']['total_pairs']} pairs")
print(f"Time: {result['statistics']['execution_time']:.2f}s")

# Total time: ~2 minutes for 300K records (3x faster!)
```

**Changes:** Switch to `BulkBlockingService` for large datasets  
**Benefit:** 3-5x performance improvement

---

## Example 3: Environment Configuration

### Before (Insecure - Hardcoded Credentials)
```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# DON'T DO THIS - credentials in code!
pipeline = EntityResolutionPipeline(
    host="db.company.com",
    port=8529,
    username="root",
    password="MySecretPassword123",  # SECURITY RISK!
    database="production_db"
)
```

### After (Secure - Environment Variables)
```python
from dotenv import load_dotenv
import os
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Load from .env file
load_dotenv()

# Credentials come from environment (secure!)
pipeline = EntityResolutionPipeline()

# Or verify they're set
if not os.getenv('ARANGO_ROOT_PASSWORD'):
    raise ValueError("Database password not configured")

pipeline = EntityResolutionPipeline()
```

**Create `.env` file:**
```bash
ARANGO_HOST=db.company.com
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_ROOT_PASSWORD=MySecretPassword123
ARANGO_DATABASE=production_db
```

**Add to `.gitignore`:**
```bash
.env
config.json
```

**Changes:** Move credentials to `.env` file  
**Benefit:** Secure, no credentials in code, no accidental commits

---

## Example 4: Custom Configuration

### Before
```python
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Old way (still works)
pipeline = EntityResolutionPipeline(
    similarity_threshold=0.85,
    max_candidates=150
)
```

### After (More Options)
```python
from dotenv import load_dotenv
from entity_resolution.core.entity_resolver import EntityResolutionPipeline
from entity_resolution.utils.config import Config, EntityResolutionConfig

load_dotenv()

# New way (more flexible)
er_config = EntityResolutionConfig(
    similarity_threshold=0.85,
    max_candidates_per_record=150,
    ngram_length=3,
    max_cluster_size=100,
    log_level='INFO'
)

config = Config(er_config=er_config)
pipeline = EntityResolutionPipeline(config=config)
```

**Or use environment variables:**
```bash
# In .env file
ER_SIMILARITY_THRESHOLD=0.85
ER_MAX_CANDIDATES=150
ER_NGRAM_LENGTH=3
ER_LOG_LEVEL=INFO
```

```python
from dotenv import load_dotenv
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

load_dotenv()

# Loads config from environment automatically
pipeline = EntityResolutionPipeline()
```

**Changes:** Use `Config` objects or environment variables  
**Benefit:** More options, cleaner code, environment-specific settings

---

## Example 5: REST API Usage

### Before (Multiple Batch Calls)
```python
import requests
from requests.auth import HTTPBasicAuth

# Process in batches (many API calls)
batch_size = 100
all_pairs = []

for i in range(0, total_records, batch_size):
    response = requests.post(
        'http://localhost:8529/_db/mydb/entity-resolution/blocking/batch',
        auth=HTTPBasicAuth('root', 'password'),
        json={
            'collection': 'customers',
            'targetDocIds': record_ids[i:i+batch_size]
        }
    )
    all_pairs.extend(response.json()['candidates'])

# Makes 3,319 API calls for 331K records
```

### After (Single Bulk Call)
```python
import requests
from requests.auth import HTTPBasicAuth
import os

# Single API call for entire collection
response = requests.post(
    'http://localhost:8529/_db/mydb/entity-resolution/bulk/all-pairs',
    auth=HTTPBasicAuth('root', os.getenv('ARANGO_ROOT_PASSWORD')),
    json={
        'collection': 'customers',
        'strategies': ['exact', 'ngram'],
        'limit': 0  # Process all
    }
)

result = response.json()
all_pairs = result['candidate_pairs']
stats = result['statistics']

print(f"Found {stats['total_pairs']} pairs in {stats['execution_time']:.2f}s")

# Makes 1 API call for 331K records (3,319x fewer calls!)
```

**Changes:** Use new `/bulk/all-pairs` endpoint  
**Benefit:** 3,300x fewer network calls, 3-5x faster

---

## Example 6: Application Startup

### Before
```python
# app.py
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Initialize directly
pipeline = EntityResolutionPipeline()

# Start application
if __name__ == '__main__':
    app.run()
```

### After (Best Practice)
```python
# app.py
from dotenv import load_dotenv
import os
from entity_resolution.core.entity_resolver import EntityResolutionPipeline

# Load environment at startup
load_dotenv()

# Validate critical environment variables
required_vars = ['ARANGO_ROOT_PASSWORD', 'ARANGO_DATABASE']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize with environment config
pipeline = EntityResolutionPipeline()

# Start application
if __name__ == '__main__':
    print("✓ Configuration loaded from environment")
    print(f"✓ Database: {os.getenv('ARANGO_DATABASE')}")
    print(f"✓ Host: {os.getenv('ARANGO_HOST', 'localhost')}")
    app.run()
```

**Changes:** Add environment validation at startup  
**Benefit:** Fail fast if misconfigured, clear error messages

---

## Example 7: Docker Deployment

### Before (docker-compose.yml)
```yaml
version: '3'
services:
  app:
    build: .
    environment:
      - DB_HOST=arangodb
      - DB_PORT=8529
      - DB_PASSWORD=hardcoded_password  # Not ideal
```

### After (docker-compose.yml)
```yaml
version: '3'
services:
  app:
    build: .
    env_file:
      - .env  # Load from file (gitignored)
    environment:
      - ARANGO_HOST=arangodb
      - ARANGO_PORT=8529
      # Password comes from .env file (secure)
```

**Create `.env.example` for team:**
```bash
# .env.example (committed to git)
ARANGO_HOST=arangodb
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_ROOT_PASSWORD=change_me_in_production
ARANGO_DATABASE=entity_resolution
```

**Create `.env` for production (not committed):**
```bash
# .env (gitignored - actual secrets)
ARANGO_HOST=arangodb
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_ROOT_PASSWORD=actual_production_password
ARANGO_DATABASE=entity_resolution
```

**Changes:** Use `.env` file for secrets  
**Benefit:** Secure secrets management, different configs per environment

---

## Summary of Changes

| Aspect | Before | After | Benefit |
|--------|--------|-------|---------|
| **Credentials** | Hardcoded in code | Environment variables | Secure |
| **Large datasets** | Batch processing | Bulk processing | 3-5x faster |
| **API calls** | Many (3,319+) | One | Less overhead |
| **Configuration** | Limited options | Config objects + env | More flexible |
| **Security** | Credentials in git | .env gitignored | No leaks |
| **Startup** | No validation | Validate env vars | Fail fast |

---

## Migration Checklist

- [ ] Move credentials to `.env` file
- [ ] Add `.env` to `.gitignore`
- [ ] Add `load_dotenv()` to application startup
- [ ] (Optional) Switch to bulk processing for large datasets
- [ ] Test with small sample data
- [ ] Deploy to staging
- [ ] Monitor performance improvements
- [ ] Deploy to production

---

## Need Help?

**See also:**
- `LIB_USER_UPDATE_GUIDE.md` - Detailed migration guide
- `LIB_USER_UPDATE_CHECKLIST.md` - Step-by-step checklist
- `docs/BATCH_VS_BULK_PROCESSING.md` - Performance comparison
- `SECURITY.md` - Security best practices
- `examples/bulk_processing_demo.py` - Working example

---

**Questions?** Open an issue or contact support.

**Last Updated:** November 4, 2025


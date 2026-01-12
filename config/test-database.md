# Test Database Configuration

**Purpose:** Persistent test database for arango-entity-resolution library  
**Container:** `arango-entity-resolution-test`  
**Status:** [PASS] Active

---

## Quick Reference

| Setting | Value |
|---------|-------|
| **Container Name** | `arango-entity-resolution-test` |
| **Image** | `arangodb/arangodb:3.12` |
| **Port** | `8532` (mapped to internal 8529) |
| **Root Password** | `test_er_password_2025` |
| **Default Database** | `entity_resolution` |
| **Web UI** | http://localhost:8532 |

---

## Usage

### Starting the Test Container

```bash
cd .
docker-compose -f docker-compose.test.yml up -d
```

### Stopping the Test Container

```bash
docker-compose -f docker-compose.test.yml down
```

### Accessing ArangoDB Web UI

Open: http://localhost:8532

- **Username:** `root`
- **Password:** `test_er_password_2025`
- **Database:** `entity_resolution`

---

## Running Tests

### Full Test Suite

```bash
cd .
python3 test_new_features.py
```

### Environment Variables (Already Set in test_new_features.py)

```python
os.environ['ARANGO_ROOT_PASSWORD'] = 'test_er_password_2025'
os.environ['ARANGO_HOST'] = 'localhost'
os.environ['ARANGO_PORT'] = '8532'
```

### Create Test Database (if needed)

```python
from arango import ArangoClient

client = ArangoClient(hosts='http://localhost:8532')
sys_db = client.db('_system', username='root', password='test_er_password_2025')

if not sys_db.has_database('entity_resolution'):
    sys_db.create_database('entity_resolution')
```

---

## Container Management

### Check Container Status

```bash
docker ps | grep arango-entity-resolution-test
```

### View Container Logs

```bash
docker logs arango-entity-resolution-test
```

### Restart Container

```bash
docker restart arango-entity-resolution-test
```

### Remove Container and Data (Clean Start)

```bash
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
```

---

## Why a Dedicated Test Container?

1. **No Port Conflicts:** Uses port 8532 (other containers use 8529, 8530, 8531)
2. **Known Credentials:** No guessing - always `test_er_password_2025`
3. **Isolated Data:** Won't interfere with other projects
4. **Persistent:** Data survives container restarts via Docker volumes
5. **Clean State:** Can easily reset by removing volumes

---

## Test Results (Latest Run)

**Date:** December 2, 2025  
**Result:** [PASS] **7/7 Tests Passed**

```
[PASS] PASS: Module Imports
[PASS] PASS: Database Connection
[PASS] PASS: CrossCollectionMatchingService
[PASS] PASS: HybridBlockingStrategy
[PASS] PASS: GeographicBlockingStrategy
[PASS] PASS: GraphTraversalBlockingStrategy
[PASS] PASS: Pipeline Utilities
```

**Container Info:**
- ArangoDB Version: 3.12.4-3
- Collections: 8 (system collections)
- Response Time: < 100ms

---

## Troubleshooting

### Container Won't Start

**Check port availability:**
```bash
lsof -i :8532
```

**If port is in use, either:**
1. Stop the conflicting service
2. Change port in `docker-compose.test.yml`

### Database Not Found

**Create the database:**
```bash
python3 -c "
from arango import ArangoClient
client = ArangoClient(hosts='http://localhost:8532')
sys_db = client.db('_system', username='root', password='test_er_password_2025')
sys_db.create_database('entity_resolution')
print('Database created')
"
```

### Authentication Failed

**Verify password:**
The password is: `test_er_password_2025`

If you changed it, update:
1. `docker-compose.test.yml` -> `ARANGO_ROOT_PASSWORD`
2. `test_new_features.py` -> `os.environ['ARANGO_ROOT_PASSWORD']`
3. This document

---

## Integration with CI/CD

This setup can be used for automated testing:

```yaml
# Example GitHub Actions
services:
  arangodb:
    image: arangodb/arangodb:3.12
    env:
      ARANGO_ROOT_PASSWORD: test_er_password_2025
    ports:
      - 8532:8529

steps:
  - name: Run Tests
    run: python3 test_new_features.py
    env:
      ARANGO_ROOT_PASSWORD: test_er_password_2025
      ARANGO_HOST: localhost
      ARANGO_PORT: 8532
```

---

## Persistence

**Data Location:** Docker volumes
- `arango-entity-resolution_arango_test_data`
- `arango-entity-resolution_arango_test_apps`

**View volumes:**
```bash
docker volume ls | grep arango-entity-resolution
```

**Backup data:**
```bash
docker exec arango-entity-resolution-test arangodump \
  --server.password test_er_password_2025 \
  --output-directory /tmp/backup
```

---

## Never Guess Credentials Again! [PASS]

**This setup ensures:**
1. [PASS] Credentials are documented
2. [PASS] Container is always available
3. [PASS] Tests can run anytime
4. [PASS] No conflicts with other projects
5. [PASS] Easy to reset if needed

**Just remember:**
- Port: `8532`
- Password: `test_er_password_2025`
- Container: `arango-entity-resolution-test`

---

**Last Updated:** December 2, 2025  
**Status:** [PASS] Active and Tested  
**Maintainer:** arango-entity-resolution project


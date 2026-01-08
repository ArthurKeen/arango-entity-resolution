# Testing Guide

This document provides comprehensive testing instructions for the ArangoDB Entity Resolution System, covering setup, strategies, and workflows for both development and production environments.

## Table of Contents

1. [Testing Setup](#testing-setup)
2. [Testing Strategies](#testing-strategies)
3. [Automated Testing](#automated-testing)
4. [Troubleshooting](#troubleshooting)

---

## Testing Setup

### Prerequisites

Before setting up the testing environment, ensure you have the following installed:

#### Required Software

1. **Docker** (v20.0 or higher)
- Download: https://docs.docker.com/get-docker/
- Verify installation: `docker --version`
- **Note**: ArangoDB 3.12 requires Docker for Windows and macOS users

2. **Docker Compose** (v2.0 or higher)
- Usually included with Docker Desktop
- Verify installation: `docker-compose --version`

3. **Python 3.8+**
- Download: https://www.python.org/downloads/
- Verify installation: `python3 --version`

4. **curl** and **jq** (for API testing)
- macOS: `brew install jq`
- Linux: `apt-get install jq` or `yum install jq`
- Windows: Install via Chocolatey or WSL

#### System Requirements

- **RAM**: Minimum 4GB, recommended 8GB+
- **Disk Space**: Minimum 2GB free space
- **Network**: Internet connection for downloading Docker images

### Quick Setup

#### Automated Setup

The easiest way to get started:

```bash
# Clone the repository
git clone https://github.com/arangodb/arango-entity-resolution.git
cd arango-entity-resolution

# Install git hooks for quality checks
./scripts/setup-git-hooks.sh

# Run the setup script
./scripts/setup.sh
```

This script will:
- Verify all prerequisites
- Create the data directory at `~/data`
- Create environment configuration
- Install Python dependencies
- Start ArangoDB in Docker
- Create test database and schema
- Load sample data

#### Manual Setup

For manual setup or troubleshooting:

```bash
# 1. Create data directory
mkdir -p ~/data

# 2. Configure environment
cp env.example .env
# Edit .env if needed

# 3. Install Python dependencies
pip3 install -r requirements.txt

# 4. Start ArangoDB
docker-compose up -d

# 5. Create test database
python3 scripts/database/manage_db.py create --database entity_resolution_test
python3 scripts/database/manage_db.py init --database entity_resolution_test

# 6. Load sample data
python3 scripts/database/manage_db.py load-data --database entity_resolution_test --data-file data/sample/customers_sample.json
```

### Configuration

#### Environment Variables

Key settings in `.env`:

```bash
# ArangoDB Configuration
ARANGO_ROOT_PASSWORD=testpassword123 # Change for production
ARANGO_NO_AUTH=false

# Database Configuration
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_PASSWORD=testpassword123 # Set via environment variable

# Test Database Names
TEST_DB_NAME=entity_resolution_test
SAMPLE_DB_NAME=entity_resolution_sample
```

#### Data Directory Mounting

The system mounts your local `~/data` directory to `/data` in the Docker container for:
- Data persistence across container restarts
- Easy access to database files
- Backup and restore capabilities

### ArangoDB Web Interface

Access the web interface at: http://localhost:8529

**Default Credentials:**
- Username: `root`
- Password: `testpassword123`

---

## Testing Strategies

### Multi-Layered Testing Approach

We use different tools optimized for different purposes. Experience shows **CURL + JQ** is most effective for rapid debugging.

### 1. Direct HTTP Testing (Primary Method for Foxx Services)

**Tool**: `curl` + `jq` for JSON parsing 
**Purpose**: Rapid debugging and endpoint verification 
**Effectiveness**: HIGHEST for development

#### Quick Examples

```bash
# Health check
curl -u root:testpassword123 "http://localhost:8529/_db/_system/entity-resolution/health" | jq .

# Similarity computation test
curl -u root:testpassword123 -H "Content-Type: application/json" \
-d '{"docA":{"first_name":"John","last_name":"Smith"},"docB":{"first_name":"Jon","last_name":"Smith"}}' \
"http://localhost:8529/_db/_system/entity-resolution/similarity/compute" | jq .

# Available functions
curl -u root:testpassword123 "http://localhost:8529/_db/_system/entity-resolution/similarity/functions" | jq .
```

#### Why CURL Works Best

- **Immediate feedback** - See results instantly
- **Raw responses** - No Python wrapper complications
- **Easy debugging** - Clear error messages
- **Fast iteration** - Test fixes in seconds
- **Simple setup** - Just curl and jq

#### Rapid Development Cycle

```bash
# 1. Deploy
python3 scripts/foxx/automated_deploy.py

# 2. Test core functionality
curl -u root:testpassword123 "http://localhost:8529/_db/_system/entity-resolution/health" | jq .

# 3. Test specific endpoints
curl -u root:testpassword123 -H "Content-Type: application/json" \
-d '{"docA":{"first_name":"John"},"docB":{"first_name":"Jon"}}' \
"http://localhost:8529/_db/_system/entity-resolution/similarity/compute" | jq .

# 4. Debug issues (check error messages in curl response)
# 5. Fix and redeploy
# 6. Verify fix

# Total cycle time: < 30 seconds
```

### 2. Python Integration Tests

**Files**: 
- `scripts/foxx/test_foxx_deployment.py`
- `scripts/foxx/configure_service_integration.py`

**Purpose**: Comprehensive endpoint testing and service integration 
**Effectiveness**: Good for automated testing

#### Features

- Tests multiple endpoints systematically
- Provides structured reporting
- Integrates with Python services
- Good for CI/CD pipelines

#### Running Python Tests

```bash
# Run unit tests
python3 -m pytest tests/

# Run specific test file
python3 -m pytest tests/test_similarity_service.py

# Run with coverage
python3 -m pytest --cov=src/entity_resolution tests/

# Run integration tests
python3 scripts/foxx/test_foxx_deployment.py
```

### 3. Performance Benchmarking

**Files**:
- `scripts/benchmarks/similarity_performance_test.py`
- `scripts/benchmarks/performance_comparison.py`

**Purpose**: Measure Python vs Foxx performance 

#### Capabilities

- Focused performance testing
- Python vs Foxx comparison
- Throughput measurement
- Processing time analysis

```bash
# Run performance tests
python3 scripts/benchmarks/similarity_performance_test.py
python3 scripts/benchmarks/performance_comparison.py
```

### 4. Database Testing

Use the database management script for common operations:

```bash
# List all databases
python3 scripts/database/manage_db.py list

# Create a test database
python3 scripts/database/manage_db.py create --database my_test_db

# Initialize entity resolution schema
python3 scripts/database/manage_db.py init --database my_test_db

# Load test data
python3 scripts/database/manage_db.py load-data --database my_test_db --data-file data/sample/customers_sample.json

# Delete a database
python3 scripts/database/manage_db.py delete --database my_test_db
```

### 5. CRUD Operations Testing

```bash
# Count records
python3 scripts/crud/crud_operations.py count --collection customers

# Search for customers
python3 scripts/crud/crud_operations.py search-customers --query '{"city": "New York"}'

# Get a specific customer
python3 scripts/crud/crud_operations.py get-customer --id customers/1

# Create a new customer
python3 scripts/crud/crud_operations.py create-customer --data '{"first_name": "Jane", "last_name": "Doe", "email": "jane@email.com"}'

# Update a customer
python3 scripts/crud/crud_operations.py update-customer --id customers/1 --data '{"phone": "+1-555-9999"}'

# Delete a customer
python3 scripts/crud/crud_operations.py delete-customer --id customers/1

# Get potential matches
python3 scripts/crud/crud_operations.py get-matches --id customers/1

# Clear a collection
python3 scripts/crud/crud_operations.py clear --collection customers
```

### Testing Workflows

#### Basic Testing Workflow

```bash
# 1. Start environment
./scripts/setup.sh

# 2. Verify setup
python3 scripts/crud/crud_operations.py count --collection customers
# Should show 10 sample customers

# 3. Test CRUD operations
python3 scripts/crud/crud_operations.py create-customer --data '{"first_name": "Test", "last_name": "User", "email": "test@example.com"}'

# 4. Test entity resolution
python3 scripts/crud/crud_operations.py get-matches --id customers/1
```

#### Advanced Testing Workflow

```bash
# 1. Create multiple test databases
python3 scripts/database/manage_db.py create --database test_scenario_1
python3 scripts/database/manage_db.py create --database test_scenario_2

# 2. Load different datasets
python3 scripts/database/manage_db.py load-data --database test_scenario_1 --data-file data/sample/custom_data.json

# 3. Isolated testing
python3 scripts/crud/crud_operations.py --database test_scenario_1 count --collection customers
```

### Sample Data Structure

The system includes sample data with these characteristics:

#### Customer Records (10 records)
- **3 John Smith variants** - Name variations and duplicates
- **2 Mary/Maria Johnson variants** - First name variations
- **2 Robert/Bob Brown variants** - Nickname matching
- **2 Jennifer/Jenny Wilson variants** - Nickname and email variations
- **1 Sarah Davis** - Control testing

#### Blocking Keys
- **lastname_city**: Groups by last name initial + city initial
- **initials_zip**: Groups by first/last initials + zip code

#### Entity Clusters
- Pre-defined clusters showing expected resolution results
- Confidence scores for each cluster
- Golden records representing best version of each entity

---

## Automated Testing

### Git Hooks (Pre-Commit and Pre-Push)

Automated quality checks run before commits and pushes. See [GIT_HOOKS.md](GIT_HOOKS.md) for details.

#### Pre-Commit Hook (~5 seconds)
- Python syntax validation
- No hardcoded credentials
- ASCII-only code (no emojis)
- Critical module imports

#### Pre-Push Hook (~2-3 minutes)
- Core unit tests
- Service tests
- Integration tests
- Full module imports
- Code quality checks

### CI/CD Integration

#### GitHub Actions Example

```yaml
name: Entity Resolution Tests
on: [push, pull_request]

jobs:
test:
runs-on: ubuntu-latest
steps:
- uses: actions/checkout@v2

- name: Setup Python
uses: actions/setup-python@v2
with:
python-version: '3.9'

- name: Start ArangoDB
run: |
docker-compose up -d
sleep 30 # Wait for startup

- name: Install dependencies
run: pip install -r requirements.txt

- name: Setup test database
run: |
python3 scripts/database/manage_db.py create --database ci_test
python3 scripts/database/manage_db.py init --database ci_test

- name: Run tests
run: pytest tests/ --cov=src/entity_resolution
```

---

## Troubleshooting

### Common Issues

#### 1. Docker Not Starting

```bash
# Check Docker status
docker info

# Restart Docker service
sudo systemctl restart docker # Linux
# Or restart Docker Desktop on macOS/Windows
```

#### 2. ArangoDB Connection Failed

```bash
# Check if container is running
docker-compose ps

# View ArangoDB logs
docker-compose logs arangodb

# Restart ArangoDB
docker-compose restart arangodb
```

#### 3. Python Dependencies Issues

```bash
# Upgrade pip
pip3 install --upgrade pip

# Reinstall dependencies
pip3 install -r requirements.txt --force-reinstall
```

#### 4. Permission Errors

```bash
# Make scripts executable
chmod +x scripts/*.sh scripts/*/*.py

# Fix data directory permissions
sudo chown -R $USER:$USER ~/data
```

### Port Conflicts

If port 8529 is already in use:

```bash
# 1. Find conflicting process
lsof -i :8529

# 2. Change port in docker-compose.yml
# ports:
# - "8530:8529" # Use port 8530 instead

# 3. Update .env
# ARANGO_PORT=8530
```

### Debugging Success Examples

1. **JavaScript Runtime Errors**:
- CURL revealed: "query(...).next is not a function"
- Fixed with: `db._query()` instead of `query()`

2. **AQL Syntax Issues**:
- CURL revealed: "invalid number of arguments for function 'MAX()'"
- Fixed with: conditional logic instead of MAX()

3. **Authentication Problems**:
- CURL revealed: HTTP 401 responses
- Fixed with: proper authentication headers

### Cleanup

#### Temporary Cleanup
```bash
# Stop containers but keep data
docker-compose down
```

#### Complete Cleanup
```bash
# Use automated teardown
./scripts/teardown.sh

# Or manually
docker-compose down -v # Remove containers and volumes
rm -rf ~/data # Remove local data (optional)
```

---

## Security Notes

### Default Credentials
- **Production Warning**: Change default password before production
- **Test Environment**: Default credentials acceptable for local testing

### Network Security
- ArangoDB exposed only on localhost (127.0.0.1)
- No external network access by default
- Use proper authentication in production

### Data Privacy
- Sample data contains fictional records only
- Use anonymized data for testing with real datasets
- Follow GDPR/privacy regulations with real data

---

## Recommendations

### For Development
1. **Use CURL + JQ** as primary Foxx testing method
2. **Automate deployment** for rapid iteration
3. **Test immediately** after each code change
4. **Use structured JSON responses** for clear feedback

### For Production
1. **Enhance Python test scripts** with comprehensive coverage
2. **Create comprehensive test suites** for all endpoints
3. **Add monitoring endpoints** for health checks
4. **Implement automated testing** in CI/CD pipeline

### For New Features
1. **Start with CURL testing** during development
2. **Add Python integration tests** once stable
3. **Include performance benchmarks** when ready
4. **Document test cases** and expected responses

---

## Current Status

### Working Endpoints (Tested and Verified)
- `/health` - Service health and status
- `/info` - Service information and endpoints
- `/similarity/functions` - Available similarity functions
- `/similarity/compute` - Similarity computation
- `/blocking/candidates` - Generate candidate pairs
- `/clustering/wcc` - Weakly Connected Components clustering

### Testing Infrastructure
- [x] Automated deployment working
- [x] CURL testing proven effective
- [x] Python integration tests functional
- [x] Performance benchmarks available
- [x] Git hooks for quality assurance
- [x] Pre-commit checks (< 5 seconds)
- [x] Pre-push comprehensive tests (~2-3 minutes)

This comprehensive testing guide provides everything needed to develop, test, and deploy the entity resolution system with confidence.


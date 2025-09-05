# ArangoDB Entity Resolution Testing Setup

This document provides comprehensive instructions for setting up and using the ArangoDB testing environment for entity resolution development.

## Prerequisites

Before setting up the testing environment, ensure you have the following installed:

### Required Software

1. **Docker** (v20.0 or higher)
   - Download: https://docs.docker.com/get-docker/
   - Verify installation: `docker --version`
   - **Note**: ArangoDB 3.12 requires Docker for Windows and macOS users (native support discontinued)

2. **Docker Compose** (v2.0 or higher)
   - Usually included with Docker Desktop
   - Verify installation: `docker-compose --version`

3. **Python 3.8+**
   - Download: https://www.python.org/downloads/
   - Verify installation: `python3 --version`

4. **pip (Python package manager)**
   - Usually included with Python
   - Verify installation: `pip3 --version`

### System Requirements

- **RAM**: Minimum 4GB, recommended 8GB+
- **Disk Space**: Minimum 2GB free space
- **Network**: Internet connection for downloading Docker images and Python packages

## Quick Setup

### Automated Setup

The easiest way to get started is using the automated setup script:

```bash
# Clone the repository (if not already done)
git clone https://github.com/ArthurKeen/arango-entity-resolution-record-blocking.git
cd arango-entity-resolution-record-blocking

# Run the setup script
./scripts/setup.sh
```

This script will:
- ✅ Verify all prerequisites
- 📁 Create the data directory at `~/data`
- 🔧 Create environment configuration
- 📦 Install Python dependencies
- 🐳 Start ArangoDB in Docker
- 🗄️ Create test database and schema
- 📊 Load sample data

### Manual Setup

If you prefer manual setup or need to troubleshoot:

1. **Create Data Directory**
   ```bash
   mkdir -p ~/data
   ```

2. **Configure Environment**
   ```bash
   cp env.example .env
   # Edit .env if needed
   ```

3. **Install Python Dependencies**
   ```bash
   pip3 install -r requirements.txt
   ```

4. **Start ArangoDB**
   ```bash
   docker-compose up -d
   ```

5. **Create Database and Schema**
   ```bash
   python3 scripts/database/manage_db.py create --database entity_resolution_test
   python3 scripts/database/manage_db.py init --database entity_resolution_test
   ```

6. **Load Sample Data**
   ```bash
   python3 scripts/database/manage_db.py load-data --database entity_resolution_test --data-file data/sample/customers_sample.json
   ```

## Configuration

### Environment Variables

The system uses environment variables for configuration. Key settings in `.env`:

```bash
# ArangoDB Configuration
ARANGO_ROOT_PASSWORD=testpassword123  # Change for production
ARANGO_NO_AUTH=false

# Database Configuration
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_USERNAME=root

# Test Database Names
TEST_DB_NAME=entity_resolution_test
SAMPLE_DB_NAME=entity_resolution_sample
```

### Data Directory Mounting

The system mounts your local `~/data` directory to `/data` in the Docker container. This ensures:
- Data persistence across container restarts
- Easy access to database files from your local machine
- Backup and restore capabilities

## Usage

### ArangoDB Web Interface

Access the ArangoDB web interface at: http://localhost:8529

**Default Credentials:**
- Username: `root`
- Password: `testpassword123`

### Database Management

Use the database management script for common operations:

```bash
# List all databases
python3 scripts/database/manage_db.py list

# Create a new database
python3 scripts/database/manage_db.py create --database my_test_db

# Initialize entity resolution schema
python3 scripts/database/manage_db.py init --database my_test_db

# Load test data
python3 scripts/database/manage_db.py load-data --database my_test_db --data-file data/sample/customers_sample.json

# Delete a database
python3 scripts/database/manage_db.py delete --database my_test_db
```

### CRUD Operations

Use the CRUD operations script for data manipulation:

```bash
# Count records in a collection
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

# Get potential matches for a record
python3 scripts/crud/crud_operations.py get-matches --id customers/1

# Clear a collection
python3 scripts/crud/crud_operations.py clear --collection customers
```

## Testing Workflows

### Basic Testing Workflow

1. **Start Environment**
   ```bash
   ./scripts/setup.sh
   ```

2. **Verify Setup**
   ```bash
   python3 scripts/crud/crud_operations.py count --collection customers
   # Should show 10 sample customers
   ```

3. **Test CRUD Operations**
   ```bash
   # Create a test customer
   python3 scripts/crud/crud_operations.py create-customer --data '{"first_name": "Test", "last_name": "User", "email": "test@example.com", "city": "TestCity"}'
   
   # Search for the customer
   python3 scripts/crud/crud_operations.py search-customers --query '{"city": "TestCity"}'
   ```

4. **Test Entity Resolution Features**
   ```bash
   # Get potential matches for a record
   python3 scripts/crud/crud_operations.py get-matches --id customers/1
   
   # Check blocking keys
   python3 scripts/crud/crud_operations.py get-blocking-keys --id customers/1
   ```

### Advanced Testing

1. **Create Multiple Test Databases**
   ```bash
   python3 scripts/database/manage_db.py create --database test_scenario_1
   python3 scripts/database/manage_db.py create --database test_scenario_2
   ```

2. **Load Different Datasets**
   ```bash
   # Create custom test data files in data/sample/
   python3 scripts/database/manage_db.py load-data --database test_scenario_1 --data-file data/sample/custom_data.json
   ```

3. **Isolated Testing**
   ```bash
   # Use different database for each test
   python3 scripts/crud/crud_operations.py --database test_scenario_1 count --collection customers
   ```

## Sample Data Structure

The system includes sample data with the following characteristics:

### Customer Records (10 records)
- **3 John Smith variants** - Testing name variations and duplicates
- **2 Mary/Maria Johnson variants** - Testing first name variations
- **2 Robert/Bob Brown variants** - Testing nickname matching
- **2 Jennifer/Jenny Wilson variants** - Testing nickname and email variations
- **1 Sarah Davis** - Single record for control testing

### Blocking Keys
- **lastname_city**: Groups records by last name initial + city initial
- **initials_zip**: Groups records by first/last initials + zip code

### Entity Clusters
- Pre-defined clusters showing expected entity resolution results
- Confidence scores for each cluster
- Golden records representing the best version of each entity

## Troubleshooting

### Common Issues

1. **Docker Not Starting**
   ```bash
   # Check Docker status
   docker info
   
   # Restart Docker service
   sudo systemctl restart docker  # Linux
   # Or restart Docker Desktop
   ```

2. **ArangoDB Connection Failed**
   ```bash
   # Check if container is running
   docker-compose ps
   
   # View ArangoDB logs
   docker-compose logs arangodb
   
   # Restart ArangoDB
   docker-compose restart arangodb
   ```

3. **Python Dependencies Issues**
   ```bash
   # Upgrade pip
   pip3 install --upgrade pip
   
   # Reinstall dependencies
   pip3 install -r requirements.txt --force-reinstall
   ```

4. **Permission Errors**
   ```bash
   # Make scripts executable
   chmod +x scripts/*.sh scripts/*/*.py
   
   # Fix data directory permissions
   sudo chown -R $USER:$USER ~/data
   ```

### Port Conflicts

If port 8529 is already in use:

1. **Find the conflicting process**
   ```bash
   lsof -i :8529
   ```

2. **Change the port in docker-compose.yml**
   ```yaml
   ports:
     - "8530:8529"  # Use port 8530 instead
   ```

3. **Update environment variables**
   ```bash
   # In .env file
   ARANGO_PORT=8530
   ```

## Cleanup

### Temporary Cleanup
```bash
# Stop containers but keep data
docker-compose down
```

### Complete Cleanup
```bash
# Use the automated teardown script
./scripts/teardown.sh

# Or manually:
docker-compose down -v  # Remove containers and volumes
rm -rf ~/data           # Remove local data (optional)
```

## Security Notes

### Default Credentials
- **Production Warning**: Change default password before production use
- **Test Environment**: Default credentials are acceptable for local testing

### Network Security
- ArangoDB is exposed only on localhost (127.0.0.1)
- No external network access by default
- Use proper authentication in production environments

### Data Privacy
- Sample data contains fictional records only
- Use anonymized data for testing with real datasets
- Follow GDPR/privacy regulations when handling real customer data

## Advanced Configuration

### Custom Docker Configuration

Modify `docker-compose.yml` for advanced configurations:

```yaml
services:
  arangodb:
    image: arangodb:3.12
    environment:
      ARANGO_ROOT_PASSWORD: your_secure_password
      # Add custom configurations
    volumes:
      - ${HOME}/data:/data
      - ./custom-config:/etc/arangodb3  # Custom config files
    command: >
      arangod
      --server.endpoint tcp://0.0.0.0:8529
      --server.authentication true
      --log.level debug  # Change log level
```

### Performance Tuning

For large datasets, consider these optimizations:

```yaml
# In docker-compose.yml
services:
  arangodb:
    environment:
      # Increase memory
      ARANGO_STORAGE_ENGINE: rocksdb
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

## Integration with CI/CD

### GitHub Actions Example

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
          sleep 30  # Wait for startup
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Setup test database
        run: |
          python3 scripts/database/manage_db.py create --database ci_test
          python3 scripts/database/manage_db.py init --database ci_test
      - name: Run tests
        run: pytest tests/
```

This comprehensive testing setup provides a solid foundation for developing and testing your ArangoDB entity resolution system with full Docker support, automated setup, and extensive documentation for third-party users.

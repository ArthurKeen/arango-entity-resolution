#!/bin/bash
# Setup script for ArangoDB Entity Resolution Testing Environment

set -e  # Exit on any error

echo "? Setting up ArangoDB Entity Resolution Testing Environment"

# Check prerequisites
echo "? Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "[FAIL] Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "[FAIL] Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[FAIL] Python 3 is not installed. Please install Python 3.8+ first."
    exit 1
fi

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "[FAIL] pip3 is not installed. Please install pip first."
    exit 1
fi

echo "[PASS] All prerequisites found"

# Create data directory
echo "? Creating data directory..."
mkdir -p ~/data
echo "[PASS] Data directory created at ~/data"

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "? Creating environment configuration..."
    cp env.example .env
    echo "[PASS] Environment file created (.env)"
    echo "   You can modify .env to customize your setup"
else
    echo "[WARN]?  Environment file (.env) already exists"
fi

# Install Python dependencies
echo "? Installing Python dependencies..."
pip3 install -r requirements.txt
echo "[PASS] Python dependencies installed"

# Make scripts executable
echo "? Making scripts executable..."
chmod +x scripts/database/manage_db.py
chmod +x scripts/crud/crud_operations.py
echo "[PASS] Scripts are now executable"

# Start ArangoDB
echo "? Starting ArangoDB container..."
docker-compose up -d

# Wait for ArangoDB to be ready
echo "[WAIT] Waiting for ArangoDB to be ready..."
sleep 10

# Check if ArangoDB is accessible
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8529/_api/version > /dev/null 2>&1; then
        echo "[PASS] ArangoDB is ready!"
        break
    else
        echo "   Waiting for ArangoDB... (attempt $((attempt + 1))/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    fi
done

if [ $attempt -eq $max_attempts ]; then
    echo "[FAIL] ArangoDB failed to start properly"
    echo "   Check logs with: docker-compose logs arangodb"
    exit 1
fi

# Create test database and schema
echo "??  Creating test database and schema..."
python3 scripts/database/manage_db.py create --database entity_resolution_test
python3 scripts/database/manage_db.py init --database entity_resolution_test

# Load sample data
echo "? Loading sample test data..."
python3 scripts/database/manage_db.py load-data --database entity_resolution_test --data-file data/sample/customers_sample.json

echo ""
echo "? Setup complete!"
echo ""
echo "? Quick Start Guide:"
echo "   * ArangoDB Web UI: http://localhost:8529"
echo "   * Username: root"
echo "   * Password: testpassword123"
echo "   * Test Database: entity_resolution_test"
echo ""
echo "? Available Commands:"
echo "   * Start ArangoDB:     docker-compose up -d"
echo "   * Stop ArangoDB:      docker-compose down"
echo "   * View logs:          docker-compose logs arangodb"
echo "   * Database management: python3 scripts/database/manage_db.py --help"
echo "   * CRUD operations:     python3 scripts/crud/crud_operations.py --help"
echo ""
echo "? Test the setup:"
echo "   python3 scripts/crud/crud_operations.py count --collection customers"
echo ""

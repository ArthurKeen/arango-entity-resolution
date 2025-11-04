#!/usr/bin/env python3
"""
Quick database connection checker

Tests connection to ArangoDB with current configuration
and helps diagnose authentication issues.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.entity_resolution.utils.config import get_config

def check_connection():
    """Check database connection and display configuration"""
    
    print("=" * 80)
    print("DATABASE CONNECTION CHECKER")
    print("=" * 80)
    print()
    
    # Get configuration
    config = get_config()
    
    print("[CONFIG] Current Configuration:")
    print(f"  Host: {config.db.host}")
    print(f"  Port: {config.db.port}")
    print(f"  Database: {config.db.database}")
    print(f"  Username: {config.db.username}")
    print(f"  Password: {'*' * len(config.db.password) if config.db.password else '<not set>'}")
    print()
    
    # Try to connect
    print("[INFO] Testing connection...")
    
    try:
        from arango import ArangoClient
        
        client = ArangoClient(hosts=f"http://{config.db.host}:{config.db.port}")
        
        # Try to connect
        db = client.db(
            config.db.database,
            username=config.db.username,
            password=config.db.password
        )
        
        # Test with a simple query
        version = db.version()
        
        print("[OK] Connection successful!")
        print(f"  ArangoDB version: {version}")
        print()
        
        # List collections
        print("[INFO] Available collections:")
        collections = db.collections()
        for coll in collections:
            if not coll['name'].startswith('_'):  # Skip system collections
                count = db.collection(coll['name']).count()
                print(f"  - {coll['name']}: {count:,} documents")
        
        print()
        print("[OK] Ready to use!")
        return True
        
    except Exception as e:
        print(f"[ X ] Connection failed: {e}")
        print()
        print("[FIX] To fix this, set environment variables:")
        print()
        print("  export DB_HOST=localhost")
        print("  export DB_PORT=8529")
        print("  export DB_NAME=your_database_name")
        print("  export DB_USERNAME=your_username")
        print("  export DB_PASSWORD=your_password")
        print()
        print("Or update config.json in the project root")
        print()
        return False

if __name__ == "__main__":
    success = check_connection()
    sys.exit(0 if success else 1)


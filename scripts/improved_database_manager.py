#!/usr/bin/env python3
"""
Improved Database Manager for Entity Resolution

This script provides a centralized database management system that:
1. Prevents duplicate database creation
2. Automatically cleans up old databases
3. Uses consistent naming conventions
4. Provides proper cleanup on exit
"""

import sys
import os
import json
import atexit
import signal
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.database import DatabaseManager
from entity_resolution.utils.config import Config

class ImprovedDatabaseManager:
    """Improved database manager with automatic cleanup."""
    
    def __init__(self, database_type="test"):
        self.database_type = database_type
        self.config = Config.from_env()
        self.db_manager = DatabaseManager()
        self.created_databases = []
        
        # Register cleanup handlers
        atexit.register(self.cleanup_on_exit)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def get_database_name(self):
        """Get the appropriate database name based on type."""
        if self.database_type == "demo":
            return "entity_resolution_demo"
        elif self.database_type == "test":
            return "entity_resolution_test"
        elif self.database_type == "app":
            return "entity_resolution_app"
        else:
            return f"entity_resolution_{self.database_type}"
    
    def cleanup_old_databases(self, max_age_hours=24):
        """Clean up old entity resolution databases."""
        print("? Cleaning up old entity resolution databases...")
        
        try:
            if not self.db_manager.test_connection():
                print("[FAIL] Could not connect to database")
                return False
            
            sys_db = self.db_manager.get_database()
            client = self.db_manager.client
            
            # Get all entity resolution databases
            databases = sys_db.databases()
            entity_resolution_dbs = [db for db in databases if 'entity_resolution' in db and db != '_system']
            
            if not entity_resolution_dbs:
                print("[PASS] No old databases to clean up")
                return True
            
            print(f"? Found {len(entity_resolution_dbs)} entity resolution databases")
            
            # Clean up old databases (keep only the current one)
            current_db = self.get_database_name()
            databases_to_delete = [db for db in entity_resolution_dbs if db != current_db]
            
            if not databases_to_delete:
                print("[PASS] No old databases to clean up")
                return True
            
            print(f"??  Deleting {len(databases_to_delete)} old databases...")
            
            for db_name in databases_to_delete:
                try:
                    # Check if database has data worth backing up
                    db = client.db(db_name)
                    collections = db.collections()
                    custom_collections = [col for col in collections if not col["name"].startswith('_')]
                    
                    if custom_collections:
                        print(f"  ? {db_name}: has {len(custom_collections)} custom collections")
                        # Could backup here if needed
                    else:
                        print(f"  ? {db_name}: empty")
                    
                    # Delete the database
                    if sys_db.has_database(db_name):
                        sys_db.delete_database(db_name)
                        print(f"  [PASS] Deleted {db_name}")
                    
                except Exception as e:
                    print(f"  [FAIL] Error cleaning up {db_name}: {e}")
            
            print("[PASS] Old database cleanup completed")
            return True
            
        except Exception as e:
            print(f"[FAIL] Error during cleanup: {e}")
            return False
    
    def ensure_database_exists(self):
        """Ensure the appropriate database exists."""
        try:
            if not self.db_manager.test_connection():
                print("[FAIL] Could not connect to database")
                return False
            
            sys_db = self.db_manager.get_database()
            db_name = self.get_database_name()
            
            # Clean up old databases first
            self.cleanup_old_databases()
            
            # Create database if it doesn't exist
            if not sys_db.has_database(db_name):
                print(f"? Creating database: {db_name}")
                sys_db.create_database(db_name)
                self.created_databases.append(db_name)
            else:
                print(f"? Using existing database: {db_name}")
            
            # Connect to the database
            client = self.db_manager.client
            db = client.db(db_name)
            
            print(f"[PASS] Connected to database: {db.name}")
            return True
            
        except Exception as e:
            print(f"[FAIL] Error ensuring database exists: {e}")
            return False
    
    def cleanup_on_exit(self):
        """Clean up databases when script exits."""
        if self.created_databases:
            print(f"\n? Cleaning up {len(self.created_databases)} created databases...")
            try:
                sys_db = self.db_manager.get_database()
                for db_name in self.created_databases:
                    try:
                        if sys_db.has_database(db_name):
                            sys_db.delete_database(db_name)
                            print(f"  [PASS] Deleted {db_name}")
                    except Exception as e:
                        print(f"  [FAIL] Error deleting {db_name}: {e}")
            except Exception as e:
                print(f"[FAIL] Error during cleanup: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle interrupt signals."""
        print(f"\n[WARN]?  Received signal {signum}, cleaning up...")
        self.cleanup_on_exit()
        sys.exit(0)
    
    def get_database(self):
        """Get the database connection."""
        if not self.ensure_database_exists():
            return None
        
        try:
            client = self.db_manager.client
            db_name = self.get_database_name()
            return client.db(db_name)
        except Exception as e:
            print(f"[FAIL] Error getting database: {e}")
            return None

def main():
    """Example usage of the improved database manager."""
    print("? Improved Database Manager Demo")
    print("=" * 40)
    
    # Create database manager for testing
    db_mgr = ImprovedDatabaseManager("test")
    
    # Ensure database exists
    if not db_mgr.ensure_database_exists():
        print("[FAIL] Failed to setup database")
        return False
    
    # Get database connection
    db = db_mgr.get_database()
    if not db:
        print("[FAIL] Failed to get database connection")
        return False
    
    print(f"[PASS] Database manager working correctly")
    print(f"? Database: {db.name}")
    
    # List collections
    collections = db.collections()
    print(f"? Collections: {len(collections)}")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n[PASS] Improved database manager demo completed!")
        else:
            print("\n[FAIL] Improved database manager demo failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n[FAIL] Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        sys.exit(1)

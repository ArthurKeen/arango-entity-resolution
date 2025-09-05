#!/usr/bin/env python3
"""
ArangoDB Database Management Script
Handles database creation, deletion, and initialization for testing
"""

import os
import sys
import json
import argparse
from typing import Dict, List, Optional
from arango import ArangoClient
from arango.exceptions import DatabaseCreateError, DatabaseDeleteError, DocumentInsertError

# Add the scripts directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.arango_base import ArangoBaseConnection, add_common_args


class ArangoDBManager(ArangoBaseConnection):
    """Manages ArangoDB operations for entity resolution testing"""
    
    def __init__(self, host: str = "localhost", port: int = 8529, 
                 username: str = "root", password: Optional[str] = None):
        super().__init__(host, port, username, password)
        self._sys_db = None
    
    def connect(self) -> bool:
        """Establish connection to ArangoDB"""
        try:
            self._sys_db = self.client.db('_system', username=self.username, password=self.password)
            # Test connection
            self._sys_db.properties()
            self.print_success(f"Connected to ArangoDB at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.print_error(f"Failed to connect to ArangoDB: {e}")
            return False
    
    def create_database(self, db_name: str, users: Optional[List[Dict]] = None) -> bool:
        """Create a new database"""
        try:
            self._sys_db.create_database(
                name=db_name,
                users=users or [{'username': self.username, 'password': self.password, 'active': True}]
            )
            self.print_success(f"Created database: {db_name}")
            return True
        except DatabaseCreateError as e:
            if "duplicate" in str(e).lower():
                self.print_warning(f"Database {db_name} already exists")
                return True
            self.print_error(f"Failed to create database {db_name}: {e}")
            return False
    
    def delete_database(self, db_name: str) -> bool:
        """Delete a database"""
        try:
            self._sys_db.delete_database(db_name)
            print(f"✓ Deleted database: {db_name}")
            return True
        except DatabaseDeleteError as e:
            if "not found" in str(e).lower():
                print(f"⚠ Database {db_name} does not exist")
                return True
            print(f"✗ Failed to delete database {db_name}: {e}")
            return False
    
    def list_databases(self) -> List[str]:
        """List all databases"""
        try:
            databases = self._sys_db.databases()
            self.print_info("Available databases:")
            for db in databases:
                print(f"  - {db}")
            return databases
        except Exception as e:
            self.print_error(f"Failed to list databases: {e}")
            return []
    
    def initialize_entity_resolution_schema(self, db_name: str) -> bool:
        """Initialize collections and indexes for entity resolution"""
        try:
            db = self.client.db(db_name, username=self.username, password=self.password)
            
            # Create collections
            collections = [
                {
                    'name': 'customers',
                    'schema': {
                        'properties': {
                            'first_name': {'type': 'string'},
                            'last_name': {'type': 'string'},
                            'email': {'type': 'string'},
                            'phone': {'type': 'string'},
                            'address': {'type': 'string'},
                            'city': {'type': 'string'},
                            'state': {'type': 'string'},
                            'zip_code': {'type': 'string'},
                            'source': {'type': 'string'},
                            'created_at': {'type': 'string'},
                            'blocking_keys': {'type': 'array'}
                        }
                    }
                },
                {
                    'name': 'blocking_keys',
                    'schema': {
                        'properties': {
                            'key_value': {'type': 'string'},
                            'key_type': {'type': 'string'},
                            'record_ids': {'type': 'array'}
                        }
                    }
                },
                {
                    'name': 'entity_clusters',
                    'schema': {
                        'properties': {
                            'cluster_id': {'type': 'string'},
                            'record_ids': {'type': 'array'},
                            'golden_record': {'type': 'object'},
                            'confidence_score': {'type': 'number'}
                        }
                    }
                }
            ]
            
            # Create edge collections for relationships
            edge_collections = [
                {
                    'name': 'matches',
                    'edge': True,
                    'schema': {
                        'properties': {
                            'similarity_score': {'type': 'number'},
                            'match_type': {'type': 'string'},
                            'algorithm': {'type': 'string'},
                            'created_at': {'type': 'string'}
                        }
                    }
                }
            ]
            
            # Create document collections
            for coll_def in collections:
                if not db.has_collection(coll_def['name']):
                    collection = db.create_collection(coll_def['name'])
                    print(f"✓ Created collection: {coll_def['name']}")
                else:
                    collection = db.collection(coll_def['name'])
                    print(f"⚠ Collection {coll_def['name']} already exists")
                
                # Create indexes
                self._create_indexes(collection, coll_def['name'])
            
            # Create edge collections
            for coll_def in edge_collections:
                if not db.has_collection(coll_def['name']):
                    collection = db.create_collection(coll_def['name'], edge=True)
                    print(f"✓ Created edge collection: {coll_def['name']}")
                else:
                    print(f"⚠ Edge collection {coll_def['name']} already exists")
            
            print(f"✓ Initialized entity resolution schema in database: {db_name}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to initialize schema: {e}")
            return False
    
    def _create_indexes(self, collection, collection_name: str):
        """Create appropriate indexes for collections"""
        try:
            if collection_name == 'customers':
                # Hash indexes for exact matches
                collection.add_index({'type': 'hash', 'fields': ['email'], 'unique': False})
                collection.add_index({'type': 'hash', 'fields': ['phone'], 'unique': False})
                collection.add_index({'type': 'hash', 'fields': ['source'], 'unique': False})
                
                # Persistent indexes for range queries (skiplist is deprecated)
                collection.add_index({'type': 'persistent', 'fields': ['last_name', 'first_name']})
                collection.add_index({'type': 'persistent', 'fields': ['zip_code']})
                
                # Fulltext index for address search
                collection.add_index({'type': 'fulltext', 'fields': ['address']})
                
                print(f"  ✓ Created indexes for {collection_name}")
                
            elif collection_name == 'blocking_keys':
                collection.add_index({'type': 'hash', 'fields': ['key_value'], 'unique': True})
                collection.add_index({'type': 'hash', 'fields': ['key_type'], 'unique': False})
                print(f"  ✓ Created indexes for {collection_name}")
                
        except Exception as e:
            print(f"  ⚠ Warning: Could not create some indexes for {collection_name}: {e}")
    
    def load_test_data(self, db_name: str, data_file: str) -> bool:
        """Load test data from JSON file"""
        try:
            if not os.path.exists(data_file):
                print(f"✗ Data file not found: {data_file}")
                return False
            
            db = self.client.db(db_name, username=self.username, password=self.password)
            
            with open(data_file, 'r') as f:
                data = json.load(f)
            
            for collection_name, documents in data.items():
                if db.has_collection(collection_name):
                    collection = db.collection(collection_name)
                    try:
                        collection.insert_many(documents)
                        print(f"✓ Loaded {len(documents)} documents into {collection_name}")
                    except DocumentInsertError as e:
                        print(f"⚠ Some documents in {collection_name} may have been skipped: {e}")
                else:
                    print(f"⚠ Collection {collection_name} does not exist, skipping")
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to load test data: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Manage ArangoDB for entity resolution testing')
    parser.add_argument('action', choices=['create', 'delete', 'list', 'init', 'load-data'],
                       help='Action to perform')
    parser.add_argument('--database', '-d', required=False,
                       help='Database name (required for create, delete, init, load-data)')
    parser.add_argument('--data-file', required=False,
                       help='Path to test data JSON file (for load-data action)')
    
    # Add common connection arguments
    add_common_args(parser)
    
    args = parser.parse_args()
    
    # Create manager and connect
    manager = ArangoDBManager(args.host, args.port, args.username, args.password)
    
    if not manager.connect():
        sys.exit(1)
    
    # Execute action
    success = True
    
    if args.action == 'create':
        if not args.database:
            print("✗ Database name required for create action")
            sys.exit(1)
        success = manager.create_database(args.database)
        
    elif args.action == 'delete':
        if not args.database:
            print("✗ Database name required for delete action")
            sys.exit(1)
        success = manager.delete_database(args.database)
        
    elif args.action == 'list':
        manager.list_databases()
        
    elif args.action == 'init':
        if not args.database:
            print("✗ Database name required for init action")
            sys.exit(1)
        success = manager.initialize_entity_resolution_schema(args.database)
        
    elif args.action == 'load-data':
        if not args.database or not args.data_file:
            print("✗ Database name and data file required for load-data action")
            sys.exit(1)
        success = manager.load_test_data(args.database, args.data_file)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

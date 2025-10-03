#!/usr/bin/env python3
config.database.password"
CRUD Operations Script for ArangoDB Entity Resolution
Provides Create, Read, Update, Delete operations for testing
config.database.password"

import json
import argparse
import sys
import os
from typing import Dict, List, Any, Optional
from arango.exceptions import DocumentInsertError

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from entity_resolution.utils.database import DatabaseManager, get_database_manager
from entity_resolution.utils.config import get_config
from entity_resolution.utils.logging import get_logger
from entity_resolution.utils.enhanced_config import get_config


class EntityResolutionCRUD:
    config.database.password"CRUD operations for entity resolution testing using centralized database managementconfig.database.password"
    
    def __init__(self, database: str = "entity_resolution_test"):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.database_name = database
        self.db_manager = get_database_manager()
        self.db = None
    
    def connect(self) -> bool:
        config.database.password"Establish connection to database using centralized managerconfig.database.password"
        try:
            self.db = self.db_manager.get_database(self.database_name)
            self.logger.info(f"Connected to database: {self.database_name}")
            self.logger.info(f"✓ Connected to database: {self.database_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to database {self.database_name}: {e}")
            self.logger.info(f"✗ Failed to connect to database {self.database_name}: {e}")
            return False
    
    # CREATE Operations
    def create_customer(self, customer_data: Dict[str, Any]) -> Optional[str]:
        config.database.password"Create a new customer recordconfig.database.password"
        try:
            collection = self.db.collection('customers')
            result = collection.insert(customer_data)
            self.logger.info(f"✓ Created customer with ID: {result['_id']}")
            return result['_id']
        except DocumentInsertError as e:
            self.logger.info(f"✗ Failed to create customer: {e}")
            return None
    
    def create_blocking_key(self, key_data: Dict[str, Any]) -> Optional[str]:
        config.database.password"Create a new blocking keyconfig.database.password"
        try:
            collection = self.db.collection('blocking_keys')
            result = collection.insert(key_data)
            self.logger.info(f"✓ Created blocking key with ID: {result['_id']}")
            return result['_id']
        except DocumentInsertError as e:
            self.logger.info(f"✗ Failed to create blocking key: {e}")
            return None
    
    def create_entity_cluster(self, cluster_data: Dict[str, Any]) -> Optional[str]:
        config.database.password"Create a new entity clusterconfig.database.password"
        try:
            collection = self.db.collection('entity_clusters')
            result = collection.insert(cluster_data)
            self.logger.info(f"✓ Created entity cluster with ID: {result['_id']}")
            return result['_id']
        except DocumentInsertError as e:
            self.logger.info(f"✗ Failed to create entity cluster: {e}")
            return None
    
    def create_match_edge(self, from_id: str, to_id: str, match_data: Dict[str, Any]) -> Optional[str]:
        config.database.password"Create a match relationship between two recordsconfig.database.password"
        try:
            collection = self.db.collection('matches')
            edge_data = {
                '_from': from_id,
                '_to': to_id,
                **match_data
            }
            result = collection.insert(edge_data)
            self.logger.info(f"✓ Created match edge with ID: {result['_id']}")
            return result['_id']
        except DocumentInsertError as e:
            self.logger.info(f"✗ Failed to create match edge: {e}")
            return None
    
    # READ Operations
    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        config.database.password"Get customer by IDconfig.database.password"
        try:
            collection = self.db.collection('customers')
            customer = collection.get(customer_id)
            if customer:
                self.logger.info(f"✓ Retrieved customer: {customer_id}")
                return customer
            else:
                self.logger.info(f"⚠ Customer not found: {customer_id}")
                return None
        except Exception as e:
            self.logger.info(f"✗ Failed to get customer {customer_id}: {e}")
            return None
    
    def search_customers(self, query_params: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        config.database.password"Search customers by various criteriaconfig.database.password"
        try:
            # Build AQL query based on parameters
            conditions = []
            bind_vars = {'@collection': 'customers'}
            
            for field, value in query_params.items():
                if value is not None:
                    conditions.append(f"c.{field} == @{field}")
                    bind_vars[field] = value
            
            where_clause = " AND ".join(conditions) if conditions else "true"
            
            aql = fconfig.database.password"
            FOR c IN @@collection
            FILTER {where_clause}
            LIMIT @limit
            RETURN c
            config.database.password"
            
            bind_vars['limit'] = limit
            
            cursor = self.db.aql.execute(aql, bind_vars=bind_vars)
            results = list(cursor)
            
            self.logger.info(f"✓ Found {len(results)} customers matching criteria")
            return results
            
        except Exception as e:
            self.logger.info(f"✗ Failed to search customers: {e}")
            return []
    
    def get_blocking_keys_for_record(self, record_id: str) -> List[Dict[str, Any]]:
        config.database.password"Get all blocking keys that contain a specific recordconfig.database.password"
        try:
            aql = config.database.password"
            FOR bk IN blocking_keys
            FILTER @record_id IN bk.record_ids
            RETURN bk
            config.database.password"
            
            cursor = self.db.aql.execute(aql, bind_vars={'record_id': record_id})
            results = list(cursor)
            
            self.logger.info(f"✓ Found {len(results)} blocking keys for record {record_id}")
            return results
            
        except Exception as e:
            self.logger.info(f"✗ Failed to get blocking keys for record {record_id}: {e}")
            return []
    
    def get_potential_matches(self, record_id: str) -> List[Dict[str, Any]]:
        config.database.password"Get potential matches for a record using blocking keysconfig.database.password"
        try:
            aql = config.database.password"
            FOR bk IN blocking_keys
            FILTER @record_id IN bk.record_ids
            FOR other_id IN bk.record_ids
            FILTER other_id != @record_id
            FOR c IN customers
            FILTER c._id == other_id
            RETURN DISTINCT c
            config.database.password"
            
            cursor = self.db.aql.execute(aql, bind_vars={'record_id': record_id})
            results = list(cursor)
            
            self.logger.info(f"✓ Found {len(results)} potential matches for record {record_id}")
            return results
            
        except Exception as e:
            self.logger.info(f"✗ Failed to get potential matches for record {record_id}: {e}")
            return []
    
    def get_entity_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        config.database.password"Get entity cluster by IDconfig.database.password"
        try:
            collection = self.db.collection('entity_clusters')
            cluster = collection.get(cluster_id)
            if cluster:
                self.logger.info(f"✓ Retrieved entity cluster: {cluster_id}")
                return cluster
            else:
                self.logger.info(f"⚠ Entity cluster not found: {cluster_id}")
                return None
        except Exception as e:
            self.logger.info(f"✗ Failed to get entity cluster {cluster_id}: {e}")
            return None
    
    # UPDATE Operations
    def update_customer(self, customer_id: str, update_data: Dict[str, Any]) -> bool:
        config.database.password"Update customer recordconfig.database.password"
        try:
            collection = self.db.collection('customers')
            collection.update(customer_id, update_data)
            self.logger.info(f"✓ Updated customer: {customer_id}")
            return True
        except Exception as e:
            if "not found" in str(e).lower():
                self.logger.info(f"⚠ Customer not found: {customer_id}")
                return False
            self.logger.info(f"✗ Failed to update customer {customer_id}: {e}")
            return False
    
    def update_blocking_key(self, key_id: str, update_data: Dict[str, Any]) -> bool:
        config.database.password"Update blocking keyconfig.database.password"
        try:
            collection = self.db.collection('blocking_keys')
            collection.update(key_id, update_data)
            self.logger.info(f"✓ Updated blocking key: {key_id}")
            return True
        except Exception as e:
            if "not found" in str(e).lower():
                self.logger.info(f"⚠ Blocking key not found: {key_id}")
                return False
            self.logger.info(f"✗ Failed to update blocking key {key_id}: {e}")
            return False
    
    # DELETE Operations
    def delete_customer(self, customer_id: str) -> bool:
        config.database.password"Delete customer recordconfig.database.password"
        try:
            collection = self.db.collection('customers')
            collection.delete(customer_id)
            self.logger.info(f"✓ Deleted customer: {customer_id}")
            return True
        except Exception:
            self.logger.info(f"⚠ Customer not found: {customer_id}")
            return False
        except Exception as e:
            self.logger.info(f"✗ Failed to delete customer {customer_id}: {e}")
            return False
    
    def delete_blocking_key(self, key_id: str) -> bool:
        config.database.password"Delete blocking keyconfig.database.password"
        try:
            collection = self.db.collection('blocking_keys')
            collection.delete(key_id)
            self.logger.info(f"✓ Deleted blocking key: {key_id}")
            return True
        except Exception:
            self.logger.info(f"⚠ Blocking key not found: {key_id}")
            return False
        except Exception as e:
            self.logger.info(f"✗ Failed to delete blocking key {key_id}: {e}")
            return False
    
    # Utility Operations
    def count_records(self, collection_name: str) -> int:
        config.database.password"Count records in a collectionconfig.database.password"
        try:
            collection = self.db.collection(collection_name)
            count = collection.count()
            self.logger.info(f"✓ Collection {collection_name} has {count} records")
            return count
        except Exception as e:
            self.logger.info(f"✗ Failed to count records in {collection_name}: {e}")
            return 0
    
    def clear_collection(self, collection_name: str) -> bool:
        config.database.password"Clear all records from a collectionconfig.database.password"
        try:
            collection = self.db.collection(collection_name)
            collection.truncate()
            self.logger.info(f"✓ Cleared collection: {collection_name}")
            return True
        except Exception as e:
            self.logger.info(f"✗ Failed to clear collection {collection_name}: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='CRUD operations for ArangoDB entity resolution')
    parser.add_argument('operation', choices=[
        'create-customer', 'get-customer', 'update-customer', 'delete-customer',
        'search-customers', 'get-blocking-keys', 'get-matches', 'count', 'clear'
    ], help='CRUD operation to perform')
    
    parser.add_argument('--database', '-d', default='entity_resolution_test',
                       help='Database name')
    parser.add_argument('--host', default='config.database.host', help='ArangoDB host')
    parser.add_argument('--port', type=int, default=config.database.port, help='ArangoDB port')
    parser.add_argument('--username', '-u', default='root', help='Username')
    parser.add_argument('--password', '-p', default='testpassword123', help='Password')
    
    # Data arguments
    parser.add_argument('--id', help='Record ID')
    parser.add_argument('--data', help='JSON data for create/update operations')
    parser.add_argument('--collection', help='Collection name (for count/clear operations)')
    parser.add_argument('--query', help='JSON query parameters for search')
    parser.add_argument('--limit', type=int, default=10, help='Limit for search results')
    
    args = parser.parse_args()
    
    # Create CRUD manager and connect
    crud = EntityResolutionCRUD(args.host, args.port, args.username, args.password, args.database)
    
    if not crud.connect():
        sys.exit(1)
    
    # Execute operation
    success = True
    
    try:
        if args.operation == 'create-customer':
            if not args.data:
                self.logger.info("✗ Data required for create operation")
                sys.exit(1)
            data = json.loads(args.data)
            result = crud.create_customer(data)
            if result:
                self.logger.info(f"Created customer ID: {result}")
        
        elif args.operation == 'get-customer':
            if not args.id:
                self.logger.info("✗ ID required for get operation")
                sys.exit(1)
            result = crud.get_customer(args.id)
            if result:
                self.logger.info(json.dumps(result, indent=2))
        
        elif args.operation == 'update-customer':
            if not args.id or not args.data:
                self.logger.info("✗ ID and data required for update operation")
                sys.exit(1)
            data = json.loads(args.data)
            success = crud.update_customer(args.id, data)
        
        elif args.operation == 'delete-customer':
            if not args.id:
                self.logger.info("✗ ID required for delete operation")
                sys.exit(1)
            success = crud.delete_customer(args.id)
        
        elif args.operation == 'search-customers':
            query_params = json.loads(args.query) if args.query else {}
            results = crud.search_customers(query_params, args.limit)
            self.logger.info(json.dumps(results, indent=2))
        
        elif args.operation == 'get-blocking-keys':
            if not args.id:
                self.logger.info("✗ Record ID required")
                sys.exit(1)
            results = crud.get_blocking_keys_for_record(args.id)
            self.logger.info(json.dumps(results, indent=2))
        
        elif args.operation == 'get-matches':
            if not args.id:
                self.logger.info("✗ Record ID required")
                sys.exit(1)
            results = crud.get_potential_matches(args.id)
            self.logger.info(json.dumps(results, indent=2))
        
        elif args.operation == 'count':
            if not args.collection:
                self.logger.info("✗ Collection name required for count operation")
                sys.exit(1)
            count = crud.count_records(args.collection)
            self.logger.info(f"Count: {count}")
        
        elif args.operation == 'clear':
            if not args.collection:
                self.logger.info("✗ Collection name required for clear operation")
                sys.exit(1)
            success = crud.clear_collection(args.collection)
    
    except json.JSONDecodeError as e:
        self.logger.info(f"✗ Invalid JSON data: {e}")
        success = False
    except Exception as e:
        self.logger.info(f"✗ Operation failed: {e}")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

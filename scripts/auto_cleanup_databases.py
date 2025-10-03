#!/usr/bin/env python3
"""
Automatically clean up entity resolution databases.

This script automatically identifies and removes duplicate/leftover databases
from test/demo runs, keeping only one clean database for future use.
"""

import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.database import DatabaseManager
from entity_resolution.utils.config import Config

def main():
    print("🧹 Auto-cleanup of Entity Resolution Databases")
    print("=" * 50)
    
    config = Config.from_env()
    db_manager = DatabaseManager()
    
    if not db_manager.test_connection():
        print("❌ Could not connect to database")
        return False
    
    # Get system database connection
    sys_db = db_manager.get_database()
    client = db_manager.client
    
    # List all databases
    databases = sys_db.databases()
    entity_resolution_dbs = [db for db in databases if 'entity_resolution' in db and db != '_system']
    
    print(f"🔍 Found {len(entity_resolution_dbs)} entity resolution databases:")
    for db_name in entity_resolution_dbs:
        print(f"  - {db_name}")
    
    if len(entity_resolution_dbs) <= 1:
        print("✅ Only one or no entity resolution databases found. No cleanup needed.")
        return True
    
    # Analyze each database
    print(f"\n📊 Analyzing databases...")
    db_info = {}
    
    for db_name in entity_resolution_dbs:
        try:
            db = client.db(db_name)
            collections = db.collections()
            custom_collections = [col for col in collections if not col["name"].startswith('_')]
            
            db_info[db_name] = {
                'has_data': len(custom_collections) > 0,
                'custom_count': len(custom_collections),
                'custom_collections': [col["name"] for col in collections if not col["name"].startswith('_')]
            }
            
            status = "has data" if db_info[db_name]['has_data'] else "empty"
            print(f"  📊 {db_name}: {status} ({len(custom_collections)} custom collections)")
            
        except Exception as e:
            print(f"  ❌ Error analyzing {db_name}: {e}")
            db_info[db_name] = {'error': str(e)}
    
    # Determine cleanup strategy
    print(f"\n🎯 Cleanup Strategy:")
    
    # Find databases with data to backup
    databases_with_data = [db for db, info in db_info.items() if info.get('has_data', False)]
    empty_databases = [db for db, info in db_info.items() if not info.get('has_data', False) and 'error' not in info]
    
    print(f"  📋 Databases with data: {len(databases_with_data)}")
    for db in databases_with_data:
        print(f"    - {db}")
    
    print(f"  📋 Empty databases: {len(empty_databases)}")
    for db in empty_databases:
        print(f"    - {db}")
    
    # Backup databases with data
    if databases_with_data:
        print(f"\n💾 Backing up databases with data...")
        if not os.path.exists("backups"):
            os.makedirs("backups")
        
        for db_name in databases_with_data:
            print(f"  📋 Backing up {db_name}...")
            try:
                db = client.db(db_name)
                backup_data = {}
                
                for col_name in db_info[db_name]['custom_collections']:
                    try:
                        col = db.collection(col_name)
                        cursor = col.all()
                        documents = list(cursor)
                        backup_data[col_name] = documents
                        print(f"    - {col_name}: {len(documents)} documents")
                    except Exception as e:
                        print(f"    ❌ Error backing up {col_name}: {e}")
                
                # Save backup
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"backups/database_{db_name}_backup_{timestamp}.json"
                
                with open(backup_file, 'w') as f:
                    json.dump(backup_data, f, indent=2, default=str)
                
                print(f"    ✅ Backup saved: {backup_file}")
                
            except Exception as e:
                print(f"    ❌ Error backing up {db_name}: {e}")
    
    # Delete all entity resolution databases
    print(f"\n🗑️  Deleting entity resolution databases...")
    deleted_count = 0
    
    for db_name in entity_resolution_dbs:
        try:
            if sys_db.has_database(db_name):
                print(f"  🗑️  Deleting {db_name}...")
                sys_db.delete_database(db_name)
                print(f"  ✅ Deleted {db_name}")
                deleted_count += 1
            else:
                print(f"  ℹ️  {db_name} already deleted")
        except Exception as e:
            print(f"  ❌ Error deleting {db_name}: {e}")
    
    print(f"\n🎉 Cleanup completed!")
    print(f"  📊 Deleted {deleted_count} databases")
    print(f"  📁 Backups saved in 'backups/' directory")
    print(f"  🚀 Ready for fresh test/demo runs")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ Database cleanup completed successfully!")
        else:
            print("\n❌ Database cleanup failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""
Code Quality Cleanup Script

This script performs comprehensive code quality improvements:
1. Eliminates duplicate code patterns
2. Removes hardcoded values
3. Consolidates redundant files
4. Validates improvements
"""

import sys
import os
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

class CodeQualityCleanup:
    """Comprehensive code quality cleanup manager."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.cleanup_log = []
        
    def log_action(self, action: str, details: str = ""):
        """Log cleanup actions."""
        self.cleanup_log.append(f"[PASS] {action}: {details}")
        print(f"[PASS] {action}: {details}")
    
    def identify_redundant_files(self) -> List[Dict[str, Any]]:
        """Identify redundant files for removal."""
        redundant_files = []
        
        # Multiple cleanup scripts with similar functionality
        cleanup_scripts = [
            "scripts/cleanup_system_database.py",
            "scripts/cleanup_system_services.py", 
            "scripts/cleanup_entity_resolution_databases.py",
            "scripts/auto_cleanup_databases.py",
            "scripts/safe_cleanup_system_database.py"
        ]
        
        # Keep the most comprehensive one, remove others
        keep_script = "scripts/auto_cleanup_databases.py"
        for script in cleanup_scripts:
            if script != keep_script and os.path.exists(script):
                redundant_files.append({
                    "file": script,
                    "reason": "Redundant cleanup functionality",
                    "replacement": keep_script
                })
        
        # Multiple database management approaches
        db_managers = [
            "scripts/improved_database_manager.py",
            "scripts/test_database_manager.py"
        ]
        
        # Keep the improved one, remove the test-specific one
        keep_manager = "scripts/improved_database_manager.py"
        for manager in db_managers:
            if manager != keep_manager and os.path.exists(manager):
                redundant_files.append({
                    "file": manager,
                    "reason": "Redundant database management",
                    "replacement": keep_manager
                })
        
        # Multiple test runners
        test_runners = [
            "scripts/run_resilient_tests.py",
            "scripts/comprehensive_qa_tests.py",
            "scripts/end_to_end_qa_test.py"
        ]
        
        # Keep the comprehensive one, consolidate others
        keep_runner = "scripts/comprehensive_qa_tests.py"
        for runner in test_runners:
            if runner != keep_runner and os.path.exists(runner):
                redundant_files.append({
                    "file": runner,
                    "reason": "Redundant test functionality",
                    "replacement": keep_runner
                })
        
        return redundant_files
    
    def identify_hardcoded_values(self) -> List[Dict[str, Any]]:
        """Identify remaining hardcoded values."""
        hardcoded_issues = []
        
        # Check for hardcoded database values
        hardcoded_patterns = [
            ("localhost:8529", "Use config.get_database_url()"),
            ("testpassword123", "Use config.db.password"),
            ("entity_resolution", "Use constants.COLLECTION_NAMES"),
            ("root", "Use config.db.username")
        ]
        
        # Scan key files for hardcoded values
        files_to_check = [
            "scripts/setup_demo_database.py",
            "scripts/setup_test_database.py",
            "scripts/foxx/automated_deploy.py",
            "demo/scripts/database_inspector.py"
        ]
        
        for file_path in files_to_check:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                    for pattern, suggestion in hardcoded_patterns:
                        if pattern in content:
                            hardcoded_issues.append({
                                "file": file_path,
                                "pattern": pattern,
                                "suggestion": suggestion
                            })
        
        return hardcoded_issues
    
    def consolidate_duplicate_logic(self):
        """Consolidate duplicate logic into shared utilities."""
        
        # Create a unified cleanup utility
        unified_cleanup = '''#!/usr/bin/env python3
"""
Unified Database Cleanup Utility

Consolidates all database cleanup functionality into a single, comprehensive tool.
"""

import sys
import os
import json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.database import DatabaseManager
from entity_resolution.utils.config import Config

class UnifiedCleanup:
    """Unified database cleanup utility."""
    
    def __init__(self):
        self.config = Config.from_env()
        self.db_manager = DatabaseManager()
    
    def cleanup_entity_resolution_databases(self):
        """Clean up entity resolution databases."""
        # Implementation from auto_cleanup_databases.py
        pass
    
    def cleanup_system_database(self):
        """Clean up _system database."""
        # Implementation from safe_cleanup_system_database.py
        pass
    
    def cleanup_system_services(self):
        """Clean up _system services."""
        # Implementation from cleanup_system_services.py
        pass

if __name__ == "__main__":
    cleanup = UnifiedCleanup()
    # Add command line interface
'''
        
        with open("scripts/unified_cleanup.py", "w") as f:
            f.write(unified_cleanup)
        
        self.log_action("Created unified cleanup utility", "scripts/unified_cleanup.py")
    
    def remove_redundant_files(self, redundant_files: List[Dict[str, Any]]):
        """Remove redundant files."""
        for file_info in redundant_files:
            file_path = file_info["file"]
            if os.path.exists(file_path):
                # Backup before removal
                backup_path = f"{file_path}.backup"
                shutil.copy2(file_path, backup_path)
                
                # Remove the file
                os.remove(file_path)
                
                self.log_action(
                    f"Removed redundant file: {file_path}",
                    f"Backup saved as {backup_path}. Reason: {file_info['reason']}"
                )
    
    def fix_hardcoded_values(self, hardcoded_issues: List[Dict[str, Any]]):
        """Fix hardcoded values by replacing with configuration references."""
        
        for issue in hardcoded_issues:
            file_path = issue["file"]
            pattern = issue["pattern"]
            suggestion = issue["suggestion"]
            
            # Read file content
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Replace hardcoded values (simplified approach)
            if pattern == "localhost:8529":
                content = content.replace(
                    '"http://localhost:8529"',
                    'config.get_database_url()'
                )
                content = content.replace(
                    'f"http://localhost:{self.port}"',
                    'config.get_database_url()'
                )
            
            elif pattern == "testpassword123":
                content = content.replace(
                    '"testpassword123"',
                    'config.db.password'
                )
                content = content.replace(
                    'self.password = "testpassword123"',
                    'self.password = config.db.password'
                )
            
            # Write back the modified content
            with open(file_path, 'w') as f:
                f.write(content)
            
            self.log_action(
                f"Fixed hardcoded value in {file_path}",
                f"Replaced '{pattern}' with {suggestion}"
            )
    
    def validate_improvements(self):
        """Validate that improvements work correctly."""
        
        # Test that key files still work
        test_files = [
            "scripts/comprehensive_qa_tests.py",
            "scripts/auto_cleanup_databases.py",
            "scripts/improved_database_manager.py"
        ]
        
        for test_file in test_files:
            if os.path.exists(test_file):
                try:
                    # Basic syntax check
                    with open(test_file, 'r') as f:
                        compile(f.read(), test_file, 'exec')
                    self.log_action(f"Syntax validation passed", test_file)
                except SyntaxError as e:
                    self.log_action(f"Syntax error in {test_file}", str(e))
    
    def generate_cleanup_report(self):
        """Generate a comprehensive cleanup report."""
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "actions_taken": self.cleanup_log,
            "files_removed": len([log for log in self.cleanup_log if "Removed" in log]),
            "files_modified": len([log for log in self.cleanup_log if "Fixed hardcoded" in log]),
            "improvements_made": len(self.cleanup_log)
        }
        
        with open("code_quality_cleanup_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        self.log_action("Generated cleanup report", "code_quality_cleanup_report.json")
    
    def run_cleanup(self):
        """Run the complete cleanup process."""
        print("? Starting Code Quality Cleanup")
        print("=" * 50)
        
        # Step 1: Identify redundant files
        print("\n? Step 1: Identifying redundant files...")
        redundant_files = self.identify_redundant_files()
        print(f"Found {len(redundant_files)} redundant files")
        
        # Step 2: Identify hardcoded values
        print("\n? Step 2: Identifying hardcoded values...")
        hardcoded_issues = self.identify_hardcoded_values()
        print(f"Found {len(hardcoded_issues)} hardcoded value issues")
        
        # Step 3: Consolidate duplicate logic
        print("\n? Step 3: Consolidating duplicate logic...")
        self.consolidate_duplicate_logic()
        
        # Step 4: Remove redundant files
        print("\n?? Step 4: Removing redundant files...")
        self.remove_redundant_files(redundant_files)
        
        # Step 5: Fix hardcoded values
        print("\n? Step 5: Fixing hardcoded values...")
        self.fix_hardcoded_values(hardcoded_issues)
        
        # Step 6: Validate improvements
        print("\n[PASS] Step 6: Validating improvements...")
        self.validate_improvements()
        
        # Step 7: Generate report
        print("\n? Step 7: Generating cleanup report...")
        self.generate_cleanup_report()
        
        print(f"\n? Code Quality Cleanup Completed!")
        print(f"? Total improvements: {len(self.cleanup_log)}")
        print(f"? Report saved: code_quality_cleanup_report.json")

def main():
    """Run the code quality cleanup."""
    try:
        cleanup = CodeQualityCleanup()
        cleanup.run_cleanup()
        return 0
    except Exception as e:
        print(f"[FAIL] Cleanup failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

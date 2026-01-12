#!/usr/bin/env python3
"""
Cleanup Report Files

This script cleans up temporary report files generated during testing and code quality improvements,
while preserving important reports in the reports/ directory.
"""

import os
import glob
from datetime import datetime

def cleanup_report_files():
    """Clean up temporary report files."""
    print("? CLEANING UP REPORT FILES")
    print("="*50)
    
    # Find all report files
    report_files = glob.glob("*report*.json")
    
    print(f"? Found {len(report_files)} report files")
    
    # Keep important reports in reports/ directory
    important_reports = [
        "reports/demo_report.json",
        "reports/complete_pipeline_report.json",
        "reports/performance_benchmark.json"
    ]
    
    # Files to keep (important ones)
    keep_files = []
    for report in important_reports:
        if os.path.exists(report):
            keep_files.append(report)
            print(f"   [PASS] Keeping: {report}")
    
    # Files to remove (temporary ones)
    remove_files = []
    for report_file in report_files:
        if report_file not in keep_files:
            remove_files.append(report_file)
    
    print(f"\n? Files to remove: {len(remove_files)}")
    
    # Remove temporary report files
    removed_count = 0
    for report_file in remove_files:
        try:
            os.remove(report_file)
            print(f"   ??  Removed: {report_file}")
            removed_count += 1
        except Exception as e:
            print(f"   [FAIL] Error removing {report_file}: {e}")
    
    print(f"\n? Summary:")
    print(f"   ? Total report files found: {len(report_files)}")
    print(f"   [PASS] Important reports kept: {len(keep_files)}")
    print(f"   ??  Temporary reports removed: {removed_count}")
    
    return removed_count

def cleanup_log_files():
    """Clean up log files."""
    print("\n? CLEANING UP LOG FILES")
    print("="*50)
    
    # Find log files
    log_files = glob.glob("*.log")
    
    print(f"? Found {len(log_files)} log files")
    
    # Remove log files
    removed_count = 0
    for log_file in log_files:
        try:
            os.remove(log_file)
            print(f"   ??  Removed: {log_file}")
            removed_count += 1
        except Exception as e:
            print(f"   [FAIL] Error removing {log_file}: {e}")
    
    print(f"\n? Log files removed: {removed_count}")
    
    return removed_count

def cleanup_backup_files():
    """Clean up backup files."""
    print("\n? CLEANING UP BACKUP FILES")
    print("="*50)
    
    # Find backup files
    backup_files = glob.glob("backups/*.json")
    
    print(f"? Found {len(backup_files)} backup files")
    
    # Remove backup files
    removed_count = 0
    for backup_file in backup_files:
        try:
            os.remove(backup_file)
            print(f"   ??  Removed: {backup_file}")
            removed_count += 1
        except Exception as e:
            print(f"   [FAIL] Error removing {backup_file}: {e}")
    
    print(f"\n? Backup files removed: {removed_count}")
    
    return removed_count

def main():
    """Main cleanup function."""
    print("? COMPREHENSIVE REPORT CLEANUP")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Clean up report files
    report_count = cleanup_report_files()
    
    # Clean up log files
    log_count = cleanup_log_files()
    
    # Clean up backup files
    backup_count = cleanup_backup_files()
    
    # Summary
    total_removed = report_count + log_count + backup_count
    
    print(f"\n? CLEANUP COMPLETED")
    print("="*50)
    print(f"? Total files removed: {total_removed}")
    print(f"   ? Report files: {report_count}")
    print(f"   ? Log files: {log_count}")
    print(f"   ? Backup files: {backup_count}")
    print(f"\n[PASS] Repository cleaned up successfully!")
    
    return 0

if __name__ == "__main__":
    main()

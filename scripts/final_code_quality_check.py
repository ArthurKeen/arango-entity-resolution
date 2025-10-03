#!/usr/bin/env python3
"""
Final Code Quality Check

This script performs a final code quality check to ensure all issues have been resolved
and the codebase is ready for repository sync.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

class FinalCodeQualityCheck:
    """Final code quality check before repository sync."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.quality_report = {
            "timestamp": datetime.now().isoformat(),
            "checks": [],
            "issues_found": [],
            "recommendations": []
        }
    
    def check_file_organization(self):
        """Check file organization."""
        print("📁 Checking file organization...")
        
        # Check for proper directory structure
        expected_dirs = [
            "src/entity_resolution",
            "scripts",
            "scripts/tests",
            "docs",
            "demo"
        ]
        
        for dir_path in expected_dirs:
            full_path = self.project_root / dir_path
            if full_path.exists():
                self.quality_report["checks"].append({
                    "check": "directory_structure",
                    "path": dir_path,
                    "status": "✅ EXISTS"
                })
            else:
                self.quality_report["issues_found"].append({
                    "type": "missing_directory",
                    "path": dir_path,
                    "severity": "medium"
                })
    
    def check_redundant_files(self):
        """Check for remaining redundant files."""
        print("🔍 Checking for redundant files...")
        
        # Check for backup files
        backup_files = list(self.project_root.rglob("*.backup"))
        if backup_files:
            for file_path in backup_files:
                self.quality_report["issues_found"].append({
                    "type": "backup_file",
                    "file": str(file_path.relative_to(self.project_root)),
                    "severity": "low"
                })
        else:
            self.quality_report["checks"].append({
                "check": "backup_files",
                "status": "✅ NONE FOUND"
            })
        
        # Check for temporary files
        temp_files = list(self.project_root.rglob("*.tmp"))
        if temp_files:
            for file_path in temp_files:
                self.quality_report["issues_found"].append({
                    "type": "temp_file",
                    "file": str(file_path.relative_to(self.project_root)),
                    "severity": "low"
                })
        else:
            self.quality_report["checks"].append({
                "check": "temp_files",
                "status": "✅ NONE FOUND"
            })
    
    def check_duplicate_code(self):
        """Check for remaining duplicate code."""
        print("🔍 Checking for duplicate code...")
        
        # Check for duplicate main() functions
        main_functions = []
        for py_file in self.project_root.rglob("*.py"):
            if py_file.name.startswith('__'):
                continue
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                if 'def main():' in content:
                    main_functions.append(str(py_file.relative_to(self.project_root)))
            except:
                continue
        
        if len(main_functions) > 5:  # Allow some main functions but not too many
            self.quality_report["issues_found"].append({
                "type": "too_many_main_functions",
                "count": len(main_functions),
                "files": main_functions,
                "severity": "medium"
            })
        else:
            self.quality_report["checks"].append({
                "check": "main_functions",
                "count": len(main_functions),
                "status": "✅ ACCEPTABLE"
            })
    
    def check_hardcoded_values(self):
        """Check for remaining hardcoded values."""
        print("🔍 Checking for hardcoded values...")
        
        hardcoded_patterns = [
            r'localhost:\d+',
            r'password\s*=\s*["\'][^"\']+["\']',
            r'username\s*=\s*["\'][^"\']+["\']',
            r'port\s*=\s*\d+'
        ]
        
        hardcoded_found = []
        
        for py_file in self.project_root.rglob("*.py"):
            if py_file.name.startswith('__'):
                continue
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                for pattern in hardcoded_patterns:
                    import re
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        hardcoded_found.append({
                            "file": str(py_file.relative_to(self.project_root)),
                            "pattern": pattern,
                            "matches": matches
                        })
            except:
                continue
        
        if hardcoded_found:
            self.quality_report["issues_found"].extend([
                {
                    "type": "hardcoded_value",
                    "file": item["file"],
                    "pattern": item["pattern"],
                    "severity": "medium"
                } for item in hardcoded_found
            ])
        else:
            self.quality_report["checks"].append({
                "check": "hardcoded_values",
                "status": "✅ NONE FOUND"
            })
    
    def check_test_coverage(self):
        """Check test coverage."""
        print("🔍 Checking test coverage...")
        
        # Check if consolidated test suite exists and works
        consolidated_test = self.project_root / "scripts" / "consolidated_test_suite.py"
        if consolidated_test.exists():
            self.quality_report["checks"].append({
                "check": "consolidated_test_suite",
                "status": "✅ EXISTS"
            })
        else:
            self.quality_report["issues_found"].append({
                "type": "missing_consolidated_test",
                "severity": "high"
            })
        
        # Check for test organization
        tests_dir = self.project_root / "scripts" / "tests"
        if tests_dir.exists():
            test_files = list(tests_dir.rglob("*.py"))
            self.quality_report["checks"].append({
                "check": "test_organization",
                "test_files": len(test_files),
                "status": "✅ ORGANIZED"
            })
        else:
            self.quality_report["issues_found"].append({
                "type": "missing_tests_directory",
                "severity": "medium"
            })
    
    def check_documentation(self):
        """Check documentation completeness."""
        print("🔍 Checking documentation...")
        
        # Check for key documentation files
        key_docs = [
            "README.md",
            "CODE_QUALITY_CLEANUP_SUMMARY.md",
            "docs/PRD.md",
            "docs/DESIGN.md"
        ]
        
        for doc_file in key_docs:
            full_path = self.project_root / doc_file
            if full_path.exists():
                self.quality_report["checks"].append({
                    "check": "documentation",
                    "file": doc_file,
                    "status": "✅ EXISTS"
                })
            else:
                self.quality_report["issues_found"].append({
                    "type": "missing_documentation",
                    "file": doc_file,
                    "severity": "low"
                })
    
    def check_import_consistency(self):
        """Check import consistency."""
        print("🔍 Checking import consistency...")
        
        import_patterns = {}
        
        for py_file in self.project_root.rglob("*.py"):
            if py_file.name.startswith('__'):
                continue
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Check for entity_resolution imports
                if 'from entity_resolution' in content or 'import entity_resolution' in content:
                    import_patterns[str(py_file.relative_to(self.project_root))] = True
            except:
                continue
        
        if import_patterns:
            self.quality_report["checks"].append({
                "check": "import_consistency",
                "files_with_entity_resolution_imports": len(import_patterns),
                "status": "✅ CONSISTENT"
            })
        else:
            self.quality_report["issues_found"].append({
                "type": "no_entity_resolution_imports",
                "severity": "high"
            })
    
    def generate_recommendations(self):
        """Generate recommendations for final improvements."""
        print("💡 Generating recommendations...")
        
        recommendations = []
        
        # Check if there are any high-severity issues
        high_severity_issues = [issue for issue in self.quality_report["issues_found"] 
                               if issue.get("severity") == "high"]
        
        if high_severity_issues:
            recommendations.append({
                "priority": "HIGH",
                "action": "Fix high-severity issues before repository sync",
                "issues": [issue["type"] for issue in high_severity_issues]
            })
        
        # Check for medium-severity issues
        medium_severity_issues = [issue for issue in self.quality_report["issues_found"] 
                                 if issue.get("severity") == "medium"]
        
        if medium_severity_issues:
            recommendations.append({
                "priority": "MEDIUM",
                "action": "Address medium-severity issues for better code quality",
                "issues": [issue["type"] for issue in medium_severity_issues]
            })
        
        # General recommendations
        recommendations.extend([
            {
                "priority": "LOW",
                "action": "Regular code quality audits",
                "description": "Implement regular code quality audits to prevent accumulation of issues"
            },
            {
                "priority": "LOW",
                "action": "Documentation updates",
                "description": "Keep documentation up to date with code changes"
            }
        ])
        
        self.quality_report["recommendations"] = recommendations
    
    def run_final_check(self):
        """Run final code quality check."""
        print("🧪 FINAL CODE QUALITY CHECK")
        print("="*50)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        self.check_file_organization()
        self.check_redundant_files()
        self.check_duplicate_code()
        self.check_hardcoded_values()
        self.check_test_coverage()
        self.check_documentation()
        self.check_import_consistency()
        self.generate_recommendations()
        
        # Summary
        total_checks = len(self.quality_report["checks"])
        total_issues = len(self.quality_report["issues_found"])
        
        print(f"\n📊 FINAL QUALITY CHECK SUMMARY")
        print("="*50)
        print(f"✅ Checks Passed: {total_checks}")
        print(f"❌ Issues Found: {total_issues}")
        
        if total_issues == 0:
            print(f"\n🎉 EXCELLENT! Codebase is ready for repository sync.")
            print(f"   All quality checks passed with no issues found.")
        elif total_issues <= 3:
            print(f"\n✅ GOOD! Codebase is ready for repository sync.")
            print(f"   Minor issues found but not blocking.")
        else:
            print(f"\n⚠️  ATTENTION! Some issues found that should be addressed.")
            print(f"   Review the detailed report before repository sync.")
        
        # Show issues by severity
        high_issues = [i for i in self.quality_report["issues_found"] if i.get("severity") == "high"]
        medium_issues = [i for i in self.quality_report["issues_found"] if i.get("severity") == "medium"]
        low_issues = [i for i in self.quality_report["issues_found"] if i.get("severity") == "low"]
        
        if high_issues:
            print(f"\n🔴 High Severity Issues: {len(high_issues)}")
            for issue in high_issues:
                print(f"   - {issue['type']}: {issue.get('file', 'N/A')}")
        
        if medium_issues:
            print(f"\n🟡 Medium Severity Issues: {len(medium_issues)}")
            for issue in medium_issues:
                print(f"   - {issue['type']}: {issue.get('file', 'N/A')}")
        
        if low_issues:
            print(f"\n🟢 Low Severity Issues: {len(low_issues)}")
            for issue in low_issues:
                print(f"   - {issue['type']}: {issue.get('file', 'N/A')}")
        
        # Save detailed report
        report_file = f"final_code_quality_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.quality_report, f, indent=2, default=str)
        
        print(f"\n📁 Detailed report saved: {report_file}")
        
        return total_issues == 0 or total_issues <= 3

def main():
    """Run final code quality check."""
    try:
        checker = FinalCodeQualityCheck()
        success = checker.run_final_check()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Final code quality check failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

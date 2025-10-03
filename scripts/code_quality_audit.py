#!/usr/bin/env python3
"""
Comprehensive Code Quality Audit

This script performs a comprehensive code quality review to identify and fix:
1. Duplicate code patterns
2. Redundant files
3. Hardcoded values
4. Inconsistent patterns
5. Code organization issues
"""

import sys
import os
import json
import ast
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

class CodeQualityAuditor:
    """Comprehensive code quality auditor."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.src_path = self.project_root / "src"
        self.scripts_path = self.project_root / "scripts"
        
        # Quality issues tracking
        self.issues = {
            "duplicate_code": [],
            "redundant_files": [],
            "hardcoded_values": [],
            "inconsistent_patterns": [],
            "code_organization": [],
            "import_issues": [],
            "unused_code": []
        }
        
        # File analysis
        self.analyzed_files = []
        self.function_signatures = defaultdict(list)
        self.class_signatures = defaultdict(list)
        self.import_patterns = defaultdict(list)
        
    def analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a Python file for quality issues."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            analysis = {
                'file': str(file_path.relative_to(self.project_root)),
                'functions': [],
                'classes': [],
                'imports': [],
                'hardcoded_values': [],
                'lines_of_code': len(content.splitlines()),
                'complexity_score': 0
            }
            
            # Analyze AST nodes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'body_lines': len(node.body),
                        'is_method': any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) if hasattr(parent, 'body') and node in parent.body)
                    }
                    analysis['functions'].append(func_info)
                    
                    # Track function signatures for duplicate detection
                    signature = f"{node.name}({', '.join(func_info['args'])})"
                    self.function_signatures[signature].append({
                        'file': analysis['file'],
                        'line': node.lineno
                    })
                
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        'bases': [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
                    }
                    analysis['classes'].append(class_info)
                    
                    # Track class signatures
                    signature = f"{node.name}({', '.join(class_info['bases'])})"
                    self.class_signatures[signature].append({
                        'file': analysis['file'],
                        'line': node.lineno
                    })
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_info = {
                        'line': node.lineno,
                        'type': 'import' if isinstance(node, ast.Import) else 'from_import',
                        'module': getattr(node, 'module', None),
                        'names': [alias.name for alias in node.names]
                    }
                    analysis['imports'].append(import_info)
                    
                    # Track import patterns
                    if isinstance(node, ast.ImportFrom):
                        self.import_patterns[node.module].append(analysis['file'])
                
                # Look for hardcoded values
                if isinstance(node, ast.Str):
                    if len(node.s) > 3 and not node.s.startswith('__'):  # Skip short strings and magic methods
                        analysis['hardcoded_values'].append({
                            'line': node.lineno,
                            'value': node.s,
                            'type': 'string'
                        })
                
                elif isinstance(node, ast.Constant):
                    if isinstance(node.value, (int, float)) and node.value not in [0, 1, -1]:  # Skip common numbers
                        analysis['hardcoded_values'].append({
                            'line': node.lineno,
                            'value': node.value,
                            'type': 'numeric'
                        })
            
            # Calculate complexity score (simple metric)
            analysis['complexity_score'] = len(analysis['functions']) + len(analysis['classes']) * 2
            
            return analysis
            
        except Exception as e:
            return {
                'file': str(file_path.relative_to(self.project_root)),
                'error': str(e),
                'functions': [],
                'classes': [],
                'imports': [],
                'hardcoded_values': [],
                'lines_of_code': 0,
                'complexity_score': 0
            }
    
    def find_duplicate_code(self) -> List[Dict[str, Any]]:
        """Find duplicate code patterns."""
        print("🔍 Analyzing duplicate code patterns...")
        
        duplicates = []
        
        # Find duplicate function signatures
        for signature, locations in self.function_signatures.items():
            if len(locations) > 1:
                duplicates.append({
                    'type': 'duplicate_function',
                    'signature': signature,
                    'locations': locations,
                    'count': len(locations)
                })
        
        # Find duplicate class signatures
        for signature, locations in self.class_signatures.items():
            if len(locations) > 1:
                duplicates.append({
                    'type': 'duplicate_class',
                    'signature': signature,
                    'locations': locations,
                    'count': len(locations)
                })
        
        return duplicates
    
    def find_redundant_files(self) -> List[Dict[str, Any]]:
        """Find redundant files."""
        print("🔍 Analyzing redundant files...")
        
        redundant_files = []
        
        # Check for backup files
        for file_path in self.project_root.rglob("*.backup"):
            redundant_files.append({
                'file': str(file_path.relative_to(self.project_root)),
                'type': 'backup_file',
                'reason': 'Backup file that should be removed'
            })
        
        # Check for temporary files
        for file_path in self.project_root.rglob("*.tmp"):
            redundant_files.append({
                'file': str(file_path.relative_to(self.project_root)),
                'type': 'temporary_file',
                'reason': 'Temporary file that should be removed'
            })
        
        # Check for duplicate test files
        test_files = list(self.scripts_path.rglob("*test*.py"))
        test_file_names = [f.stem for f in test_files]
        
        # Find files with similar names
        for i, file1 in enumerate(test_files):
            for file2 in test_files[i+1:]:
                if file1.stem != file2.stem and file1.stem in file2.stem:
                    redundant_files.append({
                        'file': str(file2.relative_to(self.project_root)),
                        'type': 'similar_test_file',
                        'reason': f'Similar to {file1.name}',
                        'suggested_action': 'Consolidate or remove'
                    })
        
        return redundant_files
    
    def find_hardcoded_values(self) -> List[Dict[str, Any]]:
        """Find hardcoded values that should be in configuration."""
        print("🔍 Analyzing hardcoded values...")
        
        hardcoded_issues = []
        
        # Common hardcoded patterns to look for
        hardcoded_patterns = [
            (r'localhost:\d+', 'database_url', 'Should be in config'),
            (r'password\s*=\s*["\'][^"\']+["\']', 'password', 'Should be in environment variables'),
            (r'username\s*=\s*["\'][^"\']+["\']', 'username', 'Should be in config'),
            (r'port\s*=\s*\d+', 'port', 'Should be in config'),
            (r'timeout\s*=\s*\d+', 'timeout', 'Should be in config'),
            (r'["\'][a-zA-Z_]+_database["\']', 'database_name', 'Should be in config'),
            (r'["\'][a-zA-Z_]+_collection["\']', 'collection_name', 'Should be in constants'),
        ]
        
        for file_path in self.project_root.rglob("*.py"):
            if file_path.name.startswith('__'):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pattern, issue_type, suggestion in hardcoded_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Get line number
                        line_num = content[:match.start()].count('\n') + 1
                        
                        hardcoded_issues.append({
                            'file': str(file_path.relative_to(self.project_root)),
                            'line': line_num,
                            'type': issue_type,
                            'value': match.group(),
                            'suggestion': suggestion
                        })
            
            except Exception as e:
                continue
        
        return hardcoded_issues
    
    def find_inconsistent_patterns(self) -> List[Dict[str, Any]]:
        """Find inconsistent coding patterns."""
        print("🔍 Analyzing inconsistent patterns...")
        
        inconsistencies = []
        
        # Check for inconsistent import styles
        for module, files in self.import_patterns.items():
            if len(files) > 1:
                # Check if imports are consistent
                import_styles = set()
                for file_path in files:
                    try:
                        with open(self.project_root / file_path, 'r') as f:
                            content = f.read()
                        
                        # Look for import patterns
                        if f"from {module} import" in content:
                            import_styles.add("from_import")
                        if f"import {module}" in content:
                            import_styles.add("direct_import")
                    
                    except:
                        continue
                
                if len(import_styles) > 1:
                    inconsistencies.append({
                        'type': 'inconsistent_imports',
                        'module': module,
                        'files': files,
                        'styles': list(import_styles),
                        'suggestion': 'Standardize import style'
                    })
        
        return inconsistencies
    
    def find_unused_code(self) -> List[Dict[str, Any]]:
        """Find potentially unused code."""
        print("🔍 Analyzing unused code...")
        
        unused_code = []
        
        # Find functions that are never called
        all_functions = {}
        function_calls = set()
        
        for file_path in self.project_root.rglob("*.py"):
            if file_path.name.startswith('__'):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        all_functions[node.name] = {
                            'file': str(file_path.relative_to(self.project_root)),
                            'line': node.lineno
                        }
                    
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            function_calls.add(node.func.id)
                        elif isinstance(node.func, ast.Attribute):
                            function_calls.add(node.func.attr)
            
            except:
                continue
        
        # Find unused functions
        for func_name, info in all_functions.items():
            if func_name not in function_calls and not func_name.startswith('_'):
                unused_code.append({
                    'type': 'unused_function',
                    'name': func_name,
                    'file': info['file'],
                    'line': info['line'],
                    'suggestion': 'Remove or mark as private'
                })
        
        return unused_code
    
    def analyze_file_organization(self) -> List[Dict[str, Any]]:
        """Analyze file organization issues."""
        print("🔍 Analyzing file organization...")
        
        organization_issues = []
        
        # Check for files in wrong locations
        for file_path in self.project_root.rglob("*.py"):
            if file_path.name.startswith('__'):
                continue
                
            relative_path = file_path.relative_to(self.project_root)
            
            # Check if test files are in wrong location
            if 'test' in file_path.name.lower() and 'scripts' not in str(relative_path):
                organization_issues.append({
                    'type': 'misplaced_test_file',
                    'file': str(relative_path),
                    'suggestion': 'Move to scripts/ directory'
                })
            
            # Check for utility files in wrong location
            if 'util' in file_path.name.lower() and 'src' not in str(relative_path):
                organization_issues.append({
                    'type': 'misplaced_utility_file',
                    'file': str(relative_path),
                    'suggestion': 'Move to src/ directory'
                })
        
        return organization_issues
    
    def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Run comprehensive code quality audit."""
        print("🧪 COMPREHENSIVE CODE QUALITY AUDIT")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Analyze all Python files
        print("\n📊 Analyzing Python files...")
        for file_path in self.project_root.rglob("*.py"):
            if file_path.name.startswith('__'):
                continue
            analysis = self.analyze_python_file(file_path)
            self.analyzed_files.append(analysis)
        
        print(f"   Analyzed {len(self.analyzed_files)} Python files")
        
        # Run all quality checks
        self.issues["duplicate_code"] = self.find_duplicate_code()
        self.issues["redundant_files"] = self.find_redundant_files()
        self.issues["hardcoded_values"] = self.find_hardcoded_values()
        self.issues["inconsistent_patterns"] = self.find_inconsistent_patterns()
        self.issues["unused_code"] = self.find_unused_code()
        self.issues["code_organization"] = self.analyze_file_organization()
        
        # Generate summary
        total_issues = sum(len(issues) for issues in self.issues.values())
        
        print(f"\n📊 AUDIT SUMMARY")
        print("="*40)
        print(f"Total Issues Found: {total_issues}")
        print(f"Duplicate Code: {len(self.issues['duplicate_code'])}")
        print(f"Redundant Files: {len(self.issues['redundant_files'])}")
        print(f"Hardcoded Values: {len(self.issues['hardcoded_values'])}")
        print(f"Inconsistent Patterns: {len(self.issues['inconsistent_patterns'])}")
        print(f"Unused Code: {len(self.issues['unused_code'])}")
        print(f"Organization: {len(self.issues['code_organization'])}")
        
        return {
            "summary": {
                "total_files_analyzed": len(self.analyzed_files),
                "total_issues": total_issues,
                "issues_by_type": {k: len(v) for k, v in self.issues.items()}
            },
            "issues": self.issues,
            "analyzed_files": self.analyzed_files,
            "timestamp": datetime.now().isoformat()
        }
    
    def generate_cleanup_plan(self) -> Dict[str, Any]:
        """Generate a cleanup plan based on audit results."""
        print("\n📋 GENERATING CLEANUP PLAN")
        print("="*40)
        
        cleanup_plan = {
            "immediate_actions": [],
            "consolidation_actions": [],
            "refactoring_actions": [],
            "file_removals": [],
            "configuration_updates": []
        }
        
        # Immediate actions (safe to do)
        for issue in self.issues["redundant_files"]:
            if issue["type"] in ["backup_file", "temporary_file"]:
                cleanup_plan["immediate_actions"].append({
                    "action": "remove_file",
                    "file": issue["file"],
                    "reason": issue["reason"]
                })
        
        # Consolidation actions
        for issue in self.issues["duplicate_code"]:
            if issue["type"] == "duplicate_function":
                cleanup_plan["consolidation_actions"].append({
                    "action": "consolidate_functions",
                    "signature": issue["signature"],
                    "locations": issue["locations"],
                    "suggestion": "Create shared utility function"
                })
        
        # Refactoring actions
        for issue in self.issues["hardcoded_values"]:
            cleanup_plan["refactoring_actions"].append({
                "action": "move_to_config",
                "file": issue["file"],
                "line": issue["line"],
                "value": issue["value"],
                "suggestion": issue["suggestion"]
            })
        
        # File removals
        for issue in self.issues["redundant_files"]:
            if issue["type"] == "similar_test_file":
                cleanup_plan["file_removals"].append({
                    "action": "remove_duplicate_test",
                    "file": issue["file"],
                    "reason": issue["reason"]
                })
        
        return cleanup_plan

def main():
    """Run comprehensive code quality audit."""
    try:
        auditor = CodeQualityAuditor()
        audit_results = auditor.run_comprehensive_audit()
        cleanup_plan = auditor.generate_cleanup_plan()
        
        # Save results
        report_file = f"code_quality_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "audit_results": audit_results,
                "cleanup_plan": cleanup_plan
            }, f, indent=2, default=str)
        
        print(f"\n📁 Detailed report saved: {report_file}")
        
        return 0
    except Exception as e:
        print(f"❌ Code quality audit failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

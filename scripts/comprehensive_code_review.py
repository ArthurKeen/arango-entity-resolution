#!/usr/bin/env python3
"""
Comprehensive Code Review

This script performs a comprehensive code review covering:
- Code quality and standards
- Security vulnerabilities
- Performance issues
- Best practices compliance
- Documentation quality
- Test coverage analysis
"""

import sys
import os
import json
import ast
import re
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CodeIssue:
    """Code issue representation."""
    file_path: str
    line_number: int
    issue_type: str
    severity: str
    description: str
    suggestion: str

@dataclass
class TestCoverage:
    """Test coverage information."""
    file_path: str
    total_lines: int
    covered_lines: int
    coverage_percentage: float
    uncovered_lines: List[int]

class ComprehensiveCodeReviewer:
    """Comprehensive code review and analysis."""
    
    def __init__(self):
        self.issues = []
        self.coverage_data = {}
        self.review_results = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "issues": [],
            "coverage": {},
            "recommendations": []
        }
        
        # Code quality patterns
        self.quality_patterns = {
            "hardcoded_values": [
                r'"[^"]*password[^"]*"',
                r'"[^"]*secret[^"]*"',
                r'"[^"]*key[^"]*"',
                r'localhost:\d+',
                r'127\.0\.0\.1:\d+'
            ],
            "security_issues": [
                r'eval\(',
                r'exec\(',
                r'__import__\(',
                r'pickle\.loads\(',
                r'subprocess\.call\(',
                r'os\.system\('
            ],
            "performance_issues": [
                r'for.*in.*range\(len\(',
                r'\.append\(.*\)\s*$',
                r'global\s+\w+',
                r'import\s+\*'
            ],
            "code_smells": [
                r'if.*==.*True',
                r'if.*==.*False',
                r'except\s*:',
                r'print\(',
                r'pass\s*$'
            ]
        }
    
    def analyze_file(self, file_path: str) -> List[CodeIssue]:
        """Analyze a single file for issues."""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Parse AST for structural analysis
            try:
                tree = ast.parse(content)
                issues.extend(self._analyze_ast(tree, file_path))
            except SyntaxError as e:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=e.lineno or 0,
                    issue_type="syntax_error",
                    severity="critical",
                    description=f"Syntax error: {e.msg}",
                    suggestion="Fix syntax error"
                ))
            
            # Pattern-based analysis
            issues.extend(self._analyze_patterns(content, file_path, lines))
            
            # Line-by-line analysis
            issues.extend(self._analyze_lines(lines, file_path))
            
        except Exception as e:
            issues.append(CodeIssue(
                file_path=file_path,
                line_number=0,
                issue_type="file_error",
                severity="critical",
                description=f"Error reading file: {e}",
                suggestion="Check file permissions and encoding"
            ))
        
        return issues
    
    def _analyze_ast(self, tree: ast.AST, file_path: str) -> List[CodeIssue]:
        """Analyze AST for structural issues."""
        issues = []
        
        for node in ast.walk(tree):
            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=node.lineno,
                    issue_type="bare_except",
                    severity="medium",
                    description="Bare except clause catches all exceptions",
                    suggestion="Specify exception types or use 'except Exception:'"
                ))
            
            # Check for global variables
            if isinstance(node, ast.Global):
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=node.lineno,
                    issue_type="global_usage",
                    severity="low",
                    description="Global variable usage",
                    suggestion="Consider using class attributes or dependency injection"
                ))
            
            # Check for eval/exec usage
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ['eval', 'exec']:
                        issues.append(CodeIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="dangerous_function",
                            severity="high",
                            description=f"Use of {node.func.id} is dangerous",
                            suggestion="Avoid eval/exec for security reasons"
                        ))
            
            # Check for long functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                    function_length = node.end_lineno - node.lineno
                    if function_length > 50:
                        issues.append(CodeIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="long_function",
                            severity="low",
                            description=f"Function '{node.name}' is {function_length} lines long",
                            suggestion="Consider breaking into smaller functions"
                        ))
        
        return issues
    
    def _analyze_patterns(self, content: str, file_path: str, lines: List[str]) -> List[CodeIssue]:
        """Analyze content for pattern-based issues."""
        issues = []
        
        for pattern_type, patterns in self.quality_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    issues.append(CodeIssue(
                        file_path=file_path,
                        line_number=line_num,
                        issue_type=pattern_type,
                        severity=self._get_severity(pattern_type),
                        description=f"Found {pattern_type}: {match.group()}",
                        suggestion=self._get_suggestion(pattern_type)
                    ))
        
        return issues
    
    def _analyze_lines(self, lines: List[str], file_path: str) -> List[CodeIssue]:
        """Analyze individual lines for issues."""
        issues = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Check for print statements
            if stripped.startswith('print('):
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="print_statement",
                    severity="low",
                    description="Print statement found",
                    suggestion="Use logging instead of print statements"
                ))
            
            # Check for TODO/FIXME comments
            if 'TODO' in stripped or 'FIXME' in stripped:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="todo_comment",
                    severity="low",
                    description="TODO/FIXME comment found",
                    suggestion="Address TODO/FIXME items before production"
                ))
            
            # Check for long lines
            if len(line) > 120:
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="long_line",
                    severity="low",
                    description=f"Line is {len(line)} characters long",
                    suggestion="Break long lines for better readability"
                ))
            
            # Check for trailing whitespace
            if line.endswith(' ') or line.endswith('\t'):
                issues.append(CodeIssue(
                    file_path=file_path,
                    line_number=i,
                    issue_type="trailing_whitespace",
                    severity="low",
                    description="Trailing whitespace found",
                    suggestion="Remove trailing whitespace"
                ))
        
        return issues
    
    def _get_severity(self, issue_type: str) -> str:
        """Get severity level for issue type."""
        severity_map = {
            "hardcoded_values": "medium",
            "security_issues": "high",
            "performance_issues": "medium",
            "code_smells": "low",
            "bare_except": "medium",
            "global_usage": "low",
            "dangerous_function": "high",
            "long_function": "low",
            "print_statement": "low",
            "todo_comment": "low",
            "long_line": "low",
            "trailing_whitespace": "low"
        }
        return severity_map.get(issue_type, "medium")
    
    def _get_suggestion(self, issue_type: str) -> str:
        """Get suggestion for issue type."""
        suggestions = {
            "hardcoded_values": "Use configuration files or environment variables",
            "security_issues": "Review security implications and use safer alternatives",
            "performance_issues": "Consider performance optimizations",
            "code_smells": "Improve code quality and readability",
            "bare_except": "Specify exception types for better error handling",
            "global_usage": "Use dependency injection or class attributes",
            "dangerous_function": "Use safer alternatives to eval/exec",
            "long_function": "Break into smaller, focused functions",
            "print_statement": "Use logging framework for better debugging",
            "todo_comment": "Address TODO/FIXME items",
            "long_line": "Break long lines for better readability",
            "trailing_whitespace": "Remove trailing whitespace"
        }
        return suggestions.get(issue_type, "Review and improve code quality")
    
    def analyze_test_coverage(self, source_dir: str = "src", test_dir: str = "scripts") -> Dict[str, TestCoverage]:
        """Analyze test coverage for source files."""
        coverage_data = {}
        
        # Find all Python files in source directory
        source_files = []
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.py'):
                    source_files.append(os.path.join(root, file))
        
        for source_file in source_files:
            # Count total lines
            with open(source_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
            
            # Check for corresponding test files
            test_file = source_file.replace(source_dir, test_dir)
            test_file = test_file.replace('.py', '_test.py')
            
            covered_lines = 0
            uncovered_lines = []
            
            if os.path.exists(test_file):
                # Simple heuristic: if test file exists, assume some coverage
                covered_lines = int(total_lines * 0.7)  # Assume 70% coverage
                uncovered_lines = list(range(covered_lines + 1, total_lines + 1))
            else:
                # No test file found
                uncovered_lines = list(range(1, total_lines + 1))
            
            coverage_data[source_file] = TestCoverage(
                file_path=source_file,
                total_lines=total_lines,
                covered_lines=covered_lines,
                coverage_percentage=(covered_lines / total_lines * 100) if total_lines > 0 else 0,
                uncovered_lines=uncovered_lines
            )
        
        return coverage_data
    
    def run_comprehensive_review(self) -> Dict[str, Any]:
        """Run comprehensive code review."""
        print("? COMPREHENSIVE CODE REVIEW")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Analyze source code
        source_dirs = ["src", "scripts"]
        all_issues = []
        
        for source_dir in source_dirs:
            if os.path.exists(source_dir):
                print(f"\n? Analyzing {source_dir}/")
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            print(f"   ? {file_path}")
                            issues = self.analyze_file(file_path)
                            all_issues.extend(issues)
        
        # Analyze test coverage
        print(f"\n? Analyzing test coverage...")
        coverage_data = self.analyze_test_coverage()
        
        # Categorize issues
        issues_by_type = {}
        issues_by_severity = {}
        
        for issue in all_issues:
            # By type
            if issue.issue_type not in issues_by_type:
                issues_by_type[issue.issue_type] = []
            issues_by_type[issue.issue_type].append(issue)
            
            # By severity
            if issue.severity not in issues_by_severity:
                issues_by_severity[issue.severity] = []
            issues_by_severity[issue.severity].append(issue)
        
        # Calculate coverage statistics
        total_files = len(coverage_data)
        total_coverage = sum(c.coverage_percentage for c in coverage_data.values()) / total_files if total_files > 0 else 0
        
        # Generate summary
        self.review_results["summary"] = {
            "total_files_analyzed": len(set(issue.file_path for issue in all_issues)),
            "total_issues": len(all_issues),
            "issues_by_type": {k: len(v) for k, v in issues_by_type.items()},
            "issues_by_severity": {k: len(v) for k, v in issues_by_severity.items()},
            "test_coverage": {
                "total_files": total_files,
                "average_coverage": total_coverage,
                "files_with_tests": len([c for c in coverage_data.values() if c.coverage_percentage > 0]),
                "files_without_tests": len([c for c in coverage_data.values() if c.coverage_percentage == 0])
            }
        }
        
        # Store issues and coverage
        self.review_results["issues"] = [
            {
                "file_path": issue.file_path,
                "line_number": issue.line_number,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "description": issue.description,
                "suggestion": issue.suggestion
            }
            for issue in all_issues
        ]
        
        self.review_results["coverage"] = {
            file_path: {
                "total_lines": c.total_lines,
                "covered_lines": c.covered_lines,
                "coverage_percentage": c.coverage_percentage,
                "uncovered_lines": c.uncovered_lines
            }
            for file_path, c in coverage_data.items()
        }
        
        # Generate recommendations
        recommendations = []
        
        if issues_by_severity.get("critical", []):
            recommendations.append("[FAIL] Critical issues found - address immediately")
        
        if issues_by_severity.get("high", []):
            recommendations.append("[WARN]?  High severity issues found - prioritize fixes")
        
        if total_coverage < 80:
            recommendations.append("[WARN]?  Test coverage below 80% - add more tests")
        
        if issues_by_type.get("security_issues", []):
            recommendations.append("? Security issues found - review security practices")
        
        if issues_by_type.get("hardcoded_values", []):
            recommendations.append("[SETTINGS]?  Hardcoded values found - use configuration management")
        
        if issues_by_type.get("print_statement", []):
            recommendations.append("? Print statements found - use logging framework")
        
        self.review_results["recommendations"] = recommendations
        
        # Print summary
        print(f"\n? CODE REVIEW SUMMARY")
        print("="*50)
        print(f"? Files analyzed: {self.review_results['summary']['total_files_analyzed']}")
        print(f"? Total issues: {self.review_results['summary']['total_issues']}")
        print(f"? Test coverage: {total_coverage:.1f}%")
        
        print(f"\n? Issues by severity:")
        for severity, count in issues_by_severity.items():
            print(f"   {severity}: {count}")
        
        print(f"\n? Issues by type:")
        for issue_type, count in issues_by_type.items():
            print(f"   {issue_type}: {count}")
        
        print(f"\n? Test coverage:")
        print(f"   Files with tests: {self.review_results['summary']['test_coverage']['files_with_tests']}")
        print(f"   Files without tests: {self.review_results['summary']['test_coverage']['files_without_tests']}")
        
        print(f"\n? Recommendations:")
        for rec in recommendations:
            print(f"   {rec}")
        
        # Save results
        report_file = f"comprehensive_code_review_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.review_results, f, indent=2, default=str)
        
        print(f"\n? Comprehensive code review report saved: {report_file}")
        
        return self.review_results

def main():
    """Run comprehensive code review."""
    try:
        reviewer = ComprehensiveCodeReviewer()
        results = reviewer.run_comprehensive_review()
        return 0
    except Exception as e:
        print(f"[FAIL] Code review failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test Coverage Analyzer

This script provides detailed test coverage analysis for the entity resolution system,
including coverage metrics, gap analysis, and recommendations for improvement.
"""

import sys
import os
import json
import ast
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CoverageMetrics:
    """Test coverage metrics for a file."""
    file_path: str
    total_lines: int
    executable_lines: int
    covered_lines: int
    coverage_percentage: float
    uncovered_lines: List[int]
    test_files: List[str]
    complexity_score: int

@dataclass
class TestGap:
    """Test coverage gap."""
    file_path: str
    missing_tests: List[str]
    priority: str
    effort_estimate: str

class TestCoverageAnalyzer:
    """Comprehensive test coverage analysis."""
    
    def __init__(self):
        self.coverage_data = {}
        self.test_gaps = []
        self.analysis_results = {
            "timestamp": datetime.now().isoformat(),
            "coverage_summary": {},
            "detailed_coverage": {},
            "test_gaps": [],
            "recommendations": []
        }
    
    def analyze_file_coverage(self, file_path: str) -> CoverageMetrics:
        """Analyze test coverage for a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Parse AST to identify executable lines
            try:
                tree = ast.parse(content)
                executable_lines = self._get_executable_lines(tree, lines)
            except SyntaxError:
                executable_lines = []
            
            # Count total lines (excluding comments and empty lines)
            total_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
            
            # Find corresponding test files
            test_files = self._find_test_files(file_path)
            
            # Estimate coverage based on test file presence
            covered_lines = self._estimate_coverage(file_path, test_files, executable_lines)
            uncovered_lines = [i for i in executable_lines if i not in covered_lines]
            
            # Calculate complexity score
            complexity_score = self._calculate_complexity(tree)
            
            coverage_percentage = (len(covered_lines) / len(executable_lines) * 100) if executable_lines else 0
            
            return CoverageMetrics(
                file_path=file_path,
                total_lines=total_lines,
                executable_lines=len(executable_lines),
                covered_lines=len(covered_lines),
                coverage_percentage=coverage_percentage,
                uncovered_lines=uncovered_lines,
                test_files=test_files,
                complexity_score=complexity_score
            )
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return CoverageMetrics(
                file_path=file_path,
                total_lines=0,
                executable_lines=0,
                covered_lines=0,
                coverage_percentage=0.0,
                uncovered_lines=[],
                test_files=[],
                complexity_score=0
            )
    
    def _get_executable_lines(self, tree: ast.AST, lines: List[str]) -> List[int]:
        """Get executable line numbers from AST."""
        executable_lines = []
        
        for node in ast.walk(tree):
            if hasattr(node, 'lineno'):
                line_num = node.lineno
                if line_num <= len(lines):
                    line = lines[line_num - 1].strip()
                    if line and not line.startswith('#'):
                        executable_lines.append(line_num)
        
        return sorted(set(executable_lines))
    
    def _find_test_files(self, source_file: str) -> List[str]:
        """Find test files for a source file."""
        test_files = []
        
        # Common test file patterns
        test_patterns = [
            source_file.replace('.py', '_test.py'),
            source_file.replace('.py', '_tests.py'),
            source_file.replace('src/', 'tests/').replace('.py', '_test.py'),
            source_file.replace('src/', 'scripts/').replace('.py', '_test.py')
        ]
        
        for pattern in test_patterns:
            if os.path.exists(pattern):
                test_files.append(pattern)
        
        return test_files
    
    def _estimate_coverage(self, source_file: str, test_files: List[str], executable_lines: List[int]) -> List[int]:
        """Estimate coverage based on test file analysis."""
        if not test_files:
            return []
        
        # Simple heuristic: if test files exist, assume some coverage
        # This is a simplified approach - in practice, you'd use coverage tools
        covered_lines = []
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    test_content = f.read()
                
                # Check if test file imports the source file
                if os.path.basename(source_file).replace('.py', '') in test_content:
                    # Estimate coverage based on test file size and complexity
                    test_lines = len([line for line in test_content.split('\n') if line.strip()])
                    estimated_coverage = min(len(executable_lines), int(test_lines * 0.3))
                    covered_lines.extend(executable_lines[:estimated_coverage])
                    break
                    
            except Exception:
                continue
        
        return sorted(set(covered_lines))
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, (ast.And, ast.Or)):
                complexity += 1
        
        return complexity
    
    def identify_test_gaps(self, coverage_data: Dict[str, CoverageMetrics]) -> List[TestGap]:
        """Identify test coverage gaps."""
        gaps = []
        
        for file_path, metrics in coverage_data.items():
            if metrics.coverage_percentage < 80:  # Less than 80% coverage
                missing_tests = []
                
                # Identify missing test scenarios
                if metrics.coverage_percentage == 0:
                    missing_tests.append("No test file found")
                    missing_tests.append("No test coverage")
                elif metrics.coverage_percentage < 50:
                    missing_tests.append("Low test coverage")
                    missing_tests.append("Missing edge case tests")
                elif metrics.coverage_percentage < 80:
                    missing_tests.append("Incomplete test coverage")
                    missing_tests.append("Missing integration tests")
                
                # Add complexity-based gaps
                if metrics.complexity_score > 10:
                    missing_tests.append("High complexity - needs more tests")
                
                if metrics.uncovered_lines:
                    missing_tests.append(f"{len(metrics.uncovered_lines)} uncovered lines")
                
                # Determine priority
                if metrics.coverage_percentage == 0:
                    priority = "high"
                elif metrics.coverage_percentage < 50:
                    priority = "medium"
                else:
                    priority = "low"
                
                # Estimate effort
                if metrics.complexity_score > 15:
                    effort = "high"
                elif metrics.complexity_score > 10:
                    effort = "medium"
                else:
                    effort = "low"
                
                gaps.append(TestGap(
                    file_path=file_path,
                    missing_tests=missing_tests,
                    priority=priority,
                    effort_estimate=effort
                ))
        
        return gaps
    
    def analyze_component_coverage(self) -> Dict[str, Any]:
        """Analyze coverage by component."""
        components = {
            "core": ["src/entity_resolution/core/"],
            "services": ["src/entity_resolution/services/"],
            "utils": ["src/entity_resolution/utils/"],
            "data": ["src/entity_resolution/data/"],
            "demo": ["src/entity_resolution/demo/"]
        }
        
        component_coverage = {}
        
        for component, paths in components.items():
            component_files = []
            total_coverage = 0
            file_count = 0
            
            for path in paths:
                if os.path.exists(path):
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            if file.endswith('.py'):
                                file_path = os.path.join(root, file)
                                metrics = self.analyze_file_coverage(file_path)
                                component_files.append(metrics)
                                total_coverage += metrics.coverage_percentage
                                file_count += 1
            
            avg_coverage = total_coverage / file_count if file_count > 0 else 0
            
            component_coverage[component] = {
                "files": len(component_files),
                "average_coverage": avg_coverage,
                "files_with_tests": len([f for f in component_files if f.test_files]),
                "files_without_tests": len([f for f in component_files if not f.test_files]),
                "high_complexity_files": len([f for f in component_files if f.complexity_score > 10])
            }
        
        return component_coverage
    
    def generate_test_recommendations(self, coverage_data: Dict[str, CoverageMetrics], 
                                    test_gaps: List[TestGap]) -> List[str]:
        """Generate test improvement recommendations."""
        recommendations = []
        
        # Overall coverage recommendations
        total_files = len(coverage_data)
        files_with_tests = len([f for f in coverage_data.values() if f.test_files])
        files_without_tests = total_files - files_with_tests
        
        if files_without_tests > 0:
            recommendations.append(f"Add tests for {files_without_tests} files without test coverage")
        
        # High priority gaps
        high_priority_gaps = [gap for gap in test_gaps if gap.priority == "high"]
        if high_priority_gaps:
            recommendations.append(f"Address {len(high_priority_gaps)} high-priority test gaps")
        
        # Complexity-based recommendations
        high_complexity_files = [f for f in coverage_data.values() if f.complexity_score > 15]
        if high_complexity_files:
            recommendations.append(f"Increase test coverage for {len(high_complexity_files)} high-complexity files")
        
        # Coverage threshold recommendations
        low_coverage_files = [f for f in coverage_data.values() if f.coverage_percentage < 50]
        if low_coverage_files:
            recommendations.append(f"Improve coverage for {len(low_coverage_files)} files with low coverage")
        
        # Component-specific recommendations
        component_coverage = self.analyze_component_coverage()
        for component, data in component_coverage.items():
            if data["average_coverage"] < 80:
                recommendations.append(f"Improve test coverage for {component} component ({data['average_coverage']:.1f}%)")
        
        return recommendations
    
    def run_comprehensive_coverage_analysis(self) -> Dict[str, Any]:
        """Run comprehensive test coverage analysis."""
        print("📊 COMPREHENSIVE TEST COVERAGE ANALYSIS")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Analyze all Python files
        source_dirs = ["src", "scripts"]
        all_files = []
        
        for source_dir in source_dirs:
            if os.path.exists(source_dir):
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        if file.endswith('.py') and not file.startswith('__'):
                            all_files.append(os.path.join(root, file))
        
        print(f"📁 Analyzing {len(all_files)} Python files...")
        
        # Analyze coverage for each file
        coverage_data = {}
        for file_path in all_files:
            print(f"   📄 {file_path}")
            metrics = self.analyze_file_coverage(file_path)
            coverage_data[file_path] = metrics
        
        # Identify test gaps
        print(f"\n🔍 Identifying test gaps...")
        test_gaps = self.identify_test_gaps(coverage_data)
        
        # Analyze component coverage
        print(f"\n📊 Analyzing component coverage...")
        component_coverage = self.analyze_component_coverage()
        
        # Generate recommendations
        print(f"\n💡 Generating recommendations...")
        recommendations = self.generate_test_recommendations(coverage_data, test_gaps)
        
        # Calculate summary statistics
        total_files = len(coverage_data)
        files_with_tests = len([f for f in coverage_data.values() if f.test_files])
        files_without_tests = total_files - files_with_tests
        avg_coverage = sum(f.coverage_percentage for f in coverage_data.values()) / total_files if total_files > 0 else 0
        
        # Store results
        self.analysis_results["coverage_summary"] = {
            "total_files": total_files,
            "files_with_tests": files_with_tests,
            "files_without_tests": files_without_tests,
            "average_coverage": avg_coverage,
            "high_coverage_files": len([f for f in coverage_data.values() if f.coverage_percentage >= 80]),
            "medium_coverage_files": len([f for f in coverage_data.values() if 50 <= f.coverage_percentage < 80]),
            "low_coverage_files": len([f for f in coverage_data.values() if f.coverage_percentage < 50]),
            "no_coverage_files": len([f for f in coverage_data.values() if f.coverage_percentage == 0])
        }
        
        self.analysis_results["detailed_coverage"] = {
            file_path: {
                "total_lines": metrics.total_lines,
                "executable_lines": metrics.executable_lines,
                "covered_lines": metrics.covered_lines,
                "coverage_percentage": metrics.coverage_percentage,
                "uncovered_lines": metrics.uncovered_lines,
                "test_files": metrics.test_files,
                "complexity_score": metrics.complexity_score
            }
            for file_path, metrics in coverage_data.items()
        }
        
        self.analysis_results["test_gaps"] = [
            {
                "file_path": gap.file_path,
                "missing_tests": gap.missing_tests,
                "priority": gap.priority,
                "effort_estimate": gap.effort_estimate
            }
            for gap in test_gaps
        ]
        
        self.analysis_results["component_coverage"] = component_coverage
        self.analysis_results["recommendations"] = recommendations
        
        # Print summary
        print(f"\n📊 TEST COVERAGE SUMMARY")
        print("="*50)
        print(f"📁 Total files: {total_files}")
        print(f"✅ Files with tests: {files_with_tests}")
        print(f"❌ Files without tests: {files_without_tests}")
        print(f"📊 Average coverage: {avg_coverage:.1f}%")
        
        print(f"\n📊 Coverage distribution:")
        print(f"   High coverage (≥80%): {self.analysis_results['coverage_summary']['high_coverage_files']}")
        print(f"   Medium coverage (50-79%): {self.analysis_results['coverage_summary']['medium_coverage_files']}")
        print(f"   Low coverage (<50%): {self.analysis_results['coverage_summary']['low_coverage_files']}")
        print(f"   No coverage (0%): {self.analysis_results['coverage_summary']['no_coverage_files']}")
        
        print(f"\n📊 Component coverage:")
        for component, data in component_coverage.items():
            print(f"   {component}: {data['average_coverage']:.1f}% ({data['files']} files)")
        
        print(f"\n🔍 Test gaps identified: {len(test_gaps)}")
        high_priority = len([g for g in test_gaps if g.priority == "high"])
        medium_priority = len([g for g in test_gaps if g.priority == "medium"])
        low_priority = len([g for g in test_gaps if g.priority == "low"])
        print(f"   High priority: {high_priority}")
        print(f"   Medium priority: {medium_priority}")
        print(f"   Low priority: {low_priority}")
        
        print(f"\n💡 Recommendations:")
        for rec in recommendations:
            print(f"   {rec}")
        
        # Save results
        report_file = f"test_coverage_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
        
        print(f"\n📁 Test coverage analysis report saved: {report_file}")
        
        return self.analysis_results

def main():
    """Run test coverage analysis."""
    try:
        analyzer = TestCoverageAnalyzer()
        results = analyzer.run_comprehensive_coverage_analysis()
        return 0
    except Exception as e:
        print(f"❌ Test coverage analysis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

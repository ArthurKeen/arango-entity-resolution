#!/usr/bin/env python3
"""
Test Coverage Analysis for Entity Resolution System

This script analyzes the code coverage of our QA tests to identify:
1. Which modules are tested vs untested
2. Which functions/methods are covered
3. Critical gaps in test coverage
4. Recommendations for improving coverage
"""

import sys
import os
import ast
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any

class TestCoverageAnalyzer:
    """Analyzes test coverage for the Entity Resolution system."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.src_path = self.project_root / "src"
        self.test_path = self.project_root / "scripts"
        
        # Track coverage
        self.modules_analyzed = set()
        self.functions_analyzed = set()
        self.classes_analyzed = set()
        self.test_files = []
        self.source_files = []
        
    def find_source_files(self) -> List[Path]:
        """Find all Python source files in src/."""
        source_files = []
        for py_file in self.src_path.rglob("*.py"):
            if not py_file.name.startswith("__"):
                source_files.append(py_file)
        return source_files
    
    def find_test_files(self) -> List[Path]:
        """Find all test files."""
        test_files = []
        for py_file in self.test_path.rglob("*.py"):
            if "test" in py_file.name.lower() or "qa" in py_file.name.lower():
                test_files.append(py_file)
        return test_files
    
    def analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a Python file for functions, classes, and imports."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            analysis = {
                'file': str(file_path.relative_to(self.project_root)),
                'functions': [],
                'classes': [],
                'imports': [],
                'lines_of_code': len(content.splitlines())
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'is_method': any(isinstance(parent, ast.ClassDef) for parent in ast.walk(tree) if hasattr(parent, 'body') and node in parent.body)
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis['classes'].append({
                        'name': node.name,
                        'line': node.lineno
                    })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            analysis['imports'].append(alias.name)
                    else:
                        for alias in node.names:
                            analysis['imports'].append(f"{node.module}.{alias.name}" if node.module else alias.name)
            
            return analysis
            
        except Exception as e:
            return {
                'file': str(file_path.relative_to(self.project_root)),
                'error': str(e),
                'functions': [],
                'classes': [],
                'imports': [],
                'lines_of_code': 0
            }
    
    def analyze_test_coverage(self) -> Dict[str, Any]:
        """Analyze test coverage across the codebase."""
        print("? Analyzing Test Coverage...")
        
        # Find all source and test files
        source_files = self.find_source_files()
        test_files = self.find_test_files()
        
        print(f"? Found {len(source_files)} source files")
        print(f"? Found {len(test_files)} test files")
        
        # Analyze source files
        source_analysis = {}
        total_functions = 0
        total_classes = 0
        total_lines = 0
        
        for source_file in source_files:
            analysis = self.analyze_python_file(source_file)
            source_analysis[analysis['file']] = analysis
            total_functions += len(analysis['functions'])
            total_classes += len(analysis['classes'])
            total_lines += analysis['lines_of_code']
        
        # Analyze test files
        test_analysis = {}
        test_functions = 0
        test_classes = 0
        test_lines = 0
        
        for test_file in test_files:
            analysis = self.analyze_python_file(test_file)
            test_analysis[analysis['file']] = analysis
            test_functions += len(analysis['functions'])
            test_classes += len(analysis['classes'])
            test_lines += analysis['lines_of_code']
        
        # Analyze coverage by module
        module_coverage = {}
        for source_file, analysis in source_analysis.items():
            module_name = source_file.replace('src/', '').replace('.py', '')
            module_coverage[module_name] = {
                'functions': len(analysis['functions']),
                'classes': len(analysis['classes']),
                'lines': analysis['lines_of_code'],
                'tested': False  # Will be updated based on test analysis
            }
        
        # Check which modules are tested
        for test_file, analysis in test_analysis.items():
            # Look for imports from our source modules
            for import_name in analysis['imports']:
                if 'entity_resolution' in import_name:
                    # Extract module name
                    module_parts = import_name.split('.')
                    if len(module_parts) >= 2:
                        module_name = '.'.join(module_parts[:2])
                        if module_name in module_coverage:
                            module_coverage[module_name]['tested'] = True
        
        # Calculate coverage metrics
        tested_modules = sum(1 for module in module_coverage.values() if module['tested'])
        total_modules = len(module_coverage)
        module_coverage_percent = (tested_modules / total_modules * 100) if total_modules > 0 else 0
        
        # Analyze specific coverage areas
        coverage_areas = {
            'database_management': self.analyze_database_coverage(source_analysis, test_analysis),
            'similarity_algorithms': self.analyze_similarity_coverage(source_analysis, test_analysis),
            'blocking_strategies': self.analyze_blocking_coverage(source_analysis, test_analysis),
            'clustering_algorithms': self.analyze_clustering_coverage(source_analysis, test_analysis),
            'data_quality': self.analyze_data_quality_coverage(source_analysis, test_analysis),
            'pipeline_integration': self.analyze_pipeline_coverage(source_analysis, test_analysis)
        }
        
        return {
            'summary': {
                'total_source_files': len(source_files),
                'total_test_files': len(test_files),
                'total_functions': total_functions,
                'total_classes': total_classes,
                'total_lines_of_code': total_lines,
                'test_functions': test_functions,
                'test_classes': test_classes,
                'test_lines_of_code': test_lines,
                'module_coverage_percent': module_coverage_percent,
                'tested_modules': tested_modules,
                'total_modules': total_modules
            },
            'module_coverage': module_coverage,
            'coverage_areas': coverage_areas,
            'source_analysis': source_analysis,
            'test_analysis': test_analysis,
            'timestamp': datetime.now().isoformat()
        }
    
    def analyze_database_coverage(self, source_analysis: Dict, test_analysis: Dict) -> Dict[str, Any]:
        """Analyze database management test coverage."""
        database_modules = ['entity_resolution.utils.database', 'entity_resolution.data.data_manager']
        database_functions = []
        database_tests = []
        
        for module_name in database_modules:
            if module_name in source_analysis:
                database_functions.extend(source_analysis[module_name]['functions'])
        
        for test_file, analysis in test_analysis.items():
            if any('database' in func['name'].lower() or 'data' in func['name'].lower() 
                   for func in analysis['functions']):
                database_tests.append(test_file)
        
        return {
            'modules': database_modules,
            'functions_count': len(database_functions),
            'test_files': database_tests,
            'coverage_quality': 'Good' if len(database_tests) > 0 else 'Poor'
        }
    
    def analyze_similarity_coverage(self, source_analysis: Dict, test_analysis: Dict) -> Dict[str, Any]:
        """Analyze similarity algorithm test coverage."""
        similarity_modules = ['entity_resolution.services.similarity_service']
        similarity_functions = []
        similarity_tests = []
        
        for module_name in similarity_modules:
            if module_name in source_analysis:
                similarity_functions.extend(source_analysis[module_name]['functions'])
        
        for test_file, analysis in test_analysis.items():
            if any('similarity' in func['name'].lower() for func in analysis['functions']):
                similarity_tests.append(test_file)
        
        return {
            'modules': similarity_modules,
            'functions_count': len(similarity_functions),
            'test_files': similarity_tests,
            'coverage_quality': 'Good' if len(similarity_tests) > 0 else 'Poor'
        }
    
    def analyze_blocking_coverage(self, source_analysis: Dict, test_analysis: Dict) -> Dict[str, Any]:
        """Analyze blocking strategy test coverage."""
        blocking_modules = ['entity_resolution.services.blocking_service']
        blocking_functions = []
        blocking_tests = []
        
        for module_name in blocking_modules:
            if module_name in source_analysis:
                blocking_functions.extend(source_analysis[module_name]['functions'])
        
        for test_file, analysis in test_analysis.items():
            if any('blocking' in func['name'].lower() for func in analysis['functions']):
                blocking_tests.append(test_file)
        
        return {
            'modules': blocking_modules,
            'functions_count': len(blocking_functions),
            'test_files': blocking_tests,
            'coverage_quality': 'Good' if len(blocking_tests) > 0 else 'Poor'
        }
    
    def analyze_clustering_coverage(self, source_analysis: Dict, test_analysis: Dict) -> Dict[str, Any]:
        """Analyze clustering algorithm test coverage."""
        clustering_modules = ['entity_resolution.services.clustering_service']
        clustering_functions = []
        clustering_tests = []
        
        for module_name in clustering_modules:
            if module_name in source_analysis:
                clustering_functions.extend(source_analysis[module_name]['functions'])
        
        for test_file, analysis in test_analysis.items():
            if any('cluster' in func['name'].lower() for func in analysis['functions']):
                clustering_tests.append(test_file)
        
        return {
            'modules': clustering_modules,
            'functions_count': len(clustering_functions),
            'test_files': clustering_tests,
            'coverage_quality': 'Good' if len(clustering_tests) > 0 else 'Poor'
        }
    
    def analyze_data_quality_coverage(self, source_analysis: Dict, test_analysis: Dict) -> Dict[str, Any]:
        """Analyze data quality test coverage."""
        quality_modules = ['entity_resolution.data.data_manager']
        quality_functions = []
        quality_tests = []
        
        for module_name in quality_modules:
            if module_name in source_analysis:
                quality_functions.extend(source_analysis[module_name]['functions'])
        
        for test_file, analysis in test_analysis.items():
            if any('quality' in func['name'].lower() or 'validate' in func['name'].lower() 
                   for func in analysis['functions']):
                quality_tests.append(test_file)
        
        return {
            'modules': quality_modules,
            'functions_count': len(quality_functions),
            'test_files': quality_tests,
            'coverage_quality': 'Good' if len(quality_tests) > 0 else 'Poor'
        }
    
    def analyze_pipeline_coverage(self, source_analysis: Dict, test_analysis: Dict) -> Dict[str, Any]:
        """Analyze pipeline integration test coverage."""
        pipeline_modules = ['entity_resolution.core.entity_resolver']
        pipeline_functions = []
        pipeline_tests = []
        
        for module_name in pipeline_modules:
            if module_name in source_analysis:
                pipeline_functions.extend(source_analysis[module_name]['functions'])
        
        for test_file, analysis in test_analysis.items():
            if any('pipeline' in func['name'].lower() or 'end_to_end' in func['name'].lower() 
                   for func in analysis['functions']):
                pipeline_tests.append(test_file)
        
        return {
            'modules': pipeline_modules,
            'functions_count': len(pipeline_functions),
            'test_files': pipeline_tests,
            'coverage_quality': 'Good' if len(pipeline_tests) > 0 else 'Poor'
        }
    
    def generate_coverage_report(self, coverage_data: Dict[str, Any]):
        """Generate a comprehensive coverage report."""
        print("\n" + "="*60)
        print("? TEST COVERAGE ANALYSIS REPORT")
        print("="*60)
        
        summary = coverage_data['summary']
        print(f"? Source Files: {summary['total_source_files']}")
        print(f"? Test Files: {summary['total_test_files']}")
        print(f"? Total Functions: {summary['total_functions']}")
        print(f"? Total Classes: {summary['total_classes']}")
        print(f"? Total Lines of Code: {summary['total_lines_of_code']}")
        print(f"? Test Lines of Code: {summary['test_lines_of_code']}")
        print(f"? Module Coverage: {summary['module_coverage_percent']:.1f}%")
        
        print(f"\n? Coverage by Area:")
        for area, data in coverage_data['coverage_areas'].items():
            quality = data['coverage_quality']
            status = "[PASS]" if quality == 'Good' else "[FAIL]"
            print(f"   {status} {area.replace('_', ' ').title()}: {quality}")
            print(f"      Functions: {data['functions_count']}")
            print(f"      Test Files: {len(data['test_files'])}")
        
        print(f"\n? Module Coverage Details:")
        for module, data in coverage_data['module_coverage'].items():
            status = "[PASS]" if data['tested'] else "[FAIL]"
            print(f"   {status} {module}: {data['functions']} functions, {data['lines']} lines")
        
        # Save detailed report
        report_file = f"test_coverage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(coverage_data, f, indent=2, default=str)
        
        print(f"\n? Detailed report saved: {report_file}")
        
        # Recommendations
        print(f"\n? Coverage Recommendations:")
        untested_modules = [module for module, data in coverage_data['module_coverage'].items() if not data['tested']]
        if untested_modules:
            print(f"   [FAIL] Untested modules: {', '.join(untested_modules)}")
        
        poor_coverage_areas = [area for area, data in coverage_data['coverage_areas'].items() if data['coverage_quality'] == 'Poor']
        if poor_coverage_areas:
            print(f"   [FAIL] Poor coverage areas: {', '.join(poor_coverage_areas)}")
        
        if not untested_modules and not poor_coverage_areas:
            print(f"   [PASS] Excellent coverage across all modules and areas!")

def main():
    """Run test coverage analysis."""
    try:
        analyzer = TestCoverageAnalyzer()
        coverage_data = analyzer.analyze_test_coverage()
        analyzer.generate_coverage_report(coverage_data)
        return 0
    except Exception as e:
        print(f"[FAIL] Coverage analysis failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

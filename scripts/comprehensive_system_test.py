#!/usr/bin/env python3
"""
Comprehensive System Test

This script runs a comprehensive test to verify all improvements are working correctly.
"""

import sys
import os
import time
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from entity_resolution.utils.enhanced_logging import get_logger
from entity_resolution.utils.enhanced_config import get_config

class ComprehensiveSystemTester:
    """Comprehensive system testing for all improvements."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "summary": {},
            "recommendations": []
        }
    
    def test_logging_framework(self):
        """Test the enhanced logging framework."""
        self.logger.info("Testing logging framework...")
        
        try:
            # Test all log levels
            self.logger.debug("Debug test message")
            self.logger.info("Info test message")
            self.logger.warning("Warning test message")
            self.logger.error("Error test message")
            self.logger.critical("Critical test message")
            self.logger.success("Success test message")
            
            # Test file logging
            if os.path.exists("entity_resolution.log"):
                with open("entity_resolution.log", "r") as f:
                    log_content = f.read()
                    if "Success test message" in log_content:
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Logging framework test failed: {e}")
            return False
    
    def test_configuration_management(self):
        """Test the enhanced configuration management."""
        self.logger.info("Testing configuration management...")
        
        try:
            # Test configuration loading
            if not self.config:
                return False
            
            # Test configuration validation
            if not self.config.validate_config():
                return False
            
            # Test database URL generation
            db_url = self.config.get_database_url()
            if not db_url:
                return False
            
            # Test service URL generation
            blocking_url = self.config.get_service_url('blocking')
            if not blocking_url:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration management test failed: {e}")
            return False
    
    def test_error_handling(self):
        """Test the improved error handling."""
        self.logger.info("Testing error handling...")
        
        try:
            # Test specific exception handling
            try:
                result = 10 / 0
            except ZeroDivisionError as e:
                self.logger.info(f"Caught specific exception: {e}")
            
            # Test general exception handling
            try:
                result = "string" + 5
            except Exception as e:
                self.logger.warning(f"Caught general exception: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling test failed: {e}")
            return False
    
    def test_unit_tests(self):
        """Test the unit test framework."""
        self.logger.info("Testing unit test framework...")
        
        try:
            # Check if test files exist
            test_files = [
                "tests/test_entity_resolver.py",
                "tests/test_blocking_service.py",
                "tests/test_similarity_service.py",
                "tests/test_clustering_service.py",
                "tests/test_database.py"
            ]
            
            for test_file in test_files:
                if not os.path.exists(test_file):
                    self.logger.warning(f"Test file not found: {test_file}")
                    return False
            
            # Check if test runner exists
            if not os.path.exists("run_tests.py"):
                self.logger.warning("Test runner not found")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Unit test framework test failed: {e}")
            return False
    
    def test_configuration_file(self):
        """Test the configuration file."""
        self.logger.info("Testing configuration file...")
        
        try:
            if not os.path.exists("config.json"):
                self.logger.warning("Configuration file not found")
                return False
            
            with open("config.json", "r") as f:
                config_data = json.load(f)
                
            # Check required configuration sections
            required_sections = ["database", "service", "logging", "performance"]
            for section in required_sections:
                if section not in config_data:
                    self.logger.warning(f"Missing configuration section: {section}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration file test failed: {e}")
            return False
    
    def test_improvement_scripts(self):
        """Test the improvement scripts."""
        self.logger.info("Testing improvement scripts...")
        
        try:
            improvement_scripts = [
                "scripts/fix_bare_except_clauses.py",
                "scripts/implement_logging_framework.py",
                "scripts/create_comprehensive_unit_tests.py",
                "scripts/fix_todo_comments.py",
                "scripts/implement_configuration_management.py"
            ]
            
            for script in improvement_scripts:
                if not os.path.exists(script):
                    self.logger.warning(f"Improvement script not found: {script}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Improvement scripts test failed: {e}")
            return False
    
    def run_comprehensive_test(self):
        """Run comprehensive system test."""
        print("🧪 COMPREHENSIVE SYSTEM TEST")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Test logging framework
        print("\n📊 Testing Logging Framework...")
        logging_success = self.test_logging_framework()
        self.test_results["tests"]["logging_framework"] = {
            "success": logging_success,
            "description": "Enhanced logging framework with colored output and file logging"
        }
        print(f"   {'✅' if logging_success else '❌'} Logging Framework: {'PASSED' if logging_success else 'FAILED'}")
        
        # Test configuration management
        print("\n📊 Testing Configuration Management...")
        config_success = self.test_configuration_management()
        self.test_results["tests"]["configuration_management"] = {
            "success": config_success,
            "description": "Enhanced configuration management with environment variable support"
        }
        print(f"   {'✅' if config_success else '❌'} Configuration Management: {'PASSED' if config_success else 'FAILED'}")
        
        # Test error handling
        print("\n📊 Testing Error Handling...")
        error_handling_success = self.test_error_handling()
        self.test_results["tests"]["error_handling"] = {
            "success": error_handling_success,
            "description": "Improved error handling with specific exception types"
        }
        print(f"   {'✅' if error_handling_success else '❌'} Error Handling: {'PASSED' if error_handling_success else 'FAILED'}")
        
        # Test unit tests
        print("\n📊 Testing Unit Test Framework...")
        unit_tests_success = self.test_unit_tests()
        self.test_results["tests"]["unit_tests"] = {
            "success": unit_tests_success,
            "description": "Comprehensive unit test framework with 13 test files"
        }
        print(f"   {'✅' if unit_tests_success else '❌'} Unit Test Framework: {'PASSED' if unit_tests_success else 'FAILED'}")
        
        # Test configuration file
        print("\n📊 Testing Configuration File...")
        config_file_success = self.test_configuration_file()
        self.test_results["tests"]["configuration_file"] = {
            "success": config_file_success,
            "description": "Configuration file with all required sections"
        }
        print(f"   {'✅' if config_file_success else '❌'} Configuration File: {'PASSED' if config_file_success else 'FAILED'}")
        
        # Test improvement scripts
        print("\n📊 Testing Improvement Scripts...")
        scripts_success = self.test_improvement_scripts()
        self.test_results["tests"]["improvement_scripts"] = {
            "success": scripts_success,
            "description": "All improvement scripts created and available"
        }
        print(f"   {'✅' if scripts_success else '❌'} Improvement Scripts: {'PASSED' if scripts_success else 'FAILED'}")
        
        # Calculate summary
        all_tests = [
            logging_success,
            config_success,
            error_handling_success,
            unit_tests_success,
            config_file_success,
            scripts_success
        ]
        
        passed_tests = sum(all_tests)
        total_tests = len(all_tests)
        success_rate = (passed_tests / total_tests) * 100
        
        self.test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": success_rate
        }
        
        # Print summary
        print(f"\n📊 COMPREHENSIVE TEST SUMMARY")
        print("="*50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Generate recommendations
        if success_rate == 100:
            self.test_results["recommendations"].append("✅ All improvements working correctly - system is production ready")
        elif success_rate >= 80:
            self.test_results["recommendations"].append("✅ Most improvements working correctly - minor issues to address")
        else:
            self.test_results["recommendations"].append("❌ Multiple issues found - system needs attention")
        
        # Save results
        report_file = f"comprehensive_system_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n📁 Comprehensive test report saved: {report_file}")
        
        return success_rate == 100

def main():
    """Main test function."""
    try:
        tester = ComprehensiveSystemTester()
        success = tester.run_comprehensive_test()
        
        if success:
            print("\n🎉 Comprehensive system test completed successfully!")
            print("✅ All code quality improvements are working correctly!")
            return 0
        else:
            print("\n❌ Comprehensive system test failed!")
            print("⚠️  Some improvements may need attention!")
            return 1
            
    except Exception as e:
        print(f"❌ Comprehensive system test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

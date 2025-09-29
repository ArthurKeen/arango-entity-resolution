"""
Unified Demo Manager

Consolidates all demo functionality to eliminate duplication and provide
a single interface for all entity resolution demonstrations.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from abc import ABC, abstractmethod

from ..utils.config import get_config
from ..utils.logging import get_logger
from ..utils.database import DatabaseMixin
from ..utils.constants import (
    DEMO_CONFIG,
    COLLECTION_NAMES,
    DATA_QUALITY_THRESHOLDS,
    BUSINESS_IMPACT_MULTIPLIERS,
    get_business_impact_estimate
)


class BaseDemoManager(DatabaseMixin, ABC):
    """
    Abstract base class for all demo managers
    
    Provides common functionality for generating and managing
    entity resolution demonstrations.
    """
    
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.logger = get_logger(self.__class__.__name__)
        
        # Demo state
        self.demo_data = []
        self.demo_metadata = {}
        self.results = {}
        self.timing_data = {}
    
    @abstractmethod
    def generate_demo_data(self, record_count: int = None, 
                          duplicate_rate: float = None) -> bool:
        """Generate demonstration data"""
        pass
    
    @abstractmethod
    def run_demo(self, **kwargs) -> Dict[str, Any]:
        """Run the demonstration"""
        pass
    
    def save_demo_data(self, data_dir: Path) -> bool:
        """Save demo data and metadata to files"""
        try:
            data_dir.mkdir(exist_ok=True)
            
            # Save demo data
            data_file = data_dir / "demo_data.json"
            with open(data_file, 'w') as f:
                json.dump(self.demo_data, f, indent=2)
            
            # Save metadata
            metadata_file = data_dir / "demo_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(self.demo_metadata, f, indent=2)
            
            self.logger.info(f"Demo data saved to {data_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save demo data: {e}")
            return False
    
    def load_demo_data(self, data_dir: Path) -> bool:
        """Load demo data and metadata from files"""
        try:
            data_file = data_dir / "demo_data.json"
            metadata_file = data_dir / "demo_metadata.json"
            
            if data_file.exists() and metadata_file.exists():
                with open(data_file, 'r') as f:
                    self.demo_data = json.load(f)
                
                with open(metadata_file, 'r') as f:
                    self.demo_metadata = json.load(f)
                
                self.logger.info(f"Demo data loaded from {data_dir}")
                return True
            else:
                self.logger.warning(f"Demo data files not found in {data_dir}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to load demo data: {e}")
            return False
    
    def calculate_business_impact(self, customer_count: int = None, 
                                duplicate_rate: float = None,
                                marketing_budget: int = None) -> Dict[str, Any]:
        """Calculate business impact of duplicates"""
        
        # Use demo data if parameters not provided
        customer_count = customer_count or len(self.demo_data)
        duplicate_rate = duplicate_rate or self.demo_metadata.get('duplication_rate', 0.2)
        marketing_budget = marketing_budget or (customer_count * 50)  # $50 per customer
        
        return get_business_impact_estimate(customer_count, duplicate_rate, marketing_budget)
    
    def get_demo_summary(self) -> Dict[str, Any]:
        """Get summary of demo results"""
        return {
            "demo_type": self.__class__.__name__,
            "timestamp": datetime.now().isoformat(),
            "data_summary": {
                "record_count": len(self.demo_data),
                "metadata": self.demo_metadata
            },
            "results_summary": self.results,
            "timing_data": self.timing_data,
            "business_impact": self.calculate_business_impact()
        }


class PresentationDemoManager(BaseDemoManager):
    """
    Demo manager for interactive presentations
    
    Provides step-by-step demonstration with manual control
    and clear explanations of the entity resolution problem.
    """
    
    def __init__(self):
        super().__init__()
        self.current_step = 0
        self.auto_mode = False
        self.presentation_state = {}
    
    def generate_demo_data(self, record_count: int = 10, 
                          duplicate_rate: float = 0.3) -> bool:
        """Generate presentation-friendly demo data with clear examples"""
        
        # Create specific examples that are easy to explain
        self.demo_data = [
            # Group 1: John Smith variations (obvious duplicates)
            {
                "id": "rec_001",
                "first_name": "John",
                "last_name": "Smith", 
                "email": "john.smith@email.com",
                "phone": "555-123-4567",
                "company": "Acme Corp",
                "address": "123 Main St, New York, NY",
                "source_system": "CRM",
                "data_quality_score": 95
            },
            {
                "id": "rec_002",
                "first_name": "Jon",
                "last_name": "Smith",
                "email": "j.smith@acme.com", 
                "phone": "(555) 123-4567",
                "company": "Acme Corporation",
                "address": "123 Main Street, NYC, NY",
                "source_system": "Marketing",
                "data_quality_score": 88
            },
            {
                "id": "rec_003",
                "first_name": "Johnny",
                "last_name": "Smith",
                "email": "johnsmith@gmail.com",
                "phone": "5551234567",
                "company": "ACME Corp.",
                "address": "123 Main St, New York",
                "source_system": "Sales",
                "data_quality_score": 78
            },
            
            # Group 2: Sarah Johnson variations (subtle duplicates)
            {
                "id": "rec_004",
                "first_name": "Sarah",
                "last_name": "Johnson",
                "email": "sarah.johnson@techstart.com",
                "phone": "555-987-6543",
                "company": "TechStart Inc",
                "address": "456 Oak Ave, Boston, MA",
                "source_system": "CRM",
                "data_quality_score": 92
            },
            {
                "id": "rec_005",
                "first_name": "Sara",
                "last_name": "Johnson", 
                "email": "s.johnson@techstart.com",
                "phone": "555-987-6543",
                "company": "TechStart Incorporated",
                "address": "456 Oak Avenue, Boston",
                "source_system": "Support",
                "data_quality_score": 85
            },
            
            # Group 3: Robert Wilson / Bob Wilson (nickname variations)
            {
                "id": "rec_006",
                "first_name": "Robert",
                "last_name": "Wilson",
                "email": "robert.wilson@global.com",
                "phone": "555-555-5555",
                "company": "Global Systems",
                "address": "789 Pine St, Chicago, IL",
                "source_system": "ERP",
                "data_quality_score": 90
            },
            {
                "id": "rec_007",
                "first_name": "Bob",
                "last_name": "Wilson",
                "email": "bob.wilson@global.com",
                "phone": "555-555-5555",
                "company": "Global Systems LLC",
                "address": "789 Pine Street, Chicago",
                "source_system": "CRM",
                "data_quality_score": 87
            },
            
            # Non-duplicate records for contrast
            {
                "id": "rec_008",
                "first_name": "Alice",
                "last_name": "Brown",
                "email": "alice.brown@innovation.com",
                "phone": "555-111-2222",
                "company": "Innovation Labs",
                "address": "321 Elm St, Seattle, WA",
                "source_system": "CRM",
                "data_quality_score": 93
            },
            {
                "id": "rec_009",
                "first_name": "Michael",
                "last_name": "Davis",
                "email": "mike.davis@startup.com", 
                "phone": "555-333-4444",
                "company": "Startup XYZ",
                "address": "654 Cedar Ave, Austin, TX",
                "source_system": "Marketing",
                "data_quality_score": 89
            },
            {
                "id": "rec_010",
                "first_name": "Jennifer",
                "last_name": "Miller",
                "email": "jen.miller@enterprise.com",
                "phone": "555-777-8888",
                "company": "Enterprise Solutions",
                "address": "987 Maple Dr, Denver, CO",
                "source_system": "Sales",
                "data_quality_score": 91
            }
        ]
        
        # Create metadata 
        self.demo_metadata = {
            "total_records": len(self.demo_data),
            "unique_entities": 7,  # 3 duplicate groups + 4 unique records = 7 entities
            "duplicate_groups": 3,
            "duplication_rate": 0.3,  # 30% of records are duplicates
            "data_sources": ["CRM", "Marketing", "Sales", "Support", "ERP"],
            "demo_type": "presentation",
            "created_at": datetime.now().isoformat(),
            "duplicate_group_info": [
                {
                    "group_id": 1,
                    "primary_name": "John Smith",
                    "record_ids": ["rec_001", "rec_002", "rec_003"],
                    "variations": ["John Smith", "Jon Smith", "Johnny Smith"]
                },
                {
                    "group_id": 2,
                    "primary_name": "Sarah Johnson",
                    "record_ids": ["rec_004", "rec_005"],
                    "variations": ["Sarah Johnson", "Sara Johnson"]
                },
                {
                    "group_id": 3,
                    "primary_name": "Robert Wilson",
                    "record_ids": ["rec_006", "rec_007"],
                    "variations": ["Robert Wilson", "Bob Wilson"]
                }
            ]
        }
        
        return True
    
    def run_demo(self, auto_mode: bool = False) -> Dict[str, Any]:
        """Run interactive presentation demo"""
        self.auto_mode = auto_mode
        
        try:
            # Generate data if not already loaded
            if not self.demo_data:
                self.generate_demo_data()
            
            # Run presentation steps
            self._run_act1_reveal_problem()
            self._run_act2_demonstrate_solution()
            self._run_act3_show_results()
            
            return {
                "success": True,
                "demo_type": "presentation",
                "summary": self.get_demo_summary()
            }
            
        except Exception as e:
            self.logger.error(f"Presentation demo failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _run_act1_reveal_problem(self):
        """Act 1: Reveal the duplicate problem"""
        self.presentation_state["act1"] = {
            "customer_database_shown": True,
            "duplicates_revealed": True,
            "business_impact_calculated": True
        }
    
    def _run_act2_demonstrate_solution(self):
        """Act 2: Demonstrate AI solution"""
        self.presentation_state["act2"] = {
            "similarity_analysis": True,
            "clustering_shown": True,
            "golden_records_created": True
        }
    
    def _run_act3_show_results(self):
        """Act 3: Show results and business value"""
        self.presentation_state["act3"] = {
            "before_after_comparison": True,
            "roi_calculated": True,
            "next_steps_presented": True
        }


class AutomatedDemoManager(BaseDemoManager):
    """
    Demo manager for automated demonstrations
    
    Provides fast, automated demonstration for testing
    and quick overview purposes.
    """
    
    def generate_demo_data(self, record_count: int = 1000, 
                          duplicate_rate: float = 0.2) -> bool:
        """Generate larger dataset for automated demo"""
        # This would integrate with the existing data generator
        # For now, create a simplified version
        
        # Temporary simplified data generation
        # In production, this would use the actual DataGenerator
        self.demo_data = [
            {"id": f"record_{i}", "name": f"Person {i}", "value": i}
            for i in range(record_count)
        ]
        self.demo_metadata = {
            "total_records": record_count,
            "duplicate_rate": duplicate_rate,
            "generated_at": datetime.now().isoformat()
        }
        
        return True
    
    def run_demo(self, record_count: int = 1000) -> Dict[str, Any]:
        """Run automated demo with full pipeline"""
        
        try:
            start_time = time.time()
            
            # Generate data
            if not self.demo_data:
                self.generate_demo_data(record_count)
            
            # Run entity resolution pipeline
            pipeline_results = self._run_entity_resolution_pipeline()
            
            total_time = time.time() - start_time
            
            return {
                "success": True,
                "demo_type": "automated",
                "total_time": total_time,
                "pipeline_results": pipeline_results,
                "summary": self.get_demo_summary()
            }
            
        except Exception as e:
            self.logger.error(f"Automated demo failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _run_entity_resolution_pipeline(self) -> Dict[str, Any]:
        """Run the complete entity resolution pipeline"""
        # This would integrate with the existing pipeline
        # For now, return simulated results
        
        return {
            "similarity_pairs": len(self.demo_data) * 2,
            "clusters_found": int(len(self.demo_data) * 0.8),
            "golden_records": int(len(self.demo_data) * 0.8),
            "processing_time": 2.5
        }


def get_demo_manager(demo_type: str = "presentation") -> BaseDemoManager:
    """
    Factory function to get the appropriate demo manager
    
    Args:
        demo_type: Type of demo ("presentation", "automated")
        
    Returns:
        Demo manager instance
    """
    if demo_type.lower() == "presentation":
        return PresentationDemoManager()
    elif demo_type.lower() == "automated":
        return AutomatedDemoManager()
    else:
        raise ValueError(f"Unknown demo type: {demo_type}")


# Convenience functions
def run_presentation_demo(auto_mode: bool = False) -> Dict[str, Any]:
    """Run presentation demo (convenience function)"""
    demo = PresentationDemoManager()
    return demo.run_demo(auto_mode=auto_mode)


def run_automated_demo(record_count: int = 1000) -> Dict[str, Any]:
    """Run automated demo (convenience function)"""
    demo = AutomatedDemoManager()
    return demo.run_demo(record_count=record_count)

"""
Entity Resolution Demo Module

Provides unified demo management and presentation capabilities
for entity resolution demonstrations.
"""

from .demo_manager import (
    BaseDemoManager,
    PresentationDemoManager,
    AutomatedDemoManager,
    get_demo_manager,
    run_presentation_demo,
    run_automated_demo
)

__all__ = [
    'BaseDemoManager',
    'PresentationDemoManager', 
    'AutomatedDemoManager',
    'get_demo_manager',
    'run_presentation_demo',
    'run_automated_demo'
]

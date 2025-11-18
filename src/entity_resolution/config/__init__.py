"""
Configuration components for entity resolution pipelines.

This module provides configuration-driven ER pipeline support, allowing
users to define complete ER workflows via YAML/JSON configuration files.
"""

from .er_config import (
    ERPipelineConfig,
    BlockingConfig,
    SimilarityConfig,
    ClusteringConfig
)

__all__ = [
    'ERPipelineConfig',
    'BlockingConfig',
    'SimilarityConfig',
    'ClusteringConfig',
]


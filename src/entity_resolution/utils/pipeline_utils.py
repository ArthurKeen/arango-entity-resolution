"""
Pipeline Utilities

Provides utilities for managing ER pipeline state, cleaning results, and
common pipeline operations.
"""

from typing import Dict, List, Any, Optional
from arango.database import StandardDatabase

from .logging import get_logger


def clean_er_results(
    db: StandardDatabase,
    collections: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Clean previous ER results from specified collections.
    
    Removes all documents from the specified collections (typically edge collections
    and result collections from previous ER runs). Gracefully handles missing
    collections and logs cleanup results.
    
    Args:
        db: ArangoDB database connection
        collections: List of collection names to clean. If None, uses defaults:
            - 'similarTo' (similarity edges)
            - 'entity_clusters' (clustering results)
            - 'address_sameAs' (address ER edges)
    
    Returns:
        Dictionary with cleanup results:
        {
            'collections_cleaned': List[str],  # Names of successfully cleaned collections
            'removed_counts': Dict[str, int],  # Collection name -> count of removed documents
            'errors': List[Dict[str, str]],    # List of {'collection': str, 'error': str}
            'total_removed': int                # Total documents removed across all collections
        }
    """
    logger = get_logger(__name__)
    
    default_collections = ['similarTo', 'entity_clusters', 'address_sameAs']
    collections = collections or default_collections
    
    result = {
        'collections_cleaned': [],
        'removed_counts': {},
        'errors': [],
        'total_removed': 0
    }
    
    logger.info("Cleaning previous ER results...")
    
    for coll_name in collections:
        try:
            if db.has_collection(coll_name):
                coll = db.collection(coll_name)
                old_count = coll.count()
                if old_count > 0:
                    coll.truncate()
                    result['collections_cleaned'].append(coll_name)
                    result['removed_counts'][coll_name] = old_count
                    result['total_removed'] += old_count
                    logger.info(f"  ✓ Removed {old_count:,} documents from '{coll_name}'")
                else:
                    logger.debug(f"  - Collection '{coll_name}' is already empty")
            else:
                logger.debug(f"  - Collection '{coll_name}' does not exist (skipping)")
        except Exception as e:
            error_info = {'collection': coll_name, 'error': str(e)}
            result['errors'].append(error_info)
            logger.warning(f"  ⚠ Could not clean collection '{coll_name}': {e}")
    
    if result['total_removed'] > 0:
        logger.info(f"Cleaned {len(result['collections_cleaned'])} collection(s), "
                   f"removed {result['total_removed']:,} total documents")
    else:
        logger.info("No previous results to clean")
    
    return result


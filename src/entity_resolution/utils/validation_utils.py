"""
Validation Utilities

Provides utilities for validating ER pipeline results and data consistency.
"""

from typing import Dict, List, Any, Optional
from arango.database import StandardDatabase

from .logging import get_logger


def validate_er_results(
    db: StandardDatabase,
    results: Dict[str, Any],
    validations: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Validate ER pipeline results.
    
    Compares expected counts from pipeline results with actual document counts
    in collections. Useful for detecting data consistency issues and verifying
    that the pipeline completed successfully.
    
    Args:
        db: ArangoDB database connection
        results: Results dictionary from ER pipeline (e.g., from service.run()).
            Should contain keys like 'edges_created', 'clusters_found', etc.
        validations: List of validation configurations. Each config should have:
            - 'collection': Collection name to check
            - 'expected_key': Key in results dict containing expected count
            - 'description': Optional description for logging
        
            If None, uses defaults:
            [
                {
                    'collection': 'similarTo',
                    'expected_key': 'edges_created',
                    'description': 'Similarity edges'
                },
                {
                    'collection': 'entity_clusters',
                    'expected_key': 'clusters_found',
                    'description': 'Entity clusters'
                },
                {
                    'collection': 'address_sameAs',
                    'expected_key': 'edges_created',
                    'description': 'Address sameAs edges'
                }
            ]
    
    Returns:
        Dictionary with validation results:
        {
            'passed': bool,  # True if all validations passed
            'validations': [
                {
                    'collection': str,
                    'expected': int,
                    'actual': int,
                    'status': 'pass' | 'fail' | 'error',
                    'description': str,
                    'error': Optional[str]
                },
                ...
            ],
            'summary': {
                'total': int,
                'passed': int,
                'failed': int,
                'errors': int
            }
        }
    """
    logger = get_logger(__name__)
    
    # Default validations
    if validations is None:
        validations = [
            {
                'collection': 'similarTo',
                'expected_key': 'edges_created',
                'description': 'Similarity edges'
            },
            {
                'collection': 'entity_clusters',
                'expected_key': 'clusters_found',
                'description': 'Entity clusters'
            },
            {
                'collection': 'address_sameAs',
                'expected_key': 'edges_created',
                'description': 'Address sameAs edges'
            }
        ]
    
    validation_results = []
    passed_count = 0
    failed_count = 0
    error_count = 0
    
    logger.info("Validating ER pipeline results...")
    
    for validation in validations:
        collection_name = validation['collection']
        expected_key = validation['expected_key']
        description = validation.get('description', collection_name)
        
        validation_result = {
            'collection': collection_name,
            'expected': 0,
            'actual': 0,
            'status': 'error',
            'description': description,
            'error': None
        }
        
        # Get expected count from results
        expected_count = results.get(expected_key, 0)
        validation_result['expected'] = expected_count
        
        # Skip validation if expected count is 0 (no results expected)
        if expected_count == 0:
            validation_result['status'] = 'pass'
            validation_result['actual'] = 0
            validation_results.append(validation_result)
            passed_count += 1
            logger.debug(f"  - {description}: No results expected (skipped)")
            continue
        
        # Get actual count from collection
        try:
            if db.has_collection(collection_name):
                coll = db.collection(collection_name)
                actual_count = coll.count()
                validation_result['actual'] = actual_count
                
                # Compare counts
                if actual_count == expected_count:
                    validation_result['status'] = 'pass'
                    passed_count += 1
                    logger.info(f"  ✓ {description}: {actual_count:,} documents (expected: {expected_count:,})")
                else:
                    validation_result['status'] = 'fail'
                    failed_count += 1
                    logger.warning(
                        f"  ⚠ {description}: Count mismatch - "
                        f"expected {expected_count:,}, found {actual_count:,}"
                    )
            else:
                validation_result['status'] = 'fail'
                validation_result['error'] = f"Collection '{collection_name}' does not exist"
                failed_count += 1
                logger.warning(f"  ⚠ {description}: Collection does not exist")
        except Exception as e:
            validation_result['status'] = 'error'
            validation_result['error'] = str(e)
            error_count += 1
            logger.error(f"  ✗ {description}: Error during validation - {e}")
        
        validation_results.append(validation_result)
    
    # Build summary
    all_passed = (failed_count == 0 and error_count == 0)
    
    result = {
        'passed': all_passed,
        'validations': validation_results,
        'summary': {
            'total': len(validations),
            'passed': passed_count,
            'failed': failed_count,
            'errors': error_count
        }
    }
    
    if all_passed:
        logger.info(f"✓ Validation passed: {passed_count}/{len(validations)} validations passed")
    else:
        logger.warning(
            f"⚠ Validation issues: {passed_count} passed, "
            f"{failed_count} failed, {error_count} errors"
        )
    
    return result


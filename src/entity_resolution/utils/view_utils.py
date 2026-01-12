"""
ArangoSearch View Utilities

Provides utilities for verifying and fixing ArangoSearch view analyzer configurations.
Handles database-prefixed analyzer names and view accessibility verification.
"""

from typing import Dict, List, Any, Optional, Tuple
from arango.database import StandardDatabase
import logging

from .logging import get_logger


def resolve_analyzer_name(db: StandardDatabase, analyzer_name: str) -> str:
    """
    Resolve analyzer name, checking for database-prefixed versions.
    
    In ArangoDB, analyzers may be stored with a database prefix
    (e.g., 'database_name::analyzer_name'). This function finds the
    actual analyzer name that exists in the database.
    
    Args:
        db: ArangoDB database connection
        analyzer_name: Base analyzer name (e.g., 'address_normalizer')
    
    Returns:
        Actual analyzer name (with prefix if present, otherwise original)
    """
    logger = get_logger(__name__)
    
    # Get all existing analyzers
    existing_analyzers = {a['name'] for a in db.analyzers()}
    
    # Check if analyzer exists as-is (no prefix)
    if analyzer_name in existing_analyzers:
        return analyzer_name
    
    # Try to get database name and check for prefixed version
    db_name = None
    try:
        # Try to get database name from properties
        props = db.properties()
        db_name = props.get('name')
    except (AttributeError, Exception):
        try:
            # Try direct attribute access
            db_name = db.name
        except (AttributeError, Exception):
            pass
    
    # Check if analyzer exists with database prefix
    if db_name:
        prefixed_name = f"{db_name}::{analyzer_name}"
        if prefixed_name in existing_analyzers:
            logger.debug(f"Using database-prefixed analyzer: {prefixed_name}")
            return prefixed_name
    
    # Fallback: search for any analyzer ending with ::analyzer_name
    for existing_name in existing_analyzers:
        if existing_name.endswith(f"::{analyzer_name}"):
            logger.debug(f"Found prefixed analyzer: {existing_name}")
            return existing_name
    
    # If not found, return original (will fail during view creation if truly missing)
    # This allows built-in analyzers like 'text_en' and 'identity' to work
    return analyzer_name


def verify_view_analyzers(
    db: StandardDatabase,
    view_name: str,
    collection_name: str,
    test_query: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Verify that ArangoSearch view is accessible and uses correct analyzers.
    
    Tests view accessibility with a simple query. If the view fails with
    analyzer-related errors, it may need to be recreated with correct
    database-prefixed analyzer names.
    
    Args:
        db: ArangoDB database connection
        view_name: Name of the ArangoSearch view to verify
        collection_name: Name of the collection linked to the view
        test_query: Optional AQL query to test view. If None, uses default:
            FOR doc IN {view_name} LIMIT 1 RETURN 1
    
    Returns:
        Tuple of (is_accessible: bool, error_message: Optional[str])
        - is_accessible: True if view works correctly, False otherwise
        - error_message: Error message if view is not accessible, None if accessible
    """
    logger = get_logger(__name__)
    
    # Check if view exists
    try:
        existing_views = {v['name'] for v in db.views()}
        if view_name not in existing_views:
            return False, f"View '{view_name}' does not exist"
    except Exception as e:
        return False, f"Could not check for view existence: {e}"
    
    # Use default test query if not provided
    if test_query is None:
        test_query = f"FOR doc IN {view_name} LIMIT 1 RETURN 1"
    
    # Test view accessibility
    try:
        list(db.aql.execute(test_query))
        logger.debug(f"View '{view_name}' is accessible")
        return True, None
    except Exception as e:
        error_msg = str(e).lower()
        if 'failed to build scorers' in error_msg or 'analyzer' in error_msg:
            logger.warning(f"View '{view_name}' may have analyzer name issues: {e}")
            return False, f"Analyzer configuration issue: {e}"
        else:
            # Other errors (e.g., collection not found, syntax errors)
            return False, f"View accessibility error: {e}"


def fix_view_analyzer_names(
    db: StandardDatabase,
    view_name: str,
    collection_name: str,
    field_analyzers: Dict[str, List[str]],
    view_properties: Optional[Dict[str, Any]] = None,
    wait_seconds: int = 10
) -> Dict[str, Any]:
    """
    Recreate ArangoSearch view with correct database-prefixed analyzer names.
    
    This function:
    1. Resolves all analyzer names to their database-prefixed versions
    2. Deletes the existing view (if it exists)
    3. Creates a new view with correct analyzer names
    4. Optionally waits for view indices to initialize
    
    Args:
        db: ArangoDB database connection
        view_name: Name of the ArangoSearch view to create/fix
        collection_name: Name of the collection to link to the view
        field_analyzers: Dictionary mapping field names to lists of analyzer names.
            Example:
            {
                'ADDRESS_LINE_1': ['address_normalizer', 'text_en'],
                'PRIMARY_TOWN': ['text_normalizer'],
                'TERRITORY_CODE': ['identity']
            }
        view_properties: Optional additional view properties (e.g., 'includeAllFields').
            If None, uses defaults: {'includeAllFields': False}
        wait_seconds: Number of seconds to wait after view creation for indices to initialize
    
    Returns:
        Dictionary with operation results:
        {
            'view_created': bool,
            'view_name': str,
            'analyzers_resolved': Dict[str, List[str]],  # Field -> resolved analyzer names
            'wait_seconds': int,
            'error': Optional[str]
        }
    """
    logger = get_logger(__name__)
    result = {
        'view_created': False,
        'view_name': view_name,
        'analyzers_resolved': {},
        'wait_seconds': wait_seconds,
        'error': None
    }
    
    # Resolve all analyzer names
    resolved_field_analyzers = {}
    for field_name, analyzer_list in field_analyzers.items():
        resolved_analyzers = [
            resolve_analyzer_name(db, analyzer_name)
            for analyzer_name in analyzer_list
        ]
        resolved_field_analyzers[field_name] = resolved_analyzers
        result['analyzers_resolved'][field_name] = resolved_analyzers
        logger.debug(f"Resolved analyzers for field '{field_name}': {resolved_analyzers}")
    
    # Delete existing view if it exists
    try:
        existing_views = {v['name'] for v in db.views()}
        if view_name in existing_views:
            logger.info(f"Deleting existing view '{view_name}'...")
            db.delete_view(view_name)
            logger.info(f"Deleted view '{view_name}'")
    except Exception as e:
        logger.warning(f"Could not delete existing view '{view_name}': {e}")
        # Continue anyway - view creation may overwrite
    
    # Prepare view properties
    if view_properties is None:
        view_properties = {'includeAllFields': False}
    
    # Build fields configuration
    fields_config = {}
    for field_name, analyzer_list in resolved_field_analyzers.items():
        fields_config[field_name] = {'analyzers': analyzer_list}
    
    # Create view
    try:
        logger.info(f"Creating view '{view_name}' with resolved analyzer names...")
        db.create_arangosearch_view(
            name=view_name,
            properties={
                'links': {
                    collection_name: {
                        **view_properties,
                        'fields': fields_config
                    }
                }
            }
        )
        result['view_created'] = True
        logger.info(f"Successfully created view '{view_name}'")
        
        # Wait for view indices to initialize
        if wait_seconds > 0:
            logger.info(f"Waiting {wait_seconds} seconds for view indices to initialize...")
            time.sleep(wait_seconds)
        
    except Exception as e:
        error_msg = f"Failed to create view '{view_name}': {e}"
        result['error'] = error_msg
        logger.error(error_msg)
    
    return result


def verify_and_fix_view_analyzers(
    db: StandardDatabase,
    view_name: str,
    collection_name: str,
    field_analyzers: Dict[str, List[str]],
    view_properties: Optional[Dict[str, Any]] = None,
    test_query: Optional[str] = None,
    wait_seconds: int = 10,
    auto_fix: bool = True
) -> Dict[str, Any]:
    """
    Verify view accessibility and automatically fix analyzer name issues if needed.
    
    This is a convenience function that combines verify_view_analyzers() and
    fix_view_analyzer_names() to provide self-healing view configuration.
    
    Args:
        db: ArangoDB database connection
        view_name: Name of the ArangoSearch view to verify/fix
        collection_name: Name of the collection linked to the view
        field_analyzers: Dictionary mapping field names to lists of analyzer names
        view_properties: Optional additional view properties
        test_query: Optional AQL query to test view accessibility
        wait_seconds: Number of seconds to wait after view creation
        auto_fix: If True, automatically fix analyzer issues if detected
    
    Returns:
        Dictionary with verification and fix results:
        {
            'verified': bool,
            'fixed': bool,
            'view_name': str,
            'error': Optional[str],
            'fix_result': Optional[Dict[str, Any]]
        }
    """
    logger = get_logger(__name__)
    result = {
        'verified': False,
        'fixed': False,
        'view_name': view_name,
        'error': None,
        'fix_result': None
    }
    
    # Verify view
    is_accessible, error_msg = verify_view_analyzers(
        db, view_name, collection_name, test_query
    )
    
    if is_accessible:
        result['verified'] = True
        logger.info(f"[OK] View '{view_name}' is accessible")
        return result
    
    # View is not accessible
    result['error'] = error_msg
    logger.warning(f"[WARN]?  View '{view_name}' may have analyzer name issues: {error_msg}")
    
    # Auto-fix if enabled
    if auto_fix and ('analyzer' in error_msg.lower() or 'scorers' in error_msg.lower()):
        logger.info(f"Attempting to fix view '{view_name}'...")
        fix_result = fix_view_analyzer_names(
            db, view_name, collection_name, field_analyzers,
            view_properties, wait_seconds
        )
        result['fix_result'] = fix_result
        
        if fix_result.get('view_created'):
            result['fixed'] = True
            # Verify again after fix
            is_accessible, error_msg = verify_view_analyzers(
                db, view_name, collection_name, test_query
            )
            result['verified'] = is_accessible
            if not is_accessible:
                result['error'] = f"View still not accessible after fix: {error_msg}"
        else:
            result['error'] = fix_result.get('error', 'Unknown error during fix')
    
    return result


"""
Graph utilities for ArangoDB entity resolution.

Provides common utilities for working with graph structures, vertex IDs,
and edge operations in ArangoDB.
"""

from typing import Optional


def format_vertex_id(key: str, vertex_collection: Optional[str] = None) -> str:
    """
    Format a document key as a vertex ID for edge _from/_to.
    
    ArangoDB edges require vertex IDs in the format "collection/key".
    This function handles various input formats and ensures proper formatting.
    
    Args:
        key: Document key or already-formatted vertex ID
        vertex_collection: Collection name for the vertex.
            If None, uses "vertices" as default.
            If provided, uses "{vertex_collection}/{key}".
    
    Returns:
        Formatted vertex ID: "collection/key"
    
    Examples:
        >>> format_vertex_id("123", "companies")
        'companies/123'
        
        >>> format_vertex_id("companies/123", "companies")
        'companies/123'  # Already formatted
        
        >>> format_vertex_id("123")
        'vertices/123'  # Default collection
    """
    # If already formatted (contains /), return as-is
    if '/' in key:
        return key
    
    # Use provided collection or default to "vertices"
    collection = vertex_collection if vertex_collection else "vertices"
    
    return f"{collection}/{key}"


def extract_key_from_vertex_id(vertex_id: str) -> str:
    """
    Extract document key from vertex ID.
    
    ArangoDB vertex IDs are in format "collection/key". This function
    extracts just the key part, or returns the input if already a key.
    
    Args:
        vertex_id: Vertex ID in format "collection/key" or just "key"
    
    Returns:
        Document key (without collection prefix)
    
    Examples:
        >>> extract_key_from_vertex_id("companies/123")
        '123'
        
        >>> extract_key_from_vertex_id("123")
        '123'  # Already a key
    """
    # If contains /, split and take the last part
    if '/' in vertex_id:
        return vertex_id.split('/')[-1]
    
    # Already a key
    return vertex_id


def parse_vertex_id(vertex_id: str) -> tuple[str, str]:
    """
    Parse vertex ID into collection and key components.
    
    Args:
        vertex_id: Vertex ID in format "collection/key" or just "key"
    
    Returns:
        Tuple of (collection, key). If input is just a key, 
        collection will be None.
    
    Examples:
        >>> parse_vertex_id("companies/123")
        ('companies', '123')
        
        >>> parse_vertex_id("123")
        (None, '123')
    """
    if '/' in vertex_id:
        parts = vertex_id.split('/', 1)  # Split on first / only
        return parts[0], parts[1]
    
    return None, vertex_id


def normalize_vertex_ids(vertex_ids: list[str], vertex_collection: Optional[str] = None) -> list[str]:
    """
    Normalize a list of vertex IDs to ensure consistent formatting.
    
    Args:
        vertex_ids: List of vertex IDs (may be mixed formats)
        vertex_collection: Collection name to use for unformatted keys
    
    Returns:
        List of properly formatted vertex IDs
    
    Examples:
        >>> normalize_vertex_ids(["123", "companies/456", "789"], "companies")
        ['companies/123', 'companies/456', 'companies/789']
    """
    return [format_vertex_id(vid, vertex_collection) for vid in vertex_ids]


def is_valid_vertex_id(vertex_id: str) -> bool:
    """
    Check if a string is a valid vertex ID format.
    
    A valid vertex ID should be either:
    - "collection/key" format
    - Just "key" (can be formatted later)
    
    Args:
        vertex_id: String to validate
    
    Returns:
        True if valid format, False otherwise
    
    Examples:
        >>> is_valid_vertex_id("companies/123")
        True
        
        >>> is_valid_vertex_id("123")
        True
        
        >>> is_valid_vertex_id("")
        False
        
        >>> is_valid_vertex_id("/123")
        False  # Empty collection
    """
    if not vertex_id or not isinstance(vertex_id, str):
        return False
    
    # If contains /, check both parts are non-empty
    if '/' in vertex_id:
        parts = vertex_id.split('/')
        return len(parts) == 2 and all(part.strip() for part in parts)
    
    # Just a key - should be non-empty
    return bool(vertex_id.strip())


def extract_collection_from_vertex_id(vertex_id: str) -> Optional[str]:
    """
    Extract collection name from vertex ID.
    
    Args:
        vertex_id: Vertex ID in format "collection/key"
    
    Returns:
        Collection name, or None if not in full format
    
    Examples:
        >>> extract_collection_from_vertex_id("companies/123")
        'companies'
        
        >>> extract_collection_from_vertex_id("123")
        None  # No collection in ID
    """
    collection, _ = parse_vertex_id(vertex_id)
    return collection


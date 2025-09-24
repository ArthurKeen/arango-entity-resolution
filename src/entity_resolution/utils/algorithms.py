"""
Common Algorithms for Entity Resolution

Shared algorithm implementations used across multiple services:
- Soundex phonetic algorithm
- String similarity functions
- Data validation functions
"""

import re
from typing import Dict, Any, List


def soundex(name: str) -> str:
    """
    Generate Soundex code for a name
    
    Standard Soundex algorithm implementation used for phonetic matching.
    
    Args:
        name: Input name string
        
    Returns:
        4-character Soundex code
    """
    if not name:
        return "0000"
    
    name = name.upper().strip()
    if not name:
        return "0000"
    
    # Soundex mapping
    soundex_map = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6'
    }
    
    # Keep first letter
    result = name[0]
    
    # Process remaining characters
    for char in name[1:]:
        if char in soundex_map:
            code = soundex_map[char]
            # Don't add consecutive duplicates
            if not result or result[-1] != code:
                result += code
    
    # Remove vowels and H, W, Y (except first letter)
    if len(result) > 1:
        result = result[0] + ''.join(c for c in result[1:] if c.isdigit())
    
    # Pad with zeros or truncate to 4 characters
    result = (result + "000")[:4]
    
    return result


def validate_email(email: str) -> Dict[str, Any]:
    """
    Validate email format
    
    Args:
        email: Email string to validate
        
    Returns:
        Validation result with validity flag and reason
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = bool(re.match(email_pattern, str(email).strip()))
    return {'valid': is_valid, 'reason': 'format_check'}


def validate_phone(phone: str) -> Dict[str, Any]:
    """
    Validate phone number format
    
    Args:
        phone: Phone number string to validate
        
    Returns:
        Validation result with validity flag and reason
    """
    # Simple US phone number validation
    phone_clean = re.sub(r'[^\d]', '', str(phone))
    is_valid = len(phone_clean) >= 10 and len(phone_clean) <= 11
    return {'valid': is_valid, 'reason': 'length_check'}


def validate_zip_code(zip_code: str) -> Dict[str, Any]:
    """
    Validate ZIP code format
    
    Args:
        zip_code: ZIP code string to validate
        
    Returns:
        Validation result with validity flag and reason
    """
    zip_pattern = r'^\d{5}(-\d{4})?$'
    is_valid = bool(re.match(zip_pattern, str(zip_code).strip()))
    return {'valid': is_valid, 'reason': 'format_check'}


def validate_state(state: str) -> Dict[str, Any]:
    """
    Validate US state code
    
    Args:
        state: State code string to validate
        
    Returns:
        Validation result with validity flag and reason
    """
    valid_states = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    }
    is_valid = str(state).strip().upper() in valid_states
    return {'valid': is_valid, 'reason': 'state_code_check'}


def get_default_validation_rules() -> Dict[str, callable]:
    """
    Get default validation rules for common fields
    
    Returns:
        Dictionary mapping field names to validation functions
    """
    return {
        'email': validate_email,
        'phone': validate_phone,
        'zip_code': validate_zip_code,
        'state': validate_state
    }


def normalize_field_value(field_name: str, value: Any) -> str:
    """
    Normalize field values for comparison
    
    Args:
        field_name: Name of the field being normalized
        value: Value to normalize
        
    Returns:
        Normalized string value
    """
    if value is None:
        return ""
    
    # Convert to string and strip whitespace
    normalized = str(value).strip()
    
    # Field-specific normalization
    if field_name in ['email']:
        normalized = normalized.lower()
    elif field_name in ['phone']:
        # Remove non-digits from phone numbers
        normalized = re.sub(r'[^\d]', '', normalized)
    elif field_name in ['first_name', 'last_name', 'company', 'city', 'state']:
        # Title case for names and places
        normalized = normalized.title()
    elif field_name in ['address']:
        # Basic address normalization
        normalized = normalized.title()
        # Normalize common abbreviations
        normalized = re.sub(r'\bSt\.?\b', 'Street', normalized)
        normalized = re.sub(r'\bAve\.?\b', 'Avenue', normalized)
        normalized = re.sub(r'\bRd\.?\b', 'Road', normalized)
        normalized = re.sub(r'\bDr\.?\b', 'Drive', normalized)
    
    return normalized


def extract_field_features(field_name: str, value: Any) -> List[str]:
    """
    Extract features from field values for blocking
    
    Args:
        field_name: Name of the field
        value: Field value
        
    Returns:
        List of feature strings for blocking
    """
    if value is None:
        return []
    
    normalized = normalize_field_value(field_name, value)
    if not normalized:
        return []
    
    features = []
    
    # Add full value
    features.append(normalized)
    
    # Field-specific feature extraction
    if field_name in ['first_name', 'last_name']:
        # Add first 3 characters
        if len(normalized) >= 3:
            features.append(normalized[:3])
        # Add Soundex code
        features.append(soundex(normalized))
    elif field_name == 'email':
        # Add domain
        if '@' in normalized:
            domain = normalized.split('@')[1]
            features.append(domain)
    elif field_name == 'phone':
        # Add area code if available
        if len(normalized) >= 10:
            features.append(normalized[:3])  # Area code
    elif field_name == 'address':
        # Add first word (usually house number)
        words = normalized.split()
        if words:
            features.append(words[0])
    
    return features

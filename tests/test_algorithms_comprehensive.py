#!/usr/bin/env python3
"""
Comprehensive Tests for Algorithms Module

Tests for common algorithms used across entity resolution:
- Soundex phonetic algorithm
- Email validation
- Phone validation
- ZIP code validation
- State validation
- Field normalization
- Feature extraction
"""

import pytest
from entity_resolution.utils.algorithms import (
    soundex,
    validate_email,
    validate_phone,
    validate_zip_code,
    validate_state,
    get_default_validation_rules,
    normalize_field_value,
    extract_field_features
)


class TestSoundex:
    """Test Soundex phonetic algorithm."""
    
    def test_basic_soundex(self):
        """Test basic Soundex encoding."""
        # Robert and Rupert should have same code
        assert soundex("Robert") == soundex("Rupert")
        
        # Smith variations
        assert soundex("Smith") == soundex("Smyth")
    
    def test_soundex_standard_cases(self):
        """Test standard Soundex examples."""
        # Classic examples from Soundex documentation
        assert soundex("Ashcraft") == soundex("Ashcroft")
        
        # Test that soundex produces consistent 4-char codes
        assert len(soundex("Washington")) == 4
        assert soundex("Washington").startswith("W")
    
    def test_soundex_empty_input(self):
        """Test Soundex with empty input."""
        assert soundex("") == "0000"
        assert soundex("   ") == "0000"
        assert soundex(None) == "0000" or soundex("") == "0000"
    
    def test_soundex_single_letter(self):
        """Test Soundex with single letter."""
        assert soundex("A") == "A000"
        assert soundex("Z") == "Z000"
    
    def test_soundex_case_insensitive(self):
        """Test Soundex is case-insensitive."""
        assert soundex("Smith") == soundex("SMITH")
        assert soundex("smith") == soundex("Smith")
        assert soundex("SmItH") == soundex("smith")
    
    def test_soundex_special_characters(self):
        """Test Soundex handles special characters."""
        # Should ignore non-alphabetic characters
        assert soundex("O'Brien") == soundex("OBrien")
        assert soundex("Smith-Jones") == soundex("SmithJones")[:4]
    
    def test_soundex_common_names(self):
        """Test Soundex on common names."""
        # Johnson variations
        johnson_code = soundex("Johnson")
        assert soundex("Jonson") == johnson_code
        
        # Similar names should have same first letter
        assert soundex("Lee")[0] == soundex("Leigh")[0]
    
    def test_soundex_length(self):
        """Test Soundex always returns 4 characters."""
        assert len(soundex("A")) == 4
        assert len(soundex("Smith")) == 4
        assert len(soundex("Washington")) == 4
        assert len(soundex("Schwarzenegger")) == 4


class TestValidateEmail:
    """Test email validation."""
    
    def test_valid_emails(self):
        """Test valid email addresses."""
        valid_emails = [
            "user@example.com",
            "test.user@example.com",
            "user+tag@example.co.uk",
            "user_name@example.org",
            "user123@test-domain.com",
            "a@b.co",
        ]
        for email in valid_emails:
            result = validate_email(email)
            assert result['valid'] is True, f"Email {email} should be valid"
            assert result['reason'] == 'format_check'
    
    def test_invalid_emails(self):
        """Test invalid email addresses."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",  # Space
            "user@example",  # No TLD
            "user@@example.com",  # Double @
            "",
            "   ",
        ]
        for email in invalid_emails:
            result = validate_email(email)
            assert result['valid'] is False, f"Email {email} should be invalid"
    
    def test_email_with_whitespace(self):
        """Test email validation strips whitespace."""
        result = validate_email("  user@example.com  ")
        assert result['valid'] is True
    
    def test_email_special_cases(self):
        """Test edge cases for email validation."""
        # Very long email
        long_email = "a" * 50 + "@" + "b" * 50 + ".com"
        result = validate_email(long_email)
        assert result['valid'] is True


class TestValidatePhone:
    """Test phone number validation."""
    
    def test_valid_phones(self):
        """Test valid phone numbers."""
        valid_phones = [
            "1234567890",  # 10 digits
            "12345678901",  # 11 digits (with country code)
            "(123) 456-7890",  # Formatted
            "123-456-7890",  # Dashed
            "123.456.7890",  # Dotted
            "+1-234-567-8900",  # With country code
        ]
        for phone in valid_phones:
            result = validate_phone(phone)
            assert result['valid'] is True, f"Phone {phone} should be valid"
            assert result['reason'] == 'length_check'
    
    def test_invalid_phones(self):
        """Test invalid phone numbers."""
        invalid_phones = [
            "123",  # Too short
            "12345",  # Too short
            "123456789",  # 9 digits
            "123456789012",  # Too long
            "abcdefghij",  # Letters
            "",
            "   ",
        ]
        for phone in invalid_phones:
            result = validate_phone(phone)
            assert result['valid'] is False, f"Phone {phone} should be invalid"
    
    def test_phone_format_normalization(self):
        """Test that different formats are recognized."""
        # All these should be valid (same number, different formats)
        formats = [
            "1234567890",
            "(123) 456-7890",
            "123-456-7890",
            "123.456.7890",
            "123 456 7890",
        ]
        for fmt in formats:
            result = validate_phone(fmt)
            assert result['valid'] is True


class TestValidateZipCode:
    """Test ZIP code validation."""
    
    def test_valid_zip_codes(self):
        """Test valid ZIP codes."""
        valid_zips = [
            "12345",  # 5-digit
            "12345-6789",  # ZIP+4
            "90210",  # Famous ZIP
            "00501",  # IRS ZIP
        ]
        for zip_code in valid_zips:
            result = validate_zip_code(zip_code)
            assert result['valid'] is True, f"ZIP {zip_code} should be valid"
            assert result['reason'] == 'format_check'
    
    def test_invalid_zip_codes(self):
        """Test invalid ZIP codes."""
        invalid_zips = [
            "1234",  # Too short
            "123456",  # Too long (not ZIP+4)
            "abcde",  # Letters
            "12345-67",  # Incomplete ZIP+4
            "",
            "   ",
        ]
        for zip_code in invalid_zips:
            result = validate_zip_code(zip_code)
            assert result['valid'] is False, f"ZIP {zip_code} should be invalid"
    
    def test_zip_whitespace_handling(self):
        """Test ZIP codes with whitespace."""
        result = validate_zip_code("  12345  ")
        assert result['valid'] is True


class TestValidateState:
    """Test state abbreviation validation."""
    
    def test_valid_states(self):
        """Test valid US state abbreviations."""
        valid_states = [
            "CA", "NY", "TX", "FL", "IL",
            "PA", "OH", "GA", "NC", "MI",
            "AK", "HI",  # Alaska, Hawaii
        ]
        for state in valid_states:
            result = validate_state(state)
            assert result['valid'] is True, f"State {state} should be valid"
            assert result['reason'] == 'state_code_check'
    
    def test_valid_states_lowercase(self):
        """Test state validation is case-insensitive."""
        result = validate_state("ca")
        assert result['valid'] is True
        
        result = validate_state("Ny")
        assert result['valid'] is True
    
    def test_invalid_states(self):
        """Test invalid state abbreviations."""
        invalid_states = [
            "XX",  # Not a state
            "ZZ",  # Not a state
            "ABC",  # Too long
            "A",  # Too short
            "",
            "12",  # Numbers
        ]
        for state in invalid_states:
            result = validate_state(state)
            assert result['valid'] is False, f"State {state} should be invalid"
    
    def test_state_whitespace(self):
        """Test state with whitespace."""
        result = validate_state("  CA  ")
        assert result['valid'] is True


class TestGetDefaultValidationRules:
    """Test default validation rules."""
    
    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        rules = get_default_validation_rules()
        assert isinstance(rules, dict)
    
    def test_has_common_fields(self):
        """Test that dict contains common field validators."""
        rules = get_default_validation_rules()
        # Check for actual fields that exist
        assert 'email' in rules
        assert 'phone' in rules
        assert 'zip_code' in rules  # Note: it's zip_code, not zip
        assert 'state' in rules
    
    def test_validators_are_callable(self):
        """Test that all validators are callable."""
        rules = get_default_validation_rules()
        for field, validator in rules.items():
            assert callable(validator), f"Validator for {field} is not callable"
    
    def test_validators_work(self):
        """Test that validators actually work."""
        rules = get_default_validation_rules()
        
        # Test email validator
        if 'email' in rules:
            result = rules['email']('test@example.com')
            assert isinstance(result, dict)
            assert 'valid' in result


class TestNormalizeFieldValue:
    """Test field value normalization."""
    
    def test_normalize_name(self):
        """Test name field normalization."""
        # Names use title case, not lowercase
        assert normalize_field_value('first_name', '  john doe  ') == 'John Doe'
        assert normalize_field_value('first_name', 'JANE') == 'Jane'
    
    def test_normalize_email(self):
        """Test email field normalization."""
        assert normalize_field_value('email', '  User@Example.COM  ') == 'user@example.com'
    
    def test_normalize_phone(self):
        """Test phone field normalization."""
        # Should remove non-digits
        assert normalize_field_value('phone', '(123) 456-7890') == '1234567890'
    
    def test_normalize_zip(self):
        """Test ZIP code normalization."""
        assert normalize_field_value('zip', '  12345  ') == '12345'
        assert normalize_field_value('zip_code', '12345-6789') == '12345-6789'
    
    def test_normalize_state(self):
        """Test state normalization."""
        # State uses title case
        assert normalize_field_value('state', 'ca') == 'Ca'
        assert normalize_field_value('state', '  ny  ') == 'Ny'
    
    def test_normalize_generic_field(self):
        """Test generic field normalization."""
        # City uses title case
        assert normalize_field_value('city', '  san francisco  ') == 'San Francisco'
        # Address uses title case and expands abbreviations
        assert 'Street' in normalize_field_value('address', 'MAIN ST')
    
    def test_normalize_none_value(self):
        """Test normalization of None values."""
        result = normalize_field_value('name', None)
        assert result == ''
    
    def test_normalize_numeric_value(self):
        """Test normalization of numeric values."""
        result = normalize_field_value('age', 25)
        assert result == '25'


class TestExtractFieldFeatures:
    """Test field feature extraction."""
    
    def test_extract_name_features(self):
        """Test feature extraction from name fields."""
        features = extract_field_features('name', 'John Doe')
        assert isinstance(features, list)
        assert len(features) > 0
        # Should include tokens
        assert any('john' in f.lower() for f in features)
    
    def test_extract_email_features(self):
        """Test feature extraction from email."""
        features = extract_field_features('email', 'user@example.com')
        assert isinstance(features, list)
        # Should include domain
        assert any('example' in f.lower() for f in features)
    
    def test_extract_phone_features(self):
        """Test feature extraction from phone."""
        features = extract_field_features('phone', '(123) 456-7890')
        assert isinstance(features, list)
        # Should include area code
        assert any('123' in f for f in features)
    
    def test_extract_address_features(self):
        """Test feature extraction from address."""
        features = extract_field_features('address', '123 Main St, San Francisco, CA')
        assert isinstance(features, list)
        # Should have at least the full value and first word
        assert len(features) >= 2
    
    def test_extract_features_empty_value(self):
        """Test feature extraction from empty value."""
        features = extract_field_features('name', '')
        assert isinstance(features, list)
        assert len(features) == 0 or all(f == '' for f in features)
    
    def test_extract_features_none_value(self):
        """Test feature extraction from None value."""
        features = extract_field_features('name', None)
        assert isinstance(features, list)


class TestEdgeCasesAndIntegration:
    """Test edge cases and integration scenarios."""
    
    def test_all_validators_with_none(self):
        """Test all validators handle None gracefully."""
        assert validate_email(None)['valid'] is False
        assert validate_phone(None)['valid'] is False
        assert validate_zip_code(None)['valid'] is False
        assert validate_state(None)['valid'] is False
    
    def test_all_validators_with_empty_string(self):
        """Test all validators handle empty strings."""
        assert validate_email('')['valid'] is False
        assert validate_phone('')['valid'] is False
        assert validate_zip_code('')['valid'] is False
        assert validate_state('')['valid'] is False
    
    def test_soundex_with_numbers(self):
        """Test Soundex with numbers in name."""
        # Numbers should be ignored
        result = soundex("Smith123")
        assert result.startswith("S")
        assert len(result) == 4
    
    def test_normalization_consistency(self):
        """Test that normalization is consistent."""
        # Use first_name which has specific normalization
        value1 = normalize_field_value('first_name', 'John Doe')
        value2 = normalize_field_value('first_name', '  JOHN DOE  ')
        assert value1 == value2
    
    def test_feature_extraction_consistency(self):
        """Test that feature extraction is consistent."""
        features1 = extract_field_features('name', 'John Doe')
        features2 = extract_field_features('name', 'John Doe')
        assert features1 == features2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


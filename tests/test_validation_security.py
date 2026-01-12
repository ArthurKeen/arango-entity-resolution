#!/usr/bin/env python3
"""
Comprehensive Security Tests for Validation Module

Tests all validation functions with:
- Valid inputs
- Edge cases
- Boundary conditions  
- Malicious input patterns (AQL injection attempts)
- Type errors
"""

import pytest
from entity_resolution.utils.validation import (
    validate_collection_name,
    validate_field_name,
    validate_field_names,
    validate_graph_name,
    validate_view_name,
    validate_database_name,
    sanitize_string_for_display
)


class TestValidateCollectionName:
    """Test collection name validation and AQL injection prevention."""
    
    def test_valid_collection_names(self):
        """Test valid collection names are accepted."""
        valid_names = [
            "users",
            "customers",
            "test_collection",
            "myCollection123",
            "a",  # Single letter
            "Collection_With_Underscores",
            "c" * 256  # Max length
        ]
        for name in valid_names:
            assert validate_collection_name(name) == name
    
    def test_reject_empty_name(self):
        """Test empty names are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_collection_name("")
    
    def test_reject_non_string(self):
        """Test non-string types are rejected."""
        with pytest.raises(ValueError, match="must be a string"):
            validate_collection_name(123)
        
        # None is caught by empty check first
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_collection_name(None)
    
    def test_reject_starts_with_number(self):
        """Test names starting with numbers are rejected."""
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_collection_name("123users")
    
    def test_reject_starts_with_underscore(self):
        """Test system collection prefix is rejected."""
        # Underscore triggers "must start with letter" error first
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_collection_name("_system")
        
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_collection_name("_users")
    
    def test_reject_special_characters(self):
        """Test special characters are rejected."""
        invalid_names = [
            "users-table",  # Hyphen
            "users.table",  # Dot
            "users table",  # Space
            "users@home",   # @ symbol
            "users#1",      # Hash
            "users$",       # Dollar
            "users%",       # Percent
            "users&",       # Ampersand
            "users*",       # Asterisk
            "users()",      # Parentheses
            "users[]",      # Brackets
            "users{}",      # Braces
            "users|",       # Pipe
            "users\\",      # Backslash
            "users/",       # Forward slash
            "users?",       # Question mark
            "users!",       # Exclamation
        ]
        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid collection name"):
                validate_collection_name(name)
    
    def test_reject_too_long(self):
        """Test names exceeding 256 characters are rejected."""
        too_long = "a" * 257
        with pytest.raises(ValueError, match="too long"):
            validate_collection_name(too_long)
    
    def test_aql_injection_attempts(self):
        """Test AQL injection patterns are blocked."""
        injection_attempts = [
            "'; DROP COLLECTION users--",
            "users'; DELETE",
            "users' OR '1'='1",
            "users\"; DROP",
            "users`; REMOVE",
            "users\n; DROP",
            "users\r\n; DELETE",
            "users\t; REMOVE",
            "users/**/; DROP",
            "users--%20DROP",
            "users;--",
            "1' UNION SELECT",
            "admin'--",
            "' or 1=1--",
            "users'; INSERT",
            "users\x00; DROP",  # Null byte
        ]
        for injection in injection_attempts:
            with pytest.raises(ValueError):
                validate_collection_name(injection)
    
    def test_unicode_rejected(self):
        """Test unicode characters are rejected."""
        unicode_names = [
            "users(TM)",
            "users(C)",
            "users(R)",
            "usersEUR",
            "usersGBP",
            "usersJPY",
            "users??",
            "users???",
            "users??????",
            "users?",
            "users\u200b",  # Zero-width space
        ]
        for name in unicode_names:
            with pytest.raises(ValueError):
                validate_collection_name(name)


class TestValidateFieldName:
    """Test field name validation."""
    
    def test_valid_field_names(self):
        """Test valid field names are accepted."""
        valid_names = [
            "name",
            "first_name",
            "firstName",
            "_id",
            "_key",
            "_private",
            "field123",
            "a" * 256  # Max length
        ]
        for name in valid_names:
            assert validate_field_name(name) == name
    
    def test_valid_nested_fields(self):
        """Test nested field paths are accepted when allowed."""
        nested = [
            "address.city",
            "person.address.street",
            "a.b.c.d.e",
            "user.profile.settings.theme",
            "_doc.nested._field"
        ]
        for name in nested:
            assert validate_field_name(name, allow_nested=True) == name
    
    def test_reject_nested_when_not_allowed(self):
        """Test nested fields are rejected when allow_nested=False."""
        with pytest.raises(ValueError, match="Invalid field name"):
            validate_field_name("address.city", allow_nested=False)
    
    def test_reject_empty_field(self):
        """Test empty field names are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_field_name("")
    
    def test_reject_non_string(self):
        """Test non-string types are rejected."""
        with pytest.raises(ValueError, match="must be a string"):
            validate_field_name(123)
    
    def test_reject_special_characters(self):
        """Test special characters are rejected in field names."""
        invalid = [
            "name-field",
            "name field",
            "name@domain",
            "name$var",
            "name[0]",
            "name{key}",
            "name|pipe",
            "name/path",
            "name\\escape",
            "name;command",
            "name'quote",
            "name\"quote",
        ]
        for name in invalid:
            with pytest.raises(ValueError):
                validate_field_name(name)
    
    def test_reject_invalid_nested_patterns(self):
        """Test invalid nested field patterns are rejected."""
        invalid_nested = [
            "address..city",  # Double dot
            ".address",       # Starts with dot
            "address.",       # Ends with dot
            "address.1city",  # Number at start of segment
            "address.-city",  # Special char after dot
        ]
        for name in invalid_nested:
            with pytest.raises(ValueError):
                validate_field_name(name, allow_nested=True)
    
    def test_reject_too_long(self):
        """Test field names exceeding 256 characters are rejected."""
        too_long = "a" * 257
        with pytest.raises(ValueError, match="too long"):
            validate_field_name(too_long)
    
    def test_aql_injection_in_fields(self):
        """Test AQL injection patterns in field names are blocked."""
        injection_attempts = [
            "name'; DROP",
            "name' OR '1'='1",
            "name\"; REMOVE",
            "name/**/DROP",
            "name--comment",
            "name;command",
        ]
        for injection in injection_attempts:
            with pytest.raises(ValueError):
                validate_field_name(injection)


class TestValidateFieldNames:
    """Test batch field name validation."""
    
    def test_valid_field_list(self):
        """Test valid list of field names."""
        fields = ["name", "email", "phone", "address.city"]
        result = validate_field_names(fields)
        assert result == fields
    
    def test_reject_non_list(self):
        """Test non-list input is rejected."""
        with pytest.raises(ValueError, match="must be a list"):
            validate_field_names("name")
        
        with pytest.raises(ValueError, match="must be a list"):
            validate_field_names({"name": "value"})
    
    def test_reject_invalid_field_in_list(self):
        """Test list with invalid field is rejected."""
        with pytest.raises(ValueError):
            validate_field_names(["name", "email", "invalid field with spaces"])
    
    def test_empty_list(self):
        """Test empty list is accepted."""
        assert validate_field_names([]) == []
    
    def test_nested_field_control(self):
        """Test allow_nested parameter works for lists."""
        fields = ["name", "address.city"]
        
        # Should work with nested allowed
        result = validate_field_names(fields, allow_nested=True)
        assert result == fields
        
        # Should fail with nested not allowed
        with pytest.raises(ValueError):
            validate_field_names(fields, allow_nested=False)


class TestValidateGraphName:
    """Test graph name validation."""
    
    def test_valid_graph_names(self):
        """Test valid graph names are accepted."""
        valid = ["socialGraph", "knowledge_graph", "graph123"]
        for name in valid:
            assert validate_graph_name(name) == name
    
    def test_follows_collection_rules(self):
        """Test graph names follow same rules as collections."""
        # Should reject same patterns as collections
        with pytest.raises(ValueError):
            validate_graph_name("_system_graph")
        
        with pytest.raises(ValueError):
            validate_graph_name("graph-name")
        
        with pytest.raises(ValueError):
            validate_graph_name("123graph")


class TestValidateViewName:
    """Test view name validation."""
    
    def test_valid_view_names(self):
        """Test valid view names are accepted."""
        valid = ["searchView", "my_view", "view123"]
        for name in valid:
            assert validate_view_name(name) == name
    
    def test_follows_collection_rules(self):
        """Test view names follow same rules as collections."""
        with pytest.raises(ValueError):
            validate_view_name("_system_view")
        
        with pytest.raises(ValueError):
            validate_view_name("view-name")


class TestValidateDatabaseName:
    """Test database name validation."""
    
    def test_valid_database_names(self):
        """Test valid database names are accepted."""
        valid = [
            "mydb",
            "test_db",
            "db-name",  # Hyphens allowed in database names
            "database123",
            "a",
            "A" * 64  # Max length
        ]
        for name in valid:
            assert validate_database_name(name) == name
    
    def test_reject_empty(self):
        """Test empty database names are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_database_name("")
    
    def test_reject_starts_with_number(self):
        """Test database names starting with numbers are rejected."""
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_database_name("123db")
    
    def test_reject_special_characters(self):
        """Test special characters (except hyphen) are rejected."""
        invalid = [
            "db.name",
            "db name",
            "db@home",
            "db#1",
            "db$",
            "db%",
            "db&",
            "db*",
        ]
        for name in invalid:
            with pytest.raises(ValueError):
                validate_database_name(name)
    
    def test_reject_too_long(self):
        """Test database names exceeding 64 characters are rejected."""
        too_long = "a" * 65
        with pytest.raises(ValueError, match="too long"):
            validate_database_name(too_long)
    
    def test_system_database_not_allowed_underscore(self):
        """Test database names starting with underscore are rejected."""
        # Even _system is rejected by our validation (must start with letter)
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_database_name("_system")
    
    def test_aql_injection_attempts(self):
        """Test AQL injection in database names is blocked."""
        injection_attempts = [
            "db'; DROP",
            "db' OR '1'='1",
            "db\"; DELETE",
        ]
        for injection in injection_attempts:
            with pytest.raises(ValueError):
                validate_database_name(injection)


class TestSanitizeStringForDisplay:
    """Test string sanitization for safe logging."""
    
    def test_normal_strings_unchanged(self):
        """Test normal strings pass through unchanged."""
        normal = "Hello, World! 123"
        assert sanitize_string_for_display(normal) == normal
    
    def test_control_characters_removed(self):
        """Test control characters are replaced."""
        with_control = "Hello\x00World\x01"
        sanitized = sanitize_string_for_display(with_control)
        assert "\x00" not in sanitized
        assert "\x01" not in sanitized
        assert "Hello" in sanitized
        assert "World" in sanitized
    
    def test_newlines_preserved(self):
        """Test newlines and tabs are preserved."""
        with_whitespace = "Line 1\nLine 2\tTabbed"
        sanitized = sanitize_string_for_display(with_whitespace)
        assert "\n" in sanitized
        assert "\t" in sanitized
    
    def test_truncation(self):
        """Test long strings are truncated."""
        long_string = "a" * 200
        sanitized = sanitize_string_for_display(long_string, max_length=50)
        assert len(sanitized) <= 53  # 50 + "..."
        assert sanitized.endswith("...")
    
    def test_non_string_converted(self):
        """Test non-string values are converted to strings."""
        assert "123" in sanitize_string_for_display(123)
        assert "None" in sanitize_string_for_display(None)
        assert "True" in sanitize_string_for_display(True)
    
    def test_log_injection_prevented(self):
        """Test log injection attempts are sanitized."""
        # Attempt to inject fake log entries
        injection = "Normal log\n[ERROR] Fake error from attacker"
        sanitized = sanitize_string_for_display(injection, max_length=50)
        # Should be truncated, preventing the fake log entry
        assert len(sanitized) <= 53


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""
    
    def test_exact_max_length_collection(self):
        """Test collection name at exactly 256 characters."""
        exact_max = "a" * 256
        assert validate_collection_name(exact_max) == exact_max
    
    def test_exact_max_length_field(self):
        """Test field name at exactly 256 characters."""
        exact_max = "a" * 256
        assert validate_field_name(exact_max) == exact_max
    
    def test_exact_max_length_database(self):
        """Test database name at exactly 64 characters."""
        exact_max = "a" * 64
        assert validate_database_name(exact_max) == exact_max
    
    def test_single_character_names(self):
        """Test single-character names are valid."""
        assert validate_collection_name("a") == "a"
        assert validate_field_name("a") == "a"
        assert validate_database_name("a") == "a"
    
    def test_case_sensitivity(self):
        """Test validation is case-sensitive and preserves case."""
        mixed_case = "MyCollectionName"
        assert validate_collection_name(mixed_case) == mixed_case
        
        upper = "COLLECTION"
        assert validate_collection_name(upper) == upper
        
        lower = "collection"
        assert validate_collection_name(lower) == lower


class TestIntegrationPatterns:
    """Test real-world usage patterns."""
    
    def test_typical_entity_resolution_collections(self):
        """Test typical ER collection names work."""
        collections = [
            "customers",
            "companies",
            "similarity_edges",
            "candidate_pairs",
            "golden_records",
            "blocking_keys"
        ]
        for coll in collections:
            assert validate_collection_name(coll) == coll
    
    def test_typical_field_names(self):
        """Test typical ER field names work."""
        fields = [
            "name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "address",
            "city",
            "state",
            "zip",
            "country",
            "_key",
            "_id",
            "_from",
            "_to"
        ]
        for field in fields:
            assert validate_field_name(field) == field
    
    def test_typical_nested_fields(self):
        """Test typical nested field paths work."""
        nested = [
            "address.street",
            "address.city",
            "address.state",
            "address.zip",
            "person.name.first",
            "person.name.last",
            "company.contact.email",
            "metadata.source.system"
        ]
        for field in nested:
            assert validate_field_name(field, allow_nested=True) == field


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


"""
Unit tests for entity_resolution.utils.validation module.

Tests all public validation and sanitization functions for correct
acceptance, rejection, and edge-case handling.
"""

import pytest

from entity_resolution.utils.validation import (
    validate_collection_name,
    validate_database_name,
    validate_field_name,
    validate_field_names,
    validate_graph_name,
    validate_view_name,
    sanitize_string_for_display,
)


# ---------------------------------------------------------------------------
# validate_collection_name
# ---------------------------------------------------------------------------

class TestValidateCollectionName:
    """Tests for validate_collection_name()."""

    @pytest.mark.unit
    def test_accepts_simple_name(self):
        """Valid lowercase alpha name is accepted and returned unchanged."""
        assert validate_collection_name("companies") == "companies"

    @pytest.mark.unit
    def test_accepts_name_with_digits_and_underscores(self):
        """Alphanumeric names with underscores are accepted."""
        assert validate_collection_name("test_collection_123") == "test_collection_123"

    @pytest.mark.unit
    def test_accepts_mixed_case(self):
        """Mixed-case names are accepted."""
        assert validate_collection_name("MyCollection") == "MyCollection"

    @pytest.mark.unit
    def test_rejects_empty_string(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_collection_name("")

    @pytest.mark.unit
    def test_rejects_none_input(self):
        """None raises ValueError (empty-string branch or type check)."""
        with pytest.raises((ValueError, TypeError)):
            validate_collection_name(None)

    @pytest.mark.unit
    def test_rejects_non_string_input(self):
        """Integer input raises ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            validate_collection_name(123)

    @pytest.mark.unit
    def test_rejects_name_starting_with_digit(self):
        """Names starting with a digit are rejected."""
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_collection_name("1collection")

    @pytest.mark.unit
    def test_rejects_name_starting_with_underscore(self):
        """Names starting with underscore are rejected (reserved for system)."""
        with pytest.raises(ValueError):
            validate_collection_name("_system")

    @pytest.mark.unit
    def test_rejects_special_characters(self):
        """Names with special characters are rejected."""
        for bad in ["my-collection", "my.collection", "my collection", "col@name"]:
            with pytest.raises(ValueError):
                validate_collection_name(bad)

    @pytest.mark.unit
    def test_rejects_sql_injection_attempt(self):
        """SQL/AQL injection strings are rejected."""
        with pytest.raises(ValueError):
            validate_collection_name("'; DROP TABLE users; --")

    @pytest.mark.unit
    def test_rejects_name_exceeding_max_length(self):
        """Names longer than 256 characters are rejected."""
        long_name = "a" * 257
        with pytest.raises(ValueError, match="too long"):
            validate_collection_name(long_name)

    @pytest.mark.unit
    def test_accepts_name_at_max_length(self):
        """A 256-character name is accepted."""
        name = "a" * 256
        assert validate_collection_name(name) == name

    @pytest.mark.unit
    def test_rejects_unicode_letters(self):
        """Unicode letters outside ASCII are rejected by the regex."""
        with pytest.raises(ValueError):
            validate_collection_name("cöllection")


# ---------------------------------------------------------------------------
# validate_database_name
# ---------------------------------------------------------------------------

class TestValidateDatabaseName:
    """Tests for validate_database_name()."""

    @pytest.mark.unit
    def test_accepts_simple_name(self):
        """Valid lowercase name is accepted."""
        assert validate_database_name("mydb") == "mydb"

    @pytest.mark.unit
    def test_accepts_hyphens(self):
        """Database names may contain hyphens (unlike collection names)."""
        assert validate_database_name("my-database") == "my-database"

    @pytest.mark.unit
    def test_accepts_underscores_and_digits(self):
        """Underscores and digits are accepted."""
        assert validate_database_name("db_test_42") == "db_test_42"

    @pytest.mark.unit
    def test_rejects_empty_string(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_database_name("")

    @pytest.mark.unit
    def test_rejects_non_string(self):
        """Non-string input raises ValueError."""
        with pytest.raises(ValueError, match="must be a string"):
            validate_database_name(42)

    @pytest.mark.unit
    def test_rejects_name_starting_with_digit(self):
        """Names starting with a digit are rejected."""
        with pytest.raises(ValueError, match="must start with a letter"):
            validate_database_name("9db")

    @pytest.mark.unit
    def test_rejects_name_exceeding_max_length(self):
        """Names longer than 64 characters are rejected."""
        with pytest.raises(ValueError, match="too long"):
            validate_database_name("d" * 65)

    @pytest.mark.unit
    def test_accepts_name_at_max_length(self):
        """A 64-character name is accepted."""
        name = "d" * 64
        assert validate_database_name(name) == name

    @pytest.mark.unit
    def test_rejects_special_characters(self):
        """Dots, spaces, and other special chars are rejected."""
        for bad in ["my.db", "my db", "db@host"]:
            with pytest.raises(ValueError):
                validate_database_name(bad)

    @pytest.mark.unit
    def test_rejects_injection_attempt(self):
        """Injection-style input is rejected."""
        with pytest.raises(ValueError):
            validate_database_name("db; DROP DATABASE")


# ---------------------------------------------------------------------------
# validate_field_name
# ---------------------------------------------------------------------------

class TestValidateFieldName:
    """Tests for validate_field_name()."""

    @pytest.mark.unit
    def test_accepts_simple_field(self):
        """Simple field name is accepted."""
        assert validate_field_name("first_name") == "first_name"

    @pytest.mark.unit
    def test_accepts_nested_field_by_default(self):
        """Dotted nested field names are accepted when allow_nested=True (default)."""
        assert validate_field_name("address.city") == "address.city"

    @pytest.mark.unit
    def test_rejects_nested_field_when_disallowed(self):
        """Dotted names are rejected when allow_nested=False."""
        with pytest.raises(ValueError):
            validate_field_name("address.city", allow_nested=False)

    @pytest.mark.unit
    def test_rejects_empty_string(self):
        """Empty field name is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_field_name("")

    @pytest.mark.unit
    def test_rejects_non_string(self):
        """Non-string input is rejected."""
        with pytest.raises(ValueError, match="must be a string"):
            validate_field_name(99)

    @pytest.mark.unit
    def test_rejects_field_exceeding_max_length(self):
        """Field names longer than 256 characters are rejected."""
        with pytest.raises(ValueError, match="too long"):
            validate_field_name("f" * 257)

    @pytest.mark.unit
    def test_accepts_field_starting_with_underscore(self):
        """Field names starting with underscore are valid."""
        assert validate_field_name("_key") == "_key"

    @pytest.mark.unit
    def test_rejects_field_starting_with_digit(self):
        """Field names starting with a digit are rejected."""
        with pytest.raises(ValueError):
            validate_field_name("1field")

    @pytest.mark.unit
    def test_rejects_field_with_spaces(self):
        """Spaces in field names are rejected."""
        with pytest.raises(ValueError):
            validate_field_name("my field")

    @pytest.mark.unit
    def test_deeply_nested_field(self):
        """Deeply nested dotted fields are accepted."""
        assert validate_field_name("a.b.c.d.e") == "a.b.c.d.e"

    @pytest.mark.unit
    def test_rejects_trailing_dot(self):
        """Trailing dot is rejected."""
        with pytest.raises(ValueError):
            validate_field_name("field.")

    @pytest.mark.unit
    def test_rejects_leading_dot(self):
        """Leading dot is rejected."""
        with pytest.raises(ValueError):
            validate_field_name(".field")


# ---------------------------------------------------------------------------
# validate_field_names (batch)
# ---------------------------------------------------------------------------

class TestValidateFieldNames:
    """Tests for validate_field_names()."""

    @pytest.mark.unit
    def test_accepts_valid_list(self):
        """A list of valid field names is accepted."""
        result = validate_field_names(["name", "address", "phone"])
        assert result == ["name", "address", "phone"]

    @pytest.mark.unit
    def test_rejects_non_list_input(self):
        """Non-list input raises ValueError."""
        with pytest.raises(ValueError, match="must be a list"):
            validate_field_names("not_a_list")

    @pytest.mark.unit
    def test_rejects_if_any_name_invalid(self):
        """If any name is invalid, the whole batch fails."""
        with pytest.raises(ValueError):
            validate_field_names(["valid_name", "123invalid"])

    @pytest.mark.unit
    def test_empty_list_accepted(self):
        """An empty list returns an empty list."""
        assert validate_field_names([]) == []


# ---------------------------------------------------------------------------
# validate_graph_name / validate_view_name (delegates)
# ---------------------------------------------------------------------------

class TestValidateGraphAndViewName:
    """Tests for validate_graph_name and validate_view_name (delegation to collection rules)."""

    @pytest.mark.unit
    def test_graph_name_valid(self):
        """Valid graph name passes."""
        assert validate_graph_name("myGraph") == "myGraph"

    @pytest.mark.unit
    def test_graph_name_invalid(self):
        """Invalid graph name is rejected."""
        with pytest.raises(ValueError):
            validate_graph_name("")

    @pytest.mark.unit
    def test_view_name_valid(self):
        """Valid view name passes."""
        assert validate_view_name("searchView") == "searchView"

    @pytest.mark.unit
    def test_view_name_invalid(self):
        """Invalid view name is rejected."""
        with pytest.raises(ValueError):
            validate_view_name("1invalid")


# ---------------------------------------------------------------------------
# sanitize_string_for_display
# ---------------------------------------------------------------------------

class TestSanitizeStringForDisplay:
    """Tests for sanitize_string_for_display()."""

    @pytest.mark.unit
    def test_returns_normal_string_unchanged(self):
        """A printable string under max_length is returned as-is."""
        assert sanitize_string_for_display("hello") == "hello"

    @pytest.mark.unit
    def test_truncates_long_string(self):
        """Strings exceeding max_length are truncated with ellipsis."""
        result = sanitize_string_for_display("a" * 200, max_length=10)
        assert result == "a" * 10 + "..."

    @pytest.mark.unit
    def test_replaces_control_characters(self):
        """Non-printable control characters are replaced with '?'."""
        result = sanitize_string_for_display("hello\x00world")
        assert "\x00" not in result
        assert "?" in result

    @pytest.mark.unit
    def test_preserves_newline_and_tab(self):
        """Newlines and tabs are preserved."""
        result = sanitize_string_for_display("line1\nline2\tcol")
        assert "\n" in result
        assert "\t" in result

    @pytest.mark.unit
    def test_converts_non_string_to_string(self):
        """Non-string input is converted to str before sanitizing."""
        result = sanitize_string_for_display(12345)
        assert result == "12345"

    @pytest.mark.unit
    def test_custom_max_length(self):
        """Custom max_length is honoured."""
        result = sanitize_string_for_display("abcdef", max_length=3)
        assert result == "abc..."

    @pytest.mark.unit
    def test_string_exactly_at_max_length(self):
        """A string exactly at max_length is not truncated."""
        result = sanitize_string_for_display("abcde", max_length=5)
        assert result == "abcde"

    @pytest.mark.unit
    def test_empty_string(self):
        """Empty string is returned as-is."""
        assert sanitize_string_for_display("") == ""

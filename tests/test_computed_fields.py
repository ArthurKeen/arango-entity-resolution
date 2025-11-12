"""
Comprehensive tests for computed fields in CollectBlockingStrategy.

Tests cover:
- Validation of computed field names
- Single and multiple computed fields
- Filtering on computed fields
- Complex AQL expressions
- Error handling
- Integration with real blocking operations
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.entity_resolution.strategies import CollectBlockingStrategy


@pytest.fixture
def mock_db():
    """Mock ArangoDB database."""
    db = Mock()
    db.aql = Mock()
    return db


class TestComputedFieldValidation:
    """Test computed field name validation."""
    
    def test_valid_computed_field_names(self, mock_db):
        """Valid computed field names should be accepted."""
        valid_names = [
            {"zip5": "LEFT(d.postal_code, 5)"},
            {"phone_normalized": "REGEX_REPLACE(d.phone, '[^0-9]', '')"},
            {"name_key": "CONCAT(d.first_name, '_', d.last_name)"},
            {"field_123": "d.value"},
            {"_private": "d.field"},  # Leading underscore now allowed after first char
        ]
        
        for computed_fields in valid_names:
            strategy = CollectBlockingStrategy(
                db=mock_db,
                collection="test",
                blocking_fields=list(computed_fields.keys()),
                computed_fields=computed_fields
            )
            assert strategy.computed_fields == computed_fields
    
    def test_reject_invalid_computed_field_names(self, mock_db):
        """Invalid computed field names should raise ValueError."""
        invalid_names = [
            {"zip-5": "LEFT(d.postal_code, 5)"},  # Hyphen not allowed
            {"phone.normalized": "d.phone"},      # Dot not allowed
            {"name key": "d.name"},               # Space not allowed
            {"123field": "d.field"},              # Cannot start with digit
            {"field@123": "d.field"},             # Special char not allowed
        ]
        
        for computed_fields in invalid_names:
            with pytest.raises(ValueError, match="must be alphanumeric|cannot start with a digit"):
                CollectBlockingStrategy(
                    db=mock_db,
                    collection="test",
                    blocking_fields=list(computed_fields.keys()),
                    computed_fields=computed_fields
                )
    
    def test_computed_field_bypasses_standard_validation(self, mock_db):
        """Computed field names should not be validated as document fields."""
        # "123" would fail document field validation, but should pass as computed field name
        # Actually, it should still fail because it starts with a digit
        with pytest.raises(ValueError, match="cannot start with a digit"):
            CollectBlockingStrategy(
                db=mock_db,
                collection="test",
                blocking_fields=["123"],
                computed_fields={"123": "d.field"}
            )
        
        # But "field123" should work
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="test",
            blocking_fields=["field123"],
            computed_fields={"field123": "d.field"}
        )
        assert "field123" in strategy.computed_fields


class TestComputedFieldQueryGeneration:
    """Test AQL query generation with computed fields."""
    
    def test_single_computed_field(self, mock_db):
        """Test query generation with one computed field."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["address", "zip5"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
        )
        
        query = strategy._build_collect_query()
        
        assert "FOR d IN companies" in query
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        assert "COLLECT address = d.address, zip5 = zip5" in query
    
    def test_multiple_computed_fields(self, mock_db):
        """Test query generation with multiple computed fields."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["name_norm", "phone_norm", "zip5"],
            computed_fields={
                "name_norm": "UPPER(d.name)",
                "phone_norm": "REGEX_REPLACE(d.phone, '[^0-9]', '')",
                "zip5": "LEFT(d.postal_code, 5)"
            }
        )
        
        query = strategy._build_collect_query()
        
        assert "LET name_norm = UPPER(d.name)" in query
        assert "LET phone_norm = REGEX_REPLACE(d.phone, '[^0-9]', '')" in query
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        assert "COLLECT name_norm = name_norm, phone_norm = phone_norm, zip5 = zip5" in query
    
    def test_mixed_computed_and_regular_fields(self, mock_db):
        """Test blocking with both computed and regular fields."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["state", "zip5"],  # state is regular, zip5 is computed
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
        )
        
        query = strategy._build_collect_query()
        
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        assert "COLLECT state = d.state, zip5 = zip5" in query
    
    def test_complex_computed_expressions(self, mock_db):
        """Test complex AQL expressions in computed fields."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["complex_key"],
            computed_fields={
                "complex_key": "CONCAT(LEFT(UPPER(d.name), 3), '_', LEFT(d.postal_code, 5), '_', d.state)"
            }
        )
        
        query = strategy._build_collect_query()
        
        assert "LET complex_key = CONCAT(LEFT(UPPER(d.name), 3), '_', LEFT(d.postal_code, 5), '_', d.state)" in query
        assert "COLLECT complex_key = complex_key" in query


class TestComputedFieldFiltering:
    """Test filtering on computed fields."""
    
    def test_filter_on_computed_field(self, mock_db):
        """Computed fields should use variable reference, not d.field."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["zip5"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"},
            filters={
                "zip5": {"not_null": True, "min_length": 5}
            }
        )
        
        query = strategy._build_collect_query()
        
        # Should filter on "zip5", not "d.zip5"
        assert "FILTER zip5 != null" in query
        assert "FILTER LENGTH(zip5) >= 5" in query
        assert "FILTER d.zip5" not in query  # Should NOT use d.zip5
    
    def test_filter_on_regular_field(self, mock_db):
        """Regular fields should use d.field reference."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["state", "zip5"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"},
            filters={
                "state": {"not_null": True},  # Regular field
                "zip5": {"min_length": 5}      # Computed field
            }
        )
        
        query = strategy._build_collect_query()
        
        # Regular field uses d.field
        assert "FILTER d.state != null" in query
        # Computed field uses variable name
        assert "FILTER LENGTH(zip5) >= 5" in query
    
    def test_all_filter_types_on_computed_field(self, mock_db):
        """All filter types should work on computed fields."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["phone_norm"],
            computed_fields={"phone_norm": "REGEX_REPLACE(d.phone, '[^0-9]', '')"},
            filters={
                "phone_norm": {
                    "not_null": True,
                    "min_length": 10,
                    "max_length": 15,
                    "not_equal": ["0000000000", "1111111111"]
                }
            }
        )
        
        query = strategy._build_collect_query()
        
        assert "FILTER phone_norm != null" in query
        assert "FILTER LENGTH(phone_norm) >= 10" in query
        assert "FILTER LENGTH(phone_norm) <= 15" in query
        assert 'FILTER phone_norm != "0000000000"' in query
        assert 'FILTER phone_norm != "1111111111"' in query


class TestComputedFieldBlockingPairs:
    """Test actual pair generation with computed fields."""
    
    def test_generate_candidates_with_computed_field(self, mock_db):
        """Test end-to-end pair generation with computed fields."""
        # Mock the AQL cursor return value
        mock_cursor = [
            {
                "doc1_key": "1",
                "doc2_key": "2",
                "blocking_keys": {"address": "123 Main St", "zip5": "12345"},
                "block_size": 2,
                "method": "collect_blocking"
            },
            {
                "doc1_key": "3",
                "doc2_key": "4",
                "blocking_keys": {"address": "456 Oak Ave", "zip5": "67890"},
                "block_size": 2,
                "method": "collect_blocking"
            }
        ]
        mock_db.aql.execute.return_value = mock_cursor
        
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["address", "zip5"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
        )
        
        pairs = strategy.generate_candidates()
        
        assert len(pairs) == 2
        assert pairs[0]["doc1_key"] == "1"
        assert pairs[0]["doc2_key"] == "2"
        assert pairs[0]["blocking_keys"]["zip5"] == "12345"
        
        # Verify query was executed
        mock_db.aql.execute.assert_called_once()
        query = mock_db.aql.execute.call_args[0][0]
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
    
    def test_statistics_with_computed_fields(self, mock_db):
        """Statistics should include computed field information."""
        mock_db.aql.execute.return_value = []
        
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["zip5"],
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"}
        )
        
        pairs = strategy.generate_candidates()
        stats = strategy.get_statistics()
        
        assert "blocking_fields" in stats
        assert "zip5" in stats["blocking_fields"]


class TestComputedFieldEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_computed_fields(self, mock_db):
        """Empty computed_fields dict should work."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["state"],
            computed_fields={}
        )
        
        assert strategy.computed_fields == {}
        query = strategy._build_collect_query()
        # Should not have computed field LET statements (only the doc_keys LET is present)
        assert "LET zip5" not in query
        assert "LET phone" not in query
        # Verify it still has the standard doc_keys LET
        assert "LET doc_keys = group[*].d._key" in query
    
    def test_none_computed_fields(self, mock_db):
        """None computed_fields should default to empty dict."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["state"],
            computed_fields=None
        )
        
        assert strategy.computed_fields == {}
    
    def test_computed_field_not_in_blocking_fields(self, mock_db):
        """Computed field defined but not used in blocking should still be computed."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["state"],  # Only using state
            computed_fields={"zip5": "LEFT(d.postal_code, 5)"}  # zip5 defined but unused
        )
        
        query = strategy._build_collect_query()
        
        # Should still generate LET statement (might be used in filters)
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        # But not in COLLECT
        assert "COLLECT state = d.state" in query
        assert "zip5 = zip5" not in query.split("COLLECT")[1].split("INTO")[0]
    
    def test_only_computed_fields(self, mock_db):
        """Blocking with only computed fields (no regular fields)."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["zip5", "phone_norm"],
            computed_fields={
                "zip5": "LEFT(d.postal_code, 5)",
                "phone_norm": "REGEX_REPLACE(d.phone, '[^0-9]', '')"
            }
        )
        
        query = strategy._build_collect_query()
        
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        assert "LET phone_norm = REGEX_REPLACE(d.phone, '[^0-9]', '')" in query
        assert "COLLECT zip5 = zip5, phone_norm = phone_norm" in query
        # Should not reference any d.field in COLLECT
        collect_clause = query.split("COLLECT")[1].split("INTO")[0]
        assert "d." not in collect_clause
    
    def test_computed_field_with_conditional(self, mock_db):
        """Computed field with conditional logic."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["contact_key"],
            computed_fields={
                "contact_key": "d.phone != null ? d.phone : SPLIT(d.email, '@')[1]"
            }
        )
        
        query = strategy._build_collect_query()
        
        assert "LET contact_key = d.phone != null ? d.phone : SPLIT(d.email, '@')[1]" in query
    
    def test_computed_field_with_nested_access(self, mock_db):
        """Computed field accessing nested document fields."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["city_state"],
            computed_fields={
                "city_state": "CONCAT(d.location.city, '_', d.location.state)"
            }
        )
        
        query = strategy._build_collect_query()
        
        assert "LET city_state = CONCAT(d.location.city, '_', d.location.state)" in query


class TestComputedFieldRealWorldScenarios:
    """Test real-world use cases from dnb_er migration."""
    
    def test_address_zip5_blocking(self, mock_db):
        """Real scenario: Address + ZIP5 blocking from dnb_er."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["address", "zip5"],
            computed_fields={
                "zip5": "LEFT(d.POSTAL_CODE, 5)"  # POSTAL_CODE is the actual field
            },
            filters={
                "address": {"not_null": True, "min_length": 5},
                "zip5": {"not_null": True, "min_length": 5}
            },
            max_block_size=50,
            min_block_size=2
        )
        
        query = strategy._build_collect_query()
        
        # Verify correct query structure
        assert "FOR d IN companies" in query
        assert "LET zip5 = LEFT(d.POSTAL_CODE, 5)" in query
        assert "FILTER d.address != null" in query
        assert "FILTER LENGTH(d.address) >= 5" in query
        assert "FILTER zip5 != null" in query
        assert "FILTER LENGTH(zip5) >= 5" in query
        assert "COLLECT address = d.address, zip5 = zip5" in query
        assert "FILTER LENGTH(doc_keys) >= 2" in query
        assert "FILTER LENGTH(doc_keys) <= 50" in query
    
    def test_phone_normalization_blocking(self, mock_db):
        """Real scenario: Normalized phone blocking."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="customers",
            blocking_fields=["phone_digits", "state"],
            computed_fields={
                "phone_digits": "REGEX_REPLACE(d.phone_number, '[^0-9]', '')"
            },
            filters={
                "phone_digits": {
                    "not_null": True,
                    "min_length": 10,
                    "not_equal": ["0000000000", "1111111111"]
                },
                "state": {"not_null": True}
            },
            max_block_size=100,
            min_block_size=2
        )
        
        query = strategy._build_collect_query()
        
        assert "LET phone_digits = REGEX_REPLACE(d.phone_number, '[^0-9]', '')" in query
        assert "FILTER phone_digits != null" in query
        assert "FILTER LENGTH(phone_digits) >= 10" in query
        assert 'FILTER phone_digits != "0000000000"' in query
        assert "COLLECT phone_digits = phone_digits, state = d.state" in query
    
    def test_multiple_derived_keys(self, mock_db):
        """Real scenario: Multiple derived blocking keys."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["name_key", "zip5", "state"],
            computed_fields={
                "name_key": "CONCAT(LEFT(UPPER(d.company_name), 3), '_', LEFT(d.ceo_last_name, 4))",
                "zip5": "LEFT(d.postal_code, 5)"
            },
            filters={
                "name_key": {"not_null": True, "min_length": 5},
                "zip5": {"min_length": 5},
                "state": {"not_null": True}
            },
            max_block_size=30,
            min_block_size=2
        )
        
        query = strategy._build_collect_query()
        
        assert "LET name_key = CONCAT(LEFT(UPPER(d.company_name), 3), '_', LEFT(d.ceo_last_name, 4))" in query
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        assert "COLLECT name_key = name_key, zip5 = zip5, state = d.state" in query


class TestComputedFieldDocumentation:
    """Test that examples from documentation actually work."""
    
    def test_docs_example_basic(self, mock_db):
        """Example from COMPUTED_FIELDS_GUIDE.md - basic."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="companies",
            blocking_fields=["address", "zip5"],
            computed_fields={
                "zip5": "LEFT(d.postal_code, 5)"
            },
            filters={
                "address": {"not_null": True, "min_length": 5},
                "zip5": {"not_null": True, "min_length": 5}
            },
            max_block_size=50,
            min_block_size=2
        )
        
        query = strategy._build_collect_query()
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query
        assert strategy.blocking_fields == ["address", "zip5"]
    
    def test_docs_example_phone_normalization(self, mock_db):
        """Example from COMPUTED_FIELDS_GUIDE.md - phone normalization."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="customers",
            blocking_fields=["phone_normalized", "state"],
            computed_fields={
                "phone_normalized": "REGEX_REPLACE(d.phone, '[^0-9]', '')"
            },
            filters={
                "phone_normalized": {
                    "not_null": True,
                    "min_length": 10,
                    "not_equal": ["0000000000", "1111111111"]
                },
                "state": {"not_null": True}
            },
            max_block_size=100,
            min_block_size=2
        )
        
        query = strategy._build_collect_query()
        assert "LET phone_normalized = REGEX_REPLACE(d.phone, '[^0-9]', '')" in query
    
    def test_docs_example_name_initials(self, mock_db):
        """Example from COMPUTED_FIELDS_GUIDE.md - name initials."""
        strategy = CollectBlockingStrategy(
            db=mock_db,
            collection="persons",
            blocking_fields=["name_key", "zip5"],
            computed_fields={
                "name_key": "CONCAT(LEFT(d.first_name, 1), LEFT(d.middle_name, 1), '_', d.last_name)",
                "zip5": "LEFT(d.postal_code, 5)"
            },
            filters={
                "name_key": {"not_null": True, "min_length": 3}
            },
            max_block_size=50,
            min_block_size=2
        )
        
        query = strategy._build_collect_query()
        assert "LET name_key = CONCAT(LEFT(d.first_name, 1), LEFT(d.middle_name, 1), '_', d.last_name)" in query
        assert "LET zip5 = LEFT(d.postal_code, 5)" in query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


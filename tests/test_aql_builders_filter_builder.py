import pytest

from entity_resolution.utils.aql_builders import build_aql_filter_conditions


def test_build_aql_filter_conditions_generates_conditions_and_bind_vars() -> None:
    conditions, bind_vars = build_aql_filter_conditions(
        {
            "name": {"not_null": True, "equals": "Acme", "min_length": 3},
            "status": {"not_equal": ["inactive", "deleted"]},
        },
        var_name="d",
    )

    assert "d.name != null" in conditions
    assert "d.name == @filter_name_equals" in conditions
    assert "LENGTH(d.name) >= @filter_name_min_length" in conditions
    assert "d.status != @filter_status_not_equal_0" in conditions
    assert "d.status != @filter_status_not_equal_1" in conditions

    assert bind_vars["filter_name_equals"] == "Acme"
    assert bind_vars["filter_name_min_length"] == 3
    assert bind_vars["filter_status_not_equal_0"] == "inactive"
    assert bind_vars["filter_status_not_equal_1"] == "deleted"


def test_build_aql_filter_conditions_rejects_invalid_field_name() -> None:
    with pytest.raises(ValueError, match="field name"):
        build_aql_filter_conditions({"bad-name": {"equals": "x"}}, var_name="d")


def test_build_aql_filter_conditions_supports_computed_field_map() -> None:
    conditions, bind_vars = build_aql_filter_conditions(
        {"zip5": {"equals": "12345"}},
        var_name="d",
        computed_field_map={"zip5": "_computed_zip5"},
    )

    assert "_computed_zip5 == @filter_zip5_equals" in conditions
    assert bind_vars["filter_zip5_equals"] == "12345"


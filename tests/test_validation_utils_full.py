import pytest

from entity_resolution.utils.validation import (
    sanitize_string_for_display,
    validate_collection_name,
    validate_database_name,
    validate_field_name,
    validate_field_names,
    validate_graph_name,
    validate_view_name,
)


def test_validate_collection_name_accepts_valid() -> None:
    assert validate_collection_name("companies") == "companies"
    assert validate_collection_name("test_collection_123") == "test_collection_123"


@pytest.mark.parametrize(
    "name",
    [
        "",
        None,
        123,
        "1bad",
        "_system_like",
        "bad-name",
        "bad name",
        "bad$name",
        "a" * 257,
    ],
)
def test_validate_collection_name_rejects_invalid(name) -> None:
    with pytest.raises(ValueError):
        validate_collection_name(name)  # type: ignore[arg-type]


def test_validate_field_name_accepts_nested_by_default() -> None:
    assert validate_field_name("first_name") == "first_name"
    assert validate_field_name("address.city") == "address.city"
    assert validate_field_name("a.b_c.d1") == "a.b_c.d1"


def test_validate_field_name_rejects_nested_when_disallowed() -> None:
    with pytest.raises(ValueError):
        validate_field_name("address.city", allow_nested=False)


@pytest.mark.parametrize(
    "name",
    [
        "",
        None,
        123,
        "bad-field!",
        "bad field",
        "a" * 257,
    ],
)
def test_validate_field_name_rejects_invalid(name) -> None:
    with pytest.raises(ValueError):
        validate_field_name(name)  # type: ignore[arg-type]


def test_validate_field_names_validates_list_and_elements() -> None:
    assert validate_field_names(["a", "b_c", "d.e"]) == ["a", "b_c", "d.e"]
    assert validate_field_names(["a", "b_c"], allow_nested=False) == ["a", "b_c"]

    with pytest.raises(ValueError):
        validate_field_names("not-a-list")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        validate_field_names(["ok", "bad-field!"])


def test_validate_graph_and_view_name_delegate_to_collection_rules() -> None:
    assert validate_graph_name("graph1") == "graph1"
    assert validate_view_name("my_view") == "my_view"

    with pytest.raises(ValueError):
        validate_graph_name("bad-name")
    with pytest.raises(ValueError):
        validate_view_name("bad-view")


@pytest.mark.parametrize(
    "name",
    [
        "",
        None,
        123,
        "1bad",
        "bad.name",
        "bad name",
        "a" * 65,
    ],
)
def test_validate_database_name_rejects_invalid(name) -> None:
    with pytest.raises(ValueError):
        validate_database_name(name)  # type: ignore[arg-type]


def test_validate_database_name_accepts_valid() -> None:
    assert validate_database_name("entity_resolution_test") == "entity_resolution_test"
    assert validate_database_name("my-db_1") == "my-db_1"


def test_sanitize_string_for_display_removes_control_chars_and_truncates() -> None:
    s = "hello\u0000world\t\nok"
    out = sanitize_string_for_display(s, max_length=100)
    assert out == "hello?world\t\nok"

    out2 = sanitize_string_for_display("x" * 10, max_length=5)
    assert out2 == "xxxxx..."


def test_sanitize_string_for_display_coerces_non_string() -> None:
    assert sanitize_string_for_display(12345) == "12345"


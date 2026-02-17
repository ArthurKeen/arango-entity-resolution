"""
AQL query builder helpers.

These utilities are intentionally pure and side-effect free so they can be reused
across strategies/services and unit tested easily.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .validation import validate_field_name


def _normalize_bind_var_fragment(value: str) -> str:
    """
    Normalize an arbitrary string into a safe bind-var name fragment.

    AQL bind var identifiers must be [A-Za-z_][A-Za-z0-9_]*.
    """
    frag = re.sub(r"[^a-zA-Z0-9_]", "_", value)
    frag = re.sub(r"_+", "_", frag).strip("_")
    if not frag:
        frag = "field"
    if frag[0].isdigit():
        frag = f"f_{frag}"
    return frag


def build_aql_filter_conditions(
    field_filters: Dict[str, Any],
    *,
    var_name: str,
    computed_field_map: Optional[Dict[str, str]] = None,
    bind_var_prefix: str = "filter",
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Build AQL filter conditions using bind variables.

    Args:
        field_filters: Filter specs keyed by field name.
        var_name: AQL variable name to prefix document fields with (e.g. "d", "doc", "node").
        computed_field_map: Optional mapping of computed field name -> AQL reference (e.g. "_computed_zip5").
            When provided, filters for those fields will use the mapped reference instead of "{var_name}.{field}".
        bind_var_prefix: Prefix for generated bind variable names.

    Supported operators (subset used across the codebase today):
        - not_null: bool
        - equals: any
        - not_equal: any | list[any]
        - min_length: int
        - max_length: int
        - contains: str
        - regex: str

    Returns:
        (conditions, bind_vars)
    """
    computed_field_map = computed_field_map or {}
    conditions: List[str] = []
    bind_vars: Dict[str, Any] = {}

    for field_name, filters in (field_filters or {}).items():
        if not isinstance(filters, dict):
            continue

        # Determine reference (computed field vs regular document field).
        if field_name in computed_field_map:
            field_ref = computed_field_map[field_name]
        else:
            validate_field_name(field_name, allow_nested=True)
            field_ref = f"{var_name}.{field_name}"

        # not_null
        if filters.get("not_null"):
            conditions.append(f"{field_ref} != null")

        # equals
        if "equals" in filters:
            bind_name = f"{bind_var_prefix}_{_normalize_bind_var_fragment(field_name)}_equals"
            bind_vars[bind_name] = filters["equals"]
            conditions.append(f"{field_ref} == @{bind_name}")

        # not_equal
        if "not_equal" in filters:
            values = filters["not_equal"]
            if not isinstance(values, list):
                values = [values]
            for idx, value in enumerate(values):
                bind_name = f"{bind_var_prefix}_{_normalize_bind_var_fragment(field_name)}_not_equal_{idx}"
                bind_vars[bind_name] = value
                conditions.append(f"{field_ref} != @{bind_name}")

        # min_length / max_length
        if "min_length" in filters:
            bind_name = f"{bind_var_prefix}_{_normalize_bind_var_fragment(field_name)}_min_length"
            bind_vars[bind_name] = int(filters["min_length"])
            conditions.append(f"LENGTH({field_ref}) >= @{bind_name}")

        if "max_length" in filters:
            bind_name = f"{bind_var_prefix}_{_normalize_bind_var_fragment(field_name)}_max_length"
            bind_vars[bind_name] = int(filters["max_length"])
            conditions.append(f"LENGTH({field_ref}) <= @{bind_name}")

        # contains
        if "contains" in filters:
            bind_name = f"{bind_var_prefix}_{_normalize_bind_var_fragment(field_name)}_contains"
            bind_vars[bind_name] = str(filters["contains"])
            conditions.append(f"CONTAINS({field_ref}, @{bind_name})")

        # regex
        if "regex" in filters:
            bind_name = f"{bind_var_prefix}_{_normalize_bind_var_fragment(field_name)}_regex"
            bind_vars[bind_name] = str(filters["regex"])
            conditions.append(f"REGEX_TEST({field_ref}, @{bind_name})")

    return conditions, bind_vars


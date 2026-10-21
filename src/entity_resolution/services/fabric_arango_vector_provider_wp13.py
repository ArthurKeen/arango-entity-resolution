"""Deprecated alias of :mod:`entity_resolution.canonical_hub`.

Kept so that code importing the work-package path keeps working. Planned for
removal in 3.10.0, extended to 3.11.0 because a known consumer had not yet
migrated. Import from ``entity_resolution.canonical_hub``.
"""

import warnings

warnings.warn(
    "entity_resolution.services.fabric_arango_vector_provider_wp13 is deprecated "
    "and will be removed in 3.11.0; import from entity_resolution.canonical_hub",
    DeprecationWarning,
    stacklevel=2,
)

from entity_resolution.canonical_hub.arango_vector_provider import (  # noqa: E402,F401
    ArangoCanonicalHubVectorProvider,
)

__all__ = ["ArangoCanonicalHubVectorProvider"]

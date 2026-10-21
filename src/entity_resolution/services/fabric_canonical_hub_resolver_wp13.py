"""Deprecated alias of :mod:`entity_resolution.canonical_hub`.

Kept for one release so that code importing the work-package path keeps
working; removed in 3.10.0. Import from ``entity_resolution.canonical_hub``.
"""

import warnings

warnings.warn(
    "entity_resolution.services.fabric_canonical_hub_resolver_wp13 is deprecated "
    "and will be removed in 3.10.0; import from entity_resolution.canonical_hub",
    DeprecationWarning,
    stacklevel=2,
)

from entity_resolution.canonical_hub.resolver import *  # noqa: E402,F401,F403
from entity_resolution.canonical_hub.resolver import __all__  # noqa: E402,F401

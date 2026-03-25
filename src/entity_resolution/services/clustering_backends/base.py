"""Protocol definition for clustering backends."""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable


@runtime_checkable
class ClusteringBackend(Protocol):
    """Interface for pluggable WCC clustering backends.

    Each backend implements a different algorithm for finding weakly
    connected components in a similarity edge collection.  The ``cluster``
    method returns raw component lists; filtering by minimum size and
    persistence are handled by the calling service.
    """

    def cluster(self) -> List[List[str]]:
        """Return connected components as lists of document keys."""
        ...

    def backend_name(self) -> str:
        """Return the canonical backend identifier string."""
        ...

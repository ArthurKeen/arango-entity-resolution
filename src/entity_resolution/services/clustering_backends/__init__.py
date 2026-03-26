"""Pluggable clustering backends for WCC clustering."""

from .base import ClusteringBackend
from .python_dfs import PythonDFSBackend
from .python_union_find import PythonUnionFindBackend
from .aql_graph import AQLGraphBackend

__all__ = [
    "ClusteringBackend",
    "PythonDFSBackend",
    "PythonUnionFindBackend",
    "AQLGraphBackend",
]

try:
    from .python_sparse import PythonSparseBackend
    __all__.append("PythonSparseBackend")
except ImportError:
    pass

from .gae_wcc import GAEWCCBackend
__all__.append("GAEWCCBackend")

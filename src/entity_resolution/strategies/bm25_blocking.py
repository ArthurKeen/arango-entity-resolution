"""
BM25-based fuzzy blocking strategy using ArangoSearch.

This strategy uses ArangoDB's BM25 scoring for fast text similarity matching.
Much faster than Levenshtein for initial candidate generation, particularly
effective for name matching and fuzzy text search.
"""

from typing import Iterator, List, Dict, Any, Optional
from arango.database import StandardDatabase
import time

from .base_strategy import BlockingStrategy
from ..utils.validation import validate_view_name, validate_field_name

#: Bounds on the adaptive chunk size. The floor keeps request overhead from
#: dominating; the ceiling stops a fast early chunk from growing into one that
#: exceeds the client timeout later, when the view is larger or text is longer.
_MIN_CHUNK_SIZE = 100
_MAX_CHUNK_SIZE = 20_000


class BM25BlockingStrategy(BlockingStrategy):
    """
    BM25-based fuzzy blocking using ArangoSearch.
    
    Uses ArangoDB's BM25 scoring for fast text similarity matching. This is
    particularly effective for:
    - Name matching (company names, person names)
    - Fuzzy text search
    - Initial candidate generation before detailed similarity scoring
    
    Key benefits:
    - 400x faster than Levenshtein for initial filtering
    - Leverages ArangoSearch full-text capabilities
    - Configurable BM25 threshold
    - Optional blocking field for geographic/categorical constraints
    
    Requirements:
    - ArangoSearch view must be created on the collection
    - View must index the search field with appropriate analyzer
    
    Example:
        ```python
        # First create view (one-time setup):
        db.create_view(
            name='companies_search',
            view_type='arangosearch',
            properties={
                'links': {
                    'companies': {
                        'fields': {
                            'name': {'analyzers': ['text_en']}
                        }
                    }
                }
            }
        )
        
        # Then use strategy:
        strategy = BM25BlockingStrategy(
            db=db,
            collection='companies',
            search_view='companies_search',
            search_field='name',
            bm25_threshold=2.0,
            limit_per_entity=20,
            blocking_field='state'
        )
        pairs = strategy.generate_candidates()
        ```
    
    Performance: O(n log n) where n = number of documents
    """
    
    def __init__(
        self,
        db: StandardDatabase,
        collection: str,
        search_view: str,
        search_field: str,
        bm25_threshold: float = 2.0,
        limit_per_entity: int = 20,
        blocking_field: Optional[str] = None,
        filters: Optional[Dict[str, Dict[str, Any]]] = None,
        analyzer: str = "text_en",
        match_mode: str = "tokens",
        chunk_size: int = 1000,
        chunk_target_seconds: float = 20.0
    ):
        """
        Initialize BM25-based blocking strategy.
        
        Args:
            db: ArangoDB database connection
            collection: Source collection name
            search_view: ArangoSearch view name (must be created beforehand)
            search_field: Field to perform BM25 search on (e.g., "company_name")
            bm25_threshold: Minimum BM25 score to include. Higher values = stricter
                matching. Typical range: 1.0-5.0. Default 2.0.
            limit_per_entity: Maximum candidates per source entity. Prevents
                explosion with common names. Default 20.
            blocking_field: Optional field to constrain matches (e.g., "state").
                Only matches entities with same value in this field.
            filters: Optional filters per field (see base class for format)
            analyzer: ArangoSearch analyzer to use. Default "text_en".
                Must match analyzer configured in the view.
            match_mode: How a candidate is matched against the source text.

                ``"tokens"`` (default) — disjunctive token match ranked by
                BM25. Records are candidates when they share any token, and
                BM25 ranks by how much they share, weighting rare tokens
                higher. This is the standard formulation for text blocking and
                tolerates word-order differences and extra words.

                ``"phrase"`` — legacy behaviour, requiring the source text to
                appear in the candidate as an exact consecutive token sequence.
                This is near-exact matching, not fuzzy: on the Abt-Buy
                benchmark it produced ZERO candidate pairs, because product
                titles differ in word order and length. Retained only for
                callers that depend on it.
        
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        super().__init__(db, collection, filters)
        
        # Validate inputs first
        if not search_view:
            raise ValueError("search_view cannot be empty")
        if not search_field:
            raise ValueError("search_field cannot be empty")
        if bm25_threshold <= 0:
            raise ValueError("bm25_threshold must be positive")
        if limit_per_entity <= 0:
            raise ValueError("limit_per_entity must be positive")
        
        # Validate names for security (prevent AQL injection)
        self.search_view = validate_view_name(search_view)
        self.search_field = validate_field_name(search_field)
        self.bm25_threshold = bm25_threshold
        self.limit_per_entity = limit_per_entity
        self.blocking_field = validate_field_name(blocking_field) if blocking_field else None
        if match_mode not in ("tokens", "phrase"):
            raise ValueError(
                f"match_mode must be 'tokens' or 'phrase', got {match_mode!r}"
            )
        if chunk_size < 0:
            raise ValueError("chunk_size must be non-negative (0 disables chunking)")
        if chunk_target_seconds <= 0:
            raise ValueError("chunk_target_seconds must be positive")
        #: INITIAL source documents per request; adapted at runtime toward
        #: chunk_target_seconds, so no single query approaches the client
        #: read timeout regardless of collection size or text length.
        self.chunk_size = chunk_size
        #: Wall-clock budget per request. Comfortably under python-arango's
        #: 60s default so a slow chunk still returns rather than timing out.
        self.chunk_target_seconds = chunk_target_seconds
        self._doc_count: Optional[int] = None
        self.match_mode = match_mode
        # The analyzer is interpolated into the query, so it must be validated
        # like any other identifier rather than trusted from config.
        self.analyzer = validate_field_name(analyzer)
    
    def generate_candidates(self) -> List[Dict[str, Any]]:
        """
        Generate candidate pairs using BM25 fuzzy matching.
        
        Process:
        1. Apply filters to source documents
        2. For each document, search for similar documents using BM25
        3. Filter by BM25 threshold
        4. Optionally constrain by blocking field (e.g., same state)
        5. Limit candidates per entity
        6. Return candidate pairs with BM25 scores
        
        Returns:
            List of candidate pairs:
            [
                {
                    "doc1_key": "123",
                    "doc2_key": "456",
                    "bm25_score": 5.2,
                    "search_field": "company_name",
                    "blocking_field_value": "CA",  # If blocking_field specified
                    "method": "bm25_blocking"
                },
                ...
            ]
        
        Performance: O(n log n) - faster than exact matching for fuzzy text
        """
        start_time = time.time()

        pairs = list(self.iter_candidates())

        # Normalize pairs
        normalized_pairs = self._normalize_pairs(pairs)
        
        # Update statistics
        execution_time = time.time() - start_time
        self._update_statistics(normalized_pairs, execution_time)
        
        # Add additional stats
        self._stats.update({
            'search_view': self.search_view,
            'search_field': self.search_field,
            'bm25_threshold': self.bm25_threshold,
            'limit_per_entity': self.limit_per_entity,
            'blocking_field': self.blocking_field,
            'avg_bm25_score': self._calculate_avg_bm25_score(normalized_pairs),
            'max_bm25_score': self._calculate_max_bm25_score(normalized_pairs)
        })
        
        return normalized_pairs
    
    def iter_candidates(self, chunk_size: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        """Yield candidate pairs, executing the search in bounded chunks.

        The strategy previously issued ONE query containing a per-document
        subquery over the whole collection and materialised every pair before
        returning. Measured on the DBLP-Scholar benchmark (66,879 documents),
        that took 19.3 minutes against 7.1 seconds for 4,910 — roughly 13x the
        records for 164x the time — and the single request exceeded
        python-arango's default 60-second read timeout, so any direct caller
        above ~10k records hit that first.

        Chunking bounds both: each request covers ``chunk_size`` source
        documents, so no single query runs long enough to time out, and a
        streaming caller can process pairs without holding them all in memory.

        Correctness note: chunking the OUTER loop is safe because each source
        document searches the entire view independently, so the set of pairs is
        unchanged — only the number of requests differs. The query sorts by
        ``_key`` before applying ``LIMIT``, without which two chunks could
        overlap or skip documents and silently lose pairs.

        Args:
            chunk_size: source documents per request. Defaults to
                ``self.chunk_size``. Pass ``0`` to force a single request
                (the pre-chunking behaviour).

        Yields:
            Raw candidate-pair dicts, before symmetric normalisation.
        """
        size = self.chunk_size if chunk_size is None else chunk_size
        base_bind = {
            "bm25_threshold": self.bm25_threshold,
            "limit_per_entity": self.limit_per_entity,
        }

        if not size or size <= 0:
            cursor = self.db.aql.execute(
                self._build_bm25_query(chunked=False), bind_vars=dict(base_bind)
            )
            yield from cursor
            return

        query = self._build_bm25_query(chunked=True)
        total_docs = self._source_document_count()
        offset = 0
        chunks = 0
        sizes: List[int] = []

        while offset < total_docs:
            started = time.time()
            bind_vars = dict(base_bind, chunk_offset=offset, chunk_size=size)
            cursor = self.db.aql.execute(query, bind_vars=bind_vars)
            for row in cursor:
                yield row
            elapsed = time.time() - started

            chunks += 1
            sizes.append(size)
            offset += size

            # Adapt to the measured per-document cost. A fixed chunk size cannot
            # be right for every workload: cost per source document scales with
            # the size of the view being searched and the length of the text, so
            # a size that is comfortable on 5k documents can exceed the client
            # timeout on 67k. Measured on DBLP-Scholar at ~17ms/document, a
            # 5,000-document chunk takes ~87s and still times out at the default
            # 60s. Targeting a wall-clock budget per request keeps every query
            # short regardless of workload.
            if elapsed > self.chunk_target_seconds and size > _MIN_CHUNK_SIZE:
                size = max(_MIN_CHUNK_SIZE, size // 2)
            elif elapsed < self.chunk_target_seconds / 3 and size < _MAX_CHUNK_SIZE:
                size = min(_MAX_CHUNK_SIZE, size * 2)

        self._stats["chunks_executed"] = chunks
        self._stats["chunk_sizes"] = sizes
        self._stats["chunk_size"] = sizes[-1] if sizes else size

    def _source_document_count(self) -> int:
        """Number of source documents, cached for the duration of a run."""
        if self._doc_count is None:
            self._doc_count = self.db.collection(self.collection).count()
        return self._doc_count

    def _build_bm25_query(self, chunked: bool = False) -> str:
        """
        Build the AQL query for BM25-based blocking.

        The query uses a per-entity subquery so that ``LIMIT
        @limit_per_entity`` applies *per source document* rather than
        globally. Earlier versions placed ``LIMIT`` at the outer level of
        a nested ``FOR``; in AQL that limits the flattened result stream
        across all (d1, d2) iterations, so the strategy returned exactly
        ``limit_per_entity`` pairs total regardless of collection size
        rather than the intended top-K candidates per source entity.

        Returns:
            AQL query string
        """
        # Outer loop: iterate source documents and apply d1-level filters.
        # SORT by _key before any LIMIT so chunked execution partitions the
        # collection deterministically: without a stable order, two chunks can
        # overlap or skip documents entirely and blocking silently loses pairs.
        query_parts = [f"FOR d1 IN {self.collection}"]
        if chunked:
            query_parts.append("    SORT d1._key")
            query_parts.append("    LIMIT @chunk_offset, @chunk_size")

        if self.filters:
            search_field_filters = self.filters.get(self.search_field, {})
            if search_field_filters:
                if search_field_filters.get('not_null'):
                    query_parts.append(f"    FILTER d1.{self.search_field} != null")
                if 'min_length' in search_field_filters:
                    try:
                        min_len = int(search_field_filters['min_length'])
                    except (TypeError, ValueError) as exc:
                        raise ValueError("filter min_length must be an integer") from exc
                    if min_len < 0:
                        raise ValueError("filter min_length must be non-negative")
                    query_parts.append(f"    FILTER LENGTH(d1.{self.search_field}) > {min_len}")

            if self.blocking_field and self.blocking_field in self.filters:
                blocking_filters = self.filters[self.blocking_field]
                if blocking_filters.get('not_null'):
                    query_parts.append(f"    FILTER d1.{self.blocking_field} != null")

        # Per-entity subquery: candidates for this specific d1. The
        # `LIMIT @limit_per_entity` lives inside this subquery, so it
        # caps results per source document. `SORT bm25_score DESC` makes
        # the limit pick the highest-scoring matches.
        if self.match_mode == "phrase":
            # Legacy: requires d1's text to appear in d2 as an exact consecutive
            # token sequence. Retained for callers that depend on it, but it is
            # near-exact matching, NOT fuzzy — see the match_mode docstring.
            search_expr = (
                f"                PHRASE(d2.{self.search_field}, "
                f"d1.{self.search_field}, \"{self.analyzer}\"),"
            )
        else:
            # Token mode (default): disjunctive token match ranked by BM25 —
            # the standard formulation for text blocking. Two records match on
            # any shared token and BM25 ranks by how much they share, weighting
            # rare tokens higher, so word order and extra words no longer matter.
            search_expr = (
                f"                d2.{self.search_field} IN "
                f"TOKENS(d1.{self.search_field}, \"{self.analyzer}\"),"
            )

        sub_parts = [
            f"    LET candidates = (",
            f"        FOR d2 IN {self.search_view}",
            f"            SEARCH ANALYZER(",
            search_expr,
            f"                \"{self.analyzer}\"",
            f"            )",
            f"            LET bm25_score = BM25(d2)",
            f"            FILTER bm25_score > @bm25_threshold",
        ]
        if self.blocking_field:
            sub_parts.append(
                f"            FILTER d2.{self.blocking_field} == d1.{self.blocking_field}"
            )
        sub_parts.extend([
            # Exclude only the self-pair. A `d1._key < d2._key` filter here
            # would interact with the per-entity LIMIT to silently drop real
            # pairs: if B's top-K contains A but A's top-K does not contain B,
            # the pair is only discoverable from B, and the key filter throws
            # exactly that direction away. Symmetric duplicates are collapsed
            # afterwards by _normalize_pairs, which costs nothing and loses
            # nothing.
            f"            FILTER d1._key != d2._key",
            f"            SORT bm25_score DESC",
            f"            LIMIT @limit_per_entity",
        ])

        sub_return_fields = [
            "doc2_key: d2._key",
            "bm25_score: bm25_score",
        ]
        if self.blocking_field:
            sub_return_fields.append(f"blocking_field_value: d2.{self.blocking_field}")
        sub_parts.append(
            "            RETURN {\n                "
            + ",\n                ".join(sub_return_fields)
            + "\n            }"
        )
        sub_parts.append("    )")
        query_parts.extend(sub_parts)

        # Outer return: flatten per-entity candidates with d1 metadata.
        query_parts.append("    FOR c IN candidates")
        return_fields = [
            "doc1_key: d1._key",
            "doc2_key: c.doc2_key",
            "bm25_score: c.bm25_score",
            f'search_field: "{self.search_field}"',
            'method: "bm25_blocking"',
        ]
        if self.blocking_field:
            return_fields.append("blocking_field_value: c.blocking_field_value")

        query_parts.append(
            "        RETURN {\n            "
            + ",\n            ".join(return_fields)
            + "\n        }"
        )

        return "\n".join(query_parts)
    
    def _calculate_avg_bm25_score(self, pairs: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate average BM25 score from pairs.
        
        Args:
            pairs: List of candidate pairs
        
        Returns:
            Average BM25 score or None if no pairs
        """
        if not pairs:
            return None
        
        scores = [p.get('bm25_score', 0) for p in pairs if 'bm25_score' in p]
        if not scores:
            return None
        
        return round(sum(scores) / len(scores), 2)
    
    def _calculate_max_bm25_score(self, pairs: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate maximum BM25 score from pairs.
        
        Args:
            pairs: List of candidate pairs
        
        Returns:
            Maximum BM25 score or None if no pairs
        """
        if not pairs:
            return None
        
        scores = [p.get('bm25_score', 0) for p in pairs if 'bm25_score' in p]
        if not scores:
            return None
        
        return round(max(scores), 2)
    
    def __repr__(self) -> str:
        """String representation of the strategy."""
        return (f"BM25BlockingStrategy("
                f"collection='{self.collection}', "
                f"search_view='{self.search_view}', "
                f"search_field='{self.search_field}', "
                f"threshold={self.bm25_threshold})")


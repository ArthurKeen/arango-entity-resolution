"""Estimate and persist EM model parameters from real candidate pairs (plan 1.1).

Ties the pure EM core (:mod:`entity_resolution.learning.em_estimator`) to a live
database: samples candidate pairs from the similarity-edge collection, recomputes
per-field agreement with the configured comparators, runs Fellegi-Sunter EM,
computes per-field term-frequency tables, and persists the learned parameters to
``er_model_params`` (versioned + config-hashed for reproducibility) and the TF
tables to ``er_term_frequencies``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .em_estimator import EMEstimator, EMResult
from ..utils.graph_utils import extract_key_from_vertex_id

logger = logging.getLogger(__name__)

_MODEL_COLLECTION = "er_model_params"
_TF_COLLECTION = "er_term_frequencies"


def config_hash(
    field_names: Sequence[str],
    agreement_thresholds: Dict[str, float],
    algorithm: str,
    comparison_levels: Optional[Dict[str, Any]] = None,
) -> str:
    """Stable hash identifying an estimation configuration.

    Comparison levels are part of the identity, not decoration: per-level m/u are
    estimated against a specific set of bands, so a model trained with
    ``[0.95, 0.7]`` means something different from one trained with
    ``[0.9, 0.5]``. Omitting levels from the hash would let the loader hand back
    parameters learned under different bins — the same silent-mismatch class of
    bug as reusing a model trained at another agreement threshold.

    Only the structure is hashed (names and thresholds, in order); the learned
    probabilities are the output, not the identity.
    """
    payload: Dict[str, Any] = {
        "fields": sorted(field_names),
        "thresholds": {k: agreement_thresholds[k] for k in sorted(agreement_thresholds)},
        "algorithm": algorithm,
    }
    if comparison_levels:
        payload["comparison_levels"] = {
            field: [
                [str(level.get("name")), level.get("min_similarity")]
                for level in comparison_levels[field]
            ]
            for field in sorted(comparison_levels)
        }
    return hashlib.md5(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def _collapse_to_binary(level_probs: Sequence[float]) -> float:
    """Binary-equivalent probability from a per-level vector.

    "Agrees" in binary terms means the comparison reached any level above the
    fallback, so the equivalent scalar is the total probability mass outside the
    final level. Clamped away from 0 and 1 because the scorer takes
    ``log(m/u)`` and ``log((1-m)/(1-u))``.
    """
    if not level_probs:
        return 0.5
    agree_mass = float(sum(level_probs[:-1]))
    return min(max(agree_mass, 1e-6), 1 - 1e-6)


class ModelParameterEstimator:
    """Sample → compare → EM → persist, against a live ArangoDB."""

    def __init__(
        self,
        db: Any,
        similarity_service: Any,
        edge_collection: str,
        field_names: Sequence[str],
        *,
        agreement_thresholds: Optional[Dict[str, float]] = None,
        default_threshold: float = 0.85,
        algorithm: Optional[str] = None,
        model_collection: str = _MODEL_COLLECTION,
        tf_collection: str = _TF_COLLECTION,
        comparison_levels: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db
        # A BatchSimilarityService (or anything exposing compute_similarities_detailed).
        self.similarity_service = similarity_service
        self.edge_collection = edge_collection
        self.field_names = list(field_names)
        self.agreement_thresholds = dict(agreement_thresholds or {})
        self.default_threshold = default_threshold
        self.model_collection = model_collection
        self.tf_collection = tf_collection
        self.algorithm = algorithm or getattr(
            similarity_service, "algorithm_name", "unknown"
        )
        #: Per-field comparison levels (structure only). When present, estimation
        #: is categorical over those bands instead of binary agree/disagree.
        self.comparison_levels = {
            field: [dict(level) for level in levels]
            for field, levels in (comparison_levels or {}).items()
            if field in set(self.field_names)
        }
        #: How u was obtained on the most recent estimate() call — persisted as
        #: provenance, since it materially changes what the weights mean.
        self._last_u_estimation: str = "unknown"

    # ------------------------------------------------------------------
    # Sampling + estimation
    # ------------------------------------------------------------------

    def sample_random_pair_comparisons(
        self, sample_size: int, source_collection: str
    ) -> List[Dict[str, float]]:
        """Compare RANDOM record pairs — the population ``u`` is defined over.

        Draws ``2 * sample_size`` random records in a single pass and pairs them
        off. Two records drawn at random from a real collection are
        overwhelmingly likely to be different entities, so their agreement rate
        estimates ``u`` (the probability a field agrees *by chance*) directly.

        This is deliberately NOT the candidate-edge population: those pairs
        already passed a similarity gate, so measuring ``u`` there conflates
        "non-match" with "near-match".
        """
        from ..utils.validation import validate_collection_name

        validate_collection_name(source_collection)
        cursor = self.db.aql.execute(
            """
            FOR d IN @@col
                SORT RAND()
                LIMIT @n
                RETURN d._key
            """,
            bind_vars={"@col": source_collection, "n": int(sample_size) * 2},
        )
        keys = [k for k in cursor if k]
        if len(keys) < 2:
            return []

        half = len(keys) // 2
        pairs: List[Tuple[str, str]] = [
            (a, b) for a, b in zip(keys[:half], keys[half : half * 2]) if a != b
        ]
        if not pairs:
            return []

        detailed = self.similarity_service.compute_similarities_detailed(
            pairs, threshold=0.0, preserve_missing=True
        )
        return [d.get("field_scores", {}) for d in detailed]

    def estimate_u_from_random_pairs(
        self, sample_size: int, source_collection: str
    ) -> Dict[str, float]:
        """Measure per-field ``u`` as the agreement rate among random pairs.

        ``u_f = P(field f agrees | the pair is NOT a match)``. Because random
        pairs are effectively all non-matches, this is a direct count rather
        than something EM has to infer — and it is only counted over pairs where
        the field was actually observed, matching the null-level convention used
        by the scorer and by :meth:`EMEstimator.build_gamma`.

        Returns an empty dict when no random pairs could be drawn, so callers
        can fall back to joint EM estimation.
        """
        comparisons = self.sample_random_pair_comparisons(sample_size, source_collection)
        if not comparisons:
            return {}

        agree_counts: Dict[str, int] = {f: 0 for f in self.field_names}
        observed_counts: Dict[str, int] = {f: 0 for f in self.field_names}
        for comp in comparisons:
            for field in self.field_names:
                value = comp.get(field)
                if value is None:
                    continue  # unobserved: carries no information about u
                observed_counts[field] += 1
                threshold = self.agreement_thresholds.get(field, self.default_threshold)
                if value >= threshold:
                    agree_counts[field] += 1

        u_values: Dict[str, float] = {}
        for field in self.field_names:
            observed = observed_counts[field]
            if observed == 0:
                continue  # never observed — leave it to the EM default
            # Clamp away from 0: a field that never agreed by chance in the
            # sample would otherwise make log(m/u) infinite.
            u_values[field] = max(agree_counts[field] / observed, 1.0 / (observed + 1))
        return u_values

    def sample_comparisons(self, sample_size: int) -> List[Dict[str, float]]:
        """Sample non-suppressed candidate pairs and compute per-field scores.

        This is the right population for estimating ``m`` (agreement given a
        match): true matches are concentrated among the candidates that survived
        blocking. It is the WRONG population for ``u`` — see
        :meth:`estimate_u_from_random_pairs`.
        """
        cursor = self.db.aql.execute(
            """
            FOR e IN @@edges
                FILTER e.suppressed != true
                SORT RAND()
                LIMIT @n
                RETURN [e._from, e._to]
            """,
            bind_vars={"@edges": self.edge_collection, "n": int(sample_size)},
        )
        pairs: List[Tuple[str, str]] = [
            (extract_key_from_vertex_id(a), extract_key_from_vertex_id(b)) for a, b in cursor
        ]
        if not pairs:
            return []
        detailed = self.similarity_service.compute_similarities_detailed(
            pairs, threshold=0.0, preserve_missing=True
        )
        return [d.get("field_scores", {}) for d in detailed]

    def estimate(
        self,
        sample_size: int = 100_000,
        *,
        max_iterations: int = 50,
        tol: float = 1e-5,
        source_collection: Optional[str] = None,
        u_sample_size: int = 10_000,
    ) -> EMResult:
        """Estimate m/u/lambda.

        When ``source_collection`` is given, ``u`` is first measured from random
        record pairs drawn from it and then held fixed while EM estimates ``m``
        and ``lambda`` over the candidate pairs. This two-population split is the
        correct construction: candidate pairs are the right sample for ``m`` but
        a biased one for ``u``, because they all cleared a similarity threshold.

        Without ``source_collection`` the estimator falls back to joint EM over
        candidates alone, which is left available for backward compatibility but
        yields an inflated ``u`` and correspondingly compressed match weights.
        The choice is recorded on the persisted model as ``u_estimation``.
        """
        comparisons = self.sample_comparisons(sample_size)
        if not comparisons:
            raise ValueError(
                f"no candidate pairs sampled from '{self.edge_collection}'; "
                "run blocking/edge creation first"
            )

        fixed_u: Dict[str, float] = {}
        if source_collection:
            fixed_u = self.estimate_u_from_random_pairs(
                u_sample_size, source_collection
            )
            if fixed_u:
                logger.info(
                    "Estimated u from %d random pairs over '%s': %s",
                    u_sample_size, source_collection,
                    {k: round(v, 4) for k, v in fixed_u.items()},
                )
            else:
                logger.warning(
                    "Could not draw random pairs from '%s'; falling back to "
                    "joint EM estimation of u (biased upward).",
                    source_collection,
                )

        estimator = EMEstimator(
            field_names=self.field_names,
            agreement_thresholds=self.agreement_thresholds,
            default_threshold=self.default_threshold,
            max_iterations=max_iterations,
            tol=tol,
        )
        if self.comparison_levels:
            # Categorical estimation over the configured bands. fixed_u from
            # random pairs is a per-field scalar (P(agree | non-match)), which
            # cannot be spread across levels without inventing a shape, so it is
            # not forwarded here; u is learned jointly and recorded as such
            # rather than mislabelled as measured.
            logger.info(
                "Estimating categorical m/u over configured comparison levels for %s",
                sorted(self.comparison_levels),
            )
            result = estimator.estimate_categorical(
                comparisons, self.comparison_levels
            )
            self._last_u_estimation = "joint_em_categorical"
            return result

        result = estimator.estimate(comparisons, fixed_u=fixed_u or None)
        self._last_u_estimation = (
            "random_pairs" if fixed_u else "joint_em_candidates_only"
        )
        return result

    # ------------------------------------------------------------------
    # Term frequencies (Splink's second pillar)
    # ------------------------------------------------------------------

    def compute_term_frequencies(
        self,
        source_collection: str,
        fields: Sequence[str],
        *,
        top_n: int = 100,
    ) -> Dict[str, Any]:
        """Per-field value frequencies via one COLLECT per field.

        Stores the ``top_n`` most common values and the total non-null count per
        field, so the scorer can scale u-probability by relative value frequency
        (a common value agreeing is weaker evidence than a rare one).
        """
        from ..utils.validation import validate_collection_name, validate_field_name

        validate_collection_name(source_collection)
        tables: Dict[str, Any] = {}
        for field in fields:
            validate_field_name(field)
            cursor = self.db.aql.execute(
                f"""
                FOR d IN @@col
                    FILTER d.{field} != null
                    COLLECT value = d.{field} WITH COUNT INTO cnt
                    SORT cnt DESC
                    LIMIT @top_n
                    RETURN {{value: value, count: cnt}}
                """,
                bind_vars={"@col": source_collection, "top_n": int(top_n)},
            )
            rows = list(cursor)
            total_cursor = self.db.aql.execute(
                f"""
                FOR d IN @@col
                    FILTER d.{field} != null
                    COLLECT WITH COUNT INTO cnt
                    RETURN cnt
                """,
                bind_vars={"@col": source_collection},
            )
            total = next(iter(total_cursor), 0)
            tables[field] = {
                "total": total,
                "top_values": [
                    {"value": r["value"], "count": r["count"],
                     "relative_frequency": (r["count"] / total) if total else 0.0}
                    for r in rows
                ],
            }
        return tables

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _ensure(self, name: str) -> None:
        if not self.db.has_collection(name):
            self.db.create_collection(name)

    def _next_version(self, chash: str) -> int:
        self._ensure(self.model_collection)
        cursor = self.db.aql.execute(
            """
            FOR d IN @@col FILTER d.config_hash == @h
                COLLECT AGGREGATE mx = MAX(d.version) RETURN mx
            """,
            bind_vars={"@col": self.model_collection, "h": chash},
        )
        current = next(iter(cursor), None)
        return int(current) + 1 if current else 1

    def persist(self, result: EMResult, *, sample_size: int) -> Dict[str, Any]:
        """Persist an EM result to ``er_model_params`` (versioned, config-hashed)."""
        chash = self.configuration_hash()
        version = self._next_version(chash)
        doc = {
            "_key": f"{chash}_v{version}",
            "config_hash": chash,
            "version": version,
            "algorithm": self.algorithm,
            "fields": result.fields,
            "agreement_thresholds": self._effective_thresholds(),
            "m": result.m,
            "u": result.u,
            "lambda": result.lambda_,
            "converged": result.converged,
            "iterations": result.iterations,
            "n_pairs": result.n_pairs,
            "log_likelihood": result.log_likelihood,
            "sample_size": sample_size,
            # Provenance: "random_pairs" means u was measured on an unbiased
            # non-match sample; "joint_em_candidates_only" means it was inferred
            # from candidates alone and is inflated. Weights are not comparable
            # across the two, so consumers must be able to tell them apart.
            "u_estimation": self._last_u_estimation,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        # Multi-level models carry their learned per-level probabilities plus the
        # band structure they were estimated against. Both are needed to rebuild
        # the scorer: the probabilities are meaningless without the thresholds
        # that produced them.
        levels = getattr(result, "level_names", None)
        if levels:
            doc["model_type"] = "categorical"
            doc["comparison_levels"] = self._learned_comparison_levels(result)
            doc["level_observed_counts"] = dict(result.observed_counts)
            # A categorical result's m/u are per-level VECTORS, but the scorer's
            # base model is scalar per field (it drives fields without levels and
            # the term-frequency adjustment). Collapse to the binary equivalent —
            # P(reaches any level above the fallback) — so a categorical model
            # still loads through the same code path. Writing the vectors here
            # would make FellegiSunterScorer clip a list and fail at load.
            doc["m"] = {f: _collapse_to_binary(result.m[f]) for f in result.fields}
            doc["u"] = {f: _collapse_to_binary(result.u[f]) for f in result.fields}
            doc["m_levels"] = {f: list(result.m[f]) for f in result.fields}
            doc["u_levels"] = {f: list(result.u[f]) for f in result.fields}
        else:
            doc["model_type"] = "binary"
        self.db.collection(self.model_collection).insert(doc, overwrite=True)
        return doc

    def _learned_comparison_levels(self, result: Any) -> Dict[str, Any]:
        """Merge learned m/u back into the configured band structure."""
        thresholds = {
            field: [level.get("min_similarity") for level in levels]
            for field, levels in self.comparison_levels.items()
        }
        return result.to_comparison_levels(
            {f: thresholds[f] for f in result.fields if f in thresholds}
        )

    def persist_term_frequencies(self, tables: Dict[str, Any]) -> int:
        """Persist TF tables, one doc per field (overwrite by field key)."""
        self._ensure(self.tf_collection)
        coll = self.db.collection(self.tf_collection)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        count = 0
        for field, table in tables.items():
            coll.insert(
                {"_key": field, "field": field, "updated_at": now, **table},
                overwrite=True,
            )
            count += 1
        return count

    def _effective_thresholds(self) -> Dict[str, float]:
        return {f: self.agreement_thresholds.get(f, self.default_threshold) for f in self.field_names}

    def configuration_hash(self) -> str:
        """Stable identity for the exact comparison model this estimator uses."""
        return config_hash(
            self.field_names,
            self._effective_thresholds(),
            self.algorithm,
            self.comparison_levels or None,
        )

    def list_model_configurations(self) -> List[Dict[str, Any]]:
        """Summarise the configurations models have been trained under.

        Used to explain a lookup miss: a model existing under a *different*
        configuration is a different situation from no model at all, and the
        two need different fixes.
        """
        if not self.db.has_collection(self.model_collection):
            return []
        cursor = self.db.aql.execute(
            """
            FOR d IN @@col
                COLLECT h = d.config_hash
                AGGREGATE latest = MAX(d.version), trained = MAX(d.created_at)
                RETURN { config_hash: h, version: latest, created_at: trained }
            """,
            bind_vars={"@col": self.model_collection},
        )
        return list(cursor)

    def load_term_frequencies(self) -> Dict[str, Dict[Any, float]]:
        """Load persisted TF tables as ``{field: {value: relative_frequency}}``.

        Returns an empty dict when the collection does not exist yet, so a
        scorer can be built before any TF run has happened.
        """
        from .fellegi_sunter_scorer import term_frequency_tables_from_docs

        if not self.db.has_collection(self.tf_collection):
            return {}
        docs = list(self.db.collection(self.tf_collection).all())
        return term_frequency_tables_from_docs(docs)

    def load_latest(self, chash: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load the most recent model parameters, optionally for one config.

        With ``chash``, returns the highest version for that configuration.

        Without it, returns the most recently **created** model. Sorting by
        ``version`` alone is ambiguous across configurations: each config hash
        starts its own version sequence at 1, so several models can share
        ``version == 1`` and the winner is whichever the storage engine happens
        to return. That silently hands back a model trained under a *different*
        field set and agreement thresholds than the caller is scoring with —
        which is not a hypothetical, since retraining after any config change
        produces exactly this state.

        Prefer passing ``chash`` (see :func:`config_hash`) whenever the
        configuration is known; it is the only way to guarantee the parameters
        match the comparisons being made.
        """
        if not self.db.has_collection(self.model_collection):
            return None
        bind: Dict[str, Any] = {"@col": self.model_collection}
        if chash:
            bind["h"] = chash
            query = (
                "FOR d IN @@col FILTER d.config_hash == @h "
                "SORT d.version DESC LIMIT 1 RETURN d"
            )
        else:
            query = (
                "FOR d IN @@col SORT d.created_at DESC, d.version DESC "
                "LIMIT 1 RETURN d"
            )
        cursor = self.db.aql.execute(query, bind_vars=bind)
        return next(iter(cursor), None)

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(
        self,
        source_collection: str,
        *,
        sample_size: int = 100_000,
        with_term_frequencies: bool = True,
        tf_fields: Optional[Sequence[str]] = None,
        u_sample_size: int = 10_000,
    ) -> Dict[str, Any]:
        """Estimate, persist, and (optionally) compute/persist term frequencies.

        ``source_collection`` is passed through to :meth:`estimate` so ``u`` is
        measured from random record pairs rather than inferred from the biased
        candidate population.
        """
        result = self.estimate(
            sample_size,
            source_collection=source_collection,
            u_sample_size=u_sample_size,
        )
        model_doc = self.persist(result, sample_size=sample_size)
        out: Dict[str, Any] = {
            "model": result.to_dict(),
            "model_key": model_doc["_key"],
            "version": model_doc["version"],
            "u_estimation": model_doc["u_estimation"],
        }
        if with_term_frequencies:
            fields = list(tf_fields) if tf_fields else self.field_names
            tables = self.compute_term_frequencies(source_collection, fields)
            out["term_frequency_fields"] = self.persist_term_frequencies(tables)
        return out

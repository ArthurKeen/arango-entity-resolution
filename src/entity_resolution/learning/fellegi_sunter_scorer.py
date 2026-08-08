"""Fellegi-Sunter posterior scorer fed by learned (or configured) m/u.

Turns per-field similarity scores into a calibrated match posterior using
per-field m/u probabilities (typically EM-learned, see
:class:`entity_resolution.learning.model_parameter_estimator.ModelParameterEstimator`).
This is the runtime counterpart of the honest FS math added to the legacy
scorer in plan 0.2 — extracted so the active ``BatchSimilarityService`` path can
consume learned parameters.

``score(field_scores)`` returns the posterior P(match | agreement pattern):

    logit(posterior) = logit(prior) + sum_f LLR_f
    LLR_f = log(m_f / u_f)         if field f agrees (sim >= threshold)
          = log((1-m_f)/(1-u_f))   if field f is observed and disagrees
          = 0                      if field f is NOT OBSERVED on this pair

The third case is the **null comparison level** and it matters a great deal.
"Absent" is not evidence of difference: a record that simply lacks a phone
number has not disagreed about its phone number. Charging the disagreement LLR
for missing data systematically drives sparse records below threshold, so
identical-but-incomplete records fail to merge — one of the classic
record-linkage defects, and previously the behaviour here.

A field counts as unobserved when it is absent from ``field_scores`` or maps to
``None``. Callers must therefore preserve ``None`` rather than coercing missing
similarities to ``0.0``, which is indistinguishable from "compared, totally
different". :class:`~entity_resolution.services.batch_similarity_service.BatchSimilarityService`
passes ``preserve_missing=True`` for exactly this reason.

The same convention holds during training: :meth:`EMEstimator.build_gamma` emits
``NaN`` for unobserved fields and :func:`estimate_mu` estimates each field's
m/u only over the pairs where that field was observed. Training and scoring
therefore share one definition of "no evidence" — if they disagreed, the learned
parameters would be applied under a different model than the one that produced
them.

The posterior is in [0, 1] and monotone in the summed log-likelihood ratio.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

_EPS = 1e-6


class FellegiSunterScorer:
    """Scores per-field similarities into a calibrated match posterior."""

    def __init__(
        self,
        m: Mapping[str, float],
        u: Mapping[str, float],
        *,
        agreement_thresholds: Optional[Mapping[str, float]] = None,
        default_threshold: float = 0.85,
        match_prior: float = 0.5,
        term_frequencies: Optional[Mapping[str, Mapping[Any, float]]] = None,
        comparison_levels: Optional[
            Mapping[str, List[Mapping[str, Any]]]
        ] = None,
    ) -> None:
        """
        Args:
            m: per-field P(agree | match).
            u: per-field P(agree | non-match) — the chance agreement rate.
            agreement_thresholds: per-field similarity cutoff for "agrees".
            default_threshold: cutoff for fields with no explicit threshold.
            match_prior: prior P(match) for a candidate pair.
            term_frequencies: optional ``{field: {value: relative_frequency}}``
                enabling term-frequency adjustment (see :meth:`total_llr`).
                Build it from the ``er_term_frequencies`` collection via
                :func:`term_frequency_tables_from_docs`.
            comparison_levels: optional per-field ordered categorical levels.
                Each level has ``name``, ``m``, ``u`` and, except for the final
                fallback, ``min_similarity``. When omitted, the established
                binary agree/disagree model is used unchanged.
        """
        if not m or not u:
            raise ValueError("m and u must be non-empty per-field probability maps")
        self.fields = [f for f in m if f in u]
        if not self.fields:
            raise ValueError("m and u share no fields")
        self.m = {f: _clip(m[f]) for f in self.fields}
        self.u = {f: _clip(u[f]) for f in self.fields}
        self.agreement_thresholds = dict(agreement_thresholds or {})
        self.default_threshold = default_threshold
        self.match_prior = min(max(match_prior, _EPS), 1 - _EPS)
        self._prior_logit = math.log(self.match_prior / (1 - self.match_prior))
        self.term_frequencies: Dict[str, Dict[Any, float]] = {
            field: dict(table)
            for field, table in (term_frequencies or {}).items()
            if field in self.m
        }
        # Precompute per-field agree/disagree LLRs.
        self._llr_agree = {f: math.log(self.m[f] / self.u[f]) for f in self.fields}
        self._llr_disagree = {
            f: math.log((1 - self.m[f]) / (1 - self.u[f])) for f in self.fields
        }
        self.comparison_levels = self._normalise_comparison_levels(
            comparison_levels or {}
        )

    def _normalise_comparison_levels(
        self,
        configured: Mapping[str, List[Mapping[str, Any]]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Validate and precompute ordered multi-level comparison weights."""
        normalised: Dict[str, List[Dict[str, Any]]] = {}
        for field, raw_levels in configured.items():
            if field not in self.m:
                continue
            if not raw_levels:
                raise ValueError(
                    f"comparison_levels[{field!r}] must contain at least one level"
                )

            levels: List[Dict[str, Any]] = []
            previous_threshold = float("inf")
            fallback_seen = False
            names = set()
            for index, raw in enumerate(raw_levels):
                name = str(raw.get("name") or "").strip()
                if not name or name in names:
                    raise ValueError(
                        f"comparison levels for {field!r} need unique non-empty names"
                    )
                names.add(name)
                level_m = _clip(raw["m"])
                level_u = _clip(raw["u"])
                threshold = raw.get("min_similarity")
                if threshold is None:
                    if index != len(raw_levels) - 1:
                        raise ValueError(
                            f"fallback comparison level for {field!r} must be last"
                        )
                    fallback_seen = True
                else:
                    threshold = float(threshold)
                    if not 0.0 <= threshold <= 1.0:
                        raise ValueError("comparison level thresholds must be in [0, 1]")
                    if threshold >= previous_threshold:
                        raise ValueError(
                            f"comparison levels for {field!r} must use descending thresholds"
                        )
                    previous_threshold = threshold

                levels.append({
                    "name": name,
                    "min_similarity": threshold,
                    "m": level_m,
                    "u": level_u,
                    "llr": math.log(level_m / level_u),
                })

            if not fallback_seen:
                raise ValueError(
                    f"comparison_levels[{field!r}] requires a final fallback level"
                )
            if abs(sum(level["m"] for level in levels) - 1.0) > 1e-3:
                raise ValueError(
                    f"comparison-level m probabilities for {field!r} must sum to 1"
                )
            if abs(sum(level["u"] for level in levels) - 1.0) > 1e-3:
                raise ValueError(
                    f"comparison-level u probabilities for {field!r} must sum to 1"
                )
            normalised[field] = levels
        return normalised

    def _comparison_level(self, field: str, similarity: float) -> Dict[str, Any]:
        for level in self.comparison_levels[field]:
            threshold = level["min_similarity"]
            if threshold is None or similarity >= threshold:
                return level
        raise RuntimeError(f"no comparison level selected for field {field!r}")

    def _comparison_level_llr(
        self,
        field: str,
        level: Mapping[str, Any],
        shared_value: Any = None,
    ) -> float:
        """Return a categorical level's LLR, with exact-value TF adjustment."""
        base = float(level["llr"])
        if shared_value is None or level["min_similarity"] is None:
            return base
        table = self.term_frequencies.get(field)
        if not table:
            return base
        p_v = table.get(shared_value)
        if p_v is None:
            return base
        return math.log(float(level["m"]) / _clip(p_v))

    # ------------------------------------------------------------------
    # Term-frequency adjustment
    # ------------------------------------------------------------------

    def _agree_llr(self, field: str, shared_value: Any = None) -> float:
        """Agreement LLR for a field, term-frequency adjusted when possible.

        The base ``u`` is an *average* chance-agreement rate over all values.
        That average is wrong for any specific value: two records both saying
        "Smith" is weak evidence, while two both saying "Xanthopoulos" is
        strong, yet an unadjusted model scores them identically.

        Conditioned on one record holding value ``v``, the probability that an
        unrelated record also holds ``v`` is just ``v``'s relative frequency, so
        the value-specific chance rate is ``p_v`` and the agreement weight
        becomes ``log(m / p_v)``. Averaging ``p_v`` over how often each value
        occurs recovers the base ``u = sum_v p_v^2``, so the adjustment is a
        refinement of the learned parameter rather than a replacement for it.

        Applied ONLY on exact agreement (``shared_value`` is not None), because
        a fuzzy match between two *different* values has no single frequency to
        look up — the same restriction Splink places on TF adjustment.
        """
        base = self._llr_agree[field]
        if shared_value is None:
            return base
        table = self.term_frequencies.get(field)
        if not table:
            return base
        p_v = table.get(shared_value)
        if p_v is None:
            # Value outside the persisted top-N table: no frequency evidence,
            # so fall back to the average rather than guessing.
            return base
        return math.log(self.m[field] / _clip(p_v))

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def total_llr(
        self,
        field_scores: Mapping[str, float],
        exact_values: Optional[Mapping[str, Any]] = None,
    ) -> float:
        """Sum of per-field log-likelihood ratios for an agreement pattern.

        Args:
            field_scores: per-field similarity. Unobserved fields (absent or
                ``None``) contribute exactly zero — the null comparison level
                described in the module docstring.
            exact_values: optional ``{field: value}`` for fields where the two
                records hold the *identical* value, enabling term-frequency
                adjustment for those fields.
        """
        exact_values = exact_values or {}
        total = 0.0
        for f in self.fields:
            sim = field_scores.get(f)
            if sim is None:
                continue  # null level: no evidence either way
            if f in self.comparison_levels:
                level = self._comparison_level(f, float(sim))
                total += self._comparison_level_llr(
                    f, level, exact_values.get(f)
                )
                continue
            threshold = self.agreement_thresholds.get(f, self.default_threshold)
            if sim >= threshold:
                total += self._agree_llr(f, exact_values.get(f))
            else:
                total += self._llr_disagree[f]
        return total

    @classmethod
    def from_model_doc(
        cls,
        doc: Dict,
        *,
        match_prior: Optional[float] = None,
        term_frequencies: Optional[Mapping[str, Mapping[Any, float]]] = None,
    ) -> "FellegiSunterScorer":
        """Build from an ``er_model_params`` document (as persisted by 1.1A).

        ``term_frequencies`` is supplied separately because the TF tables live
        in their own collection (``er_term_frequencies``); use
        :func:`term_frequency_tables_from_docs` to shape them.
        """
        return cls(
            m=doc["m"],
            u=doc["u"],
            agreement_thresholds=doc.get("agreement_thresholds"),
            match_prior=match_prior if match_prior is not None else doc.get("lambda", 0.5),
            term_frequencies=term_frequencies,
            comparison_levels=doc.get("comparison_levels"),
        )

    def observed_fields(self, field_scores: Mapping[str, float]) -> int:
        """How many model fields this pair actually supplied evidence for.

        Useful for a minimum-evidence guard: a pair whose only observed field is
        low-information should not be treated with the same confidence as a pair
        that agreed across many fields.
        """
        return sum(1 for f in self.fields if field_scores.get(f) is not None)

    def score(
        self,
        field_scores: Mapping[str, float],
        exact_values: Optional[Mapping[str, Any]] = None,
    ) -> float:
        """Posterior match probability in [0, 1]."""
        llr = self.total_llr(field_scores, exact_values)
        return 1.0 / (1.0 + math.exp(-(llr + self._prior_logit)))

    def explain(
        self,
        field_scores: Mapping[str, float],
        exact_values: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Decompose a score into per-field evidence — a match-weight waterfall.

        Returns the prior logit, one entry per field, and the resulting total
        and posterior. Because the model is additive in log-odds, the entries
        sum exactly to ``total_llr``, so the output reads as a waterfall: start
        at the prior, add each field's contribution, arrive at the score.

        Each field entry reports:

        ``state``
            ``agree`` / ``disagree`` / ``not_observed``.
        ``llr``
            That field's contribution in nats (0.0 when not observed).
        ``tf_adjusted``
            Whether a term-frequency adjustment was applied.
        ``base_llr`` / ``tf_delta``
            The unadjusted agreement weight and how much the value's rarity
            moved it — positive for a rare value, negative for a common one.

        This is the glass-box counterpart to an LLM's free-text rationale: it
        states exactly which evidence moved the decision and by how much.
        """
        exact_values = exact_values or {}
        entries: List[Dict[str, Any]] = []
        total = 0.0

        for f in self.fields:
            sim = field_scores.get(f)
            if sim is None:
                entries.append({
                    "field": f,
                    "state": "not_observed",
                    "similarity": None,
                    "llr": 0.0,
                    "tf_adjusted": False,
                })
                continue

            if f in self.comparison_levels:
                level = self._comparison_level(f, float(sim))
                shared = exact_values.get(f)
                base = float(level["llr"])
                llr = self._comparison_level_llr(f, level, shared)
                adjusted = llr != base
                entry = {
                    "field": f,
                    "state": level["name"],
                    "comparison_level": level["name"],
                    "similarity": sim,
                    "min_similarity": level["min_similarity"],
                    "m": level["m"],
                    "u": level["u"],
                    "llr": llr,
                    "tf_adjusted": adjusted,
                    "base_llr": base,
                }
                if adjusted:
                    entry["shared_value"] = shared
                    entry["value_frequency"] = self.term_frequencies[f].get(shared)
                    entry["tf_delta"] = llr - base
                entries.append(entry)
                total += llr
                continue

            threshold = self.agreement_thresholds.get(f, self.default_threshold)
            if sim >= threshold:
                shared = exact_values.get(f)
                base = self._llr_agree[f]
                llr = self._agree_llr(f, shared)
                adjusted = llr != base
                entry: Dict[str, Any] = {
                    "field": f,
                    "state": "agree",
                    "similarity": sim,
                    "llr": llr,
                    "tf_adjusted": adjusted,
                    "base_llr": base,
                }
                if adjusted:
                    entry["shared_value"] = shared
                    entry["value_frequency"] = self.term_frequencies[f].get(shared)
                    entry["tf_delta"] = llr - base
                entries.append(entry)
            else:
                llr = self._llr_disagree[f]
                entries.append({
                    "field": f,
                    "state": "disagree",
                    "similarity": sim,
                    "llr": llr,
                    "tf_adjusted": False,
                })
            total += llr

        posterior = 1.0 / (1.0 + math.exp(-(total + self._prior_logit)))
        return {
            "prior": self.match_prior,
            "prior_logit": self._prior_logit,
            "fields": entries,
            "total_llr": total,
            "posterior": posterior,
        }


def _clip(p: float) -> float:
    return min(max(float(p), _EPS), 1 - _EPS)


def term_frequency_tables_from_docs(
    docs: "Mapping[str, Any] | list",
) -> Dict[str, Dict[Any, float]]:
    """Shape ``er_term_frequencies`` documents into scorer lookup tables.

    Accepts either the raw persisted documents (each ``{field, total,
    top_values: [{value, count, relative_frequency}]}``) or the in-memory dict
    returned by
    :meth:`~entity_resolution.learning.model_parameter_estimator.ModelParameterEstimator.compute_term_frequencies`,
    and returns ``{field: {value: relative_frequency}}``.

    Frequencies missing from a document are recomputed from ``count / total``,
    so tables written by an older version still load.
    """
    if isinstance(docs, Mapping):
        iterable = [
            {"field": field, **table} for field, table in docs.items()
        ]
    else:
        iterable = list(docs)

    tables: Dict[str, Dict[Any, float]] = {}
    for doc in iterable:
        field = doc.get("field") or doc.get("_key")
        if not field:
            continue
        total = doc.get("total") or 0
        table: Dict[Any, float] = {}
        for row in doc.get("top_values", []):
            value = row.get("value")
            if value is None:
                continue
            freq = row.get("relative_frequency")
            if freq is None:
                count = row.get("count", 0)
                freq = (count / total) if total else 0.0
            if freq > 0:
                table[value] = float(freq)
        if table:
            tables[field] = table
    return tables

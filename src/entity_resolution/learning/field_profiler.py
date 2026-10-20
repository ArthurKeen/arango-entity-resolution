"""Schema-agnostic field profiling (plan 1.4).

Samples a collection, classifies each field by type (email / phone / date /
numeric / id / person-name / org-name / address / free-text) from regex +
statistics, and emits a generated similarity configuration — comparator,
transformers, agreement threshold, and initial m/u priors per detected type.

This removes the hand-written weights/comparators dict: profiling chooses the
*comparators* and seed priors, then EM (1.1) refines the *weights*. Together a
user can point the system at an unlabeled collection and run
profile → estimate → resolve with zero hand-tuning.

:func:`classify_values` is pure and unit-testable; :class:`FieldProfiler` adds
sampling and config emission against a live database.
"""

from __future__ import annotations

import logging
import re
import statistics
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+(]?[\d][\d\s().-]{6,}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2})?|^\d{1,2}/\d{1,2}/\d{2,4}$")
_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_ORG_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|co|company|gmbh|plc|sa|ag|nv|incorporated|corporation)\b", re.I)
_STREET_SUFFIX = re.compile(r"\b(st|street|ave|avenue|rd|road|blvd|lane|ln|dr|drive|ct|court|way|pl|place)\b", re.I)

# Per-type comparator defaults: algorithm, transformer chain, agreement
# threshold for FS, and seed m/u priors (EM later refines these).
TYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "email":       {"algorithm": "jaro_winkler", "transformers": ["lower", "strip"],          "agreement_threshold": 0.95, "m": 0.95, "u": 0.005},
    "phone":       {"algorithm": "levenshtein",  "transformers": ["digits_only"],             "agreement_threshold": 1.0,  "m": 0.92, "u": 0.01},
    "date":        {"algorithm": "levenshtein",  "transformers": ["strip"],                   "agreement_threshold": 1.0,  "m": 0.90, "u": 0.02},
    "numeric":     {"algorithm": "levenshtein",  "transformers": ["strip"],                   "agreement_threshold": 1.0,  "m": 0.85, "u": 0.05},
    "id":          {"algorithm": "levenshtein",  "transformers": ["upper", "strip"],          "agreement_threshold": 1.0,  "m": 0.97, "u": 0.001},
    "person_name": {"algorithm": "jaro_winkler", "transformers": ["strip", "collapse_whitespace"], "agreement_threshold": 0.88, "m": 0.90, "u": 0.03},
    "org_name":    {"algorithm": "jaro_winkler", "transformers": ["company_suffix", "collapse_whitespace"], "agreement_threshold": 0.85, "m": 0.88, "u": 0.05},
    "address":     {"algorithm": "jaro_winkler", "transformers": ["street_suffix", "collapse_whitespace"],  "agreement_threshold": 0.85, "m": 0.88, "u": 0.06},
    "free_text":   {"algorithm": "jaccard",      "transformers": ["lower", "remove_punctuation"], "agreement_threshold": 0.6,  "m": 0.80, "u": 0.10},
    "short_string":{"algorithm": "jaro_winkler", "transformers": ["strip"],                   "agreement_threshold": 0.85, "m": 0.85, "u": 0.08},
    # Multi-word labels ("DATA PRIVACY LAWS AND REGULATIONS"): they differ by
    # inserted words, which an edit-distance measure built for short names
    # handles badly. Word Jaccard scored F1 0.541 against Jaro-Winkler's 0.253
    # on Abt-Buy titles.
    "phrase":      {"algorithm": "jaccard",      "transformers": ["lower", "remove_punctuation"], "agreement_threshold": 0.6,  "m": 0.85, "u": 0.05},
    # Embedding vectors: no string measure applies. Excluded from the emitted
    # similarity config; compare them with blocking.strategy "vector".
    "vector":      {"algorithm": None,           "transformers": [],                          "agreement_threshold": None, "m": None, "u": None},
}

# Rough relative weights by type (used as a seed before EM learns real weights).
_TYPE_WEIGHT = {
    "email": 1.0, "phone": 0.9, "id": 1.0, "person_name": 0.8, "org_name": 0.8,
    "address": 0.7, "date": 0.4, "numeric": 0.3, "free_text": 0.5, "short_string": 0.5,
    "phrase": 0.6, "vector": 0.0,
}

#: The global algorithm emit_similarity_config writes; fields whose type wants
#: another one get it in ``field_algorithms``.
_DEFAULT_ALGORITHM = "jaro_winkler"


def _fraction(values: Sequence[str], pred) -> float:
    return sum(1 for v in values if pred(v)) / len(values) if values else 0.0


def _is_numeric_vector(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) >= 2
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value)
    )


def classify_values(values: Sequence[Any]) -> Dict[str, Any]:
    """Classify a field from sampled values; returns ``{type, stats}``.

    Pure: no DB access. Numeric vectors are recognised before anything is
    stringified: a stringified list of floats has digits and many tokens, so it
    used to be typed ``address`` and compared with Jaro-Winkler at the highest
    default weight. Other non-null values are stringified and trimmed.
    """
    non_null = [v for v in values if v is not None]
    vectors = [v for v in non_null if _is_numeric_vector(v)]
    if non_null and len(vectors) / len(non_null) >= 0.8:
        dims = sorted({len(v) for v in vectors})
        return {"type": "vector", "stats": {
            "sampled": len(non_null), "non_null": len(non_null),
            "dimensions": dims[0] if len(dims) == 1 else dims,
        }}

    strs = [str(v).strip() for v in values if v is not None and str(v).strip()]
    n = len(strs)
    if n == 0:
        return {"type": "free_text", "stats": {"sampled": 0, "non_null": 0}}

    distinct = len(set(strs))
    lengths = [len(s) for s in strs]
    token_counts = [len(s.split()) for s in strs]
    avg_len = statistics.mean(lengths)
    avg_tokens = statistics.mean(token_counts)
    cardinality = distinct / n

    frac_email = _fraction(strs, lambda s: bool(_EMAIL_RE.match(s)))
    frac_phone = _fraction(strs, lambda s: bool(_PHONE_RE.match(s)) and sum(c.isdigit() for c in s) >= 7)
    frac_date = _fraction(strs, lambda s: bool(_DATE_RE.match(s)))
    frac_numeric = _fraction(strs, lambda s: bool(_NUMERIC_RE.match(s)))
    frac_org = _fraction(strs, lambda s: bool(_ORG_SUFFIX.search(s)))
    frac_street = _fraction(strs, lambda s: bool(_STREET_SUFFIX.search(s)))
    frac_has_digit = _fraction(strs, lambda s: any(c.isdigit() for c in s))
    frac_alpha_tokens = _fraction(strs, lambda s: all(t.isalpha() for t in s.split()) and s.split())

    stats = {
        "sampled": n, "distinct": distinct, "cardinality": round(cardinality, 4),
        "avg_length": round(avg_len, 2), "avg_tokens": round(avg_tokens, 2),
    }

    # Decision order: most specific first. Date precedes phone because a loose
    # phone pattern also matches dash-separated dates ("2024-01-01").
    if frac_email >= 0.8:
        ftype = "email"
    elif frac_date >= 0.8:
        ftype = "date"
    elif frac_phone >= 0.8:
        ftype = "phone"
    elif frac_numeric >= 0.9:
        ftype = "numeric"
    elif frac_org >= 0.3:
        ftype = "org_name"
    elif frac_street >= 0.3 or (frac_has_digit >= 0.5 and avg_tokens >= 3):
        ftype = "address"
    elif 2 <= avg_tokens <= 3 and frac_alpha_tokens >= 0.7:
        ftype = "person_name"
    elif cardinality >= 0.95 and avg_tokens <= 1 and bool(_ID_RE.match(strs[0])):
        ftype = "id"
    elif avg_tokens >= 5 or avg_len >= 60:
        ftype = "free_text"
    elif avg_tokens > 3 and frac_alpha_tokens >= 0.7 and frac_has_digit < 0.5:
        # Three-to-five-word labels. Below this they are names (person_name
        # above takes 2-3 tokens); at five and over, free_text.
        ftype = "phrase"
    else:
        ftype = "short_string"

    return {"type": ftype, "stats": stats}


def _sample_values(values: Sequence[Any], limit: int = 3) -> List[str]:
    """Up to ``limit`` distinct non-empty example values (stringified)."""
    out: List[str] = []
    seen: set = set()
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s[:120])
        if len(out) >= limit:
            break
    return out


def field_config(field: str, ftype: str) -> Dict[str, Any]:
    """Comparator + seed-prior config for a field of the given type."""
    d = TYPE_DEFAULTS.get(ftype, TYPE_DEFAULTS["short_string"])
    return {
        "field": field,
        "type": ftype,
        "algorithm": d["algorithm"],
        "transformers": list(d["transformers"]),
        "agreement_threshold": d["agreement_threshold"],
        "m_prior": d["m"],
        "u_prior": d["u"],
        "weight": _TYPE_WEIGHT.get(ftype, 0.5),
    }


class FieldProfiler:
    """Sample a collection, classify its fields, and emit a similarity config."""

    def __init__(self, db: Any, collection: str, *, sample_size: int = 1000) -> None:
        self.db = db
        self.collection = collection
        self.sample_size = sample_size

    def _sample(self) -> List[Dict[str, Any]]:
        from ..utils.validation import validate_collection_name

        validate_collection_name(self.collection)
        cursor = self.db.aql.execute(
            "FOR d IN @@col SORT RAND() LIMIT @n RETURN d",
            bind_vars={"@col": self.collection, "n": int(self.sample_size)},
        )
        return list(cursor)

    def profile(self, *, exclude_fields: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """Profile every non-system field; returns per-field type + config."""
        exclude = set(exclude_fields or [])
        docs = self._sample()
        # Gather values per field.
        by_field: Dict[str, List[Any]] = {}
        for doc in docs:
            for k, v in doc.items():
                if k.startswith("_") or k in exclude:
                    continue
                by_field.setdefault(k, []).append(v)

        fields: Dict[str, Any] = {}
        for field, values in by_field.items():
            completeness = round(len(values) / len(docs), 4) if docs else 0.0
            classified = classify_values(values)
            cfg = field_config(field, classified["type"])
            fields[field] = {
                "type": classified["type"],
                "completeness": completeness,
                "stats": classified["stats"],
                "config": cfg,
                "samples": _sample_values(values),
            }
        return {
            "collection": self.collection,
            "sampled_docs": len(docs),
            "fields": fields,
        }

    def emit_similarity_config(
        self,
        profile: Optional[Dict[str, Any]] = None,
        *,
        min_completeness: float = 0.3,
        max_fields: int = 12,
    ) -> Dict[str, Any]:
        """Generate a similarity config from the profile.

        Picks well-populated, discriminative fields (skips near-empty ones and
        pure free-text by default), normalizes weights, and attaches per-field
        transformers, agreement thresholds, and EM seed priors.
        """
        profile = profile or self.profile()
        excluded: Dict[str, str] = {}
        chosen = {}
        for f, info in profile["fields"].items():
            if info["type"] == "vector":
                dims = info.get("stats", {}).get("dimensions")
                excluded[f] = (
                    f"vector{f' ({dims} dimensions)' if dims else ''}: no string measure "
                    f"applies; compare it with blocking.strategy 'vector' and "
                    f"blocking.embedding_field '{f}'"
                )
            elif info["type"] == "free_text":
                excluded[f] = "free_text: long prose rarely discriminates; add it by hand if it does"
            elif info["completeness"] < min_completeness:
                excluded[f] = f"completeness {info['completeness']} is below {min_completeness}"
            else:
                chosen[f] = info
        # Prefer higher-weight, more-complete fields if over the cap.
        ordered = sorted(
            chosen.items(),
            key=lambda kv: (kv[1]["config"]["weight"], kv[1]["completeness"]),
            reverse=True,
        )[:max_fields]

        field_weights: Dict[str, float] = {}
        field_algorithms: Dict[str, str] = {}
        transformers: Dict[str, List[str]] = {}
        agreement_thresholds: Dict[str, float] = {}
        m_priors: Dict[str, float] = {}
        u_priors: Dict[str, float] = {}
        for field, info in ordered:
            c = info["config"]
            field_weights[field] = c["weight"]
            if c["algorithm"] and c["algorithm"] != _DEFAULT_ALGORITHM:
                field_algorithms[field] = c["algorithm"]
            transformers[field] = c["transformers"]
            agreement_thresholds[field] = c["agreement_threshold"]
            m_priors[field] = c["m_prior"]
            u_priors[field] = c["u_prior"]

        total = sum(field_weights.values()) or 1.0
        field_weights = {f: round(w / total, 4) for f, w in field_weights.items()}

        out: Dict[str, Any] = {
            "similarity": {
                "algorithm": _DEFAULT_ALGORITHM,
                "field_weights": field_weights,
                # Each field's comparator, where its type wants one other than
                # the global algorithm. Profiled per field and, before
                # field_algorithms existed, dropped here: every field was
                # compared with Jaro-Winkler whatever the profile said.
                "field_algorithms": field_algorithms,
                "transformers": transformers,
                "agreement_thresholds": agreement_thresholds,
                # Seed priors for EM (1.1); EM refines them from data.
                "m_priors": m_priors,
                "u_priors": u_priors,
            }
        }
        if excluded:
            # Outside "similarity" so it is never mistaken for a setting.
            out["excluded_fields"] = excluded
        return out

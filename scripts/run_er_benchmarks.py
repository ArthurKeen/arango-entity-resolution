#!/usr/bin/env python3
"""Run arango-entity-resolution against standard public ER benchmarks.

Reports the numbers the record-linkage literature reports, so this project's
matching quality is verifiable rather than asserted. Until now the repo had no
results on any public dataset, which made every quality claim unfalsifiable.

Datasets (Leipzig DBS group — the canonical record-linkage benchmarks, also used
by Ditto, Magellan, Splink evaluations and most EM papers):

============== ============ ============ ==========
dataset        source A     source B     true pairs
============== ============ ============ ==========
abt-buy        Abt 1081     Buy 1092     1097
amazon-google  Amazon 1363  Google 3226  1300
dblp-acm       DBLP 2616    ACM 2294     2224
dblp-scholar   DBLP 2616    Scholar 64k  5347
============== ============ ============ ==========

These are *linkage* tasks (match A against B). The library's blocking strategies
are dedup-shaped (one collection against itself), so both sources are loaded
into a single collection carrying a ``_source`` marker and candidate/truth pairs
are restricted to cross-source pairs. That is a standard way to run linkage
through a dedup engine and keeps the benchmark on the real pipeline rather than
a bespoke path.

Datasets (FEBRL, ANU — synthetic person records, the standard benchmark for
structured multi-field linkage):

============== ======= ========== ==============================
dataset        records true pairs  shape
============== ======= ========== ==============================
febrl1           1,000        500  500 clusters of exactly 2
febrl3           5,000      6,538  clusters of 1-6, 835 singletons
febrl3-noid      5,000      6,538  febrl3 minus soc_sec_id
============== ======= ========== ==============================

These are *deduplication* tasks: one file matched against itself, truth encoded
in the record ids rather than a mapping file. They exist because every Leipzig
dataset compares two free-text fields, which cannot distinguish a matcher that
learns per-field weights from one that averages similarities. FEBRL's ten fields
have chance-agreement rates spanning three orders of magnitude, which can — and
does: see docs/BENCHMARKS.md, where Fellegi-Sunter wins on these and loses on
those.

Metrics reported
----------------
*Blocking* — ``pair_completeness`` (share of true pairs surviving blocking; the
ceiling on achievable recall) and ``reduction_ratio`` (share of the full cross
product eliminated). A blocker can always buy recall with pairs, so both are
reported together.

*Matching* — pairwise precision/recall/F1, both at the configured threshold and
at the best-F1 operating point found by sweeping. Literature usually quotes the
best operating point; quoting only that would flatter a system that cannot pick
its threshold, so both appear.

*Clustering* — B-cubed precision/recall/F1 over the final clusters
(:mod:`entity_resolution.services.cluster_metrics`). Pairwise metrics are known
to be optimistic and dominated by large clusters; B-cubed is the entity-level
bar and is rarely reported by tools in this space.

Usage::

    python scripts/run_er_benchmarks.py --dataset abt-buy
    python scripts/run_er_benchmarks.py --dataset all --output docs/benchmark_results.json

Datasets download to ``--data-dir`` (default ``.benchmark_data/``, gitignored)
and are cached, so repeat runs are offline. Requires a local ArangoDB; the
harness creates and drops its own collections.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from entity_resolution.services.cluster_metrics import (  # noqa: E402
    b_cubed,
    pairwise_closure_metrics,
)

BASE_URL = "https://dbs.uni-leipzig.de/file"


@dataclass
class DatasetSpec:
    """How to fetch, parse and compare one LINKAGE benchmark dataset.

    Two sources, matched against each other, with truth in a mapping file.
    """

    name: str
    archive: str
    source_a: str
    source_b: str
    mapping: str
    #: Columns concatenated to form the comparable text of a record.
    text_fields_a: Sequence[str]
    text_fields_b: Sequence[str]
    #: Extra single-valued fields compared on their own, if present in both.
    aux_fields: Sequence[str] = field(default_factory=tuple)
    #: Fields scored and their weights. ``None`` uses the ``--title-weight``
    #: split over the two text fields, which is what these datasets want.
    field_weights: Optional[Dict[str, float]] = None

    is_dedup = False

    def pair_space(self, records: Sequence[Dict[str, Any]]) -> int:
        """Pairs a blocker could have emitted — the reduction-ratio denominator."""
        n_a = sum(1 for r in records if r["_source"] == "a")
        return n_a * (len(records) - n_a)


@dataclass
class DedupSpec:
    """How to fetch, parse and compare one DEDUPLICATION benchmark dataset.

    One file, matched against itself, with truth encoded in the record ids. This
    is the shape the library's blocking strategies are natively written for — the
    linkage datasets above are run through it by loading both sources into one
    collection, which is a standard trick but still a trick.
    """

    name: str
    url: str
    filename: str
    id_column: str
    #: Fields compared individually. Also concatenated to form the BM25 text.
    compare_fields: Sequence[str]
    #: Maps a record id to the id of the entity it belongs to.
    entity_of: Any
    field_weights: Optional[Dict[str, float]] = None

    is_dedup = True

    def pair_space(self, records: Sequence[Dict[str, Any]]) -> int:
        n = len(records)
        return n * (n - 1) // 2


DATASETS: Dict[str, DatasetSpec] = {
    "abt-buy": DatasetSpec(
        name="abt-buy",
        archive="Abt-Buy",
        source_a="Abt.csv",
        source_b="Buy.csv",
        mapping="abt_buy_perfectMapping.csv",
        text_fields_a=("name", "description"),
        text_fields_b=("name", "description"),
        aux_fields=("price",),
    ),
    "amazon-google": DatasetSpec(
        name="amazon-google",
        archive="Amazon-GoogleProducts",
        source_a="Amazon.csv",
        source_b="GoogleProducts.csv",
        mapping="Amzon_GoogleProducts_perfectMapping.csv",
        text_fields_a=("title", "description"),
        text_fields_b=("name", "description"),
        aux_fields=("manufacturer", "price"),
    ),
    "dblp-acm": DatasetSpec(
        name="dblp-acm",
        archive="DBLP-ACM",
        source_a="DBLP2.csv",
        source_b="ACM.csv",
        mapping="DBLP-ACM_perfectMapping.csv",
        text_fields_a=("title", "authors"),
        text_fields_b=("title", "authors"),
        aux_fields=("venue", "year"),
    ),
    "dblp-scholar": DatasetSpec(
        name="dblp-scholar",
        archive="DBLP-Scholar",
        source_a="DBLP1.csv",
        source_b="Scholar.csv",
        mapping="DBLP-Scholar_perfectMapping.csv",
        text_fields_a=("title", "authors"),
        text_fields_b=("title", "authors"),
        aux_fields=("venue", "year"),
    ),
}


# FEBRL person records: ten fields whose chance-agreement rates span three orders
# of magnitude (`state` 0.236, `street_number` 0.016, `soc_sec_id` 0.0007 on
# dataset3). That spread is the point. Every Leipzig dataset above compares two
# free-text fields where chance agreement is unmeasurably small, which is the
# regime least able to distinguish a matcher that learns per-field weights from
# one that averages similarities — so the claim that Fellegi-Sunter "earns its
# place on structured, multi-field records" could not be tested there at all.
#
# Weights are UNIFORM, deliberately. Hand-tuning them against benchmark F1 would
# be selection on labels a deployment does not have, and it would also confound
# the comparison: the question is whether FS's learned weighting beats an untuned
# average, so the average must stay untuned.
_FEBRL_FIELDS = (
    "given_name", "surname", "street_number", "address_1", "address_2",
    "suburb", "postcode", "state", "date_of_birth", "soc_sec_id",
)
_FEBRL_BASE = (
    "https://raw.githubusercontent.com/J535D165/recordlinkage/master/"
    "recordlinkage/datasets/febrl"
)


def _febrl_entity_of(record_id: str) -> str:
    """``rec-223-org`` and ``rec-223-dup-0`` are the same person.

    FEBRL encodes ground truth in the id rather than shipping a mapping file, so
    the entity is the middle token.
    """
    parts = record_id.split("-")
    return parts[1] if len(parts) > 1 else record_id


DEDUP_DATASETS: Dict[str, DedupSpec] = {
    # dataset1: 1,000 records, every entity exactly one original + one duplicate.
    "febrl1": DedupSpec(
        name="febrl1",
        url=f"{_FEBRL_BASE}/dataset1.csv",
        filename="febrl_dataset1.csv",
        id_column="rec_id",
        compare_fields=_FEBRL_FIELDS,
        entity_of=_febrl_entity_of,
        field_weights={f: 1.0 / len(_FEBRL_FIELDS) for f in _FEBRL_FIELDS},
    ),
    # dataset3: 5,000 records over 2,000 entities, clusters of 1-6 and 835
    # singletons. The singletons matter — they punish over-merging, which a
    # dataset of uniform 2-record clusters cannot.
    "febrl3": DedupSpec(
        name="febrl3",
        url=f"{_FEBRL_BASE}/dataset3.csv",
        filename="febrl_dataset3.csv",
        id_column="rec_id",
        compare_fields=_FEBRL_FIELDS,
        entity_of=_febrl_entity_of,
        field_weights={f: 1.0 / len(_FEBRL_FIELDS) for f in _FEBRL_FIELDS},
    ),
}

# soc_sec_id is close to a unique identifier: FEBRL corrupts it on some
# duplicates but usually leaves it intact, so agreement on it is nearly decisive.
# Fellegi-Sunter learns exactly that (u = 0.0007) and is right to. But a headline
# claim should not rest on a field that behaves like a primary key, so this
# variant drops it and compares the same matchers on the nine remaining fields.
_FEBRL_FIELDS_NO_ID = tuple(f for f in _FEBRL_FIELDS if f != "soc_sec_id")
DEDUP_DATASETS["febrl3-noid"] = DedupSpec(
    name="febrl3-noid",
    url=f"{_FEBRL_BASE}/dataset3.csv",
    filename="febrl_dataset3.csv",
    id_column="rec_id",
    compare_fields=_FEBRL_FIELDS_NO_ID,
    entity_of=_febrl_entity_of,
    field_weights={f: 1.0 / len(_FEBRL_FIELDS_NO_ID) for f in _FEBRL_FIELDS_NO_ID},
)

ALL_SPECS: Dict[str, Any] = {**DATASETS, **DEDUP_DATASETS}


# ---------------------------------------------------------------------------
# Fetch + parse
# ---------------------------------------------------------------------------


def ensure_dataset(spec: DatasetSpec, data_dir: Path) -> Path:
    """Download and extract a dataset if not already cached."""
    target = data_dir / spec.archive
    if target.is_dir() and (target / spec.mapping).is_file():
        return target

    data_dir.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}/{spec.archive}.zip"
    print(f"  downloading {url} ...", flush=True)
    with urllib.request.urlopen(url, timeout=180) as response:
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(target)
    return target


def _read_csv(path: Path) -> List[Dict[str, str]]:
    """Read a benchmark CSV, tolerating the BOM and latin-1 bytes they ship with."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"could not decode {path}")


def load_dedup_dataset(spec: DedupSpec, data_dir: Path) -> Tuple[
    List[Dict[str, Any]], Set[Tuple[str, str]]
]:
    """Return (records, truth_pairs) for a single-file deduplication dataset.

    Truth comes from the record ids rather than a mapping file: every pair of
    records belonging to the same entity is a true match, so a cluster of n
    records contributes n*(n-1)/2 pairs.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / spec.filename
    if not path.is_file():
        print(f"  downloading {spec.url} ...", flush=True)
        with urllib.request.urlopen(spec.url, timeout=180) as response:
            path.write_bytes(response.read())

    rows = _read_csv(path)
    records: List[Dict[str, Any]] = []
    clusters: Dict[str, List[str]] = {}
    for row in rows:
        # These CSVs put a space after each comma, so DictReader keys arrive
        # with a leading space; strip both sides of keys and values.
        clean = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        rid = clean.get(spec.id_column, "")
        if not rid:
            continue
        key = _safe_key(rid)
        doc: Dict[str, Any] = {
            "_key": key,
            "source_id": rid,
            # One logical source, but the field is kept so that downstream code
            # (and the emitted JSON) has the same shape for both dataset
            # families.
            "_source": "a",
            "text": " ".join(clean.get(f, "") for f in spec.compare_fields).strip(),
        }
        for f in spec.compare_fields:
            doc[f] = clean.get(f, "")
        records.append(doc)
        clusters.setdefault(spec.entity_of(rid), []).append(key)

    truth: Set[Tuple[str, str]] = set()
    for members in clusters.values():
        ordered = sorted(members)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                truth.add((a, b))
    return records, truth


def load_dataset(spec: DatasetSpec, data_dir: Path) -> Tuple[
    List[Dict[str, Any]], Set[Tuple[str, str]]
]:
    """Return (records, truth_pairs).

    Records carry a source-prefixed ``_key`` so the two sources can share one
    collection; truth pairs use the same prefixed keys, canonically ordered.
    """
    root = ensure_dataset(spec, data_dir)

    def build(rows, prefix, text_fields) -> List[Dict[str, Any]]:
        out = []
        for row in rows:
            rid = (row.get("id") or "").strip()
            if not rid:
                continue
            values = [str(row.get(f) or "").strip() for f in text_fields]
            doc: Dict[str, Any] = {
                "_key": f"{prefix}{_safe_key(rid)}",
                "source_id": rid,
                "_source": prefix.rstrip("_"),
                # Concatenated text drives BM25 blocking (one indexed field).
                "text": " ".join(v for v in values if v).strip(),
                # The same content split out, so similarity compares a short
                # title against a short title and a long body against a long
                # body. Concatenating them and scoring once lets a 200-word
                # description drown out the title, which is the discriminating
                # field.
                "title": values[0] if values else "",
                "body": " ".join(values[1:]).strip() if len(values) > 1 else "",
            }
            for aux in spec.aux_fields:
                value = (row.get(aux) or "").strip()
                if value:
                    doc[aux] = value
            out.append(doc)
        return out

    records = build(_read_csv(root / spec.source_a), "a_", spec.text_fields_a)
    records += build(_read_csv(root / spec.source_b), "b_", spec.text_fields_b)

    truth: Set[Tuple[str, str]] = set()
    for row in _read_csv(root / spec.mapping):
        values = [v for v in row.values() if v is not None]
        if len(values) < 2:
            continue
        left = f"a_{_safe_key(values[0].strip())}"
        right = f"b_{_safe_key(values[1].strip())}"
        truth.add(tuple(sorted((left, right))))  # type: ignore[arg-type]

    return records, truth


def _safe_key(raw: str) -> str:
    """ArangoDB keys allow a limited character set; map anything else out."""
    return "".join(c if (c.isalnum() or c in "-_.@()+,=;$!*'%") else "_" for c in raw)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _connect(args) -> Any:
    from arango import ArangoClient

    # Blocking issues one monolithic AQL query per run with no client-side
    # batching, so on the larger datasets the default 60s HTTP read timeout
    # expires mid-query. Raising the client timeout is the workaround; the
    # underlying limitation is recorded in docs/BENCHMARKS.md.
    client = ArangoClient(
        hosts=f"http://{args.host}:{args.port}",
        request_timeout=args.request_timeout,
    )
    sys_db = client.db("_system", username=args.username, password=args.password)
    if not sys_db.has_database(args.database):
        sys_db.create_database(args.database)
    return client.db(args.database, username=args.username, password=args.password)


def _load_records(db, collection: str, records: List[Dict[str, Any]]) -> None:
    if db.has_collection(collection):
        db.delete_collection(collection)
    db.create_collection(collection)
    coll = db.collection(collection)
    for start in range(0, len(records), 2000):
        coll.insert_many(records[start : start + 2000], overwrite=True)


def _view_exists(db, view: str) -> bool:
    """python-arango has no ``has_view``; enumerate instead."""
    return any(v["name"] == view for v in db.views())


def _create_view(db, view: str, collection: str, analyzer: str = "text_en") -> None:
    """ArangoSearch view over the comparable text, for BM25 blocking."""
    if _view_exists(db, view):
        db.delete_view(view)
    db.create_view(
        view,
        view_type="arangosearch",
        properties={
            "links": {
                collection: {
                    "fields": {f: {"analyzers": [analyzer]} for f in ("text", "title", "body")},
                    "includeAllFields": False,
                }
            }
        },
    )
    # ArangoSearch indexes asynchronously; poll until the view answers for the
    # expected document count rather than sleeping a fixed interval.
    expected = db.collection(collection).count()
    deadline = time.time() + 120
    while time.time() < deadline:
        cursor = db.aql.execute(
            "FOR d IN @@view SEARCH d.text != null COLLECT WITH COUNT INTO n RETURN n",
            bind_vars={"@view": view},
        )
        if (next(iter(cursor), 0) or 0) >= expected:
            return
        time.sleep(1.0)
    print("  WARNING: view did not fully index within 120s; recall may be understated")


def generate_candidates(
    db, collection: str, view: str, args, is_dedup: bool = False
) -> List[Tuple[str, str]]:
    """Candidate pairs via the library's BM25 blocking strategy."""
    from entity_resolution.strategies.bm25_blocking import BM25BlockingStrategy

    strategy = BM25BlockingStrategy(
        db=db,
        collection=collection,
        search_view=view,
        search_field=getattr(args, "blocking_field", None) or "text",
        bm25_threshold=args.bm25_threshold,
        limit_per_entity=args.limit_per_entity,
    )
    pairs = strategy.generate_candidates()

    # A linkage task can only match across sources, so same-source pairs are
    # dropped. A dedup task matches a collection against itself, where that
    # filter would remove every pair there is.
    sources = {} if is_dedup else _source_map(db, collection)
    out: Set[Tuple[str, str]] = set()
    for pair in pairs:
        k1, k2 = pair.get("doc1_key"), pair.get("doc2_key")
        if not k1 or not k2 or k1 == k2:
            continue
        if not is_dedup and sources.get(k1) == sources.get(k2):
            continue
        out.add(tuple(sorted((k1, k2))))  # type: ignore[arg-type]
    return sorted(out)


def _source_map(db, collection: str) -> Dict[str, str]:
    cursor = db.aql.execute(
        "FOR d IN @@c RETURN {k: d._key, s: d._source}",
        bind_vars={"@c": collection},
    )
    return {row["k"]: row["s"] for row in cursor}


def _field_weights(args, spec: Any = None) -> Dict[str, float]:
    """Fields compared, and how much each counts.

    A spec may name its own fields and weights (the multi-field dedup datasets
    do). Otherwise the title carries most of the signal and the body is
    supporting evidence, often missing on one side.
    """
    if spec is not None and getattr(spec, "field_weights", None):
        return dict(spec.field_weights)
    return {"title": args.title_weight, "body": 1.0 - args.title_weight}


_NORMALIZATION = {
    "strip": True,
    "case": "lower",
    "collapse_whitespace": True,
    "remove_punctuation": True,
}


def _build_similarity_service(db, collection: str, args, spec: Any = None, **extra):
    from entity_resolution.services.batch_similarity_service import (
        BatchSimilarityService,
    )

    return BatchSimilarityService(
        db=db,
        collection=collection,
        field_weights=_field_weights(args, spec),
        similarity_algorithm=args.algorithm,
        batch_size=args.batch_size,
        normalization_config=_NORMALIZATION,
        **extra,
    )


def _comparison_levels(args, fields: Sequence[str]) -> Dict[str, Any]:
    """Build per-field comparison bands from ``--comparison-levels``.

    One descending threshold list is applied to every scoring field, which is
    enough to test whether banding helps at all. Per-field tuning would confound
    the question with hand-optimisation.
    """
    raw = getattr(args, "comparison_levels", None)
    if not raw:
        return {}
    if str(raw).strip().lower() == "auto":
        # Placement inferred from this dataset's own score distribution, so the
        # benchmark reports what a user without labels would actually get.
        return {"__auto__": True}
    thresholds = [float(part) for part in str(raw).split(",") if part.strip()]
    if not thresholds:
        return {}
    if sorted(thresholds, reverse=True) != thresholds:
        raise ValueError("--comparison-levels must be descending, most selective first")
    names = ("exact", "close", "near", "weak")
    if len(thresholds) > len(names):
        raise ValueError(f"--comparison-levels supports at most {len(names)} thresholds")
    return {
        field: [
            {"name": names[i], "min_similarity": t} for i, t in enumerate(thresholds)
        ] + [{"name": "else", "min_similarity": None}]
        for field in fields
    }



def _auto_comparison_levels(
    db, collection, pairs, fields, args, spec: Any = None
) -> Dict[str, Any]:
    """Infer per-field bands from this dataset's own observed similarities.

    Bands are placed per FIELD, because their distributions differ: a short
    title and a long description do not separate at the same similarity, which
    is exactly why bands copied between datasets underperformed.

    Scores come from the same comparator the model will be trained with, on a
    sample of the candidate pairs, so the placement reflects what the estimator
    will actually see. A field whose distribution supports no separation is
    left unbanded and keeps the binary model rather than being given invented
    bands.
    """
    from entity_resolution.learning.threshold_selection import select_comparison_bands

    service = _build_similarity_service(db, collection, args, spec=spec)
    sample = list(pairs)[: args.fs_train_sample]
    detailed = service.compute_similarities_detailed(
        sample, threshold=0.0, preserve_missing=True
    )

    out: Dict[str, Any] = {}
    for field_name in fields:
        scores = [
            row["field_scores"].get(field_name)
            for row in detailed
            if row.get("field_scores", {}).get(field_name) is not None
        ]
        selection = select_comparison_bands(
            scores, n_thresholds=args.auto_band_count
        )
        if selection.thresholds:
            out[field_name] = selection.to_comparison_levels()
            print(
                f"  auto bands [{field_name}]: {selection.thresholds} "
                f"(valley depths {selection.diagnostics.get('valley_depths')})"
            )
        else:
            print(f"  auto bands [{field_name}]: declined — {selection.warning}")
    return out


def train_fs_model(
    db, collection: str, pairs: Sequence[Tuple[str, str]], args, spec: Any = None
) -> Tuple[Any, Dict[str, Any]]:
    """Train a Fellegi-Sunter model on this dataset's own candidate pairs.

    Unsupervised throughout: EM sees only the candidate pairs (no truth), and
    ``u`` is measured from random record pairs drawn from the source collection.
    Term-frequency tables are computed from the same collection.

    The candidates are materialised as an edge collection because that is the
    interface :class:`ModelParameterEstimator` samples from — the same path a
    real deployment uses after edge creation.
    """
    from entity_resolution.learning import ModelParameterEstimator
    from entity_resolution.learning.fellegi_sunter_scorer import FellegiSunterScorer

    edge_collection = f"{collection}_train_edges"
    if db.has_collection(edge_collection):
        db.delete_collection(edge_collection)
    db.create_collection(edge_collection, edge=True)
    edges = [
        {"_from": f"{collection}/{a}", "_to": f"{collection}/{b}"} for a, b in pairs
    ]
    for start in range(0, len(edges), 5000):
        db.collection(edge_collection).insert_many(edges[start : start + 5000])

    fields = list(_field_weights(args, spec))
    levels = _comparison_levels(args, fields)
    if levels.get("__auto__"):
        levels = _auto_comparison_levels(db, collection, pairs, fields, args, spec)
    estimator = ModelParameterEstimator(
        db=db,
        similarity_service=_build_similarity_service(db, collection, args, spec=spec),
        edge_collection=edge_collection,
        field_names=fields,
        default_threshold=args.fs_agreement_threshold,
        comparison_levels=levels or None,
    )
    # Train fresh: models persist across runs, and load_latest() sorts by version
    # across ALL config hashes. Each distinct configuration starts its own
    # version sequence at 1, so with several configs present a bare
    # load_latest() can return a different config's v1 — which silently made
    # every agreement-threshold setting produce identical results.
    for name in ("er_model_params", "er_term_frequencies"):
        if db.has_collection(name):
            db.delete_collection(name)

    summary = estimator.run(
        source_collection=collection,
        sample_size=args.fs_train_sample,
        u_sample_size=args.fs_u_sample,
        categorical_u_source=args.fs_categorical_u,
    )
    # Ask the estimator for its own identity rather than recomputing the hash
    # here: configuration_hash() now also covers the comparison-level structure,
    # and a local copy of the formula would silently miss the model the moment
    # the two drifted.
    model = estimator.load_latest(estimator.configuration_hash())
    if model is None:  # pragma: no cover - defensive
        raise RuntimeError("FS training produced no persisted model")
    tf_tables = estimator.load_term_frequencies() if args.fs_term_frequency else {}

    scorer = FellegiSunterScorer.from_model_doc(model, term_frequencies=tf_tables)
    trained = {
        "m": {k: round(v, 4) for k, v in model["m"].items()},
        "u": {k: round(v, 4) for k, v in model["u"].items()},
        "lambda": round(model["lambda"], 4),
        "u_estimation": model.get("u_estimation"),
        "fit_warning": model.get("fit_warning"),
        "agreement_threshold": args.fs_agreement_threshold,
        "term_frequency_fields": sorted(tf_tables),
        "converged": model.get("converged"),
        "training_pairs": summary["model"]["n_pairs"],
        "model_type": model.get("model_type", "binary"),
    }
    if model.get("model_type") == "categorical":
        trained["comparison_levels"] = {
            field: [level.get("min_similarity") for level in field_levels]
            for field, field_levels in (model.get("comparison_levels") or {}).items()
        }
        trained["m_levels"] = {
            field: [round(v, 4) for v in values]
            for field, values in (model.get("m_levels") or {}).items()
        }
        trained["u_levels"] = {
            field: [round(v, 4) for v in values]
            for field, values in (model.get("u_levels") or {}).items()
        }
    if db.has_collection(edge_collection):
        db.delete_collection(edge_collection)
    return scorer, trained


def score_pairs(
    db, collection: str, pairs: Sequence[Tuple[str, str]], args, spec: Any = None
) -> Tuple[List[Tuple[str, str, float]], Optional[Dict[str, Any]]]:
    """Score candidate pairs with the library's similarity service.

    Returns ``(scored, fs_model_info)``; the second element is ``None`` on the
    weighted-heuristic path.
    """
    fs_info: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = {}
    if args.scoring_method == "fellegi_sunter":
        scorer, fs_info = train_fs_model(db, collection, pairs, args, spec=spec)
        extra = {"scoring_method": "fellegi_sunter", "fs_scorer": scorer}

    service = _build_similarity_service(db, collection, args, spec=spec, **extra)
    scored = service.compute_similarities(
        list(pairs), threshold=0.0, return_all=True
    )
    return [(a, b, float(s)) for a, b, s in scored], fs_info


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def blocking_metrics(
    candidates: Sequence[Tuple[str, str]],
    truth: Set[Tuple[str, str]],
    full_space: int,
) -> Dict[str, float]:
    """``full_space`` is the pair count a blocker could have emitted.

    It differs by task shape — n_a*n_b for a linkage run, n*(n-1)/2 for a dedup
    run — so the caller supplies it via ``spec.pair_space`` rather than having it
    inferred here from source counts that a dedup dataset does not have.
    """
    candidate_set = set(candidates)
    retained = len(candidate_set & truth)
    return {
        "candidate_pairs": len(candidate_set),
        "true_pairs": len(truth),
        "true_pairs_retained": retained,
        "pair_completeness": retained / len(truth) if truth else 0.0,
        "reduction_ratio": 1.0 - (len(candidate_set) / full_space) if full_space else 0.0,
    }


def sweep_thresholds(
    scored: Sequence[Tuple[str, str, float]],
    truth: Set[Tuple[str, str]],
    steps: int = 99,
) -> Tuple[Dict[str, float], List[Dict[str, float]]]:
    """Pairwise P/R/F1 across thresholds; returns (best_by_f1, curve)."""
    curve: List[Dict[str, float]] = []
    best: Dict[str, float] = {"f1": -1.0}
    for i in range(1, steps + 1):
        threshold = i / (steps + 1)
        predicted = {(a, b) for a, b, s in scored if s >= threshold}
        point = _prf(predicted, truth)
        point["threshold"] = round(threshold, 4)
        curve.append(point)
        if point["f1"] > best["f1"]:
            best = point
    return best, curve


def _prf(predicted: Set[Tuple[str, str]], truth: Set[Tuple[str, str]]) -> Dict[str, float]:
    tp = len(predicted & truth)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(truth) if truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "predicted_pairs": len(predicted),
        "true_positives": tp,
    }


def _components(pairs: Set[Tuple[str, str]]) -> List[List[str]]:
    """Connected components — the clusters an ER run would emit."""
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    groups: Dict[str, List[str]] = {}
    for node in list(parent):
        groups.setdefault(find(node), []).append(node)
    return [sorted(v) for v in groups.values()]


def cluster_metrics_at(
    scored: Sequence[Tuple[str, str, float]],
    truth: Set[Tuple[str, str]],
    threshold: float,
    all_records: Sequence[str],
) -> Dict[str, Any]:
    """B-cubed and pairwise-closure metrics over the clusters at a threshold."""
    predicted_pairs = {(a, b) for a, b, s in scored if s >= threshold}
    predicted_clusters = _components(predicted_pairs)
    truth_clusters = _components(truth)
    return {
        "threshold": round(threshold, 4),
        "b_cubed": {
            k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in b_cubed(predicted_clusters, truth_clusters, all_records).items()
        },
        "pairwise_closure": {
            k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in pairwise_closure_metrics(
                predicted_clusters, truth_clusters
            ).items()
        },
        "predicted_clusters": len(predicted_clusters),
        "truth_clusters": len(truth_clusters),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_dataset(name: str, args) -> Dict[str, Any]:
    spec = ALL_SPECS[name]
    print(f"\n=== {name} ===", flush=True)

    started = time.time()
    if spec.is_dedup:
        records, truth = load_dedup_dataset(spec, Path(args.data_dir))
        print(f"  records: {len(records)} (dedup), true pairs: {len(truth)}")
    else:
        records, truth = load_dataset(spec, Path(args.data_dir))
        n_a = sum(1 for r in records if r["_source"] == "a")
        print(
            f"  records: {n_a} + {len(records) - n_a} = {len(records)}, "
            f"true pairs: {len(truth)}"
        )

    db = _connect(args)
    collection = f"bench_{name.replace('-', '_')}"
    view = f"{collection}_view"

    try:
        _load_records(db, collection, records)
        _create_view(db, view, collection, analyzer=args.analyzer)

        t0 = time.time()
        candidates = generate_candidates(
            db, collection, view, args, is_dedup=spec.is_dedup
        )
        blocking_time = time.time() - t0
        block = blocking_metrics(candidates, truth, spec.pair_space(records))
        print(
            f"  blocking: {block['candidate_pairs']:,} pairs, "
            f"completeness={block['pair_completeness']:.3f}, "
            f"reduction={block['reduction_ratio']:.5f} ({blocking_time:.1f}s)"
        )

        t0 = time.time()
        scored, fs_info = score_pairs(db, collection, candidates, args, spec=spec)
        scoring_time = time.time() - t0
        if fs_info:
            print(
                f"  FS model: m={fs_info['m']} u={fs_info['u']} "
                f"lambda={fs_info['lambda']} u_from={fs_info['u_estimation']} "
                + (f"\n  !! UNFIT MODEL: {fs_info['fit_warning']}\n  "
                   if fs_info.get("fit_warning") else "")
                + 
                f"tf_fields={fs_info['term_frequency_fields']}"
            )

        best, curve = sweep_thresholds(scored, truth)
        at_default = _prf(
            {(a, b) for a, b, s in scored if s >= args.threshold}, truth
        )
        at_default["threshold"] = args.threshold
        print(
            f"  pairwise best-F1: {best['f1']:.4f} "
            f"(P={best['precision']:.4f} R={best['recall']:.4f} @ {best['threshold']}) "
            f"| at {args.threshold}: F1={at_default['f1']:.4f}"
        )

        # Does automatic threshold selection recover the sweep's answer without
        # being told the labels? This is the honest test of the feature: the
        # unsupervised selection never sees `truth`.
        from entity_resolution.learning.threshold_selection import (
            select_threshold_supervised,
            select_threshold_unsupervised,
        )

        unsup = select_threshold_unsupervised([s for _a, _b, s in scored])
        sup = select_threshold_supervised(scored, truth)
        at_unsup = _prf(
            {(a, b) for a, b, s in scored if s >= unsup.threshold}, truth
        )
        at_unsup["threshold"] = unsup.threshold
        print(
            f"  auto-threshold: unsupervised={unsup.threshold} "
            f"(F1={at_unsup['f1']:.4f}, valley={unsup.diagnostics.get('valley_depth')}) "
            f"| supervised={sup.threshold} (F1={sup.metrics.get('f1')})"
        )

        clusters = cluster_metrics_at(
            scored, truth, best["threshold"], [r["_key"] for r in records]
        )
        bc = clusters["b_cubed"]
        print(
            f"  B-cubed: F1={bc['f1']:.4f} (P={bc['precision']:.4f} R={bc['recall']:.4f})"
        )

        n_a = sum(1 for r in records if r["_source"] == "a")
        return {
            "dataset": name,
            "task": "dedup" if spec.is_dedup else "linkage",
            "records": len(records),
            # A dedup dataset has one source, so all records fall in "a" and
            # records_b is 0 — kept so both families emit the same JSON shape.
            "records_a": n_a,
            "records_b": len(records) - n_a,
            "true_pairs": len(truth),
            "blocking": {**block, "runtime_seconds": round(blocking_time, 2)},
            "matching": {
                "best_f1": best,
                "at_configured_threshold": at_default,
                "auto_threshold": {
                    "unsupervised": {**unsup.to_dict(), "achieved": at_unsup},
                    "supervised": sup.to_dict(),
                },
                "runtime_seconds": round(scoring_time, 2),
            },
            "clustering": clusters,
            "fs_model": fs_info,
            "config": {
                "blocking": "bm25",
                "scoring_method": args.scoring_method,
                "bm25_threshold": args.bm25_threshold,
                "limit_per_entity": args.limit_per_entity,
                "similarity_algorithm": args.algorithm,
                "analyzer": args.analyzer,
            },
            "total_runtime_seconds": round(time.time() - started, 2),
            "threshold_curve": curve if args.emit_curve else None,
        }
    finally:
        if not args.keep:
            if _view_exists(db, view):
                db.delete_view(view)
            if db.has_collection(collection):
                db.delete_collection(collection)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", default="abt-buy",
        choices=[*ALL_SPECS, "all", "leipzig", "febrl"],
        help=(
            "One dataset, or a family: 'leipzig' (the four linkage datasets), "
            "'febrl' (the multi-field dedup datasets), 'all' (everything)."
        ),
    )
    parser.add_argument("--data-dir", default=str(REPO_ROOT / ".benchmark_data"))
    parser.add_argument("--output", default=None, help="Write JSON results here.")
    parser.add_argument("--markdown", default=None, help="Write a results table here.")
    parser.add_argument("--host", default=os.getenv("ARANGO_TEST_HOST", "localhost"))
    parser.add_argument("--port", default=os.getenv("ARANGO_TEST_PORT", "8529"))
    parser.add_argument("--username", default="root")
    parser.add_argument(
        "--password", default=os.getenv("ARANGO_TEST_PASSWORD", os.getenv("ARANGO_ROOT_PASSWORD", ""))
    )
    parser.add_argument("--database", default="er_benchmarks")
    parser.add_argument("--analyzer", default="text_en")
    parser.add_argument(
        "--blocking-field", default="text",
        help=(
            "Field BM25 blocking searches. Default 'text' concatenates title "
            "and body; on datasets with long descriptions that drowns the title, "
            "so 'title' can give strictly better recall with fewer pairs."
        ),
    )
    parser.add_argument("--bm25-threshold", type=float, default=1.0)
    parser.add_argument("--limit-per-entity", type=int, default=20)
    parser.add_argument(
        "--algorithm", default="jaccard", choices=["jaccard", "jaro_winkler", "levenshtein"],
        help=(
            "Word-based jaccard is the default: these are long multi-word texts, "
            "and edit-distance measures like jaro_winkler are designed for short "
            "strings such as personal names (on Abt-Buy, jaro_winkler over the "
            "concatenated text scores F1 0.25 versus jaccard's much higher figure)."
        ),
    )
    parser.add_argument(
        "--title-weight", type=float, default=0.7,
        help="Weight on the title field; the remainder goes to the body.",
    )
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument(
        "--scoring-method", default="weighted_heuristic",
        choices=["weighted_heuristic", "fellegi_sunter"],
        help=(
            "weighted_heuristic: configured field weights over the similarity "
            "measure. fellegi_sunter: train m/u by EM on this dataset's own "
            "candidate pairs (u from random pairs), then score the calibrated "
            "posterior. FS training is unsupervised — it never sees the truth file."
        ),
    )
    parser.add_argument(
        "--fs-agreement-threshold", type=float, default=0.85,
        help=(
            "Per-field similarity at or above which FS calls a field 'agreeing'. "
            "Sensitive: 0.85 suits short-string measures like Jaro-Winkler, but "
            "word-based Jaccard on long text rarely reaches it, so nearly every "
            "field reads as disagreement."
        ),
    )
    parser.add_argument("--fs-train-sample", type=int, default=50_000)
    parser.add_argument("--fs-u-sample", type=int, default=10_000)
    parser.add_argument(
        "--fs-categorical-u", choices=("candidates", "random_pairs"),
        default="candidates",
        help=(
            "Population u is measured over for MULTI-LEVEL models. 'candidates' "
            "(default) matches the population actually scored; 'random_pairs' is "
            "the textbook construction but saturates scores when blocking is "
            "aggressive (DBLP-ACM F1 at the 0.8 default: 0.910 -> 0.672)."
        ),
    )
    parser.add_argument(
        "--auto-band-count", type=int, default=2,
        help="Bands to infer per field when --comparison-levels=auto.",
    )
    parser.add_argument(
        "--comparison-levels", default=None,
        help=(
            "Descending similarity thresholds defining Fellegi-Sunter comparison "
            "bands, applied to every scoring field, e.g. '0.9,0.6' for "
            "exact/close/else. Omit for the single-cutoff binary model. Tests "
            "whether retaining similarity gradation recovers the accuracy the "
            "binary model loses on text."
        ),
    )
    parser.add_argument(
        "--no-fs-term-frequency", dest="fs_term_frequency",
        action="store_false", default=True,
        help="Disable term-frequency adjustment, to isolate its contribution.",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument(
        "--request-timeout", type=int, default=1800,
        help="HTTP read timeout in seconds (blocking runs as one large query).",
    )
    parser.add_argument("--emit-curve", action="store_true")
    parser.add_argument("--keep", action="store_true", help="Keep benchmark collections.")
    args = parser.parse_args()

    families = {
        "all": list(ALL_SPECS),
        "leipzig": list(DATASETS),
        "febrl": list(DEDUP_DATASETS),
    }
    names = families.get(args.dataset, [args.dataset])
    results = [run_dataset(name, args) for name in names]

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nJSON written to {args.output}")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(results), encoding="utf-8")
        print(f"Markdown written to {args.markdown}")
    return 0


def render_markdown(results: List[Dict[str, Any]]) -> str:
    lines = [
        "| Dataset | Records | True pairs | Pair completeness | Reduction ratio "
        "| Pairwise F1 (best) | B-cubed F1 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        block = r["blocking"]
        lines.append(
            f"| {r['dataset']} | {r['records_a']}+{r['records_b']} | {r['true_pairs']} "
            f"| {block['pair_completeness']:.3f} | {block['reduction_ratio']:.5f} "
            f"| {r['matching']['best_f1']['f1']:.4f} "
            f"| {r['clustering']['b_cubed']['f1']:.4f} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)

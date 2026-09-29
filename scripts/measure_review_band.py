#!/usr/bin/env python3
"""How much can ANY adjudicator win on a clerical-review score band?

Before paying a model (or a person) to judge ambiguous pairs, measure the
ceiling. An ORACLE, a judge that is right every time, free and instant, is an
upper bound no real adjudicator can exceed. If the oracle barely moves F1 on a
band, no model is worth running there, whichever one it is.

For each band this reports how many pairs fall in it, what share of the
matcher's errors it contains, and F1 with the band judged perfectly against the
best swept threshold, which is the most favourable honest baseline: an
adjudicator has to beat our best operating point, not our default.

No LLM is called and nothing is spent. The run is deterministic given the
harness configuration, so the JSON it writes is the artifact the
"LLM verification" section of docs/BENCHMARKS.md is checked against.

Usage::

    python scripts/measure_review_band.py --dataset amazon-google \\
        --port 8529 --password "$ARANGO_ROOT_PASSWORD" \\
        --output docs/benchmark_results_review_band.json

Any other ``run_er_benchmarks.py`` flag (``--blocking-field``, ``--algorithm``
...) is accepted and has the same meaning.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

_spec = importlib.util.spec_from_file_location("bench", REPO / "scripts" / "run_er_benchmarks.py")
bench = importlib.util.module_from_spec(_spec)
sys.modules["bench"] = bench
_spec.loader.exec_module(bench)

Pair = Tuple[str, str]

#: The shipped LLMMatchVerifier band first, then progressively wider ones.
BANDS: List[Tuple[float, float]] = [(0.55, 0.80), (0.40, 0.90), (0.30, 0.95), (0.20, 1.01), (0.0, 1.01)]


def _prf(pred: Set[Pair], truth: Set[Pair]) -> Dict[str, float]:
    tp = len(pred & truth)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(truth) if truth else 0.0
    # Unrounded: a delta of two rounded F1s can be off by one in the last digit.
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if (p + r) else 0.0}


def _r4(metrics: Dict[str, float]) -> Dict[str, float]:
    return {k: round(v, 4) for k, v in metrics.items()}


def measure(scored, truth: Set[Pair]) -> Dict:
    by_pair = {(a, b) if a < b else (b, a): s for a, b, s in scored}
    best, _curve = bench.sweep_thresholds(scored, truth)
    thr = best["threshold"]
    pred = {p for p, s in by_pair.items() if s >= thr}
    base = _prf(pred, truth)
    errors = (pred - truth) | (truth - pred)

    bands = []
    for lo, hi in BANDS:
        in_band = {p for p, s in by_pair.items() if lo <= s < hi}
        oracle = _prf((pred - in_band) | (in_band & truth), truth)
        bands.append({
            "band": [lo, hi],
            "pairs": len(in_band),
            "true_pairs": len(in_band & truth),
            "error_share": round(len(errors & in_band) / len(errors), 4) if errors else 0.0,
            "oracle_f1": round(oracle["f1"], 4),
            "oracle_delta_f1": round(oracle["f1"] - base["f1"], 4),
        })
    return {"best_threshold": thr, "baseline": _r4(base),
            "errors": {"false_positives": len(pred - truth), "false_negatives": len(truth - pred)},
            "bands": bands}


def main() -> int:
    args = bench.build_parser().parse_args()
    if args.dataset not in bench.ALL_SPECS:
        raise SystemExit("--dataset must name one dataset, not a group")
    spec = bench.ALL_SPECS[args.dataset]
    records, truth = bench.load_dataset(spec, Path(args.data_dir))
    db = bench._connect(args)
    collection = f"band_{args.dataset.replace('-', '_')}"
    view = f"{collection}_view"
    bench._load_records(db, collection, records)
    bench._create_view(db, view, collection, analyzer=args.analyzer)
    try:
        candidates = bench.generate_candidates(db, collection, view, args, is_dedup=spec.is_dedup)
        scored, _ = bench.score_pairs(db, collection, candidates, args, spec=spec)
        result = {
            "dataset": args.dataset,
            "blocking_recall": round(len(set(candidates) & truth) / len(truth), 4),
            "candidates": len(candidates),
            "config": {"blocking_field": args.blocking_field, "algorithm": args.algorithm,
                       "scoring_method": args.scoring_method},
            **measure(scored, truth),
        }
    finally:
        if not args.keep:
            if any(v["name"] == view for v in db.views()):
                db.delete_view(view)
            if db.has_collection(collection):
                db.delete_collection(collection)

    print(f"\n{args.dataset}: best threshold {result['best_threshold']:.2f}, "
          f"F1 {result['baseline']['f1']:.4f}")
    print(f"  {'band':<14}{'pairs':>8}{'% errors':>10}{'oracle F1':>11}{'delta':>9}")
    for b in result["bands"]:
        lo, hi = b["band"]
        print(f"  [{lo:.2f},{hi:.2f}){b['pairs']:>8,}{b['error_share'] * 100:>9.1f}%"
              f"{b['oracle_f1']:>11.4f}{b['oracle_delta_f1']:>+9.4f}")
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

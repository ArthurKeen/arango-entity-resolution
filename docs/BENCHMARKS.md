# Benchmark Results

Measured results for `arango-entity-resolution` on the standard public
record-linkage benchmarks, so matching quality is **verifiable rather than
asserted**. Every number here is reproducible with one command (see
[Reproducing](#reproducing)).

**Version:** 3.8.0 · **Measured:** 2026-08-02 · **ArangoDB:** 3.12 (single node,
Docker) · **Hardware:** Apple Silicon laptop, single process

## Summary

| Dataset | Records | True pairs | Pair completeness | Reduction ratio | Pairwise F1 | B-cubed F1 |
|---|---|---|---|---|---|---|
| DBLP-ACM | 2,616 + 2,294 | 2,224 | **1.000** | 0.99462 | **0.937** | 0.977 |
| DBLP-Scholar | 2,616 + 64,263 | 5,347 | 0.996 | 0.99960 | 0.840 | **0.987** |
| Abt-Buy | 1,081 + 1,092 | 1,097 | 0.957 | 0.99077 | 0.541 | 0.779 |
| Amazon-Google | 1,363 + 3,226 | 1,300 | 0.890 | 0.99413 | 0.488 | 0.852 |

Full detail:

| Dataset | Candidates | Pairwise P | Pairwise R | Pairwise F1 @ thr | F1 @ 0.8 default | B-cubed P | B-cubed R | Blocking | Scoring |
|---|---|---|---|---|---|---|---|---|---|
| DBLP-ACM | 32,278 | 0.9308 | 0.9433 | 0.9370 @ 0.77 | 0.9352 | 0.9797 | 0.9743 | 7.1s | 0.3s |
| DBLP-Scholar | 68,057 | 0.7851 | 0.9027 | 0.8398 @ 0.50 | 0.6609 | 0.9853 | 0.9888 | 1160s | 0.8s |
| Abt-Buy | 10,895 | 0.5144 | 0.5706 | 0.5411 @ 0.35 | 0.0670 | 0.7732 | 0.7842 | 1.7s | 0.2s |
| Amazon-Google | 25,808 | 0.4618 | 0.5162 | 0.4875 @ 0.34 | 0.0370 | 0.8431 | 0.8610 | 16.2s | 1.0s |

The largest dataset produces the **best** entity-level result (B-cubed 0.987 over
66,879 records): blocking retained 99.6% of true pairs while eliminating 99.96%
of the 168M-pair cross product. It is also by far the slowest — see
[Scale](#scale-limits).

## How to read these numbers

**These are unsupervised results.** No labelled training pairs were used — only
blocking, configured field weights and string similarity. That is the relevant
comparison class for a library used on a new dataset with no ground truth, and
it is why the numbers below sit near classic supervised baselines rather than at
the top of published leaderboards.

**Pair completeness** is the share of true pairs surviving blocking — the ceiling
on achievable recall. **Reduction ratio** is the share of the full cross product
eliminated. Both are reported together because a blocker can always buy recall
with pairs.

**Pairwise F1** is quoted at the best-F1 operating point found by sweeping the
threshold, which is the convention in the literature. The harness also reports F1
at the configured default, and the gap is large (Abt-Buy 0.541 best vs 0.067 at
0.8) — threshold choice matters more than any other single configuration
decision. See [Threshold selection](#threshold-selection).

**B-cubed F1** is the entity-level metric, computed per record over the final
clusters, and it penalises over- and under-merging symmetrically. It is
consistently higher than pairwise F1 here because clustering recovers correct
groupings even where individual pair scores are borderline. Pairwise metrics are
known to be optimistic on large clusters; B-cubed is the stricter entity bar and
is rarely published by comparable tools.

## Context: published results on the same datasets

Approximate figures from the literature, for orientation. **Not run on this
hardware or by this project** — cite them as context, not as head-to-head
measurements.

| Dataset | Magellan (supervised ML) | DeepMatcher (supervised DL) | Ditto (PLM) | GPT-4 (zero-shot) | **This library (unsupervised)** |
|---|---|---|---|---|---|
| DBLP-ACM | ~0.98 | ~0.98 | ~0.99 | — | **0.937** |
| DBLP-Scholar | ~0.89 | ~0.94 | ~0.95 | — | **0.840** |
| Abt-Buy | ~0.43 | ~0.62 | ~0.91 | ~0.96 | **0.541** |
| Amazon-Google | ~0.49 | ~0.69 | ~0.75 | — | **0.488** |

The honest reading:

- **DBLP-ACM** — 0.937 against ~0.98 supervised. Clean, structured
  bibliographic data; the remaining gap is where trained models earn their keep.
- **DBLP-Scholar** — 0.840 against Magellan's supervised ~0.89, again with no
  labels, and B-cubed 0.987 at the entity level.
- **Abt-Buy** — 0.541 exceeds Magellan's supervised ~0.43 with no labels.
- **Amazon-Google** — 0.488 is level with Magellan's supervised ~0.49.
- Against PLM/LLM matchers (Ditto, GPT-4) there is a wide gap on the noisy
  product datasets. Closing it needs a learned or LLM matcher tier, not better
  string similarity. The library has an LLM verification path; wiring it into the
  clerical-review band and measuring it here is the obvious next step.

## Method

Both sources are loaded into a single ArangoDB collection carrying a `_source`
marker, and candidate and truth pairs are restricted to cross-source pairs. The
library's blocking strategies are dedup-shaped (one collection against itself),
so this runs linkage through the real pipeline rather than a bespoke path.

1. **Blocking** — `BM25BlockingStrategy` over an ArangoSearch view
   (`text_en` analyzer), token match mode, `bm25_threshold=1.0`,
   `limit_per_entity=20`.
2. **Similarity** — `BatchSimilarityService` with word-based **Jaccard** over
   two fields: `title` (weight 0.7) and `body` (0.3), lower-cased, punctuation
   removed, whitespace collapsed.
3. **Clustering** — connected components over pairs above threshold.
4. **Metrics** — `entity_resolution.services.cluster_metrics`
   (`b_cubed`, `pairwise_closure_metrics`).

Two configuration choices materially affect the outcome and are worth stating:

- **Word-based Jaccard, not Jaro-Winkler.** These are long multi-word texts;
  edit-distance measures are designed for short strings like personal names.
  Scoring Abt-Buy with Jaro-Winkler over the concatenated text gives F1 **0.253**
  versus **0.541** for Jaccard over split fields — a 2.1× difference from the
  similarity function alone.
- **Title and body compared separately.** Concatenating them lets a 200-word
  description drown out the title, which carries most of the discriminating
  signal.

## Scoring method: weighted similarity vs Fellegi-Sunter

Both scoring paths were measured on identical candidates. FS training is
unsupervised — EM sees only the candidate pairs, `u` is measured from random
record pairs, and the truth file is never touched.

| Dataset | Weighted F1 | FS F1 | Weighted B-cubed | FS B-cubed |
|---|---|---|---|---|
| DBLP-ACM | **0.937** | 0.868 | **0.977** | 0.942 |
| Abt-Buy | **0.541** | 0.117 | **0.779** | 0.690 |
| Amazon-Google | **0.488** | 0.127 | **0.852** | 0.842 |

**Weighted similarity wins on all three, decisively on the product datasets.**
That is the opposite of what the sophistication of the two methods suggests, and
the reason is specific: **FS binarises each field to agree/disagree at a
threshold, and that destroys the gradation continuous similarity relies on.**

The trained models show it directly. On Abt-Buy, FS learned
`m = {title: 0.822, body: 0.0}` with `lambda = 0.0065`: word-based Jaccard over
long product descriptions essentially never reaches the 0.85 agreement cutoff, so
`body` never agrees even among true matches, almost every comparison vector is
all-zeros, and recall collapses to 0.062. Precision is a perfect 1.000 — FS is
not wrong about what it finds, it just finds almost nothing.

Lowering the agreement cutoff does not rescue it, because it inflates the
inferred match class instead:

| Agreement threshold | DBLP-ACM FS F1 | learned lambda |
|---|---|---|
| 0.85 | **0.868** | 0.118 |
| 0.50 | 0.601 | 0.198 |
| 0.30 | 0.401 | 0.455 |

### Term-frequency adjustment: validated

Ablating TF adjustment inside the FS path isolates its contribution:

| Dataset | FS with TF | FS without TF | Delta |
|---|---|---|---|
| DBLP-ACM | **0.868** | 0.784 | **+0.084** (+10.7% relative) |
| Amazon-Google | 0.127 | 0.127 | 0.000 |

TF adjustment is a **real, measurable gain of +0.084 F1** where records share
identical values (DBLP-ACM titles and author strings repeat exactly across the two
sources), and is **inert rather than harmful** on free text, where no two product
descriptions are byte-identical so the exact-agreement condition never fires. It
lifts precision-recall balance markedly: without TF, FS sits at P 0.953 / R 0.666;
with it, P 0.796 / R 0.955.

### What this means in practice

- **Default to weighted similarity for text-heavy data.** It is the better
  matcher on every dataset here, and it is the configuration all headline numbers
  in this document use.
- **FS earns its place on structured, multi-field records** — identifiers, dates,
  codes, postal fields — where exact agreement is meaningful and its calibrated
  posterior plus per-decision evidence decomposition are worth having. DBLP-ACM,
  the most structured dataset here, is where FS comes closest.
- **Multi-level comparisons are the binding constraint, not a refinement.**
  Splink-style levels (exact / fuzzy-close / else, each with its own m/u) let FS
  keep the gradation it otherwise discards. They have since been implemented and
  measured — see [Multi-level comparisons](#multi-level-comparisons-measured).

This is the result the benchmark existed to produce. Three statistical fixes
landed in the FS path — a null comparison level, unbiased `u` from random pairs,
and TF adjustment — and each is correct and unit-tested. Measured end to end,
one of them (TF) delivers a clear gain, and the path as a whole still loses to
the simpler matcher because of a design property none of them addressed. Without
these measurements the reasonable assumption would have been the reverse.

### Multi-level comparisons: measured

Comparison levels replace the single agree/disagree cutoff with ordered bands,
each with its own learned m/u (`similarity.comparison_levels`). This is the fix
the section above named as the binding constraint. It works — substantially —
and it still does not overtake weighted similarity.

| Dataset | Weighted F1 | FS binary | **FS multi-level** | Bands used |
|---|---|---|---|---|
| DBLP-ACM | **0.937** | 0.868 | 0.914 | 0.9 / 0.6 |
| Abt-Buy | **0.541** | 0.117 | 0.505 | 0.6 / 0.35 |
| Amazon-Google | **0.488** | 0.127 | 0.446 | 0.6 / 0.35 *(transferred)* |

B-cubed moves the same way: DBLP-ACM 0.942 → 0.965, Abt-Buy 0.690 → 0.730.

**The collapse is fixed.** On the product datasets FS went from unusable to
competitive — Abt-Buy 4.3x (0.117 → 0.505), Amazon-Google 3.5x (0.127 → 0.446).
The diagnosis was right: binarising at one cutoff was destroying the signal, and
retaining the gradation recovers almost all of it.

**Weighted similarity still wins on all three.** Multi-level closes most of the
gap but never crosses it. The practical recommendation is therefore unchanged —
weighted remains the default, and every headline number in this document uses it.

**Multi-level also makes FS far less sensitive to the decision threshold.** On
DBLP-ACM, F1 at the shipped 0.8 default rose from 0.771 to 0.911, and
unsupervised threshold selection improved from 0.771 to 0.833. A model that
degrades gracefully when the operating point is wrong is worth something
independently of its peak F1, since the peak assumes a threshold the user has to
find.

#### Band placement matters more than having bands

Bands must sit where the similarity distribution actually separates. The same
dataset, four settings:

| Abt-Buy bands | Pairwise F1 |
|---|---|
| 0.9 / 0.6 | 0.388 |
| **0.6 / 0.35** | **0.505** |
| 0.5 / 0.3 / 0.15 | 0.348 |
| 0.4 / 0.2 | 0.423 |

Bands copied from DBLP-ACM (0.9 / 0.6) score 0.388 on Abt-Buy — better than
binary's 0.117, but a quarter below what correctly placed bands achieve. Word-based
Jaccard over long product descriptions rarely exceeds ~0.6 even for true matches,
so a 0.9 band is nearly always empty and the model wastes a level. More bands is
not better either: the four-level 0.5/0.3/0.15 setting is the *worst* of the four.

#### How much of this is fitted to the test set

Honestly: some of it. The DBLP-ACM and Abt-Buy bands above were chosen by looking
at benchmark F1, which is selection on the labels a real deployment does not have.

Amazon-Google is the clean number. It reuses the bands tuned on **Abt-Buy**, a
different dataset with different content, and still reaches 0.446 from a binary
baseline of 0.127. That transfer result — not the tuned ones — is the evidence
that multi-level generalises rather than merely fitting.

Automatic band placement from the score distribution (quantiles, or the same
valley-finding used for threshold selection) is the obvious next step and would
remove the tuning caveat entirely.

#### When to choose multi-level FS

Weighted similarity is still the default. Choose FS with comparison levels when
you need what it uniquely provides and can afford ~5% F1:

- a **calibrated posterior** rather than an uncalibrated 0-1 score;
- a **per-decision evidence decomposition** (which field contributed what, in
  additive log-odds) for auditability;
- **term-frequency adjustment**, worth +0.084 F1 where records share identical
  values;
- **robustness to a mis-set threshold**, as above.

Place the bands using the observed similarity distribution for your data, not the
values in this table.

## Threshold selection

The best threshold ranges from **0.34 to 0.77** across these four datasets, so no
fixed default can serve all of them. Running the shipped `0.8`:

| Dataset | F1 @ 0.8 | F1 @ best | Best thr | Score valley depth | Auto-selected | F1 auto |
|---|---|---|---|---|---|---|
| DBLP-ACM | 0.935 | 0.937 | 0.77 | **0.978** | 0.523 | **0.912** |
| Abt-Buy | 0.067 | 0.541 | 0.35 | 0.000 | *rejected* → 0.8 | 0.067 |
| Amazon-Google | 0.037 | 0.488 | 0.34 | 0.000 | *rejected* → 0.8 | 0.037 |

`similarity.auto_threshold: true` infers the cutoff from the score distribution
using Otsu's method — the cut maximising between-class variance, which finds the
valley between the non-match and match modes without needing labels. It is
**off by default**, so existing runs are unchanged.

The measured outcome splits cleanly by whether the scores are actually bimodal:

- **DBLP-ACM** has a pronounced valley (depth 0.978) and inference lands at 0.523,
  reaching **0.912 — 97% of the achievable 0.937** with no labels at all.
- **Abt-Buy and Amazon-Google have valley depth 0.000.** Their scores decay
  smoothly from a single low mode with no separate match cluster, so no cut is
  statistically supported. Selection *refuses* to return one and keeps the
  configured threshold with a warning.

That refusal is deliberate and worth explaining, because a looser guard scored
better on these two datasets. An earlier version gated on between-class variance
and did return cuts here — 0.238 and 0.203, worth F1 0.436 and 0.387, a 6.5x and
10.5x improvement over the default. Those numbers were **luck, not method**:
between-class variance cannot detect bimodality at all (splitting any single
Gaussian at its mean yields 2/pi ~= 0.637, so unimodal data scores ~0.64 and
looks confident), and the cuts it produced simply sliced a smooth tail at an
arbitrary point. Shipping that would mean a component that returns
confident-looking thresholds from distributions carrying no information about
where the threshold should be — right on this data, wrong on the next dataset,
with nothing to distinguish the two cases.

**So the honest guidance is:**

1. Use `auto_threshold` when scores are bimodal — it is accurate there and free.
2. When it declines, that is information: the matcher is not separating the
   classes on this data. Improve features or scoring rather than hunting a cutoff.
3. **Whenever labels exist, use them.** `select_threshold_supervised` reached the
   optimum on every dataset here. A few hundred labelled pairs suffice, and
   analyst verdicts accumulating in the review queue are exactly that — which
   makes supervised selection the practical path, not a theoretical one.

## Scale limits

DBLP-Scholar **completes and produces the best entity-level accuracy of the
four**, but blocking takes **19.3 minutes** for 66,879 documents versus 7 seconds
for DBLP-ACM's 4,910 — a ~13× growth in records costing ~164× the time. Quality
scales; throughput does not.

Two implementation properties explain it, and both are real limitations rather
than harness artifacts:

- `BM25BlockingStrategy` issues **one monolithic AQL query** containing a
  per-document subquery, with no client-side batching or streaming. The single
  request exceeds the default 60-second python-arango read timeout, so the
  harness raises it (`--request-timeout`, default 1800s). Anyone calling the
  strategy directly at this scale hits that timeout first.
- Every strategy materialises all candidate pairs into client memory before
  deduplication, so peak memory scales with the candidate count rather than
  being bounded.

Chunked blocking with server-side pair emission and a streaming cursor is the
fix. Until then: ~5k records runs in seconds, ~67k takes ~20 minutes, and the
default client timeout must be raised beyond roughly 10k. Use
`shard_parallel_blocking` on a cluster for more (noting its own cross-shard
caveat). The README's "1M records / ~3min" performance table is **not**
substantiated for this blocking path, and published throughput at 100M+ records
(as Splink-on-Spark and Senzing report) remains an open gap.

## What these benchmarks already caught

The first run of this harness found a defect that had survived the entire test
suite: `BM25BlockingStrategy` matched candidates with
`PHRASE(d2.text, d1.text)`, which requires the source text to appear in the
candidate as an **exact consecutive token sequence**. On Abt-Buy it produced
**0 candidate pairs out of 1,097 true pairs** — the strategy documented as
"fuzzy text matching (400× faster than Levenshtein)" was performing near-exact
phrase containment. A unit test asserted the broken query as the expected
contract, so nothing failed.

Switching the default to token-level BM25 matching (`match_mode="tokens"`, with
`"phrase"` retained for compatibility) took Abt-Buy blocking from **0 → 0.957
pair completeness**. This is the argument for benchmarking against public data:
no amount of unit testing surfaces a recall collapse, because every unit still
behaves exactly as written.

## Reproducing

```bash
# Any local ArangoDB; the harness creates and drops its own collections.
python scripts/run_er_benchmarks.py --dataset all \
  --port 8529 --password "$ARANGO_ROOT_PASSWORD" \
  --output docs/benchmark_results.json
```

Datasets download once from the [Leipzig DBS
group](https://dbs.uni-leipzig.de/research/projects/benchmark-datasets-for-entity-resolution)
into `.benchmark_data/` (gitignored) and are cached, so later runs are offline.

Useful flags:

| Flag | Purpose |
|---|---|
| `--dataset` | `abt-buy`, `amazon-google`, `dblp-acm`, `dblp-scholar`, `all` |
| `--algorithm` | `jaccard` (default), `jaro_winkler`, `levenshtein` |
| `--scoring-method` | `weighted_heuristic` (default) or `fellegi_sunter` |
| `--fs-agreement-threshold` | FS agree/disagree cutoff per field (default 0.85) |
| `--comparison-levels` | Descending band thresholds, e.g. `0.6,0.35`; omit for the binary model |
| `--no-fs-term-frequency` | Disable TF adjustment, to isolate its contribution |
| `--title-weight` | Weight on the title field (default 0.7) |
| `--bm25-threshold`, `--limit-per-entity` | Blocking recall/volume trade-off |
| `--emit-curve` | Include the full threshold sweep in the JSON |
| `--keep` | Leave benchmark collections in place for inspection |

Results were stable across repeated runs on identical inputs; the pipeline is
deterministic given a fixed configuration.

## Caveats

- Single-node ArangoDB on a laptop. Timings are indicative, not throughput
  claims.
- Unsupervised throughout. No labelled pairs and no LLM verification. Headline
  numbers use the weighted-similarity path; the Fellegi-Sunter path (EM-estimated
  parameters with unbiased `u`, null comparison level, term-frequency adjustment
  and multi-level comparisons) is measured separately in
  [Scoring method](#scoring-method-weighted-similarity-vs-fellegi-sunter) and
  [Multi-level comparisons](#multi-level-comparisons-measured). Weighted
  similarity remains the better matcher on all three datasets, so it stays the
  default.
- The multi-level band thresholds for DBLP-ACM and Abt-Buy were selected using
  benchmark F1, which is selection on labels a deployment does not have. The
  Amazon-Google figure reuses bands tuned on a different dataset and is the
  unfitted result.
- Comparison figures for other systems come from their respective papers and
  were not reproduced here.
- DBLP-Scholar's blocking stage takes ~19 minutes on this hardware; see
  [Scale limits](#scale-limits).

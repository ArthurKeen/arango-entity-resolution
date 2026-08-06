# State-of-the-Art and Competitive Scorecard

**Evaluated:** August 6, 2026  
**Release baseline:** `v3.8.0` plus verified working-tree improvements  
**Overall competitive score:** **5.8/10 — differentiated mid-tier contender**

The project now has one of the broadest **open, graph-native ER toolkits** rather
than merely hosting a generic matcher in a graph database. Its overall score is
held below the leaders because this scorecard counts only shipped, wired
behavior: Splink remains ahead in probabilistic modeling, Zingg in learned
blocking/active learning, and Senzing/AWS/commercial MDM platforms in
entity-centric operation, scale, and governance.

## Capability scorecard

Scores use a 0–10 scale and compare usable, verified capability rather than
roadmap intent.

| Capability | Weight | Score | Position | Assessment |
|---|---:|---:|---|---|
| Probabilistic modeling / EM / TF | 9% | **6** | Behind Splink | Binary EM, posterior scoring, null semantics, random-pair `u`, TF adjustment, and config-hashed persistence are real; learned multi-level probabilities are absent and FS loses to weighted scoring on text |
| Blocking breadth and ANN | 8% | **8** | Leader in breadth | Nine exported strategies include native vector ANN and graph embeddings; rules are not learned and several strategies are not wired into the primary pipeline |
| Active learning | 5% | **5** | Behind Zingg | Verdicts mutate edges/clusters and tune LLM thresholds, but there is no uncertainty-sampled iterative matcher or blocker training loop |
| Threshold tuning | 6% | **6** | Partial parity | Supervised selection and guarded Otsu are wired; the UI lacks a labelled precision/recall/F1 operating curve and Otsu correctly declines on unimodal product scores |
| Cluster QA and repair | 6% | **6** | Partial parity | B-cubed, coherence/bridge analysis, suspect clusters, and repair operations exist; the graph-metric and policy suite is narrower than leaders |
| Steward Workbench | 7% | **6** | OSS parity; behind MDM | Merge/split/remove, batch verdicts, audit, profiling, thresholds, and survivorship exist; workflow assignment, RBAC, and tenancy do not |
| Explainability | 5% | **6** | Partial parity | FS waterfall, field evidence, TF effects, and optional graph evidence exist; explanations are not uniformly tied to the production scorer and structured why-not/history is incomplete |
| Incremental resolution | 6% | **6** | Partial parity | Resolve-and-commit and sequence-neutral maintenance are shipped; blocking is narrower than the batch stack and update-driven cluster retraction is open |
| Entity-centric resolution / golden records | 7% | **5** | Behind Senzing/Quantexa | Survivorship and persistent golden records are useful, but the resolution model remains fundamentally record-pairwise |
| Graph-context / collective matching | 7% | **5** | OSS niche leader | Shared-neighbor/path evidence and collective fixpoint resolution are wired but opt-in and not proven at Senzing-class maturity or scale |
| Graph embeddings | 4% | **4** | Prototype | Graph-embedding blocking exists, but the current DeepWalk/count-SVD implementation is bounded and not a production GraphSAGE/GNN path |
| Enterprise clustering | 6% | **7** | Near parity architecture | GAE WCC plus multiple local backends and automatic selection are strong; default clustering remains WCC-centric |
| LLM matcher tier | 5% | **6** | Partial parity | Uncertain-band verification, retries, budgets, and provider abstraction exist; no end-to-end quality/cost/latency benchmark has been published |
| Privacy and governance | 5% | **5** | Behind | Masking and audit attribution exist but are optional; there is no default PII policy, erasure propagation, RBAC, or tenant isolation |
| Benchmarks and regression evidence | 6% | **7** | Strong | Public Leipzig results, machine-readable artifacts, B-cubed, and quality floors are substantial; dataset breadth and release-commit reproduction remain limited |
| Candidate-generation scale | 10% | **4** | Behind | BM25 is monolithic and non-streaming, materializes pairs client-side, and takes ~19 minutes at 66,879 records |

**Weighted total:** 5.8/10, normalized across 102% of stated weights.

## Competitive position by product

| Comparator | Where this project wins | Where the comparator leads |
|---|---|---|
| [Splink](https://moj-analytical-services.github.io/splink/) | Graph context, collective and incremental resolution, native vector/graph execution, steward write workflows, MCP/LLM integration | Mature multi-level Fellegi–Sunter, EM/TF controls and diagnostics, interactive model charts, proven million-record laptop and 100M+ Spark/Athena scale |
| [Zingg](https://github.com/zinggAI/zingg) | No-label weighted baseline, graph-native evidence, richer analyst UI, transparent benchmark harness, MCP | Learned blocking, uncertainty-driven active learning, Spark-scale matching; incremental production flow is stronger in Enterprise |
| [Senzing](https://senzing.com/) | Open Python implementation, configurable algorithms, ArangoDB-native deployment and analytics, reproducibility | Real-time entity-centric learning, global identity/relationship intelligence, why/why-not/how explanations, multilingual matching, operational scale into billions |
| AWS Entity Resolution | Deployment control, transparent scoring, graph context, richer explainability and curation, no managed-service lock-in | Managed real-time rules, incremental ML processing at enterprise scale, operational SLAs and AWS data-plane integration |
| Quantexa / Tamr / Reltio-class MDM | Developer accessibility, open algorithms, embeddability, graph/LLM experimentation, cost control | Governance, source connectors, stewardship assignment, survivorship policy, RBAC/multi-tenancy, observability, support and deployment maturity |

## Measured quality position

The August benchmark demonstrates credible but uneven matching quality:

- **DBLP-ACM:** pairwise F1 **0.937**, B-cubed F1 **0.977**.
- **DBLP-Scholar:** pairwise F1 **0.840**, B-cubed F1 **0.987** over
  66,879 records.
- **Abt-Buy:** pairwise F1 **0.541**, ahead of the cited Magellan supervised
  baseline but well behind PLM/LLM matchers.
- **Amazon-Google:** pairwise F1 **0.488**, approximately level with the cited
  Magellan supervised baseline and behind deep/PLM approaches.

The honest conclusion is that the current weighted matcher is competitive on
structured/bibliographic data and credible on noisy products without labels,
but it is not a SOTA product matcher. The current FS implementation is also not
yet the answer: it scores **0.868 / 0.117 / 0.127** on DBLP-ACM, Abt-Buy, and
Amazon-Google versus **0.937 / 0.541 / 0.488** for weighted similarity. Learned
multi-level comparison categories are the binding quality improvement.

## SOTA claims the project can defend

1. **Unusually integrated graph-native OSS ER.** Candidate generation, match
   evidence, collective refinement, clustering, persistence, and analytics can
   run in one ArangoDB-centered system.
2. **Strong open-source steward workflow.** Most OSS ER libraries stop at model
   diagnostics or exported clusters; this project supports binding cluster
   edits, audit, golden-record survivorship, profiling, and threshold tuning.
3. **First-class agent interface.** The 17-tool MCP surface supports
   authentication, model-derived explanations, and budgeted/masked LLM
   verification.
4. **Unusually honest quality evidence.** The benchmark publishes poor as well
   as strong results, reports blocking recall and entity-level metrics, and
   documents the measured scaling failure.

## Claims the project should not make yet

- Overall best-in-class or SOTA matching accuracy.
- Splink-equivalent probabilistic matching before categorical multi-level EM is
  trained, persisted, wired, and benchmarked.
- Million-record or real-time candidate-generation scale from the current BM25
  path.
- Enterprise MDM readiness before RBAC, tenant isolation, immutable audit,
  deployment packaging, telemetry, and lifecycle operations exist.
- Production GraphSAGE/GNN matching; current graph embeddings are a bounded
  DeepWalk/count-SVD prototype.

## Highest-leverage moves

1. **Finish multi-level Fellegi–Sunter end to end:** comparison-level
   configuration, categorical EM, persistence, production model loading, and
   benchmark ratchets.
2. **Stream candidate generation:** chunk BM25 source records, consume a
   streaming Arango cursor, deduplicate incrementally, and add memory/throughput
   gates at 50k–1M records.
3. **Close the active-learning loop:** select uncertain/diverse pairs, train
   from adjudications, compare lift per label, and expose the loop in the
   Workbench.
4. **Broaden automatic cluster repair:** build on the existing coherence and
   bridge-edge repair path with hard-identifier vetoes and benchmarked policies.
5. **Benchmark the LLM cascade:** accuracy lift, latency, token usage, and cost
   per accepted match on the noisy product datasets.
6. **Productize operations and governance:** container, telemetry, RBAC,
   tenant/source policies, immutable audit, and erasure propagation.

## Sources and comparison boundary

Project evidence:

- [Public benchmark results](BENCHMARKS.md)
- [Current shipped and open scope](PRD.md)
- [June 2026 gap analysis](PROJECT_REVIEW_2026-06.md)

Competitor capabilities were checked against current public material:

- [Splink overview](https://moj-analytical-services.github.io/splink/) and
  [Cluster Studio](https://moj-analytical-services.github.io/splink/charts/cluster_studio_dashboard.html)
- [Zingg repository and feature summary](https://github.com/zinggAI/zingg)
- [Senzing explainability](https://senzing.com/explainability/)
- [AWS Entity Resolution workflows](https://docs.aws.amazon.com/entityresolution/latest/userguide/create-matching-workflow.html),
  [incremental ML announcement](https://aws.amazon.com/about-aws/whats-new/2026/05/aws-entity-resolution-ml/),
  and [advanced real-time matching](https://aws.amazon.com/about-aws/whats-new/2026/07/aws-entity-resolution/)

Commercial claims are not treated as independently reproduced benchmarks. This
scorecard compares documented capability and this project's measured evidence;
it is not a controlled head-to-head product evaluation.

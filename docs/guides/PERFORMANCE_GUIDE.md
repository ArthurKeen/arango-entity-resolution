# Performance Guide

**Version:** 3.5.1 | **Last Updated:** March 30, 2026

Guidance on choosing the right backends, tuning parameters, and benchmarking your entity resolution workloads.

---

## Blocking Strategy Selection

| Strategy | Speed | Recall | Best For |
|----------|-------|--------|----------|
| CollectBlocking | Very fast (O(n)) | Exact keys only | Phone+State, CEO+State, Address+Zip |
| BM25Blocking | Fast (ArangoSearch) | Fuzzy text | Company names, addresses |
| VectorBlocking | Medium (cosine sim) | Semantic | Typos, abbreviations, paraphrases |
| LSHBlocking | Fast (hashing) | Approximate | Large-scale semantic pre-filter |
| HybridBlocking | Medium | High | BM25 + Levenshtein refinement |

### Combining Strategies

Use `MultiStrategyOrchestrator` to combine multiple blocking strategies for maximum recall:

```python
from entity_resolution import MultiStrategyOrchestrator

orchestrator = MultiStrategyOrchestrator(
    strategies=[collect_strategy, bm25_strategy, vector_strategy],
    merge_mode="union",       # "union" for recall, "intersection" for precision
    deduplicate=True,
)
candidates = orchestrator.run()
print(orchestrator.get_statistics())
```

**Rule of thumb:** Start with Collect blocking for exact-match fields, add BM25 for fuzzy name matching, then add Vector blocking if you need to catch semantic variations.

---

## Clustering Backend Selection

### Performance Characteristics

| Backend | Time Complexity | Memory | Parallelism | Edge Limit |
|---------|----------------|--------|-------------|------------|
| `python_dfs` | O(V + E) | O(V + E) | Single-thread | ~100K |
| `python_union_find` | O(E * α(V)) | O(V) | Single-thread | ~1M |
| `python_sparse` | O(V + E) | O(V + E) sparse | Single-thread (C) | ~5M |
| `aql_graph` | Server-dependent | Server-side | ArangoDB parallelism | ~1M |
| `gae_wcc` | O(V + E) | Engine memory | Distributed | 100M+ |

### Recommendations

- **< 10K edges** — Any backend works; `python_union_find` is fine
- **10K – 100K edges** — `python_union_find` (fast, low memory)
- **100K – 1M edges** — `python_sparse` (if scipy installed) or `python_union_find`
- **1M+ edges** — `gae_wcc` (enterprise) or `python_sparse`

### Auto Backend

The `auto` backend (default since v3.5.0) handles this automatically:

```yaml
entity_resolution:
  clustering:
    backend: auto
    auto_select_threshold_edges: 100000
    sparse_backend_enabled: true
    gae:
      enabled: true
```

---

## Embedding Performance

### Model Size vs Speed

| Model | Dimensions | Size | Speed (CPU) | Speed (MPS) | Quality |
|-------|-----------|------|-------------|-------------|---------|
| all-MiniLM-L6-v2 | 384 | 80MB | ~200 rec/s | ~800 rec/s | Good |
| all-mpnet-base-v2 | 768 | 420MB | ~80 rec/s | ~400 rec/s | Better |
| all-MiniLM-L12-v2 | 384 | 120MB | ~150 rec/s | ~600 rec/s | Good+ |

### Batch Size Tuning

Larger batches improve GPU utilization but risk OOM:

```yaml
entity_resolution:
  embedding:
    batch_size: 128        # default
    max_batch_size: 512    # cap to prevent OOM
    device: auto
```

**CPU:** 32–128 is optimal
**MPS:** 128–512 depending on unified memory
**CUDA:** 256–1024 depending on GPU VRAM

---

## Similarity Computation

### Similarity Algorithm Speed

| Algorithm | Speed | Best For |
|-----------|-------|----------|
| Exact match | O(1) | Categorical fields (state, country) |
| Jaro-Winkler | O(n) | Short strings (names, cities) |
| Levenshtein ratio | O(n*m) | General string comparison |
| Jaccard (token) | O(n+m) | Multi-word fields (addresses) |
| Cosine (vector) | O(d) | Pre-computed embeddings |

### Field Weight Optimization

Fields with higher discriminative power should get higher weights:

```yaml
entity_resolution:
  similarity:
    weights:
      name: 0.35         # high — names are distinctive
      phone: 0.25        # high — phone is almost unique
      address: 0.20      # medium — addresses vary in format
      city: 0.10         # low — many entities share a city
      state: 0.10        # low — many entities share a state
```

---

## Benchmarking

### Built-in Benchmark CLI

```bash
# Run blocking benchmark
arango-er benchmark --collection companies --strategies collect,bm25

# Runtime health check
arango-er runtime-health

# Compare against baseline
arango-er runtime-health-compare --baseline baseline.json
```

### Profiling Tips

1. **Blocking** is usually the bottleneck — profile `generate_candidates()` time
2. **Similarity** scales with candidate count — reduce blocking output first
3. **Clustering** is fast for most backends until you hit millions of edges
4. **Embedding** generation is one-time cost — cache vectors in ArangoDB

### Memory Guidelines

| Dataset Size | RAM Needed | Notes |
|-------------|------------|-------|
| 10K records | 1 GB | Any config works |
| 100K records | 4 GB | Watch batch sizes |
| 1M records | 16 GB+ | Use sparse backend, consider GAE |
| 10M records | 64 GB+ | GAE required for clustering |

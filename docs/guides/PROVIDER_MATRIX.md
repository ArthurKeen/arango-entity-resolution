# Provider Compatibility Matrix

**Version:** 3.5.0 | **Last Updated:** March 2026

This matrix documents tested compatibility across embedding runtimes, LLM providers, clustering backends, and platform configurations.

---

## Embedding Runtime Providers

| Runtime | Device | Platform | Status | Notes |
|---------|--------|----------|--------|-------|
| PyTorch | CPU | All | Supported | Default fallback, always works |
| PyTorch | CUDA | Linux + NVIDIA | Supported | Requires `torch` with CUDA build |
| PyTorch | MPS | macOS Apple Silicon | Supported | macOS 12.3+, PyTorch 2.0+ |
| ONNX Runtime | CPU | All | Supported | `pip install onnxruntime` |
| ONNX Runtime | CoreML | macOS | Experimental | Auto-fallback to CPU on failure |
| ONNX Runtime | CUDA | Linux + NVIDIA | Experimental | `pip install onnxruntime-gpu` |
| ONNX Runtime | TensorRT | Linux + NVIDIA | Experimental | `pip install onnxruntime-gpu` |

---

## LLM Providers

| Provider | Model Example | API Key Env Var | Local | Status |
|----------|--------------|-----------------|-------|--------|
| Ollama | `llama3.2:3b` | None (local) | Yes | Supported |
| OpenRouter | `google/gemini-2.0-flash` | `OPENROUTER_API_KEY` | No | Supported |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` | No | Supported |
| Anthropic | `claude-3-5-sonnet` | `ANTHROPIC_API_KEY` | No | Supported |

### LLM Configuration

```yaml
active_learning:
  llm:
    provider: ollama          # or openrouter, openai, anthropic
    model: llama3.2:3b
    base_url: http://localhost:11434
    timeout_seconds: 60
    healthcheck_on_start: true
```

### Healthcheck

```python
from entity_resolution import LLMMatchVerifier, LLMProviderConfig

config = LLMProviderConfig(provider="ollama", model="llama3.2:3b")
verifier = LLMMatchVerifier.from_provider_config(config)
print(verifier.healthcheck())
# {'ok': True, 'model': 'ollama/llama3.2:3b', 'latency_ms': 641.3, 'error': None}
```

---

## Clustering Backends

| Backend | Type | Dependencies | Best For | Status |
|---------|------|-------------|----------|--------|
| `python_dfs` | Local | None | Small graphs (<10K edges) | Supported |
| `python_union_find` | Local | None | Medium graphs (default) | Supported |
| `python_sparse` | Local | `scipy` | Large dense graphs | Supported |
| `aql_graph` | Server-side | ArangoDB 3.11+ | Server-side processing | Supported |
| `gae_wcc` | Enterprise | GAE Engine | Millions of edges | Supported |
| `auto` | Selector | Varies | Automatic best choice | Supported (default) |

### Auto-Selection Logic

When `backend: auto` (default since v3.5.0):

1. **GAE WCC** — if `gae.enabled=True`, GAE is reachable, and edge count exceeds threshold
2. **`python_sparse`** — if scipy is installed and edge count exceeds sparse threshold
3. **`python_union_find`** — general-purpose default

---

## Platform Test Matrix

| Platform | Python | ArangoDB | PyTorch | Embedding | Clustering | LLM |
|----------|--------|----------|---------|-----------|------------|-----|
| macOS arm64 | 3.11 | 3.12 | 2.x (MPS) | PyTorch/MPS | All local | Ollama |
| Linux x86_64 | 3.10–3.12 | 3.12 | 2.x (CUDA) | PyTorch/CUDA | All + GAE | All |
| Linux x86_64 | 3.10–3.12 | 3.12 | N/A | ONNX/CPU | Local only | OpenRouter |

---

## Optional Dependency Groups

Install only what you need:

```bash
pip install arango-entity-resolution          # core only
pip install arango-entity-resolution[ml]      # + sentence-transformers, torch
pip install arango-entity-resolution[onnx]    # + onnxruntime
pip install arango-entity-resolution[sparse]  # + scipy (sparse clustering)
pip install arango-entity-resolution[llm]     # + litellm
pip install arango-entity-resolution[mcp]     # + MCP server
pip install arango-entity-resolution[ml,llm]  # combine extras
```

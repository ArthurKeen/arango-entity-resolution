"""
Example: Local LLM Match Verification with Ollama

Demonstrates using a local Ollama model to verify ambiguous entity pairs.
Requires: ollama running locally with a model pulled (e.g. llama3.2:3b).

    ollama serve
    ollama pull llama3.2:3b
    python examples/ollama_llm_verification.py
"""

from entity_resolution.config.er_config import LLMProviderConfig
from entity_resolution.reasoning.llm_verifier import LLMMatchVerifier


def main():
    # 1. Configure Ollama provider
    config = LLMProviderConfig(
        provider="ollama",
        model="llama3.2:3b",
    )
    print(f"LLM model string: {config.to_litellm_model_string()}")
    print(f"Base URL: {config.base_url}")

    # 2. Build verifier from config
    verifier = LLMMatchVerifier.from_provider_config(config, entity_type="company")

    # 3. Healthcheck
    health = verifier.healthcheck()
    print(f"\nHealthcheck: {'PASS' if health['ok'] else 'FAIL'}")
    print(f"  Latency: {health['latency_ms']}ms")
    if not health["ok"]:
        print(f"  Error: {health['error']}")
        print("  Make sure Ollama is running: ollama serve")
        return

    # 4. Verify an ambiguous match (score in 0.55–0.80 range triggers LLM)
    record_a = {
        "name": "Acme Corporation",
        "city": "New York",
        "state": "NY",
        "phone": "212-555-1234",
    }
    record_b = {
        "name": "ACME Corp.",
        "city": "New York",
        "state": "NY",
        "phone": "(212) 555-1234",
    }
    field_scores = {
        "name": {"score": 0.82, "method": "jaro_winkler"},
        "city": {"score": 1.00, "method": "jaro_winkler"},
        "state": {"score": 1.00, "method": "exact"},
        "phone": {"score": 0.65, "method": "jaro_winkler"},
    }

    print("\n--- Ambiguous Pair (score=0.72, triggers LLM) ---")
    result = verifier.verify(record_a, record_b, score=0.72, field_scores=field_scores)
    print(f"  Decision:       {result['decision']}")
    print(f"  Confidence:     {result['confidence']}")
    print(f"  Reasoning:      {result['reasoning']}")
    print(f"  Score override: {result['score_override']}")
    print(f"  LLM called:     {result['llm_called']}")

    # 5. Fast-path: clear match (no LLM call)
    print("\n--- Clear Match (score=0.95, fast-path) ---")
    result_high = verifier.verify(record_a, record_b, score=0.95)
    print(f"  Decision:   {result_high['decision']}")
    print(f"  LLM called: {result_high['llm_called']}")

    # 6. Fast-path: clear non-match (no LLM call)
    print("\n--- Clear Non-Match (score=0.30, fast-path) ---")
    result_low = verifier.verify(record_a, record_b, score=0.30)
    print(f"  Decision:   {result_low['decision']}")
    print(f"  LLM called: {result_low['llm_called']}")


if __name__ == "__main__":
    main()

"""
LLM-powered match verification for ambiguous entity pairs.

When the similarity score falls in an uncertain range (default 0.55–0.80),
this verifier calls an LLM via litellm to make a binary match/no-match
decision.  This dramatically improves precision for hard cases like
nicknames, abbreviated company names, and varied address formats.

Supports any litellm-compatible model:
    openrouter/google/gemini-2.0-flash
    openai/gpt-4o
    anthropic/claude-3-5-sonnet-20241022
    ollama/mistral  (local, no API key needed)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import litellm

logger = logging.getLogger(__name__)


MATCH_PROMPT_TEMPLATE = """\
You are an expert in data quality and entity resolution.

Two records have been compared and produced a similarity score of {score:.2f}
(scale 0–1), which is uncertain. Your job is to decide whether they refer to
the SAME real-world {entity_type}.

## Record A
{record_a}

## Record B
{record_b}

## Field-level similarity scores
{field_scores}

## Instructions
- Answer with ONLY a JSON object in this exact format:
  {{"decision": "match" | "no_match", "confidence": 0.0–1.0, "reasoning": "..."}}
- "match" means both records refer to the same {entity_type}.
- "no_match" means they are clearly different {entity_type}s.
- "confidence" is your certainty (0 = complete guess, 1 = certain).
- "reasoning" should be 1–2 sentences max.
- Do NOT add any text outside the JSON object.
"""


class LLMMatchVerifier:
    """
    Verifies ambiguous entity match pairs using an LLM.

    Parameters
    ----------
    model:
        Any litellm model string, e.g. "openrouter/google/gemini-2.0-flash"
        or "openai/gpt-4o".  Defaults to OPENROUTER_MODEL env var, falling
        back to "openrouter/google/gemini-2.0-flash".
    low_threshold:
        Pairs with scores **below** this are accepted as no_match without LLM.
    high_threshold:
        Pairs with scores **above** this are accepted as match without LLM.
    entity_type:
        Human-readable entity type for the prompt (e.g. "company", "person").
    api_key:
        Override API key; otherwise read from OPENROUTER_API_KEY / OPENAI_API_KEY.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        low_threshold: float = 0.55,
        high_threshold: float = 0.80,
        entity_type: str = "entity",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model or os.getenv("OPENROUTER_MODEL", "openrouter/google/gemini-2.0-flash")
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.entity_type = entity_type
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def needs_verification(self, score: float) -> bool:
        """Return True if the score falls in the uncertain range."""
        return self.low_threshold <= score < self.high_threshold

    def verify(
        self,
        record_a: Dict[str, Any],
        record_b: Dict[str, Any],
        score: float,
        field_scores: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call the LLM to verify whether *record_a* and *record_b* match.

        If the score is outside the uncertain range this returns immediately
        without making an LLM call.

        Returns a dict with keys:
        - ``decision``: "match" | "no_match" | "skipped"
        - ``confidence``: float (LLM's self-reported confidence)
        - ``reasoning``: str
        - ``score_override``: new score if LLM overrides original (or None)
        - ``llm_called``: bool
        - ``model``: model name used
        """
        # Fast-path for clear matches / non-matches
        if score >= self.high_threshold:
            return self._fast_result("match", score, llm_called=False)
        if score < self.low_threshold:
            return self._fast_result("no_match", score, llm_called=False)

        # LLM call for uncertain pairs
        try:
            return self._call_llm(record_a, record_b, score, field_scores or {})
        except Exception as exc:
            logger.warning("LLM verification failed (falling back to score): %s", exc)
            decision = "match" if score >= (self.low_threshold + self.high_threshold) / 2 else "no_match"
            return {
                "decision": decision,
                "confidence": score,
                "reasoning": f"LLM unavailable ({exc}); decision based on raw score.",
                "score_override": None,
                "llm_called": False,
                "model": self.model,
                "error": str(exc),
            }

    def verify_batch(
        self,
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any], float]],
        field_scores_list: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Verify a list of (record_a, record_b, score) tuples.

        Only calls the LLM for pairs in the uncertain range.
        """
        results = []
        for i, (a, b, score) in enumerate(pairs):
            fs = field_scores_list[i] if field_scores_list else None
            results.append(self.verify(a, b, score, fs))
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        record_a: Dict[str, Any],
        record_b: Dict[str, Any],
        score: float,
        field_scores: Dict[str, Any],
    ) -> Dict[str, Any]:
        # litellm is imported at module level

        # Strip internal ArangoDB keys from display
        def _clean(d: Dict[str, Any]) -> Dict[str, Any]:
            return {k: v for k, v in d.items() if not k.startswith("_")}

        fs_text = "\n".join(
            f"  {field}: {info.get('score', '?'):.2f} ({info.get('method', '?')})"
            for field, info in field_scores.items()
        ) or "  (no field breakdown available)"

        prompt = MATCH_PROMPT_TEMPLATE.format(
            score=score,
            entity_type=self.entity_type,
            record_a=json.dumps(_clean(record_a), indent=2, default=str),
            record_b=json.dumps(_clean(record_b), indent=2, default=str),
            field_scores=fs_text,
        )

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
            "temperature": 0.1,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key

        response = litellm.completion(**kwargs)
        raw = response.choices[0].message.content.strip()

        # Parse JSON response
        try:
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON: %s", raw[:200])
            parsed = {"decision": "match" if score > 0.65 else "no_match", "confidence": 0.5, "reasoning": raw}

        decision = parsed.get("decision", "no_match")
        confidence = float(parsed.get("confidence", score))
        reasoning = parsed.get("reasoning", "")

        # Synthesise a score override: if LLM says match, push above high_threshold
        if decision == "match" and score < self.high_threshold:
            score_override = self.high_threshold + (1.0 - self.high_threshold) * confidence
        elif decision == "no_match" and score >= self.low_threshold:
            score_override = self.low_threshold * (1.0 - confidence)
        else:
            score_override = None

        return {
            "decision": decision,
            "confidence": round(confidence, 4),
            "reasoning": reasoning,
            "score_override": round(score_override, 4) if score_override is not None else None,
            "llm_called": True,
            "model": self.model,
        }

    @staticmethod
    def _fast_result(decision: str, score: float, *, llm_called: bool) -> Dict[str, Any]:
        return {
            "decision": decision,
            "confidence": score,
            "reasoning": "Score outside uncertain range; no LLM call needed.",
            "score_override": None,
            "llm_called": llm_called,
            "model": None,
        }

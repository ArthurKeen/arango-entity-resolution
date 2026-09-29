"""EM must reject input outside its likelihood's domain rather than fit it.

``estimate_mu`` is Bernoulli: each observed cell is 1 (agrees) or 0 (disagrees).
Fed raw similarity scores instead, the algebra still runs and EM reported
``converged=True`` with m and u both near 0.5 — a meaningless model, returned
without a warning. ``inf`` was worse: ``isfinite`` masked it as "unobserved".
The categorical path had the analogous hole: fractional level indices were
truncated to an integer level by ``astype``.
"""

from __future__ import annotations

import numpy as np
import pytest

from entity_resolution.learning.em_estimator import estimate_categorical_mu, estimate_mu

FIELDS = ["a", "b"]
LEVELS = {"a": ["exact", "close", "else"], "b": ["exact", "close", "else"]}


def _binary():
    rng = np.random.default_rng(0)
    return rng.integers(0, 2, size=(200, 2)).astype(np.float64)


def test_binary_accepts_indicators_and_nan() -> None:
    gamma = _binary()
    gamma[::7, 1] = np.nan
    assert estimate_mu(gamma, FIELDS).n_pairs == 200


def test_binary_rejects_similarity_scores() -> None:
    gamma = np.random.default_rng(0).random((200, 2))
    with pytest.raises(ValueError, match="agreement indicators"):
        estimate_mu(gamma, FIELDS)


def test_binary_rejects_inf() -> None:
    gamma = _binary()
    gamma[3, 0] = np.inf
    with pytest.raises(ValueError, match="inf"):
        estimate_mu(gamma, FIELDS)


def test_categorical_rejects_fractional_levels() -> None:
    gamma = np.random.default_rng(0).integers(0, 3, size=(200, 2)).astype(np.float64)
    gamma[5, 1] = 1.7
    with pytest.raises(ValueError, match="integer level"):
        estimate_categorical_mu(gamma, LEVELS)


def test_categorical_rejects_inf() -> None:
    gamma = np.random.default_rng(0).integers(0, 3, size=(200, 2)).astype(np.float64)
    gamma[5, 0] = -np.inf
    with pytest.raises(ValueError, match="inf"):
        estimate_categorical_mu(gamma, LEVELS)

"""The mechanism behind "use Fellegi-Sunter on structured records".

Measured on FEBRL person records, FS beats weighted similarity decisively
(dataset3: pairwise F1 0.9995 against 0.9908, and 0.9985 against 0.9645 at the
shipped threshold), having lost on every free-text dataset. The explanation is
not that FS is better in general — it is that FEBRL's ten fields have
chance-agreement rates spanning three orders of magnitude, from `state` at 0.212
to `soc_sec_id` at 0.0007, and a uniform weighted average cannot express a 300x
difference in evidential value.

``docs/BENCHMARKS.md`` now recommends FS on that basis. This file is the gate
behind the recommendation: the benchmark needs a download and a live database, so
nothing in the unit run would notice if the mechanism broke.

What is asserted is the mechanism, not the benchmark number. And the mechanism is
narrower than "FS separates better" — with two fields that agree exactly or not at
all, FS and an average rank pairs *identically*, so a test built on that shape
would pass while proving nothing. The spread only changes decisions when partial
agreement patterns must be traded off against each other: is agreeing on one
near-unique identifier worth more than agreeing on three low-cardinality
attributes? An average cannot even ask. That trade-off is what these tests pin.

Everything runs on pure functions — comparisons built in Python, ``estimate_mu``
is numpy, the scorer takes learned parameters directly. No database.
"""

from __future__ import annotations

import math

import pytest

from entity_resolution.learning.em_estimator import EMEstimator
from entity_resolution.learning.fellegi_sunter_scorer import FellegiSunterScorer

pytestmark = pytest.mark.unit

WEAK_FIELDS = ["region", "sector", "band"]
STRONG_FIELD = "member_id"
FIELDS = [*WEAK_FIELDS, STRONG_FIELD]

# 150 entities, two records each. Three attributes take five values apiece, so
# unrelated records share one about a fifth of the time; the member id is unique
# per entity. This is the FEBRL `state` vs `soc_sec_id` contrast reduced to its
# essentials. The fixture is fully deterministic — no sampling, so no flakiness.
N_ENTITIES = 150
VALUES = ["v0", "v1", "v2", "v3", "v4"]


def _records():
    """Two records per entity, the id absent from every third duplicate.

    Without that gap the id would be a primary key and the task trivial; with it,
    the id is strong evidence rather than an answer key, and some true pairs must
    be matched without it.
    """
    out = []
    for e in range(N_ENTITIES):
        attrs = {
            "region": VALUES[e % 5],
            "sector": VALUES[(e // 5) % 5],
            "band": VALUES[(e * 3) % 5],  # gcd(3,5)=1, so balanced
        }
        member = f"MB{e:04d}XKQ"
        out.append({"entity": e, **attrs, STRONG_FIELD: member})
        out.append({
            "entity": e, **attrs,
            STRONG_FIELD: None if e % 3 == 0 else member,
        })
    return out


def _compare(r1, r2):
    """Exact-agreement comparator; ``None`` means the field was not observed."""
    out = {}
    for f in FIELDS:
        a, b = r1[f], r2[f]
        out[f] = None if a is None or b is None else (1.0 if a == b else 0.0)
    return out


@pytest.fixture(scope="module")
def parameters():
    """u counted over the pair population; m counted over the true matches.

    u is genuinely unsupervised — it is a frequency over all pairs, which are
    overwhelmingly non-matches. m uses the fixture's labels, and that is a
    deliberate scoping decision rather than a shortcut: this file gates how the
    learned SPREAD drives decisions, and mixing in EM's convergence behaviour
    made the gate brittle for a reason unrelated to what it tests. EM's own
    correctness is covered in ``test_em_estimator.py``.

    Worth recording, because it cost time to diagnose and is a real property:
    running EM on this fixture converges to the wrong latent class. It settles on
    "shares a region" (m_region = 1.0, m_member = 0.019, lambda = 0.197) rather
    than "same entity" (150 pairs of 44,850). A five-valued field creates a
    spurious class of ~8,850 co-agreeing pairs, and that split offers more
    likelihood than the true one from a standard initialisation. Unsupervised EM
    finds the DOMINANT latent split, which is not guaranteed to be the one you
    wanted — on real records the fields co-agree richly enough that the two
    coincide, which is why the FEBRL benchmark converges correctly.
    """
    records = _records()
    pairs = [
        (r1, r2)
        for i, r1 in enumerate(records)
        for r2 in records[i + 1:]
    ]
    comparisons = [(_compare(r1, r2), r1["entity"] == r2["entity"]) for r1, r2 in pairs]

    u, m = {}, {}
    for f in FIELDS:
        non_match = [c[f] for c, is_match in comparisons if not is_match and c[f] is not None]
        match = [c[f] for c, is_match in comparisons if is_match and c[f] is not None]
        # Clamped away from 0 and 1: log(m/u) and log((1-m)/(1-u)) must stay finite.
        u[f] = min(max(sum(non_match) / len(non_match), 1.0 / (len(non_match) + 1)), 1 - 1e-6)
        m[f] = min(max(sum(match) / len(match), 1e-6), 1 - 1e-6)
    return m, u


def _scorer(parameters):
    m, u = parameters
    # Match prior reflects the fixture: 150 true pairs among 44,850.
    return FellegiSunterScorer(
        m=m, u=u, match_prior=150 / 44850, default_threshold=0.5
    )


def test_chance_agreement_spread_is_recovered_from_the_data(parameters):
    """u must reflect each field's real cardinality.

    Derived, not tuned. Five values over 300 records puts 60 in each, so 5*C(60,2)
    = 8,850 pairs agree of C(300,2) = 44,850; removing the 150 true pairs leaves
    u = 8,700/44,700 = 0.195.

    The identifier agrees on NO non-match pair, because it is unique per entity.
    Its u is therefore the clamp floor, 1/(n+1) over 31,025 observed non-match
    pairs. That is the honest answer rather than a limitation: chance agreement on
    a unique key is not small, it is zero, and the floor is what keeps log(m/u)
    finite. It also means the measured spread here is ~6,000x, wider than FEBRL's
    300x.
    """
    _, u = parameters
    for f in WEAK_FIELDS:
        assert u[f] == pytest.approx(0.195, abs=0.02), (f, u)
    assert 0.0 < u[STRONG_FIELD] < 1e-3, (
        f"a unique identifier must have near-zero chance agreement, and strictly "
        f"positive so log(m/u) stays finite: {u}"
    )

    assert u["region"] > 20 * u[STRONG_FIELD], (
        f"the spread that justifies FS was not recovered: {u}"
    )


def test_the_spread_reaches_the_weights(parameters):
    """log(m/u) is what the scorer sums, so the spread must survive into it.

    A faithful u that produced indistinguishable weights would be a silent no-op
    — the failure mode this project keeps finding.
    """
    m, u = parameters
    llr = {f: math.log(m[f] / u[f]) for f in FIELDS}

    assert llr[STRONG_FIELD] > llr["region"] + 2.0, (
        f"agreeing on a unique id must outweigh agreeing on one of five values "
        f"by a wide margin, got {llr}"
    )
    for f in WEAK_FIELDS:
        assert llr[f] < 2.5, (f, llr)


def test_one_strong_agreement_outranks_three_weak_ones(parameters):
    """The decision an average cannot make, and the whole reason to prefer FS.

    Both pairs below agree on everything they can be compared on, so an untuned
    average scores them identically at 1.0 and the ordering is arbitrary. FS knows
    one near-unique identifier is worth more than three attributes with five
    values each, and orders them accordingly.
    """
    scorer = _scorer(parameters)

    weak_only = {"region": 1.0, "sector": 1.0, "band": 1.0, STRONG_FIELD: None}
    strong_only = {"region": None, "sector": None, "band": None, STRONG_FIELD: 1.0}

    def untuned_average(sims):
        observed = [v for v in sims.values() if v is not None]
        return sum(observed) / len(observed) if observed else 0.0

    assert untuned_average(weak_only) == untuned_average(strong_only) == 1.0, (
        "fixture broken: the average must be unable to separate these"
    )
    assert scorer.total_llr(strong_only) > scorer.total_llr(weak_only), (
        f"FS ranked three weak agreements ({scorer.total_llr(weak_only):.3f} "
        f"nats) above one strong one ({scorer.total_llr(strong_only):.3f} nats); "
        "the learned spread is not driving the decision"
    )


def test_a_missing_strong_field_is_not_disagreement(parameters):
    """Every third duplicate has no id and must stay matchable.

    The spread makes this sharper than the general null-handling case: charging an
    absent id as disagreement would subtract the largest weight in the model, so
    exactly those pairs would become unmatchable.
    """
    scorer = _scorer(parameters)
    base = {"region": 1.0, "sector": 1.0, "band": 1.0}

    present = scorer.total_llr({**base, STRONG_FIELD: 1.0})
    missing = scorer.total_llr({**base, STRONG_FIELD: None})
    disagrees = scorer.total_llr({**base, STRONG_FIELD: 0.0})

    assert disagrees < missing < present, (
        "an unobserved id must sit strictly between agreement and disagreement, "
        f"got present={present:.3f} missing={missing:.3f} "
        f"disagree={disagrees:.3f}"
    )

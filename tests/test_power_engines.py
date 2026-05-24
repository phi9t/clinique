"""RFC-0003 engine reproduction suite.

Validation = round-trip minimality (independently re-derived in-test from the normal-approx
formula) + agreement with published literature anchors. The in-test power functions are an
independent implementation of the formula, so they verify the engine's integer *search* found the
minimal N — not just that the engine agrees with itself.
"""

import math
from statistics import NormalDist

from clinique.power.engines import ReferenceEngine

_N = NormalDist()


def _za(alpha, sides):
    return _N.inv_cdf(1 - alpha / 2) if sides == 2 else _N.inv_cdf(1 - alpha)


def _pwr_means(n1, ratio, delta, sd, za):
    n2 = math.ceil(ratio * n1)
    se = sd * math.sqrt(1 / n1 + 1 / n2)
    return _N.cdf(abs(delta) / se - za)


def _pwr_props(n1, ratio, p1, p2, za):
    n2 = math.ceil(ratio * n1)
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return _N.cdf(abs(p1 - p2) / se - za)


def _pwr_events(events, alloc, hr, za):
    return _N.cdf(math.sqrt(events * alloc * (1 - alloc)) * abs(math.log(hr)) - za)


def test_two_means_anchor_and_minimality():
    eng = ReferenceEngine()
    r = eng.two_sample_means(delta=0.5, sd=1.0, alpha=0.05, power=0.80)
    n1 = int(r.outputs["n1"])
    assert abs(n1 - 63) <= 1  # normal-approx ~63/group (t-based gives 64)
    za = _za(0.05, 2)
    assert _pwr_means(n1, 1.0, 0.5, 1.0, za) >= 0.80
    assert _pwr_means(n1 - 1, 1.0, 0.5, 1.0, za) < 0.80


def test_two_proportions_anchor_and_minimality():
    eng = ReferenceEngine()
    r = eng.two_proportions(p1=0.6, p2=0.4, alpha=0.05, power=0.80)
    n1 = int(r.outputs["n1"])
    assert abs(n1 - 95) <= 1
    za = _za(0.05, 2)
    assert _pwr_props(n1, 1.0, 0.6, 0.4, za) >= 0.80
    assert _pwr_props(n1 - 1, 1.0, 0.6, 0.4, za) < 0.80


def test_survival_logrank_anchor_and_minimality():
    eng = ReferenceEngine()
    r = eng.survival_logrank(hazard_ratio=0.7, alpha=0.05, power=0.80)
    events = int(r.outputs["events_total"])
    assert abs(events - 247) <= 1  # Schoenfeld
    za = _za(0.05, 2)
    assert _pwr_events(events, 0.5, 0.7, za) >= 0.80
    assert _pwr_events(events - 1, 0.5, 0.7, za) < 0.80


def test_determinism():
    eng = ReferenceEngine()
    a = eng.two_sample_means(delta=0.4, sd=1.2, alpha=0.05, power=0.9)
    b = eng.two_sample_means(delta=0.4, sd=1.2, alpha=0.05, power=0.9)
    assert a == b


def test_monotonic_more_power_needs_more_n():
    eng = ReferenceEngine()
    lo = eng.two_sample_means(delta=0.5, sd=1.0, alpha=0.05, power=0.80)
    hi = eng.two_sample_means(delta=0.5, sd=1.0, alpha=0.05, power=0.90)
    assert hi.outputs["n_total"] > lo.outputs["n_total"]


def test_smaller_effect_needs_more_n():
    eng = ReferenceEngine()
    big = eng.two_sample_means(delta=0.8, sd=1.0, alpha=0.05, power=0.80)
    small = eng.two_sample_means(delta=0.3, sd=1.0, alpha=0.05, power=0.80)
    assert small.outputs["n_total"] > big.outputs["n_total"]

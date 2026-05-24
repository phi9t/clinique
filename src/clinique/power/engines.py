"""Validated power engines (RFC-0003).

The ``ReferenceEngine`` is a deterministic, pure-Python implementation used as an independent
cross-check oracle (and offline fallback for the Docker rpact engine). "Validated" here means:
deterministic + a reproduction suite that checks (a) round-trip minimality — the returned N
achieves >= target power while N-1 does not — and (b) agreement with published normal-approximation
literature anchors. This is the same validation philosophy rpact/gsDesign use.

All engines use the normal (z) approximation. The t-distribution correction for small samples is
tracked as a backlog item.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Protocol

from ..substrate.records import EngineResult

_N = NormalDist()
REFERENCE_VERSION = "reference-0.1.0"

_ACHIEVED_DP = 4  # display precision for achieved power; engines round to this canonically


def _z(p: float) -> float:
    return _N.inv_cdf(p)


def _phi(x: float) -> float:
    return _N.cdf(x)


def _za(alpha: float, sides: int) -> float:
    return _z(1.0 - alpha / 2.0) if sides == 2 else _z(1.0 - alpha)


class PowerEngine(Protocol):
    name: str
    version: str

    def two_sample_means(
        self, *, delta: float, sd: float, alpha: float, power: float, ratio: float, sides: int
    ) -> EngineResult: ...

    def two_proportions(
        self, *, p1: float, p2: float, alpha: float, power: float, ratio: float, sides: int
    ) -> EngineResult: ...

    def survival_logrank(
        self, *, hazard_ratio: float, alpha: float, power: float, allocation: float, sides: int
    ) -> EngineResult: ...


def _minimal_n1(power_fn, target: float, seed: float) -> int:
    """Smallest integer n1 >= 2 with power_fn(n1) >= target.

    power_fn is assumed monotone increasing.
    """
    n1 = max(2, math.ceil(seed))
    while n1 > 2 and power_fn(n1 - 1) >= target:
        n1 -= 1
    while power_fn(n1) < target:
        n1 += 1
    return n1


class ReferenceEngine:
    """Deterministic normal-approximation power engine (independent oracle)."""

    name = "reference"
    version = REFERENCE_VERSION

    @property
    def _tools(self) -> list[dict[str, str]]:
        return [{"name": self.name, "version": self.version}]

    def two_sample_means(
        self,
        *,
        delta: float,
        sd: float,
        alpha: float,
        power: float,
        ratio: float = 1.0,
        sides: int = 2,
    ) -> EngineResult:
        za = _za(alpha, sides)

        def pwr(n1: int) -> float:
            n2 = math.ceil(ratio * n1)
            se = sd * math.sqrt(1.0 / n1 + 1.0 / n2)
            return _phi(abs(delta) / se - za)

        seed = ((za + _z(power)) ** 2) * sd**2 * (1.0 + 1.0 / ratio) / (delta**2)
        n1 = _minimal_n1(pwr, power, seed)
        n2 = math.ceil(ratio * n1)
        return EngineResult(
            engine=self.name,
            version=self.version,
            method="two_sample_means",
            inputs={
                "delta": delta,
                "sd": sd,
                "alpha": alpha,
                "power": power,
                "ratio": ratio,
                "sides": sides,
            },
            outputs={"n1": float(n1), "n2": float(n2), "n_total": float(n1 + n2)},
            achieved={"achieved_power": round(pwr(n1), _ACHIEVED_DP)},
            tools=self._tools,
        )

    def two_proportions(
        self,
        *,
        p1: float,
        p2: float,
        alpha: float,
        power: float,
        ratio: float = 1.0,
        sides: int = 2,
    ) -> EngineResult:
        za = _za(alpha, sides)
        diff = abs(p1 - p2)

        def pwr(n1: int) -> float:
            n2 = math.ceil(ratio * n1)
            se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
            return _phi(diff / se - za)

        seed = ((za + _z(power)) ** 2) * (p1 * (1 - p1) + p2 * (1 - p2) / ratio) / (diff**2)
        n1 = _minimal_n1(pwr, power, seed)
        n2 = math.ceil(ratio * n1)
        return EngineResult(
            engine=self.name,
            version=self.version,
            method="two_proportions",
            inputs={
                "p1": p1,
                "p2": p2,
                "alpha": alpha,
                "power": power,
                "ratio": ratio,
                "sides": sides,
            },
            outputs={"n1": float(n1), "n2": float(n2), "n_total": float(n1 + n2)},
            achieved={"achieved_power": round(pwr(n1), _ACHIEVED_DP)},
            tools=self._tools,
        )

    def survival_logrank(
        self,
        *,
        hazard_ratio: float,
        alpha: float,
        power: float,
        allocation: float = 0.5,
        sides: int = 2,
    ) -> EngineResult:
        za = _za(alpha, sides)
        ln_hr = math.log(hazard_ratio)
        var_factor = allocation * (1.0 - allocation) * ln_hr**2

        def pwr(events: int) -> float:
            return _phi(math.sqrt(events * allocation * (1.0 - allocation)) * abs(ln_hr) - za)

        seed = ((za + _z(power)) ** 2) / var_factor
        events = _minimal_n1(pwr, power, seed)
        return EngineResult(
            engine=self.name,
            version=self.version,
            method="survival_logrank",
            inputs={
                "hazard_ratio": hazard_ratio,
                "alpha": alpha,
                "power": power,
                "allocation": allocation,
                "sides": sides,
            },
            outputs={"events_total": float(events)},
            achieved={"achieved_power": round(pwr(events), _ACHIEVED_DP)},
            tools=self._tools,
        )

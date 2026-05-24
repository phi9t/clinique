"""Design intake + deterministic method selection (RFC-0003 §5.2).

Method selection is rule-based here — a deterministic, testable stand-in for the LLM slot. The LLM
would *propose* the mapping with rationale; the mapping itself is what we validate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..substrate.records import Assumption


@dataclass
class DesignIntake:
    """A trial-design description sufficient to pick a method and assemble assumptions.

    ``params`` holds design-specific sourced assumptions, e.g. ``{"delta": Assumption(...),
    "sd": Assumption(...)}`` for a continuous endpoint.
    """

    endpoint_type: str  # "continuous" | "binary" | "time_to_event"
    alpha: Assumption
    power: Assumption
    params: dict[str, Assumption] = field(default_factory=dict)
    sides: int = 2
    ratio: float = 1.0
    design_type: str = "superiority"


ENDPOINT_TO_ENGINE: dict[str, str] = {
    "continuous": "two_sample_means",
    "binary": "two_proportions",
    "time_to_event": "survival_logrank",
}


def select_method(intake: DesignIntake) -> str:
    try:
        return ENDPOINT_TO_ENGINE[intake.endpoint_type]
    except KeyError as exc:
        raise ValueError(f"no engine for endpoint_type={intake.endpoint_type!r}") from exc

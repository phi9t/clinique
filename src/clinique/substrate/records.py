"""Shared dataclasses for the substrate (RFC-0000 §4/§7)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Assumption:
    """A typed, sourced input value (RFC-0003 §5.3).

    ``source_kind`` is one of ``literature`` | ``protocol`` | ``assumption``. Values with
    ``source_kind == "assumption"`` carry no external source and must be signed off by a human
    (``needs_signoff``).
    """

    name: str
    value: float
    unit: str
    source_kind: str
    source_ref: str
    rationale: str = ""

    @property
    def needs_signoff(self) -> bool:
        return self.source_kind == "assumption"


@dataclass(frozen=True)
class EngineResult:
    """The output of a *validated engine* run. The only birthplace of result numbers.

    ``outputs`` holds the primary numbers (e.g. n1/n2/n_total or events_total); ``achieved``
    holds verification numbers (e.g. achieved_power); ``inputs`` echoes the numeric inputs the
    engine actually consumed. ``tools`` records engine identity for provenance.
    """

    engine: str
    version: str
    method: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, float] = field(default_factory=dict)
    achieved: dict[str, float] = field(default_factory=dict)
    tools: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ComputationRecord:
    """A reproducible record of a computation (RFC-0003 §5.7).

    ``engine`` is the primary run; ``sensitivity_runs`` are additional engine runs whose numbers
    are also legitimate provenance. ``result`` + ``narrative`` are what humans read and are what
    the numeric-provenance linter checks.
    """

    capability: str
    method: str
    engine: EngineResult
    assumptions: list[Assumption]
    result: dict[str, float] = field(default_factory=dict)
    sensitivity_runs: list[EngineResult] = field(default_factory=list)
    narrative: str = ""
    ledger_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def unsourced_assumptions(self) -> list[Assumption]:
        return [a for a in self.assumptions if a.needs_signoff]

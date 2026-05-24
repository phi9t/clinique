"""Numeric-provenance linter (RFC-0000 §7).

No statistical/numeric value in an output may originate from LLM reasoning. Every number in a
``ComputationRecord``'s ``result`` and ``narrative`` must trace (within tolerance) to either an
``EngineResult`` (outputs/achieved/inputs, including sensitivity runs) or an ``Assumption`` value.
Numbers that don't trace are violations. The orchestrator runs this as a hard gate before writing
to the ledger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .records import ComputationRecord

# Matches ints, decimals, thousands-separated, and scientific notation.
_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?")

# Structural/formatting constants that need no provenance. Kept tiny and explicit.
DEFAULT_WHITELIST: frozenset[float] = frozenset({0.0, 1.0, 2.0, 100.0})

_ABS_TOL = 1e-6
_REL_TOL = 1e-4  # tolerates 4-decimal display rounding; far tighter than any plausible fabrication


@dataclass(frozen=True)
class Violation:
    value: float
    context: str


class NumericProvenanceError(Exception):
    """Raised when an output contains numbers that do not trace to an engine or assumption."""

    def __init__(self, violations: list[Violation]):
        self.violations = violations
        joined = "; ".join(f"{v.value!r} near '{v.context.strip()}'" for v in violations)
        super().__init__(f"{len(violations)} untraceable number(s): {joined}")


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _blessed_values(record: ComputationRecord) -> set[float]:
    vals: set[float] = set()
    for a in record.assumptions:
        vals.add(float(a.value))
    for er in (record.engine, *record.sensitivity_runs):
        for bag in (er.outputs, er.achieved, er.inputs):
            for v in bag.values():
                if _is_number(v):
                    vals.add(float(v))
    return vals


def _matches(value: float, candidates: set[float]) -> bool:
    for c in candidates:
        if abs(value - c) <= max(_ABS_TOL, _REL_TOL * abs(c)):
            return True
    return False


def _parse_numbers(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for m in _NUM_RE.finditer(text):
        raw = m.group().replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        start, end = max(0, m.start() - 24), min(len(text), m.end() + 24)
        out.append((value, text[start:end]))
    return out


def check_numeric_provenance(
    record: ComputationRecord,
    whitelist: frozenset[float] = DEFAULT_WHITELIST,
) -> list[Violation]:
    """Return the list of numbers in result+narrative that do not trace to provenance."""
    blessed = _blessed_values(record) | set(whitelist)

    targets: list[tuple[float, str]] = []
    for key, v in record.result.items():
        if _is_number(v):
            targets.append((float(v), f"result.{key}"))
    targets.extend(_parse_numbers(record.narrative))

    return [Violation(value, ctx) for value, ctx in targets if not _matches(value, blessed)]

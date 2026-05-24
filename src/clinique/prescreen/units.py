"""Lab unit normalization for prescreening threshold checks."""

from __future__ import annotations

import re

# Canonical cells/uL for absolute neutrophil count style labs.
_CELLS_PER_UL_ALIASES = {
    "/ul",
    "/uL",
    "cells/ul",
    "cells/uL",
    "cell/ul",
    "cell/uL",
    "10*3/uL",
    "10^3/uL",
    "10*3/ul",
    "10^3/ul",
    "k/ul",
    "k/uL",
    "K/uL",
    "K/ul",
    "10e3/uL",
    "x10^3/uL",
    "x10*3/uL",
}

_UNIT_RE = re.compile(
    r"(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z0-9*/^.\-]+)?",
)


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    cleaned = unit.strip().replace(" ", "")
    lowered = cleaned.lower()
    if lowered in {u.lower() for u in _CELLS_PER_UL_ALIASES}:
        return "cells/uL"
    return cleaned


def to_cells_per_ul(value: float, unit: str | None) -> float | None:
    """Convert a lab value to cells/uL when the unit is recognized."""
    if unit is None:
        return value
    cleaned = unit.strip()
    lowered = cleaned.lower().replace(" ", "")
    if lowered in {"k/ul"} or "10*3" in lowered or "10^3" in lowered:
        return value * 1000.0
    if "/ul" in lowered or "cells" in lowered:
        return value
    return None


def parse_value_with_unit(text: str) -> tuple[float, str | None] | None:
    match = _UNIT_RE.search(text)
    if match is None:
        return None
    try:
        value = float(match.group("value"))
    except ValueError:
        return None
    unit = match.group("unit")
    return value, unit


def compare_threshold(
    observed_value: float,
    observed_unit: str | None,
    *,
    operator: str,
    threshold_value: float,
    threshold_unit: str | None,
) -> bool | None:
    """Return True/False if comparable, None if units cannot be reconciled."""
    obs = to_cells_per_ul(observed_value, observed_unit)
    thr = to_cells_per_ul(threshold_value, threshold_unit)
    if obs is None or thr is None:
        # Fallback: same numeric compare when units absent
        if observed_unit is None and threshold_unit is None:
            obs, thr = observed_value, threshold_value
        else:
            return None
    if operator == ">=":
        return obs >= thr
    if operator == ">":
        return obs > thr
    if operator == "<=":
        return obs <= thr
    if operator == "<":
        return obs < thr
    if operator == "=":
        return abs(obs - thr) <= max(1e-6, 0.01 * abs(thr))
    if operator == "!=":
        return abs(obs - thr) > max(1e-6, 0.01 * abs(thr))
    raise ValueError(f"unsupported operator: {operator!r}")

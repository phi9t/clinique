"""Temporal window checks for prescreening evidence."""

from __future__ import annotations

from datetime import date, timedelta


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def window_to_days(window_value: int, window_unit: str) -> int:
    unit = window_unit.lower()
    if unit in {"day", "days"}:
        return window_value
    if unit in {"week", "weeks"}:
        return window_value * 7
    if unit in {"month", "months"}:
        return window_value * 30
    raise ValueError(f"unsupported window unit: {window_unit!r}")


def evidence_within_window(
    evidence_date: str | None,
    snapshot_date: str | None,
    *,
    window_value: int,
    window_unit: str = "days",
) -> bool | None:
    """True if evidence_date is on or before snapshot and within the lookback window.

    Returns None when dates are missing or unparseable.
    """
    ev = _parse_date(evidence_date)
    snap = _parse_date(snapshot_date)
    if ev is None or snap is None:
        return None
    if ev > snap:
        return False
    days = window_to_days(window_value, window_unit)
    earliest = snap - timedelta(days=days)
    return earliest <= ev <= snap


def document_eligible(doc_date: str | None, snapshot_date: str | None) -> bool:
    """Leakage filter: document must not be dated after snapshot."""
    ev = _parse_date(doc_date)
    snap = _parse_date(snapshot_date)
    if snap is None:
        return True
    if ev is None:
        return True
    return ev <= snap

"""Eligibility text atomizer — Protocol + deterministic ReferenceAtomizer."""

from __future__ import annotations

import re
from typing import Protocol

from .schemas import (
    CLINICAL_DOMAINS,
    CRITERION_TYPES,
    Criterion,
    TemporalConstraint,
    Threshold,
    Trial,
)

_AMBIGUITY_PATTERNS = (
    re.compile(r"adequate organ function", re.I),
    re.compile(r"sufficient organ", re.I),
    re.compile(r"measurable disease", re.I),
    re.compile(r"life expectancy", re.I),
)

_LAB_RE = re.compile(
    r"(?P<label>ANC|absolute neutrophil count|hemoglobin|platelet[s]?)"
    r"[^.\n]{0,40}?(?P<op>>=|<=|>|<|=)\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[/\w*^.]+)?",
    re.I,
)

_EXCLUSION_ABSENCE_RE = re.compile(
    r"\b(no prior|without prior|must not have|history of)\b", re.I
)

_SECTION_RE = re.compile(
    r"(?P<kind>Inclusion|Exclusion)\s+Criteria\s*:?\s*\n",
    re.I,
)

_BULLET_RE = re.compile(r"^\s*(?:[\*\-•]|\d+[\.\)])\s*(.+)$", re.M)


class Atomizer(Protocol):
    def atomize(self, trial: Trial) -> tuple[Criterion, ...]: ...


def _next_id(prefix: str, counter: dict[str, int]) -> str:
    counter[prefix] = counter.get(prefix, 0) + 1
    return f"{prefix}-{counter[prefix]:03d}"


def _domain_for_text(text: str) -> str:
    lowered = text.lower()
    if any(k in lowered for k in ("age", "years old", "gender", "sex", "female", "male")):
        return "demographic"
    if any(k in lowered for k in ("anc", "hemoglobin", "platelet", "laboratory", "lab ", "/ul")):
        return "laboratory"
    if any(k in lowered for k in ("medication", "therapy", "drug", "pembrolizumab", "pd-1")):
        return "medication"
    if "pd-l1" in lowered:
        return "medication"
    if any(k in lowered for k in ("diagnosis", "histolog", "cancer", "carcinoma", "nsclc")):
        return "condition"
    if "ecog" in lowered or "performance status" in lowered:
        return "performance_status"
    return "other"


def _ambiguity_flags(text: str) -> tuple[str, ...]:
    flags: list[str] = []
    for pattern in _AMBIGUITY_PATTERNS:
        if pattern.search(text):
            flags.append(pattern.pattern)
    return tuple(flags)


def _parse_lab(text: str) -> tuple[str | None, Threshold | None, TemporalConstraint | None]:
    match = _LAB_RE.search(text)
    if not match:
        return None, None, None
    op = match.group("op")
    value = float(match.group("value"))
    unit = (match.group("unit") or "cells/uL").strip()
    threshold = Threshold(value=value, unit=unit)
    temporal = None
    window = re.search(
        r"within\s+(\d+)\s+(day|days|week|weeks)",
        text,
        re.I,
    )
    if window:
        temporal = TemporalConstraint(
            window_value=int(window.group(1)),
            window_unit=window.group(2).lower().rstrip("s") + "s"
            if window.group(2).lower() in {"day", "week"}
            else window.group(2).lower(),
        )
    return op, threshold, temporal


class ReferenceAtomizer:
    """Deterministic stand-in: split bullets + trial demographics + simple lab regex."""

    name = "reference-atomizer"
    version = "0.1.0"

    def atomize(self, trial: Trial) -> tuple[Criterion, ...]:
        criteria: list[Criterion] = []
        counter: dict[str, int] = {}

        if trial.minimum_age.years is not None:
            criteria.append(
                Criterion(
                    criterion_id=_next_id("I", counter),
                    trial_id=trial.trial_id,
                    criterion_type="inclusion",
                    raw_text=f"Age >= {trial.minimum_age.raw or trial.minimum_age.years}",
                    clinical_domain="demographic",
                    operator=">=",
                    threshold=Threshold(value=trial.minimum_age.years, unit="years"),
                )
            )

        text = trial.eligibility_text or ""
        sections: list[tuple[str, str]] = []
        matches = list(_SECTION_RE.finditer(text))
        if not matches:
            sections.append(("inclusion", text))
        else:
            for index, match in enumerate(matches):
                kind = "inclusion" if match.group("kind").lower().startswith("inc") else "exclusion"
                start = match.end()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                sections.append((kind, text[start:end]))

        for criterion_type, block in sections:
            if criterion_type not in CRITERION_TYPES:
                continue
            prefix = "I" if criterion_type == "inclusion" else "E"
            bullets = _BULLET_RE.findall(block)
            if not bullets:
                for line in block.splitlines():
                    cleaned = line.strip()
                    if len(cleaned) > 10:
                        bullets.append(cleaned)
            for bullet in bullets:
                raw = bullet.strip()
                if len(raw) < 5:
                    continue
                domain = _domain_for_text(raw)
                op, threshold, temporal = _parse_lab(raw)
                requires_absence = bool(
                    criterion_type == "exclusion" and _EXCLUSION_ABSENCE_RE.search(raw)
                )
                flags = _ambiguity_flags(raw)
                criteria.append(
                    Criterion(
                        criterion_id=_next_id(prefix, counter),
                        trial_id=trial.trial_id,
                        criterion_type=criterion_type,
                        raw_text=raw,
                        clinical_domain=domain if domain in CLINICAL_DOMAINS else "other",
                        operator=op,
                        threshold=threshold,
                        temporal_constraint=temporal,
                        requires_absence_evidence=requires_absence,
                        is_safety_critical=domain == "laboratory",
                        ambiguity_flags=flags,
                    )
                )
        return tuple(criteria)

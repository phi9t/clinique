from __future__ import annotations

import json
from math import ceil
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

from clinique.edc.records import ValidationReport, parse_timestamp


ALLOWED_GROUND_TRUTH = {"true_positive", "false_positive", "true_negative", "safety_risk"}


@dataclass(frozen=True)
class SilentLogEntry:
    recommendation_id: str
    logged_at: object
    study_id: str
    site_id: str
    subject_id: str
    form: str
    field: str
    query_category: str
    agent_recommendation: str
    agent_evidence: tuple[str, ...]
    human_action: str
    human_action_at: object
    ground_truth: str
    reviewer_id: str
    affected_operations: bool
    safety_risk: bool

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "SilentLogEntry":
        logged_at = parse_timestamp(raw["logged_at"])
        human_action_at = parse_timestamp(raw["human_action_at"])
        if logged_at is None or human_action_at is None:
            raise ValueError("silent log timestamps are required")
        return cls(
            recommendation_id=raw["recommendation_id"],
            logged_at=logged_at,
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            query_category=raw["query_category"],
            agent_recommendation=raw["agent_recommendation"],
            agent_evidence=tuple(raw.get("agent_evidence", [])),
            human_action=raw["human_action"],
            human_action_at=human_action_at,
            ground_truth=_require_one_of("ground_truth", raw["ground_truth"], ALLOWED_GROUND_TRUTH),
            reviewer_id=raw["reviewer_id"],
            affected_operations=_require_bool(
                "affected_operations",
                raw["affected_operations"],
            ),
            safety_risk=_require_bool("safety_risk", raw["safety_risk"]),
        )


def load_silent_log(path: str | Path) -> tuple[SilentLogEntry, ...]:
    with Path(path).open() as handle:
        raw_entries = json.load(handle)
    if not isinstance(raw_entries, list):
        raise ValueError("silent log must contain a JSON list")
    if not raw_entries:
        raise ValueError("silent log must contain at least one recommendation")
    entries = tuple(SilentLogEntry.from_json(raw) for raw in raw_entries)
    impacted = [entry.recommendation_id for entry in entries if entry.affected_operations]
    if impacted:
        raise ValueError(f"silent recommendations affected operations: {', '.join(impacted)}")
    return entries


def evaluate_silent_log(
    entries: tuple[SilentLogEntry, ...],
    *,
    false_positive_tolerance_per_reviewer_week: float,
) -> ValidationReport:
    if false_positive_tolerance_per_reviewer_week < 0:
        raise ValueError("false_positive_tolerance_per_reviewer_week must be nonnegative")
    true_positives = sum(1 for entry in entries if entry.ground_truth == "true_positive")
    false_positives = sum(1 for entry in entries if entry.ground_truth == "false_positive")
    safety_risks = sum(1 for entry in entries if entry.safety_risk)
    reviewers = {entry.reviewer_id for entry in entries}
    evaluation_weeks = _evaluation_weeks(entries)
    hours_earlier = [
        max((entry.human_action_at - entry.logged_at).total_seconds() / 3600, 0.0)
        for entry in entries
        if entry.ground_truth == "true_positive"
    ]
    burden = false_positives / max(len(reviewers) * evaluation_weeks, 1)
    no_operational_impact = all(not entry.affected_operations for entry in entries)
    false_positive_burden_controlled = (
        burden <= false_positive_tolerance_per_reviewer_week
    )
    stop_criteria_triggered = safety_risks > 0
    return ValidationReport(
        report_type="edc_query_silent_prospective",
        generated_at=min(entry.logged_at for entry in entries),
        inputs={
            "recommendation_ids": [entry.recommendation_id for entry in entries],
            "reviewer_count": len(reviewers),
            "false_positive_tolerance_per_reviewer_week": false_positive_tolerance_per_reviewer_week,
        },
        metrics={
            "recommendations_total": len(entries),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "safety_risks": safety_risks,
            "evaluation_weeks": evaluation_weeks,
            "median_hours_earlier": median(hours_earlier) if hours_earlier else 0.0,
            "false_positive_burden_per_reviewer_week": burden,
        },
        gates={
            "no_operational_impact": no_operational_impact,
            "false_positive_burden_controlled": false_positive_burden_controlled,
            "stop_criteria_triggered": stop_criteria_triggered,
        },
    )


def _evaluation_weeks(entries: tuple[SilentLogEntry, ...]) -> int:
    if not entries:
        return 1
    first = min(entry.logged_at for entry in entries)
    last = max(entry.logged_at for entry in entries)
    elapsed_weeks = (last - first).total_seconds() / (7 * 24 * 60 * 60)
    return max(ceil(elapsed_weeks), 1)


def _require_bool(label: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _require_one_of(label: str, value: Any, allowed: set[str]) -> str:
    if value not in allowed:
        values = ", ".join(sorted(allowed))
        raise ValueError(f"{label} must be one of: {values}")
    return value

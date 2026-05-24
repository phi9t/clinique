from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clinique.edc.records import ValidationReport, parse_timestamp


@dataclass(frozen=True)
class RolloutGate:
    gate_id: str
    evaluated_at: object
    randomization_unit: str
    human_approval_path_validated: bool
    thresholds: dict[str, float]
    observed: dict[str, float]
    safety: dict[str, object]

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "RolloutGate":
        evaluated_at = parse_timestamp(raw["evaluated_at"])
        if evaluated_at is None:
            raise ValueError("rollout gate evaluated_at is required")
        return cls(
            gate_id=raw["gate_id"],
            evaluated_at=evaluated_at,
            randomization_unit=raw["randomization_unit"],
            human_approval_path_validated=bool(raw["human_approval_path_validated"]),
            thresholds={key: float(value) for key, value in raw["thresholds"].items()},
            observed={key: float(value) for key, value in raw["observed"].items()},
            safety=dict(raw["safety"]),
        )


def load_rollout_gate(path: str | Path) -> RolloutGate:
    with Path(path).open() as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("rollout gate must be a JSON object")
    return RolloutGate.from_json(raw)


def evaluate_rollout_gate(gate: RolloutGate) -> ValidationReport:
    primary_endpoints_met = (
        gate.observed["false_query_rate"] <= gate.thresholds["max_false_query_rate"]
        and gate.observed["duplicate_query_rate"] <= gate.thresholds["max_duplicate_query_rate"]
        and gate.observed["acceptance_rate"] >= gate.thresholds["min_acceptance_rate"]
        and gate.observed["open_queries_at_lock"] <= gate.thresholds["max_open_queries_at_lock"]
        and gate.observed["true_discrepancy_delta"]
        >= gate.thresholds["min_true_discrepancy_delta"]
        and gate.observed["manual_minutes_per_query_delta"]
        <= gate.thresholds["max_manual_minutes_per_query_delta"]
    )
    safety_endpoints_clear = (
        int(gate.safety["unauthorized_write_back"]) == 0
        and int(gate.safety["unsupported_evidence"]) == 0
        and int(gate.safety["privacy_incident"]) == 0
        and int(gate.safety["blinding_breach"]) == 0
        and bool(gate.safety["excessive_reviewer_burden"]) is False
    )
    rollout_gate_passed = (
        primary_endpoints_met
        and safety_endpoints_clear
        and gate.human_approval_path_validated
    )
    return ValidationReport(
        report_type="edc_query_controlled_rollout_gate",
        generated_at=gate.evaluated_at,
        inputs={
            "gate_id": gate.gate_id,
            "randomization_unit": gate.randomization_unit,
            "thresholds": gate.thresholds,
        },
        metrics={
            **gate.observed,
            "unauthorized_write_back": int(gate.safety["unauthorized_write_back"]),
            "unsupported_evidence": int(gate.safety["unsupported_evidence"]),
            "privacy_incident": int(gate.safety["privacy_incident"]),
            "blinding_breach": int(gate.safety["blinding_breach"]),
            "excessive_reviewer_burden": bool(gate.safety["excessive_reviewer_burden"]),
        },
        gates={
            "primary_endpoints_met": primary_endpoints_met,
            "safety_endpoints_clear": safety_endpoints_clear,
            "human_approval_path_validated": gate.human_approval_path_validated,
            "rollout_gate_passed": rollout_gate_passed,
        },
    )

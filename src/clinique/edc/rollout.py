from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from clinique.edc.records import ValidationReport, parse_timestamp


REQUIRED_THRESHOLD_KEYS = {
    "max_false_query_rate",
    "max_duplicate_query_rate",
    "min_acceptance_rate",
    "max_open_queries_at_lock",
    "min_true_discrepancy_delta",
    "max_manual_minutes_per_query_delta",
}
REQUIRED_OBSERVED_KEYS = {
    "manual_minutes_per_query_delta",
    "true_discrepancy_delta",
    "false_query_rate",
    "duplicate_query_rate",
    "query_resolution_time_delta_hours",
    "open_queries_at_lock",
    "acceptance_rate",
}
REQUIRED_SAFETY_KEYS = {
    "unauthorized_write_back",
    "unsupported_evidence",
    "privacy_incident",
    "blinding_breach",
    "excessive_reviewer_burden",
}
SAFETY_COUNT_KEYS = {
    "unauthorized_write_back",
    "unsupported_evidence",
    "privacy_incident",
    "blinding_breach",
}
RATE_KEYS = {
    "max_false_query_rate",
    "max_duplicate_query_rate",
    "min_acceptance_rate",
    "false_query_rate",
    "duplicate_query_rate",
    "acceptance_rate",
}
COUNT_KEYS = {
    "max_open_queries_at_lock",
    "open_queries_at_lock",
}
INTEGER_DELTA_KEYS = {
    "min_true_discrepancy_delta",
    "true_discrepancy_delta",
}
ALLOWED_RANDOMIZATION_UNITS = {
    "study",
    "site",
    "form_family",
    "data_manager_queue",
}


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
        _require_keys("threshold", raw["thresholds"], REQUIRED_THRESHOLD_KEYS)
        _require_keys("observed", raw["observed"], REQUIRED_OBSERVED_KEYS)
        _require_keys("safety", raw["safety"], REQUIRED_SAFETY_KEYS)
        human_approval_path_validated = _require_bool(
            "human_approval_path_validated",
            raw["human_approval_path_validated"],
        )
        safety = dict(raw["safety"])
        safety["excessive_reviewer_burden"] = _require_bool(
            "excessive_reviewer_burden",
            safety["excessive_reviewer_burden"],
        )
        for key in SAFETY_COUNT_KEYS:
            safety[key] = _require_nonnegative_int(key, safety[key])
        thresholds = _require_numeric_values(raw["thresholds"])
        observed = _require_numeric_values(raw["observed"])
        _validate_rate_values(thresholds)
        _validate_rate_values(observed)
        _validate_count_values(thresholds)
        _validate_count_values(observed)
        _validate_integer_delta_values(thresholds)
        _validate_integer_delta_values(observed)
        _validate_threshold_direction(thresholds)
        return cls(
            gate_id=raw["gate_id"],
            evaluated_at=evaluated_at,
            randomization_unit=_require_one_of(
                "randomization_unit",
                raw["randomization_unit"],
                ALLOWED_RANDOMIZATION_UNITS,
            ),
            human_approval_path_validated=human_approval_path_validated,
            thresholds=thresholds,
            observed=observed,
            safety=safety,
        )


def _require_keys(label: str, value: Any, required: set[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"rollout gate {label} must be an object")
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"missing {label} keys: {', '.join(missing)}")


def _require_bool(label: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _require_one_of(label: str, value: Any, allowed: set[str]) -> str:
    if value not in allowed:
        values = ", ".join(sorted(allowed))
        raise ValueError(f"{label} must be one of: {values}")
    return value


def _require_numeric_values(values: dict[str, Any]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{key} must be numeric")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"{key} must be finite")
        parsed[key] = numeric
    return parsed


def _require_nonnegative_int(label: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def _validate_rate_values(values: dict[str, float]) -> None:
    for key, value in values.items():
        if key in RATE_KEYS and not 0 <= value <= 1:
            raise ValueError(f"{key} must be between 0 and 1")


def _validate_count_values(values: dict[str, float]) -> None:
    for key, value in values.items():
        if key in COUNT_KEYS and (value < 0 or not value.is_integer()):
            raise ValueError(f"{key} must be a nonnegative integer")


def _validate_integer_delta_values(values: dict[str, float]) -> None:
    for key, value in values.items():
        if key in INTEGER_DELTA_KEYS and not value.is_integer():
            raise ValueError(f"{key} must be an integer")


def _validate_threshold_direction(thresholds: dict[str, float]) -> None:
    if thresholds["min_true_discrepancy_delta"] < 0:
        raise ValueError("min_true_discrepancy_delta must be nonnegative")
    if thresholds["max_manual_minutes_per_query_delta"] > 0:
        raise ValueError("max_manual_minutes_per_query_delta must be nonpositive")


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
        and gate.observed["true_discrepancy_delta"] >= gate.thresholds["min_true_discrepancy_delta"]
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
        primary_endpoints_met and safety_endpoints_clear and gate.human_approval_path_validated
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

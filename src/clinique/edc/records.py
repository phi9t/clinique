from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EdcRecord:
    record_id: str
    study_id: str
    site_id: str
    subject_id: str
    form: str
    field: str
    value: str
    collected_at: datetime
    related: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "EdcRecord":
        return cls(
            record_id=raw["record_id"],
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            value=raw.get("value", ""),
            collected_at=parse_timestamp(raw["collected_at"]) or datetime.min.replace(
                tzinfo=timezone.utc
            ),
            related=dict(raw.get("related", {})),
        )


@dataclass(frozen=True)
class EdcSnapshot:
    snapshot_id: str
    snapshot_at: datetime
    contains_phi: bool
    contains_unblinded: bool
    records: tuple[EdcRecord, ...]

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "EdcSnapshot":
        return cls(
            snapshot_id=raw["snapshot_id"],
            snapshot_at=parse_timestamp(raw["snapshot_at"]) or datetime.min.replace(
                tzinfo=timezone.utc
            ),
            contains_phi=bool(raw.get("contains_phi", False)),
            contains_unblinded=bool(raw.get("contains_unblinded", False)),
            records=tuple(EdcRecord.from_json(record) for record in raw.get("records", [])),
        )


@dataclass(frozen=True)
class EditCheckRule:
    rule_id: str
    kind: str
    form: str
    field: str
    query_category: str
    message: str
    effective_at: datetime
    retired_at: datetime | None = None
    compare_to_related: str | None = None
    operator: str | None = None

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "EditCheckRule":
        return cls(
            rule_id=raw["rule_id"],
            kind=raw["kind"],
            form=raw["form"],
            field=raw["field"],
            query_category=raw["query_category"],
            message=raw["message"],
            effective_at=parse_timestamp(raw["effective_at"]) or datetime.min.replace(
                tzinfo=timezone.utc
            ),
            retired_at=parse_timestamp(raw.get("retired_at")),
            compare_to_related=raw.get("compare_to_related"),
            operator=raw.get("operator"),
        )


@dataclass(frozen=True)
class QueryLog:
    query_id: str
    snapshot_id: str
    study_id: str
    site_id: str
    subject_id: str
    form: str
    field: str
    query_text: str
    query_category: str
    opened_at: datetime
    closed_at: datetime | None
    status: str
    resolution: str

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "QueryLog":
        opened_at = parse_timestamp(raw["opened_at"])
        if opened_at is None:
            raise ValueError("query log opened_at is required")
        return cls(
            query_id=raw["query_id"],
            snapshot_id=raw["snapshot_id"],
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            query_text=raw["query_text"],
            query_category=raw["query_category"],
            opened_at=opened_at,
            closed_at=parse_timestamp(raw.get("closed_at")),
            status=raw["status"],
            resolution=raw["resolution"],
        )


@dataclass(frozen=True)
class QueryLabel:
    snapshot_id: str
    study_id: str
    site_id: str
    subject_id: str
    form: str
    field: str
    gold_query_needed: bool
    query_category: str
    human_resolution: str
    opened_at: datetime | None
    closed_at: datetime | None
    evidence_available_at_agent_time: bool

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "QueryLabel":
        return cls(
            snapshot_id=raw["snapshot_id"],
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            gold_query_needed=bool(raw["gold_query_needed"]),
            query_category=raw["query_category"],
            human_resolution=raw["human_resolution"],
            opened_at=parse_timestamp(raw.get("opened_at")),
            closed_at=parse_timestamp(raw.get("closed_at")),
            evidence_available_at_agent_time=bool(raw["evidence_available_at_agent_time"]),
        )


@dataclass(frozen=True)
class DatabaseLockIssue:
    issue_id: str
    study_id: str
    site_id: str
    subject_id: str
    form: str
    field: str
    severity: str
    discovered_at: datetime
    description: str

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "DatabaseLockIssue":
        discovered_at = parse_timestamp(raw["discovered_at"])
        if discovered_at is None:
            raise ValueError("lock issue discovered_at is required")
        return cls(
            issue_id=raw["issue_id"],
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            severity=raw["severity"],
            discovered_at=discovered_at,
            description=raw["description"],
        )


@dataclass(frozen=True)
class FixtureBundle:
    snapshots: tuple[EdcSnapshot, ...]
    rules: tuple[EditCheckRule, ...]
    query_logs: tuple[QueryLog, ...]
    labels: tuple[QueryLabel, ...]
    lock_issues: tuple[DatabaseLockIssue, ...] = ()


@dataclass(frozen=True)
class SourceRef:
    source_type: str
    source_id: str
    observed_at: datetime


@dataclass(frozen=True)
class ReplayEvidence:
    replayed_at: datetime
    snapshot: EdcSnapshot
    active_rules: tuple[EditCheckRule, ...]
    sources: tuple[SourceRef, ...]


@dataclass(frozen=True)
class CandidateQuery:
    study_id: str
    site_id: str
    subject_id: str
    form: str
    field: str
    query_category: str
    query_text: str
    evidence: tuple[SourceRef, ...]
    rule_id: str | None = None
    is_duplicate: bool = False
    draft_only: bool = True


@dataclass(frozen=True)
class EvaluationMetrics:
    candidates_total: int
    true_discrepancies_detected: int
    false_queries: int
    false_query_rate: float
    duplicate_queries: int
    duplicate_query_rate: float
    query_category_accuracy: float
    evidence_support_accuracy: float
    median_days_earlier: float


@dataclass(frozen=True)
class ValidationReport:
    report_type: str
    generated_at: datetime
    inputs: dict[str, object]
    metrics: dict[str, object]
    gates: dict[str, bool]

    def as_dict(self) -> dict[str, object]:
        return {
            "report_type": self.report_type,
            "generated_at": self.generated_at.isoformat().replace("+00:00", "Z"),
            "inputs": self.inputs,
            "metrics": self.metrics,
            "gates": self.gates,
        }

    def write_json(self, path: str | Path) -> None:
        import json

        Path(path).write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")

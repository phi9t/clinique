from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_QUERY_CATEGORIES = {
    "missing",
    "inconsistent",
    "impossible",
    "source_mismatch",
    "duplicate",
    "no_query",
}
ALLOWED_HUMAN_RESOLUTIONS = {
    "corrected",
    "confirmed",
    "no_query_needed",
    "duplicate",
    "waived",
}
ALLOWED_QUERY_LOG_RESOLUTIONS = {
    "pending",
    "corrected",
    "confirmed",
    "duplicate",
    "waived",
}
ALLOWED_QUERY_LOG_STATUSES = {"open", "closed"}
ALLOWED_RULE_KINDS = {"required_field", "date_order", "future_date"}
ALLOWED_DATE_ORDER_OPERATORS = {"<="}


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def require_timestamp(label: str, value: str | None) -> datetime:
    parsed = parse_timestamp(value)
    if parsed is None:
        raise ValueError(f"{label} is required")
    return parsed


def require_bool(label: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def require_one_of(label: str, value: Any, allowed: set[str]) -> str:
    if value not in allowed:
        values = ", ".join(sorted(allowed))
        raise ValueError(f"{label} must be one of: {values}")
    return value


def validate_open_close_chronology(
    *,
    opened_at: datetime | None,
    closed_at: datetime | None,
    label: str,
) -> None:
    if closed_at is None:
        return
    if opened_at is None:
        raise ValueError(f"{label} closed_at requires opened_at")
    if closed_at < opened_at:
        raise ValueError(f"{label} closed_at cannot be before opened_at")


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
            collected_at=require_timestamp("collected_at", raw["collected_at"]),
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
        records = tuple(EdcRecord.from_json(record) for record in raw.get("records", []))
        validate_unique_snapshot_record_keys(raw["snapshot_id"], records)
        return cls(
            snapshot_id=raw["snapshot_id"],
            snapshot_at=require_timestamp("snapshot_at", raw["snapshot_at"]),
            contains_phi=require_bool("contains_phi", raw.get("contains_phi", False)),
            contains_unblinded=require_bool(
                "contains_unblinded",
                raw.get("contains_unblinded", False),
            ),
            records=records,
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
        effective_at = require_timestamp("effective_at", raw["effective_at"])
        retired_at = parse_timestamp(raw.get("retired_at"))
        if retired_at is not None and retired_at < effective_at:
            raise ValueError("rule retired_at cannot be before effective_at")
        kind = require_one_of("rule kind", raw["kind"], ALLOWED_RULE_KINDS)
        compare_to_related = raw.get("compare_to_related")
        operator = raw.get("operator")
        if kind == "date_order":
            if not compare_to_related:
                raise ValueError("date_order rules require compare_to_related")
            operator = require_one_of(
                "date_order operator",
                operator,
                ALLOWED_DATE_ORDER_OPERATORS,
            )
        return cls(
            rule_id=raw["rule_id"],
            kind=kind,
            form=raw["form"],
            field=raw["field"],
            query_category=require_one_of(
                "query_category",
                raw["query_category"],
                ALLOWED_QUERY_CATEGORIES,
            ),
            message=raw["message"],
            effective_at=effective_at,
            retired_at=retired_at,
            compare_to_related=compare_to_related,
            operator=operator,
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
        closed_at = parse_timestamp(raw.get("closed_at"))
        validate_open_close_chronology(
            opened_at=opened_at,
            closed_at=closed_at,
            label="query log",
        )
        status = require_one_of(
            "query log status",
            raw["status"],
            ALLOWED_QUERY_LOG_STATUSES,
        )
        resolution = require_one_of(
            "query log resolution",
            raw["resolution"],
            ALLOWED_QUERY_LOG_RESOLUTIONS,
        )
        validate_query_log_status_timestamp(status=status, closed_at=closed_at)
        validate_query_log_status_resolution(status=status, resolution=resolution)
        return cls(
            query_id=raw["query_id"],
            snapshot_id=raw["snapshot_id"],
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            query_text=raw["query_text"],
            query_category=require_one_of(
                "query_category",
                raw["query_category"],
                ALLOWED_QUERY_CATEGORIES,
            ),
            opened_at=opened_at,
            closed_at=closed_at,
            status=status,
            resolution=resolution,
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
        opened_at = parse_timestamp(raw.get("opened_at"))
        closed_at = parse_timestamp(raw.get("closed_at"))
        validate_open_close_chronology(
            opened_at=opened_at,
            closed_at=closed_at,
            label="label",
        )
        gold_query_needed = require_bool("gold_query_needed", raw["gold_query_needed"])
        query_category = require_one_of(
            "query_category",
            raw["query_category"],
            ALLOWED_QUERY_CATEGORIES,
        )
        human_resolution = require_one_of(
            "human_resolution",
            raw["human_resolution"],
            ALLOWED_HUMAN_RESOLUTIONS,
        )
        validate_query_label_semantics(
            gold_query_needed=gold_query_needed,
            query_category=query_category,
            human_resolution=human_resolution,
            opened_at=opened_at,
        )
        return cls(
            snapshot_id=raw["snapshot_id"],
            study_id=raw["study_id"],
            site_id=raw["site_id"],
            subject_id=raw["subject_id"],
            form=raw["form"],
            field=raw["field"],
            gold_query_needed=gold_query_needed,
            query_category=query_category,
            human_resolution=human_resolution,
            opened_at=opened_at,
            closed_at=closed_at,
            evidence_available_at_agent_time=require_bool(
                "evidence_available_at_agent_time",
                raw["evidence_available_at_agent_time"],
            ),
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


def validate_unique_snapshot_record_keys(snapshot_id: str, records: tuple[EdcRecord, ...]) -> None:
    seen: set[tuple[str, str, str, str, str]] = set()
    for record in records:
        key = (
            record.study_id,
            record.site_id,
            record.subject_id,
            record.form,
            record.field,
        )
        if key in seen:
            raise ValueError(f"duplicate snapshot record key in {snapshot_id}: {key}")
        seen.add(key)


def validate_unique_snapshot_ids(snapshots: tuple[EdcSnapshot, ...]) -> None:
    seen: set[str] = set()
    for snapshot in snapshots:
        if snapshot.snapshot_id in seen:
            raise ValueError(f"duplicate snapshot id: {snapshot.snapshot_id}")
        seen.add(snapshot.snapshot_id)


def validate_query_log_status_timestamp(*, status: str, closed_at: datetime | None) -> None:
    if status == "closed" and closed_at is None:
        raise ValueError("closed query logs require closed_at")
    if status == "open" and closed_at is not None:
        raise ValueError("open query logs cannot have closed_at")


def validate_query_log_status_resolution(*, status: str, resolution: str) -> None:
    if status == "open" and resolution != "pending":
        raise ValueError("open query logs require pending resolution")
    if status == "closed" and resolution == "pending":
        raise ValueError("closed query logs cannot have pending resolution")


def validate_query_label_semantics(
    *,
    gold_query_needed: bool,
    query_category: str,
    human_resolution: str,
    opened_at: datetime | None,
) -> None:
    if gold_query_needed:
        if query_category == "no_query":
            raise ValueError("true discrepancy labels cannot use no_query category")
        if human_resolution == "no_query_needed":
            raise ValueError("true discrepancy labels cannot use no_query_needed resolution")
        return

    if query_category != "no_query":
        raise ValueError("no-query labels must use no_query category")
    if human_resolution != "no_query_needed":
        raise ValueError("no-query labels must use no_query_needed resolution")
    if opened_at is not None:
        raise ValueError("no-query labels cannot have opened_at")


def validate_unique_query_log_ids(query_logs: tuple[QueryLog, ...]) -> None:
    seen: set[str] = set()
    for query in query_logs:
        if query.query_id in seen:
            raise ValueError(f"duplicate query log id: {query.query_id}")
        seen.add(query.query_id)


def validate_unique_rule_ids(rules: tuple[EditCheckRule, ...]) -> None:
    seen: set[str] = set()
    for rule in rules:
        if rule.rule_id in seen:
            raise ValueError(f"duplicate rule id: {rule.rule_id}")
        seen.add(rule.rule_id)


def validate_unique_label_keys(labels: tuple[QueryLabel, ...]) -> None:
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for label in labels:
        key = (
            label.snapshot_id,
            label.study_id,
            label.site_id,
            label.subject_id,
            label.form,
            label.field,
        )
        if key in seen:
            raise ValueError(f"duplicate label key: {key}")
        seen.add(key)


def validate_unique_lock_issue_ids(lock_issues: tuple[DatabaseLockIssue, ...]) -> None:
    seen: set[str] = set()
    for issue in lock_issues:
        if issue.issue_id in seen:
            raise ValueError(f"duplicate lock issue id: {issue.issue_id}")
        seen.add(issue.issue_id)


def validate_snapshot_references(
    snapshots: tuple[EdcSnapshot, ...],
    labels: tuple[QueryLabel, ...],
    query_logs: tuple[QueryLog, ...],
) -> None:
    snapshot_ids = {snapshot.snapshot_id for snapshot in snapshots}
    for label in labels:
        if label.snapshot_id not in snapshot_ids:
            raise ValueError(f"unknown label snapshot_id: {label.snapshot_id}")
    for query in query_logs:
        if query.snapshot_id not in snapshot_ids:
            raise ValueError(f"unknown query log snapshot_id: {query.snapshot_id}")


def validate_lock_issue_record_references(
    snapshots: tuple[EdcSnapshot, ...],
    lock_issues: tuple[DatabaseLockIssue, ...],
) -> None:
    record_keys = {
        (
            record.study_id,
            record.site_id,
            record.subject_id,
            record.form,
            record.field,
        )
        for snapshot in snapshots
        for record in snapshot.records
    }
    for issue in lock_issues:
        key = (issue.study_id, issue.site_id, issue.subject_id, issue.form, issue.field)
        if key not in record_keys:
            raise ValueError(f"unknown lock issue record key: {key}")


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
    snapshot_id: str
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

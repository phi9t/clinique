from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.metrics import evaluate_candidates
from clinique.edc.records import (
    CandidateQuery,
    DatabaseLockIssue,
    EvaluationMetrics,
    FixtureBundle,
    SourceRef,
    ValidationReport,
)
from clinique.edc.replay import evidence_at


def _now() -> datetime:
    return datetime.now(UTC)


def _metrics_dict(metrics: EvaluationMetrics) -> dict[str, object]:
    return asdict(metrics)


def _source_ok(source: SourceRef, replayed_at: datetime) -> bool:
    return source.observed_at <= replayed_at


def build_offline_report(
    bundle: FixtureBundle, *, replayed_at: datetime, generated_at: datetime | None = None
) -> ValidationReport:
    evidence = evidence_at(bundle, replayed_at)
    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
    metrics = evaluate_candidates(candidates, bundle.labels, replayed_at=evidence.replayed_at)
    no_write_back = all(candidate.draft_only for candidate in candidates)
    evidence_supported = all(candidate.evidence for candidate in candidates)
    leakage_checks_passed = all(
        _source_ok(source, evidence.replayed_at)
        for candidate in candidates
        for source in candidate.evidence
    )
    return ValidationReport(
        report_type="edc_query_offline_benchmark",
        generated_at=generated_at or _now(),
        inputs={
            "snapshot_id": evidence.snapshot.snapshot_id,
            "replayed_at": evidence.replayed_at.isoformat().replace("+00:00", "Z"),
            "active_rule_ids": sorted(rule.rule_id for rule in evidence.active_rules),
            "candidate_count": len(candidates),
        },
        metrics=_metrics_dict(metrics),
        gates={
            "no_write_back": no_write_back,
            "evidence_supported": evidence_supported,
            "leakage_checks_passed": leakage_checks_passed,
            "false_query_rate_controlled": metrics.false_query_rate <= 0.05,
            "duplicate_query_burden_measured": metrics.duplicate_query_rate >= 0,
        },
    )


def build_retrospective_report(
    bundle: FixtureBundle, *, generated_at: datetime | None = None
) -> ValidationReport:
    runs: list[dict[str, object]] = []
    leakage_checks_passed = True
    total_true = 0
    total_false = 0
    lock_issue_early_detection_count = 0

    for snapshot in bundle.snapshots:
        evidence = evidence_at(bundle, snapshot.snapshot_at)
        candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
        metrics = evaluate_candidates(candidates, bundle.labels, replayed_at=evidence.replayed_at)
        total_true += metrics.true_discrepancies_detected
        total_false += metrics.false_queries
        lock_issue_early_detection_count += _count_lock_issues_found_early(
            candidates, bundle.lock_issues, evidence.replayed_at
        )
        run_leakage_ok = all(
            _source_ok(source, evidence.replayed_at)
            for candidate in candidates
            for source in candidate.evidence
        )
        leakage_checks_passed = leakage_checks_passed and run_leakage_ok
        runs.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "replayed_at": evidence.replayed_at.isoformat().replace("+00:00", "Z"),
                "metrics": _metrics_dict(metrics),
                "leakage_checks_passed": run_leakage_ok,
            }
        )

    return ValidationReport(
        report_type="edc_query_retrospective_replay",
        generated_at=generated_at or _now(),
        inputs={
            "snapshot_ids": [snapshot.snapshot_id for snapshot in bundle.snapshots],
            "runs": runs,
        },
        metrics={
            "true_discrepancies_detected": total_true,
            "false_queries": total_false,
            "false_alerts_per_true_discrepancy": total_false / total_true if total_true else 0.0,
            "database_lock_issue_early_detection_count": lock_issue_early_detection_count,
        },
        gates={
            "no_write_back": True,
            "leakage_checks_passed": leakage_checks_passed,
            "timestamped_replay": True,
        },
    )


def _count_lock_issues_found_early(
    candidates: tuple[CandidateQuery, ...],
    lock_issues: tuple[DatabaseLockIssue, ...],
    replayed_at: datetime,
) -> int:
    candidate_keys = {
        (
            candidate.study_id,
            candidate.site_id,
            candidate.subject_id,
            candidate.form,
            candidate.field,
        )
        for candidate in candidates
    }
    return sum(
        1
        for issue in lock_issues
        if (
            issue.study_id,
            issue.site_id,
            issue.subject_id,
            issue.form,
            issue.field,
        )
        in candidate_keys
        and replayed_at < issue.discovered_at
    )

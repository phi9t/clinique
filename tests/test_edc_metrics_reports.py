from datetime import UTC, datetime
from pathlib import Path

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.metrics import evaluate_candidates
from clinique.edc.records import CandidateQuery, DatabaseLockIssue, QueryLabel, SourceRef
from clinique.edc.replay import evidence_at
from clinique.edc.reports import (
    _count_lock_issues_found_early,
    build_offline_report,
    build_retrospective_report,
)

FIXTURES = Path("tests/fixtures/edc_query")


def test_evaluate_candidates_reports_task_and_workflow_metrics():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=UTC))
    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    metrics = evaluate_candidates(candidates, bundle.labels, replayed_at=evidence.replayed_at)

    assert metrics.true_discrepancies_detected >= 3
    assert metrics.false_query_rate == 0
    assert metrics.duplicate_query_rate > 0
    assert metrics.median_days_earlier >= 0


def test_evaluate_candidates_does_not_match_labels_across_sites():
    replayed_at = datetime(2026, 3, 8, tzinfo=UTC)
    candidate = CandidateQuery(
        snapshot_id="snap-2026-03-08",
        study_id="STUDY-EDC-001",
        site_id="SITE-01",
        subject_id="SUBJ-001",
        form="AE",
        field="term",
        query_category="missing",
        query_text="AE term is required.",
        evidence=(SourceRef("record", "REC-001", replayed_at),),
    )
    label = QueryLabel(
        snapshot_id="snap-2026-03-08",
        study_id="STUDY-EDC-001",
        site_id="SITE-02",
        subject_id="SUBJ-001",
        form="AE",
        field="term",
        gold_query_needed=True,
        query_category="missing",
        human_resolution="corrected",
        opened_at=replayed_at,
        closed_at=None,
        evidence_available_at_agent_time=True,
    )

    metrics = evaluate_candidates((candidate,), (label,), replayed_at=replayed_at)

    assert metrics.true_discrepancies_detected == 0
    assert metrics.false_queries == 1


def test_evaluate_candidates_does_not_match_labels_across_snapshots():
    replayed_at = datetime(2026, 3, 1, tzinfo=UTC)
    candidate = CandidateQuery(
        snapshot_id="snap-2026-03-01",
        study_id="STUDY-EDC-001",
        site_id="SITE-01",
        subject_id="SUBJ-001",
        form="AE",
        field="term",
        query_category="missing",
        query_text="AE term is required.",
        evidence=(SourceRef("record", "REC-001", replayed_at),),
    )
    future_label = QueryLabel(
        snapshot_id="snap-2026-03-08",
        study_id="STUDY-EDC-001",
        site_id="SITE-01",
        subject_id="SUBJ-001",
        form="AE",
        field="term",
        gold_query_needed=True,
        query_category="missing",
        human_resolution="corrected",
        opened_at=datetime(2026, 3, 8, tzinfo=UTC),
        closed_at=None,
        evidence_available_at_agent_time=True,
    )

    metrics = evaluate_candidates((candidate,), (future_label,), replayed_at=replayed_at)

    assert metrics.true_discrepancies_detected == 0
    assert metrics.false_queries == 1


def test_evaluate_candidates_does_not_count_unavailable_evidence_as_true_detection():
    replayed_at = datetime(2026, 3, 8, tzinfo=UTC)
    candidate = CandidateQuery(
        snapshot_id="snap-2026-03-08",
        study_id="STUDY-EDC-001",
        site_id="SITE-01",
        subject_id="SUBJ-001",
        form="AE",
        field="term",
        query_category="missing",
        query_text="AE term is required.",
        evidence=(SourceRef("record", "REC-001", replayed_at),),
    )
    label = QueryLabel(
        snapshot_id="snap-2026-03-08",
        study_id="STUDY-EDC-001",
        site_id="SITE-01",
        subject_id="SUBJ-001",
        form="AE",
        field="term",
        gold_query_needed=True,
        query_category="missing",
        human_resolution="corrected",
        opened_at=replayed_at,
        closed_at=None,
        evidence_available_at_agent_time=False,
    )

    metrics = evaluate_candidates((candidate,), (label,), replayed_at=replayed_at)

    assert metrics.true_discrepancies_detected == 0
    assert metrics.false_queries == 1
    assert metrics.query_category_accuracy == 0


def test_lock_issue_early_detection_does_not_match_across_sites():
    replayed_at = datetime(2026, 3, 8, tzinfo=UTC)
    candidate = CandidateQuery(
        snapshot_id="snap-2026-03-08",
        study_id="STUDY-EDC-001",
        site_id="SITE-01",
        subject_id="SUBJ-001",
        form="Vitals",
        field="visit_date",
        query_category="impossible",
        query_text="Visit date is in the future.",
        evidence=(SourceRef("record", "REC-001", replayed_at),),
    )
    issue = DatabaseLockIssue(
        issue_id="LOCK-WRONG-SITE",
        study_id="STUDY-EDC-001",
        site_id="SITE-02",
        subject_id="SUBJ-001",
        form="Vitals",
        field="visit_date",
        severity="major",
        discovered_at=datetime(2026, 3, 20, tzinfo=UTC),
        description="Future visit date remained open.",
    )

    assert _count_lock_issues_found_early((candidate,), (issue,), replayed_at) == 0


def test_reports_are_json_serializable_and_include_ship_gates(tmp_path):
    bundle = load_fixture_bundle(FIXTURES)
    offline = build_offline_report(bundle, replayed_at=datetime(2026, 3, 8, tzinfo=UTC))
    replay = build_retrospective_report(bundle)

    offline_path = tmp_path / "offline.json"
    replay_path = tmp_path / "replay.json"
    offline.write_json(offline_path)
    replay.write_json(replay_path)

    assert '"no_write_back": true' in offline_path.read_text()
    assert '"leakage_checks_passed": true' in replay_path.read_text()
    assert '"database_lock_issue_early_detection_count": 1' in replay_path.read_text()
    assert '"false_alerts_per_true_discrepancy": 0.0' in replay_path.read_text()

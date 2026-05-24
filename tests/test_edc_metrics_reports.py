from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.metrics import evaluate_candidates
from clinique.edc.replay import evidence_at
from clinique.edc.reports import build_offline_report, build_retrospective_report


FIXTURES = Path("tests/fixtures/edc_query")


def test_evaluate_candidates_reports_task_and_workflow_metrics():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))
    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    metrics = evaluate_candidates(candidates, bundle.labels, replayed_at=evidence.replayed_at)

    assert metrics.true_discrepancies_detected >= 3
    assert metrics.false_query_rate == 0
    assert metrics.duplicate_query_rate > 0
    assert metrics.median_days_earlier >= 0


def test_reports_are_json_serializable_and_include_ship_gates(tmp_path):
    bundle = load_fixture_bundle(FIXTURES)
    offline = build_offline_report(bundle, replayed_at=datetime(2026, 3, 8, tzinfo=timezone.utc))
    replay = build_retrospective_report(bundle)

    offline_path = tmp_path / "offline.json"
    replay_path = tmp_path / "replay.json"
    offline.write_json(offline_path)
    replay.write_json(replay_path)

    assert '"no_write_back": true' in offline_path.read_text()
    assert '"leakage_checks_passed": true' in replay_path.read_text()
    assert '"database_lock_issue_early_detection_count": 1' in replay_path.read_text()
    assert '"false_alerts_per_true_discrepancy": 0.0' in replay_path.read_text()

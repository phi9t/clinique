from pathlib import Path

from clinique.edc.silent import evaluate_silent_log, load_silent_log


SILENT_LOG = Path("tests/fixtures/edc_query/silent_log.json")


def test_load_silent_log_rejects_recommendations_that_affect_operations(tmp_path):
    path = tmp_path / "bad_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-001",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001"],
            "human_action": "opened_query",
            "human_action_at": "2026-04-02T00:00:00Z",
            "ground_truth": "true_positive",
            "reviewer_id": "DM-001",
            "affected_operations": true,
            "safety_risk": false
          }
        ]
        """
    )

    try:
        load_silent_log(path)
    except ValueError as exc:
        assert "affected operations" in str(exc)
    else:
        raise AssertionError("expected operational-impact rejection")


def test_evaluate_silent_log_reports_burden_deltas_and_stop_criteria():
    entries = load_silent_log(SILENT_LOG)

    report = evaluate_silent_log(entries, false_positive_tolerance_per_reviewer_week=1.0)

    assert report.metrics["recommendations_total"] == 4
    assert report.metrics["true_positives"] == 2
    assert report.metrics["false_positives"] == 1
    assert report.metrics["safety_risks"] == 1
    assert report.metrics["median_hours_earlier"] == 24.0
    assert report.metrics["false_positive_burden_per_reviewer_week"] == 0.5
    assert report.gates["no_operational_impact"] is True
    assert report.gates["false_positive_burden_controlled"] is True
    assert report.gates["stop_criteria_triggered"] is True

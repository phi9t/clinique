from pathlib import Path

from clinique.edc.silent import SilentLogEntry, evaluate_silent_log, load_silent_log


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


def test_load_silent_log_rejects_string_boolean_values(tmp_path):
    path = tmp_path / "string_boolean_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-STRING-BOOL",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001"],
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "false_positive",
            "reviewer_id": "DM-001",
            "affected_operations": false,
            "safety_risk": "false"
          }
        ]
        """
    )

    try:
        load_silent_log(path)
    except ValueError as exc:
        assert "safety_risk must be a boolean" in str(exc)
    else:
        raise AssertionError("expected strict boolean rejection")


def test_load_silent_log_rejects_empty_logs(tmp_path):
    path = tmp_path / "empty_silent_log.json"
    path.write_text("[]")

    try:
        load_silent_log(path)
    except ValueError as exc:
        assert "at least one recommendation" in str(exc)
    else:
        raise AssertionError("expected empty silent log rejection")


def test_load_silent_log_rejects_unknown_ground_truth_values(tmp_path):
    path = tmp_path / "unknown_ground_truth_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-UNKNOWN-GT",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001"],
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "maybe_positive",
            "reviewer_id": "DM-001",
            "affected_operations": false,
            "safety_risk": false
          }
        ]
        """
    )

    try:
        load_silent_log(path)
    except ValueError as exc:
        assert "ground_truth must be one of" in str(exc)
    else:
        raise AssertionError("expected ground-truth enum rejection")


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


def test_evaluate_silent_log_normalizes_false_positives_by_reviewer_weeks():
    entries = tuple(
        SilentLogEntry.from_json(raw)
        for raw in [
            {
                "recommendation_id": "SIL-LONG-001",
                "logged_at": "2026-04-01T00:00:00Z",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-01",
                "subject_id": "SUBJ-001",
                "form": "AE",
                "field": "term",
                "query_category": "missing",
                "agent_recommendation": "Draft query",
                "agent_evidence": ["rec-ae-001"],
                "human_action": "no_query",
                "human_action_at": "2026-04-01T12:00:00Z",
                "ground_truth": "false_positive",
                "reviewer_id": "DM-001",
                "affected_operations": False,
                "safety_risk": False,
            },
            {
                "recommendation_id": "SIL-LONG-002",
                "logged_at": "2026-04-15T00:00:00Z",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-02",
                "subject_id": "SUBJ-002",
                "form": "AE",
                "field": "term",
                "query_category": "missing",
                "agent_recommendation": "Draft query",
                "agent_evidence": ["rec-ae-002"],
                "human_action": "no_query",
                "human_action_at": "2026-04-15T12:00:00Z",
                "ground_truth": "true_negative",
                "reviewer_id": "DM-002",
                "affected_operations": False,
                "safety_risk": False,
            },
        ]
    )

    report = evaluate_silent_log(entries, false_positive_tolerance_per_reviewer_week=1.0)

    assert report.metrics["evaluation_weeks"] == 2
    assert report.metrics["false_positive_burden_per_reviewer_week"] == 0.25

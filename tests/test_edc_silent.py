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


def test_load_silent_log_rejects_inconsistent_safety_risk_labels(tmp_path):
    path = tmp_path / "inconsistent_safety_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-SAFETY-MISSING-FLAG",
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
            "ground_truth": "safety_risk",
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
        assert "ground_truth safety_risk requires safety_risk true" in str(exc)
    else:
        raise AssertionError("expected missing safety-risk flag rejection")

    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-SAFETY-SPURIOUS-FLAG",
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
            "safety_risk": true
          }
        ]
        """
    )

    try:
        load_silent_log(path)
    except ValueError as exc:
        assert "safety_risk true requires ground_truth safety_risk" in str(exc)
    else:
        raise AssertionError("expected spurious safety-risk flag rejection")


def test_load_silent_log_rejects_unknown_query_categories(tmp_path):
    path = tmp_path / "unknown_query_category_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-UNKNOWN-CATEGORY",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "maybe_missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001"],
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "false_positive",
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
        assert "query_category must be one of" in str(exc)
    else:
        raise AssertionError("expected silent query-category enum rejection")


def test_load_silent_log_rejects_recommendations_without_evidence(tmp_path):
    path = tmp_path / "missing_evidence_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-NO-EVIDENCE",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": [],
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "false_positive",
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
        assert "silent recommendations require evidence" in str(exc)
    else:
        raise AssertionError("expected missing evidence rejection")


def test_load_silent_log_rejects_invalid_evidence_citations(tmp_path):
    path = tmp_path / "invalid_evidence_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-BLANK-EVIDENCE",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001", " "],
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "false_positive",
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
        assert "agent_evidence citations must be nonblank strings" in str(exc)
    else:
        raise AssertionError("expected blank evidence citation rejection")

    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-NONSTRING-EVIDENCE",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001", 123],
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "false_positive",
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
        assert "agent_evidence citations must be nonblank strings" in str(exc)
    else:
        raise AssertionError("expected non-string evidence citation rejection")

    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-SCALAR-EVIDENCE",
            "logged_at": "2026-04-01T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": "rec-ae-001",
            "human_action": "no_query",
            "human_action_at": "2026-04-01T12:00:00Z",
            "ground_truth": "false_positive",
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
        assert "agent_evidence must be a JSON list" in str(exc)
    else:
        raise AssertionError("expected scalar evidence rejection")


def test_load_silent_log_rejects_duplicate_recommendation_ids(tmp_path):
    path = tmp_path / "duplicate_recommendations_silent_log.json"
    path.write_text(
        """
        [
          {
            "recommendation_id": "SIL-DUP",
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
            "safety_risk": false
          },
          {
            "recommendation_id": "SIL-DUP",
            "logged_at": "2026-04-02T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-002",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-002"],
            "human_action": "no_query",
            "human_action_at": "2026-04-02T12:00:00Z",
            "ground_truth": "false_positive",
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
        assert "duplicate silent recommendation id" in str(exc)
    else:
        raise AssertionError("expected duplicate recommendation id rejection")


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


def test_evaluate_silent_log_preserves_late_recommendation_time_deltas():
    entry = SilentLogEntry.from_json(
        {
            "recommendation_id": "SIL-LATE-001",
            "logged_at": "2026-04-02T00:00:00Z",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "query_category": "missing",
            "agent_recommendation": "Draft query",
            "agent_evidence": ["rec-ae-001"],
            "human_action": "opened_query",
            "human_action_at": "2026-04-01T00:00:00Z",
            "ground_truth": "true_positive",
            "reviewer_id": "DM-001",
            "affected_operations": False,
            "safety_risk": False,
        }
    )

    report = evaluate_silent_log((entry,), false_positive_tolerance_per_reviewer_week=1.0)

    assert report.metrics["median_hours_earlier"] == -24.0


def test_evaluate_silent_log_rejects_nonfinite_false_positive_tolerance():
    entries = load_silent_log(SILENT_LOG)

    try:
        evaluate_silent_log(entries, false_positive_tolerance_per_reviewer_week=float("nan"))
    except ValueError as exc:
        assert "false_positive_tolerance_per_reviewer_week must be finite" in str(exc)
    else:
        raise AssertionError("expected NaN tolerance rejection")

    try:
        evaluate_silent_log(entries, false_positive_tolerance_per_reviewer_week=float("inf"))
    except ValueError as exc:
        assert "false_positive_tolerance_per_reviewer_week must be finite" in str(exc)
    else:
        raise AssertionError("expected infinite tolerance rejection")

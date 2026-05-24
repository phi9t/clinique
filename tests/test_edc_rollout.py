from pathlib import Path

from clinique.edc.rollout import evaluate_rollout_gate, load_rollout_gate


ROLLOUT_GATE = Path("tests/fixtures/edc_query/controlled_rollout_gate.json")


def test_evaluate_rollout_gate_passes_when_thresholds_and_safety_hold():
    gate = load_rollout_gate(ROLLOUT_GATE)

    report = evaluate_rollout_gate(gate)

    assert report.metrics["manual_minutes_per_query_delta"] == -8.0
    assert report.metrics["true_discrepancy_delta"] == 12
    assert report.metrics["false_query_rate"] == 0.03
    assert report.gates["primary_endpoints_met"] is True
    assert report.gates["safety_endpoints_clear"] is True
    assert report.gates["human_approval_path_validated"] is True
    assert report.gates["rollout_gate_passed"] is True


def test_evaluate_rollout_gate_blocks_on_safety_endpoint(tmp_path):
    path = tmp_path / "bad_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-BAD",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 1,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    report = evaluate_rollout_gate(load_rollout_gate(path))

    assert report.gates["primary_endpoints_met"] is True
    assert report.gates["safety_endpoints_clear"] is False
    assert report.gates["rollout_gate_passed"] is False


def test_load_rollout_gate_rejects_missing_required_metric_keys(tmp_path):
    path = tmp_path / "incomplete_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-INCOMPLETE",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "missing threshold keys" in str(exc)
        assert "min_true_discrepancy_delta" in str(exc)
    else:
        raise AssertionError("expected missing threshold rejection")


def test_load_rollout_gate_rejects_string_boolean_values(tmp_path):
    path = tmp_path / "string_boolean_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-STRING-BOOL",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": "false",
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": "false"
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "human_approval_path_validated must be a boolean" in str(exc)
    else:
        raise AssertionError("expected strict boolean rejection")


def test_load_rollout_gate_rejects_string_numeric_values(tmp_path):
    path = tmp_path / "string_numeric_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-STRING-NUMERIC",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": "0.05",
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "max_false_query_rate must be numeric" in str(exc)
    else:
        raise AssertionError("expected strict numeric rejection")


def test_load_rollout_gate_rejects_string_safety_count_values(tmp_path):
    path = tmp_path / "string_safety_count_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-STRING-SAFETY",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": "0",
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "unauthorized_write_back must be a nonnegative integer" in str(exc)
    else:
        raise AssertionError("expected strict safety count rejection")


def test_load_rollout_gate_rejects_out_of_range_rate_values(tmp_path):
    path = tmp_path / "out_of_range_rates_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-BAD-RATE",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 1.2,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "max_false_query_rate must be between 0 and 1" in str(exc)
    else:
        raise AssertionError("expected out-of-range rate rejection")


def test_load_rollout_gate_rejects_negative_count_values(tmp_path):
    path = tmp_path / "negative_counts_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-NEGATIVE-OBSERVED-COUNT",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": -1,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "open_queries_at_lock must be a nonnegative integer" in str(exc)
    else:
        raise AssertionError("expected negative observed count rejection")

    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-NEGATIVE-THRESHOLD-COUNT",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": -1,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "max_open_queries_at_lock must be a nonnegative integer" in str(exc)
    else:
        raise AssertionError("expected negative threshold count rejection")


def test_load_rollout_gate_rejects_fractional_count_values(tmp_path):
    path = tmp_path / "fractional_counts_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-FRACTIONAL-OBSERVED-COUNT",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4.5,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "open_queries_at_lock must be a nonnegative integer" in str(exc)
    else:
        raise AssertionError("expected fractional observed count rejection")

    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-FRACTIONAL-THRESHOLD-COUNT",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10.5,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "max_open_queries_at_lock must be a nonnegative integer" in str(exc)
    else:
        raise AssertionError("expected fractional threshold count rejection")


def test_load_rollout_gate_rejects_fractional_true_discrepancy_deltas(tmp_path):
    path = tmp_path / "fractional_delta_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-FRACTIONAL-OBSERVED-DELTA",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": -1.5,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "true_discrepancy_delta must be an integer" in str(exc)
    else:
        raise AssertionError("expected fractional observed delta rejection")

    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-FRACTIONAL-THRESHOLD-DELTA",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1.5,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "min_true_discrepancy_delta must be an integer" in str(exc)
    else:
        raise AssertionError("expected fractional threshold delta rejection")


def test_load_rollout_gate_rejects_unknown_randomization_units(tmp_path):
    path = tmp_path / "unknown_randomization_unit_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-UNKNOWN-RANDOMIZATION",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "free_text_team_bucket",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "randomization_unit must be one of" in str(exc)
        assert "form_family" in str(exc)
    else:
        raise AssertionError("expected unknown randomization-unit rejection")


def test_load_rollout_gate_rejects_permissive_improvement_thresholds(tmp_path):
    path = tmp_path / "permissive_threshold_rollout_gate.json"
    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-NEGATIVE-TRUE-DISCREPANCY-THRESHOLD",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": -1,
            "max_manual_minutes_per_query_delta": 0
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "min_true_discrepancy_delta must be nonnegative" in str(exc)
    else:
        raise AssertionError("expected permissive true-discrepancy threshold rejection")

    path.write_text(
        """
        {
          "gate_id": "ROLLOUT-POSITIVE-MINUTES-THRESHOLD",
          "evaluated_at": "2026-05-01T00:00:00Z",
          "randomization_unit": "form_family",
          "human_approval_path_validated": true,
          "thresholds": {
            "max_false_query_rate": 0.05,
            "max_duplicate_query_rate": 0.10,
            "min_acceptance_rate": 0.75,
            "max_open_queries_at_lock": 10,
            "min_true_discrepancy_delta": 1,
            "max_manual_minutes_per_query_delta": 2
          },
          "observed": {
            "manual_minutes_per_query_delta": -5,
            "true_discrepancy_delta": 4,
            "false_query_rate": 0.02,
            "duplicate_query_rate": 0.02,
            "query_resolution_time_delta_hours": -12,
            "open_queries_at_lock": 4,
            "acceptance_rate": 0.8
          },
          "safety": {
            "unauthorized_write_back": 0,
            "unsupported_evidence": 0,
            "privacy_incident": 0,
            "blinding_breach": 0,
            "excessive_reviewer_burden": false
          }
        }
        """
    )

    try:
        load_rollout_gate(path)
    except ValueError as exc:
        assert "max_manual_minutes_per_query_delta must be nonpositive" in str(exc)
    else:
        raise AssertionError("expected permissive manual-minutes threshold rejection")

import json
from pathlib import Path

from clinique.cli import main


FIXTURES = Path("tests/fixtures/edc_query")


def _internal_manifest() -> dict[str, object]:
    return {
        "manifest_version": "1",
        "generated_at": "2026-05-24T00:00:00Z",
        "sources": [
            {
                "source_type": "edc_snapshots",
                "owner": "data-management@example.test",
                "export_path": "/approved/exports/edc_snapshots",
                "schema_sketch": [
                    "snapshot_id",
                    "snapshot_at",
                    "contains_phi",
                    "contains_unblinded",
                    "record_id",
                    "study_id",
                    "site_id",
                    "subject_id",
                    "form",
                    "field",
                    "value",
                    "collected_at",
                ],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
            {
                "source_type": "query_logs",
                "owner": "data-management@example.test",
                "export_path": "/approved/exports/query_logs",
                "schema_sketch": [
                    "query_id",
                    "snapshot_id",
                    "study_id",
                    "site_id",
                    "subject_id",
                    "form",
                    "field",
                    "query_text",
                    "query_category",
                    "opened_at",
                    "closed_at",
                    "status",
                    "resolution",
                ],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
            {
                "source_type": "edit_check_history",
                "owner": "edc-build@example.test",
                "export_path": "/approved/exports/rules",
                "schema_sketch": [
                    "rule_id",
                    "kind",
                    "form",
                    "field",
                    "query_category",
                    "message",
                    "effective_at",
                ],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "no_phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
        ],
    }


def _write_internal_export_manifest(root: Path) -> Path:
    for dirname in ["edc_snapshots", "query_logs", "edit_check_history"]:
        (root / dirname).mkdir(parents=True)
    (root / "edc_snapshots" / "snapshots.json").write_text((FIXTURES / "snapshots.json").read_text())
    (root / "query_logs" / "query_logs.json").write_text((FIXTURES / "query_logs.json").read_text())
    (root / "edit_check_history" / "rules.json").write_text((FIXTURES / "rules.json").read_text())
    manifest = _internal_manifest()
    for source in manifest["sources"]:
        if source["source_type"] == "edc_snapshots":
            source["export_path"] = str(root / "edc_snapshots")
        elif source["source_type"] == "query_logs":
            source["export_path"] = str(root / "query_logs")
        elif source["source_type"] == "edit_check_history":
            source["export_path"] = str(root / "edit_check_history")
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_edc_query_validate_writes_reports_and_audit_summary(tmp_path):
    reports_dir = tmp_path / "reports"

    exit_code = main(
        [
            "edc-query",
            "validate",
            "--fixtures",
            "tests/fixtures/edc_query",
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 0
    assert (reports_dir / "offline-benchmark.json").exists()
    assert (reports_dir / "retrospective-replay.json").exists()
    audit = json.loads((reports_dir / "audit-summary.json").read_text())
    assert audit["local_synthetic_validation_complete"] is True
    assert audit["goal_complete"] is False
    assert "internal_data_validation__internal_edc_snapshots_approved_and_connected" in (
        audit["blocked_requirements"]
    )


def test_edc_query_validate_outputs_are_repeatable(tmp_path):
    reports_dir = tmp_path / "reports"
    args = [
        "edc-query",
        "validate",
        "--fixtures",
        "tests/fixtures/edc_query",
        "--reports-dir",
        str(reports_dir),
    ]

    assert main(args) == 0
    first = {
        path.name: path.read_text()
        for path in sorted(reports_dir.glob("*.json"))
    }
    assert main(args) == 0
    second = {
        path.name: path.read_text()
        for path in sorted(reports_dir.glob("*.json"))
    }

    assert second == first


def test_edc_query_validate_rejects_phi_marked_fixtures(tmp_path):
    fixture_dir = tmp_path / "bad-fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        '[{"snapshot_id":"bad","snapshot_at":"2026-03-01T00:00:00Z","contains_phi":true,'
        '"contains_unblinded":false,"records":[]}]'
    )
    (fixture_dir / "rules.json").write_text("[]")
    (fixture_dir / "query_logs.json").write_text("[]")
    (fixture_dir / "labels.json").write_text("[]")

    exit_code = main(
        [
            "edc-query",
            "validate",
            "--fixtures",
            str(fixture_dir),
            "--reports-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 2


def test_edc_query_preflight_internal_data_writes_result(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_internal_manifest()))
    output = tmp_path / "preflight.json"

    exit_code = main(
        [
            "edc-query",
            "preflight-internal-data",
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    result = json.loads(output.read_text())
    assert result["ok"] is True
    assert result["missing_required_sources"] == []


def test_edc_query_preflight_internal_data_returns_nonzero_for_unready_manifest(tmp_path):
    manifest = _internal_manifest()
    manifest["sources"] = manifest["sources"][:1]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    exit_code = main(
        [
            "edc-query",
            "preflight-internal-data",
            "--manifest",
            str(path),
        ]
    )

    assert exit_code == 3


def test_edc_query_evaluate_silent_log_writes_report_and_returns_nonzero_on_stop_criteria(
    tmp_path,
):
    output = tmp_path / "silent-report.json"

    exit_code = main(
        [
            "edc-query",
            "evaluate-silent-log",
            "--log",
            "tests/fixtures/edc_query/silent_log.json",
            "--output",
            str(output),
            "--false-positive-tolerance",
            "1.0",
        ]
    )

    assert exit_code == 6
    report = json.loads(output.read_text())
    assert report["report_type"] == "edc_query_silent_prospective"
    assert report["metrics"]["false_positive_burden_per_reviewer_week"] == 0.5
    assert report["gates"]["stop_criteria_triggered"] is True


def test_edc_query_evaluate_silent_log_returns_nonzero_when_operations_were_affected(tmp_path):
    path = tmp_path / "bad_silent_log.json"
    path.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "SIL-BAD",
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
                    "affected_operations": True,
                    "safety_risk": False,
                }
            ]
        )
    )

    exit_code = main(
        [
            "edc-query",
            "evaluate-silent-log",
            "--log",
            str(path),
            "--output",
            str(tmp_path / "silent-report.json"),
        ]
    )

    assert exit_code == 2


def test_edc_query_evaluate_silent_log_rejects_negative_false_positive_tolerance(tmp_path):
    exit_code = main(
        [
            "edc-query",
            "evaluate-silent-log",
            "--log",
            "tests/fixtures/edc_query/silent_log.json",
            "--output",
            str(tmp_path / "silent-report.json"),
            "--false-positive-tolerance",
            "-0.1",
        ]
    )

    assert exit_code == 2


def test_edc_query_evaluate_rollout_gate_writes_report(tmp_path):
    output = tmp_path / "rollout-report.json"

    exit_code = main(
        [
            "edc-query",
            "evaluate-rollout-gate",
            "--gate",
            "tests/fixtures/edc_query/controlled_rollout_gate.json",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text())
    assert report["report_type"] == "edc_query_controlled_rollout_gate"
    assert report["gates"]["rollout_gate_passed"] is True


def test_edc_query_evaluate_rollout_gate_returns_nonzero_when_gate_fails(tmp_path):
    path = tmp_path / "bad_rollout_gate.json"
    path.write_text(
        json.dumps(
            {
                "gate_id": "ROLLOUT-BAD",
                "evaluated_at": "2026-05-01T00:00:00Z",
                "randomization_unit": "form_family",
                "human_approval_path_validated": False,
                "thresholds": {
                    "max_false_query_rate": 0.05,
                    "max_duplicate_query_rate": 0.1,
                    "min_acceptance_rate": 0.75,
                    "max_open_queries_at_lock": 10,
                    "min_true_discrepancy_delta": 1,
                    "max_manual_minutes_per_query_delta": 0,
                },
                "observed": {
                    "manual_minutes_per_query_delta": 3,
                    "true_discrepancy_delta": 0,
                    "false_query_rate": 0.2,
                    "duplicate_query_rate": 0.2,
                    "query_resolution_time_delta_hours": 4,
                    "open_queries_at_lock": 20,
                    "acceptance_rate": 0.5,
                },
                "safety": {
                    "unauthorized_write_back": 0,
                    "unsupported_evidence": 0,
                    "privacy_incident": 0,
                    "blinding_breach": 0,
                    "excessive_reviewer_burden": False,
                },
            }
        )
    )

    exit_code = main(
        [
            "edc-query",
            "evaluate-rollout-gate",
            "--gate",
            str(path),
            "--output",
            str(tmp_path / "rollout-report.json"),
        ]
    )

    assert exit_code == 4


def test_edc_query_verify_workstream_writes_consolidated_evidence(tmp_path):
    reports_dir = tmp_path / "reports"

    exit_code = main(
        [
            "edc-query",
            "verify-workstream",
            "--fixtures",
            "tests/fixtures/edc_query",
            "--manifest",
            ".workstreams/edc-query-validation/internal-data-manifest.template.json",
            "--silent-log",
            "tests/fixtures/edc_query/silent_log.json",
            "--rollout-gate",
            "tests/fixtures/edc_query/controlled_rollout_gate.json",
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 5
    evidence = json.loads((reports_dir / "workstream-verification.json").read_text())
    assert evidence["local_reports_complete"] is True
    assert evidence["goal_complete"] is False
    assert set(evidence["reports"]) == {
        "audit_summary",
        "controlled_rollout_gate",
        "internal_preflight",
        "offline_benchmark",
        "retrospective_replay",
        "silent_log_evaluation",
    }
    assert "internal_data_validation__internal_edc_snapshots_approved_and_connected" in (
        evidence["blocked_requirements"]
    )


def test_edc_query_verify_workstream_can_include_internal_export_reports(tmp_path):
    reports_dir = tmp_path / "reports"

    exit_code = main(
        [
            "edc-query",
            "verify-workstream",
            "--fixtures",
            "tests/fixtures/edc_query",
            "--manifest",
            ".workstreams/edc-query-validation/internal-data-manifest.template.json",
            "--silent-log",
            "tests/fixtures/edc_query/silent_log.json",
            "--rollout-gate",
            "tests/fixtures/edc_query/controlled_rollout_gate.json",
            "--reports-dir",
            str(reports_dir),
            "--internal-export-manifest",
            "tests/fixtures/edc_query/internal_export_manifest.json",
            "--internal-labels",
            "tests/fixtures/edc_query/labels.json",
            "--internal-lock-issues",
            "tests/fixtures/edc_query/lock_issues.json",
        ]
    )

    assert exit_code == 5
    evidence = json.loads((reports_dir / "workstream-verification.json").read_text())
    assert evidence["local_internal_export_reports_complete"] is True
    assert evidence["reports"]["internal_offline_benchmark"] == str(
        reports_dir / "internal-offline-benchmark.json"
    )
    assert evidence["reports"]["internal_retrospective_replay"] == str(
        reports_dir / "internal-retrospective-replay.json"
    )
    assert evidence["gates"]["internal_export_offline"]["no_write_back"] is True
    assert evidence["gates"]["internal_export_retrospective"]["timestamped_replay"] is True
    assert "internal_data_validation__internal_l1_offline_report_generated" in (
        evidence["blocked_requirements"]
    )


def test_edc_query_verify_workstream_fails_unready_internal_manifest(tmp_path):
    reports_dir = tmp_path / "reports"
    manifest = _internal_manifest()
    manifest["sources"] = manifest["sources"][:1]
    manifest_path = tmp_path / "unready-manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    exit_code = main(
        [
            "edc-query",
            "verify-workstream",
            "--fixtures",
            "tests/fixtures/edc_query",
            "--manifest",
            str(manifest_path),
            "--silent-log",
            "tests/fixtures/edc_query/silent_log.json",
            "--rollout-gate",
            "tests/fixtures/edc_query/controlled_rollout_gate.json",
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 2
    preflight = json.loads((reports_dir / "internal-preflight-template.json").read_text())
    assert preflight["ok"] is False
    assert preflight["missing_required_sources"] == ["query_logs", "edit_check_history"]
    assert not (reports_dir / "workstream-verification.json").exists()


def test_edc_query_validate_internal_exports_writes_l1_l2_reports(tmp_path):
    manifest = _write_internal_export_manifest(tmp_path / "exports")
    reports_dir = tmp_path / "reports"

    exit_code = main(
        [
            "edc-query",
            "validate-internal-exports",
            "--manifest",
            str(manifest),
            "--labels",
            "tests/fixtures/edc_query/labels.json",
            "--lock-issues",
            "tests/fixtures/edc_query/lock_issues.json",
            "--reports-dir",
            str(reports_dir),
        ]
    )

    assert exit_code == 0
    assert (reports_dir / "internal-offline-benchmark.json").exists()
    assert (reports_dir / "internal-retrospective-replay.json").exists()
    offline = json.loads((reports_dir / "internal-offline-benchmark.json").read_text())
    assert offline["gates"]["no_write_back"] is True


def test_edc_query_validate_internal_exports_returns_nonzero_for_missing_payload(tmp_path):
    root = tmp_path / "exports"
    manifest = _write_internal_export_manifest(root)
    (root / "edit_check_history" / "rules.json").unlink()

    exit_code = main(
        [
            "edc-query",
            "validate-internal-exports",
            "--manifest",
            str(manifest),
            "--labels",
            "tests/fixtures/edc_query/labels.json",
            "--reports-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 2

import json

from clinique.cli import main


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

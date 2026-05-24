import json
from pathlib import Path

from clinique.edc.internal_import import load_internal_export_bundle


FIXTURES = Path("tests/fixtures/edc_query")


def _write_manifest(
    root: Path,
    *,
    read_only: bool = True,
    unblinded: bool = False,
    snapshot_payload: str | None = None,
) -> Path:
    for dirname in ["edc_snapshots", "query_logs", "edit_check_history"]:
        (root / dirname).mkdir(parents=True)
    (root / "edc_snapshots" / "snapshots.json").write_text(
        snapshot_payload or (FIXTURES / "snapshots.json").read_text()
    )
    (root / "query_logs" / "query_logs.json").write_text((FIXTURES / "query_logs.json").read_text())
    (root / "edit_check_history" / "rules.json").write_text((FIXTURES / "rules.json").read_text())
    manifest = {
        "manifest_version": "1",
        "generated_at": "2026-05-24T00:00:00Z",
        "sources": [
            {
                "source_type": "edc_snapshots",
                "owner": "data-management@example.test",
                "export_path": str(root / "edc_snapshots"),
                "schema_sketch": ["study_id", "site_id", "subject_id", "form", "field"],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "phi",
                "blinding_status": "unblinded" if unblinded else "blinded",
                "read_only": read_only,
            },
            {
                "source_type": "query_logs",
                "owner": "data-management@example.test",
                "export_path": str(root / "query_logs"),
                "schema_sketch": ["query_id", "subject_id", "opened_at"],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
            {
                "source_type": "edit_check_history",
                "owner": "edc-build@example.test",
                "export_path": str(root / "edit_check_history"),
                "schema_sketch": ["rule_id", "effective_at"],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "no_phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
        ],
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_load_internal_export_bundle_requires_passing_preflight(tmp_path):
    manifest = _write_manifest(tmp_path, unblinded=True)

    try:
        load_internal_export_bundle(
            manifest,
            labels_path=FIXTURES / "labels.json",
            lock_issues_path=FIXTURES / "lock_issues.json",
        )
    except ValueError as exc:
        assert "preflight" in str(exc)
    else:
        raise AssertionError("expected unblinded manifest rejection")


def test_load_internal_export_bundle_rejects_unblinded_snapshot_payload(tmp_path):
    manifest = _write_manifest(
        tmp_path,
        snapshot_payload=(
            '[{"snapshot_id":"bad","snapshot_at":"2026-03-01T00:00:00Z",'
            '"contains_phi":false,"contains_unblinded":true,"records":[]}]'
        ),
    )

    try:
        load_internal_export_bundle(
            manifest,
            labels_path=FIXTURES / "labels.json",
            lock_issues_path=FIXTURES / "lock_issues.json",
        )
    except ValueError as exc:
        assert "unblinded" in str(exc)
    else:
        raise AssertionError("expected unblinded snapshot rejection")


def test_load_internal_export_bundle_builds_fixture_bundle_from_approved_exports(tmp_path):
    manifest = _write_manifest(tmp_path)

    bundle = load_internal_export_bundle(
        manifest,
        labels_path=FIXTURES / "labels.json",
        lock_issues_path=FIXTURES / "lock_issues.json",
    )

    assert [snapshot.snapshot_id for snapshot in bundle.snapshots] == [
        "snap-2026-03-01",
        "snap-2026-03-08",
    ]
    assert {rule.rule_id for rule in bundle.rules} >= {
        "RULE-MISSING-AE",
        "RULE-CONMED-AE-DATE",
    }
    assert [issue.issue_id for issue in bundle.lock_issues] == ["LOCK-001"]


def test_load_internal_export_bundle_rejects_duplicate_lock_issue_ids(tmp_path):
    manifest = _write_manifest(tmp_path)
    issue = {
        "issue_id": "LOCK-DUP",
        "study_id": "STUDY-EDC-001",
        "site_id": "SITE-01",
        "subject_id": "SUBJ-001",
        "form": "AE",
        "field": "term",
        "severity": "major",
        "discovered_at": "2026-03-05T09:00:00Z",
        "description": "Database lock issue.",
    }
    lock_issues_path = tmp_path / "lock_issues.json"
    lock_issues_path.write_text(json.dumps([issue, dict(issue)]))

    try:
        load_internal_export_bundle(
            manifest,
            labels_path=FIXTURES / "labels.json",
            lock_issues_path=lock_issues_path,
        )
    except ValueError as exc:
        assert "duplicate lock issue id" in str(exc)
    else:
        raise AssertionError("expected duplicate lock issue id rejection")

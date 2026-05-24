import json
from pathlib import Path

from clinique.edc.fixtures import load_fixture_bundle


FIXTURES = Path("tests/fixtures/edc_query")


def test_load_fixture_bundle_has_timestamped_snapshots_and_labels():
    bundle = load_fixture_bundle(FIXTURES)

    assert [snapshot.snapshot_id for snapshot in bundle.snapshots] == [
        "snap-2026-03-01",
        "snap-2026-03-08",
    ]
    assert {label.query_category for label in bundle.labels} >= {
        "missing",
        "inconsistent",
        "impossible",
        "duplicate",
    }
    assert all(not snapshot.contains_phi for snapshot in bundle.snapshots)
    assert [issue.issue_id for issue in bundle.lock_issues] == ["LOCK-001"]


def test_fixture_bundle_rejects_unblinded_or_phi_markers(tmp_path):
    fixture_dir = tmp_path / "bad"
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        '[{"snapshot_id":"bad","snapshot_at":"2026-03-01T00:00:00Z","contains_phi":true,'
        '"contains_unblinded":false,"records":[]}]'
    )
    (fixture_dir / "rules.json").write_text("[]")
    (fixture_dir / "query_logs.json").write_text("[]")
    (fixture_dir / "labels.json").write_text("[]")

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "PHI" in str(exc)
    else:
        raise AssertionError("expected PHI fixture rejection")


def test_fixture_bundle_rejects_string_snapshot_sensitivity_flags(tmp_path):
    fixture_dir = tmp_path / "bad_snapshot_flags"
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        '[{"snapshot_id":"bad","snapshot_at":"2026-03-01T00:00:00Z","contains_phi":"false",'
        '"contains_unblinded":false,"records":[]}]'
    )
    (fixture_dir / "rules.json").write_text("[]")
    (fixture_dir / "query_logs.json").write_text("[]")
    (fixture_dir / "labels.json").write_text("[]")

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "contains_phi must be a boolean" in str(exc)
    else:
        raise AssertionError("expected string snapshot flag rejection")


def test_fixture_bundle_rejects_string_label_booleans(tmp_path):
    for field_name, expected_error in [
        ("gold_query_needed", "gold_query_needed must be a boolean"),
        (
            "evidence_available_at_agent_time",
            "evidence_available_at_agent_time must be a boolean",
        ),
    ]:
        fixture_dir = tmp_path / field_name
        fixture_dir.mkdir()
        (fixture_dir / "snapshots.json").write_text(
            '[{"snapshot_id":"snap","snapshot_at":"2026-03-01T00:00:00Z","contains_phi":false,'
            '"contains_unblinded":false,"records":[]}]'
        )
        (fixture_dir / "rules.json").write_text("[]")
        (fixture_dir / "query_logs.json").write_text("[]")
        label = {
            "snapshot_id": "snap",
            "study_id": "STUDY-EDC-001",
            "site_id": "SITE-01",
            "subject_id": "SUBJ-001",
            "form": "AE",
            "field": "term",
            "gold_query_needed": True,
            "query_category": "missing",
            "human_resolution": "corrected",
            "opened_at": "2026-03-02T09:00:00Z",
            "closed_at": None,
            "evidence_available_at_agent_time": True,
        }
        label[field_name] = "true"
        (fixture_dir / "labels.json").write_text(json.dumps([label]))

        try:
            load_fixture_bundle(fixture_dir)
        except ValueError as exc:
            assert expected_error in str(exc)
        else:
            raise AssertionError("expected string label flag rejection")

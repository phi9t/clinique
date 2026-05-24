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

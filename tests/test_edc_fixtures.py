import json
from pathlib import Path

from clinique.edc.fixtures import load_fixture_bundle


FIXTURES = Path("tests/fixtures/edc_query")


def _write_minimal_fixture_dir(
    fixture_dir: Path,
    *,
    rules: list[dict[str, object]] | None = None,
    query_logs: list[dict[str, object]] | None = None,
    labels: list[dict[str, object]] | None = None,
) -> None:
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        '[{"snapshot_id":"snap","snapshot_at":"2026-03-01T00:00:00Z","contains_phi":false,'
        '"contains_unblinded":false,"records":[]}]'
    )
    (fixture_dir / "rules.json").write_text(json.dumps(rules or []))
    (fixture_dir / "query_logs.json").write_text(json.dumps(query_logs or []))
    (fixture_dir / "labels.json").write_text(json.dumps(labels or []))


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


def test_fixture_bundle_rejects_unknown_label_enums(tmp_path):
    base_label = {
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
    for field_name, invalid_value, expected_error in [
        ("query_category", "maybe_missing", "query_category must be one of"),
        ("human_resolution", "maybe_corrected", "human_resolution must be one of"),
    ]:
        fixture_dir = tmp_path / field_name
        label = dict(base_label)
        label[field_name] = invalid_value
        _write_minimal_fixture_dir(fixture_dir, labels=[label])

        try:
            load_fixture_bundle(fixture_dir)
        except ValueError as exc:
            assert expected_error in str(exc)
        else:
            raise AssertionError("expected unknown label enum rejection")


def test_fixture_bundle_rejects_unknown_source_query_categories(tmp_path):
    fixture_dir = tmp_path / "bad_rule_category"
    _write_minimal_fixture_dir(
        fixture_dir,
        rules=[
            {
                "rule_id": "RULE-BAD",
                "kind": "required_field",
                "form": "AE",
                "field": "term",
                "query_category": "maybe_missing",
                "message": "AE term is required.",
                "effective_at": "2026-03-01T00:00:00Z",
            }
        ],
    )

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "query_category must be one of" in str(exc)
    else:
        raise AssertionError("expected unknown rule category rejection")


def test_fixture_bundle_rejects_unknown_query_log_categories(tmp_path):
    fixture_dir = tmp_path / "bad_query_log_category"
    _write_minimal_fixture_dir(
        fixture_dir,
        query_logs=[
            {
                "query_id": "Q-BAD",
                "snapshot_id": "snap",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-01",
                "subject_id": "SUBJ-001",
                "form": "AE",
                "field": "term",
                "query_text": "Please confirm AE term.",
                "query_category": "maybe_missing",
                "opened_at": "2026-03-02T09:00:00Z",
                "closed_at": None,
                "status": "open",
                "resolution": "confirmed",
            }
        ],
    )

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "query_category must be one of" in str(exc)
    else:
        raise AssertionError("expected unknown query-log category rejection")


def test_fixture_bundle_rejects_missing_snapshot_timestamps(tmp_path):
    fixture_dir = tmp_path / "missing_snapshot_time"
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        '[{"snapshot_id":"snap","snapshot_at":null,"contains_phi":false,'
        '"contains_unblinded":false,"records":[]}]'
    )
    (fixture_dir / "rules.json").write_text("[]")
    (fixture_dir / "query_logs.json").write_text("[]")
    (fixture_dir / "labels.json").write_text("[]")

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "snapshot_at is required" in str(exc)
    else:
        raise AssertionError("expected missing snapshot timestamp rejection")


def test_fixture_bundle_rejects_missing_record_timestamps(tmp_path):
    fixture_dir = tmp_path / "missing_record_time"
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        """
        [
          {
            "snapshot_id": "snap",
            "snapshot_at": "2026-03-01T00:00:00Z",
            "contains_phi": false,
            "contains_unblinded": false,
            "records": [
              {
                "record_id": "REC-BAD",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-01",
                "subject_id": "SUBJ-001",
                "form": "AE",
                "field": "term",
                "value": "",
                "collected_at": null
              }
            ]
          }
        ]
        """
    )
    (fixture_dir / "rules.json").write_text("[]")
    (fixture_dir / "query_logs.json").write_text("[]")
    (fixture_dir / "labels.json").write_text("[]")

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "collected_at is required" in str(exc)
    else:
        raise AssertionError("expected missing record timestamp rejection")


def test_fixture_bundle_rejects_missing_rule_effective_timestamps(tmp_path):
    fixture_dir = tmp_path / "missing_rule_time"
    _write_minimal_fixture_dir(
        fixture_dir,
        rules=[
            {
                "rule_id": "RULE-BAD",
                "kind": "required_field",
                "form": "AE",
                "field": "term",
                "query_category": "missing",
                "message": "AE term is required.",
                "effective_at": None,
            }
        ],
    )

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "effective_at is required" in str(exc)
    else:
        raise AssertionError("expected missing rule effective timestamp rejection")


def test_fixture_bundle_rejects_query_logs_closed_before_opened(tmp_path):
    fixture_dir = tmp_path / "bad_query_log_chronology"
    _write_minimal_fixture_dir(
        fixture_dir,
        query_logs=[
            {
                "query_id": "Q-BAD",
                "snapshot_id": "snap",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-01",
                "subject_id": "SUBJ-001",
                "form": "AE",
                "field": "term",
                "query_text": "Please confirm AE term.",
                "query_category": "missing",
                "opened_at": "2026-03-03T09:00:00Z",
                "closed_at": "2026-03-02T09:00:00Z",
                "status": "closed",
                "resolution": "confirmed",
            }
        ],
    )

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "query log closed_at cannot be before opened_at" in str(exc)
    else:
        raise AssertionError("expected query-log chronology rejection")


def test_fixture_bundle_rejects_label_closed_without_opened(tmp_path):
    fixture_dir = tmp_path / "bad_label_close_without_open"
    _write_minimal_fixture_dir(
        fixture_dir,
        labels=[
            {
                "snapshot_id": "snap",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-01",
                "subject_id": "SUBJ-001",
                "form": "AE",
                "field": "term",
                "gold_query_needed": True,
                "query_category": "missing",
                "human_resolution": "corrected",
                "opened_at": None,
                "closed_at": "2026-03-05T12:00:00Z",
                "evidence_available_at_agent_time": True,
            }
        ],
    )

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "label closed_at requires opened_at" in str(exc)
    else:
        raise AssertionError("expected label close-without-open rejection")


def test_fixture_bundle_rejects_labels_closed_before_opened(tmp_path):
    fixture_dir = tmp_path / "bad_label_chronology"
    _write_minimal_fixture_dir(
        fixture_dir,
        labels=[
            {
                "snapshot_id": "snap",
                "study_id": "STUDY-EDC-001",
                "site_id": "SITE-01",
                "subject_id": "SUBJ-001",
                "form": "AE",
                "field": "term",
                "gold_query_needed": True,
                "query_category": "missing",
                "human_resolution": "corrected",
                "opened_at": "2026-03-05T12:00:00Z",
                "closed_at": "2026-03-04T12:00:00Z",
                "evidence_available_at_agent_time": True,
            }
        ],
    )

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "label closed_at cannot be before opened_at" in str(exc)
    else:
        raise AssertionError("expected label chronology rejection")

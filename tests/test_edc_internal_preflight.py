import json

from clinique.edc.internal_preflight import preflight_internal_manifest


def _valid_manifest() -> dict[str, object]:
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
                "export_path": "/approved/exports/edit_checks",
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


def test_preflight_internal_manifest_accepts_minimum_complete_manifest(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_valid_manifest()))

    result = preflight_internal_manifest(path)

    assert result.ok is True
    assert result.missing_required_sources == ()
    assert result.unblinded_sources == ()
    assert result.non_read_only_sources == ()
    assert result.invalid_metadata == ()


def test_preflight_internal_manifest_rejects_non_object_manifest(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("[]")

    try:
        preflight_internal_manifest(path)
    except ValueError as exc:
        assert "manifest must be a JSON object" in str(exc)
    else:
        raise AssertionError("expected non-object manifest rejection")


def test_preflight_internal_manifest_rejects_invalid_manifest_metadata(tmp_path):
    manifest = _valid_manifest()
    manifest["manifest_version"] = "0"
    manifest["generated_at"] = "not-a-timestamp"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.invalid_metadata == ("generated_at", "manifest_version")


def test_preflight_internal_manifest_rejects_missing_source_and_unblinded_data(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"] = [
        {
            **manifest["sources"][0],
            "source_type": "edc_snapshots",
            "blinding_status": "unblinded",
            "read_only": False,
        }
    ]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.missing_required_sources == ("query_logs", "edit_check_history")
    assert result.unblinded_sources == ("edc_snapshots",)
    assert result.non_read_only_sources == ("edc_snapshots",)


def test_preflight_internal_manifest_rejects_duplicate_source_types(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"] = [*manifest["sources"], manifest["sources"][0]]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.duplicate_sources == ("edc_snapshots",)


def test_preflight_internal_manifest_rejects_unknown_source_types(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"] = [
        *manifest["sources"],
        {
            "source_type": "safety_database",
            "owner": "safety@example.test",
            "export_path": "/approved/exports/safety",
            "schema_sketch": ["case_id", "event_term", "seriousness"],
            "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
            "sensitivity": "phi",
            "blinding_status": "blinded",
            "read_only": True,
        },
    ]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.unknown_sources == ("safety_database",)


def test_preflight_internal_manifest_rejects_invalid_date_coverage(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "date_coverage": {"start": "2026-04-01", "end": "2026-03-31"},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots",)


def test_preflight_internal_manifest_rejects_malformed_schema_sketch_entries(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "schema_sketch": ["study_id", " "],
    }
    manifest["sources"][1] = {
        **manifest["sources"][1],
        "schema_sketch": ["query_id", 123],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots", "query_logs")


def test_preflight_internal_manifest_rejects_source_specific_schema_gaps(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "schema_sketch": ["snapshot_id", "snapshot_at", "study_id"],
    }
    manifest["sources"][1] = {
        **manifest["sources"][1],
        "schema_sketch": ["query_id", "opened_at", "status"],
    }
    manifest["sources"][2] = {
        **manifest["sources"][2],
        "schema_sketch": ["rule_id", "effective_at"],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots", "query_logs", "edit_check_history")


def test_preflight_internal_manifest_rejects_malformed_source_identity_metadata(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "owner": 123,
    }
    manifest["sources"][1] = {
        **manifest["sources"][1],
        "export_path": " ",
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots", "query_logs")


def test_preflight_internal_manifest_rejects_invalid_controlled_metadata_values(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "sensitivity": "unknown",
        "blinding_status": "masked",
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots",)

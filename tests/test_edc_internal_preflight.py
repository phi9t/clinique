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
    assert result.missing_schema_fields == {}
    assert result.duplicate_schema_fields == {}
    assert result.escaped_export_paths == ()
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


def test_preflight_internal_manifest_rejects_timezone_naive_generated_at(tmp_path):
    manifest = _valid_manifest()
    manifest["generated_at"] = "2026-05-24T00:00:00"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.invalid_metadata == ("generated_at",)


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


def test_preflight_internal_manifest_rejects_malformed_source_type_metadata(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "source_type": 123,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    try:
        preflight_internal_manifest(path)
    except ValueError as exc:
        assert "each manifest source requires source_type to be a nonblank string" in str(exc)
    else:
        raise AssertionError("expected malformed source_type rejection")


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
    assert result.missing_schema_fields == {
        "edc_snapshots": (
            "collected_at",
            "contains_phi",
            "contains_unblinded",
            "field",
            "form",
            "record_id",
            "site_id",
            "subject_id",
            "value",
        ),
        "query_logs": (
            "closed_at",
            "field",
            "form",
            "query_category",
            "query_text",
            "resolution",
            "site_id",
            "snapshot_id",
            "study_id",
            "subject_id",
        ),
        "edit_check_history": (
            "field",
            "form",
            "kind",
            "message",
            "query_category",
        ),
    }


def test_preflight_internal_manifest_fails_missing_schema_fields_with_normalized_source_type(
    tmp_path,
):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "source_type": " edc_snapshots ",
        "schema_sketch": ["snapshot_id", "snapshot_at", "study_id"],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.missing_schema_fields["edc_snapshots"] == (
        "collected_at",
        "contains_phi",
        "contains_unblinded",
        "field",
        "form",
        "record_id",
        "site_id",
        "subject_id",
        "value",
    )


def test_preflight_internal_manifest_rejects_duplicate_schema_fields(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "schema_sketch": [
            *manifest["sources"][0]["schema_sketch"],
            "study_id",
            " field ",
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots",)
    assert result.duplicate_schema_fields == {"edc_snapshots": ("field", "study_id")}


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
    assert result.invalid_source_metadata == {
        "edc_snapshots": ("owner",),
        "query_logs": ("export_path",),
    }


def test_preflight_internal_manifest_rejects_escaped_relative_export_paths(tmp_path):
    root = tmp_path / "approved-export"
    root.mkdir()
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "export_path": "../outside-export",
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.escaped_export_paths == ("edc_snapshots",)


def test_preflight_internal_manifest_rejects_invalid_controlled_metadata_values(tmp_path):
    manifest = _valid_manifest()
    manifest["sources"][0] = {
        **manifest["sources"][0],
        "sensitivity": "unknown",
        "blinding_status": "masked",
        "date_coverage": {"start": "not-a-date", "end": "2026-03-31"},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    result = preflight_internal_manifest(path)

    assert result.ok is False
    assert result.incomplete_sources == ("edc_snapshots",)
    assert result.invalid_source_metadata == {
        "edc_snapshots": ("blinding_status", "date_coverage", "sensitivity")
    }

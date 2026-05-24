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
                "schema_sketch": ["study_id", "site_id", "subject_id", "form", "field"],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
            {
                "source_type": "query_logs",
                "owner": "data-management@example.test",
                "export_path": "/approved/exports/query_logs",
                "schema_sketch": ["query_id", "subject_id", "form", "field", "opened_at"],
                "date_coverage": {"start": "2026-01-01", "end": "2026-03-31"},
                "sensitivity": "phi",
                "blinding_status": "blinded",
                "read_only": True,
            },
            {
                "source_type": "edit_check_history",
                "owner": "edc-build@example.test",
                "export_path": "/approved/exports/edit_checks",
                "schema_sketch": ["rule_id", "effective_at", "logic"],
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

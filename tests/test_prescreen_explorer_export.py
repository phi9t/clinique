"""Tests for prescreen L0 explorer JSON export."""

from __future__ import annotations

import json

from clinique.prescreen.explorer_export import (
    _load_all,
    build_payload,
    dataclass_field_names,
    default_out_dir,
    documented_field_names,
    export_explorer,
)
from clinique.prescreen.validation import report_for

EXPECTED_FILES = frozenset(
    {
        "index.json",
        "schema.json",
        "stats.json",
        "validation.json",
        "trials.json",
        "patients_synthea.json",
        "patients_pmc.json",
        "patients_mimic.json",
    }
)


def test_field_docs_cover_all_dataclass_fields():
    assert documented_field_names() == dataclass_field_names()


def test_export_writes_all_files(tmp_path):
    written = export_explorer(tmp_path)
    assert frozenset(written) == EXPECTED_FILES
    assert all((tmp_path / name).is_file() for name in EXPECTED_FILES)


def test_export_top_level_keys(tmp_path):
    export_explorer(tmp_path)
    index = json.loads((tmp_path / "index.json").read_text())
    schema = json.loads((tmp_path / "schema.json").read_text())
    stats = json.loads((tmp_path / "stats.json").read_text())
    validation = json.loads((tmp_path / "validation.json").read_text())

    assert index[0].keys() >= {
        "key",
        "family",
        "label",
        "source",
        "record_type",
        "count",
        "provenance",
    }
    assert schema.keys() >= {"records", "vocab_gloss", "pipeline"}
    assert stats.keys() >= {"trials", "patients"}
    assert validation.keys() >= {
        "records_checked",
        "error_count",
        "warning_count",
        "ok",
        "issues",
    }


def test_stats_counts_match_payload():
    payload = build_payload()
    stats = payload["stats"]
    assert stats["trials"]["count"] == len(payload["trials"])
    assert stats["patients"]["synthea"]["count"] == len(payload["patients_synthea"])
    assert stats["patients"]["pmc"]["count"] == len(payload["patients_pmc"])
    assert stats["patients"]["mimic"]["count"] == len(payload["patients_mimic"])


def test_validation_matches_report_for():
    data = _load_all()
    trials = data["trials"]
    all_corpora = data["synthea"] + data["pmc"] + data["mimic"]
    expected = report_for(trials=trials, corpora=all_corpora).to_dict()
    payload = build_payload()
    assert payload["validation"] == expected


def test_export_is_deterministic(tmp_path):
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    export_explorer(out_a)
    export_explorer(out_b)
    for name in sorted(EXPECTED_FILES):
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


def test_committed_snapshot_matches_live_export(tmp_path):
    """CI gate: committed explorer JSON must match a fresh export from fixtures."""
    export_explorer(tmp_path)
    committed = default_out_dir()
    for name in sorted(EXPECTED_FILES):
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name


def test_export_works_outside_repo_root(tmp_path, monkeypatch):
    """Fixture paths resolve from the installed module, not the process CWD."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "prescreen-out"
    export_explorer(out)
    assert (out / "index.json").is_file()
    assert (out / "trials.json").is_file()

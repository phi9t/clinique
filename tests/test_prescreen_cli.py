from __future__ import annotations

import json
from pathlib import Path

from clinique.cli import main

TRIALS = Path("tests/fixtures/prescreen/trials.jsonl")


def test_prescreen_show_exits_zero_on_committed_fixture(capsys):
    exit_code = main(
        ["prescreen", "show", "--fixtures", str(TRIALS)],
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NCT" in captured.out


def test_prescreen_validate_clean_trials_exits_zero(capsys):
    exit_code = main(
        ["prescreen", "validate", "--trials", str(TRIALS)],
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "errors" in captured.err


def test_prescreen_validate_bad_corpus_exits_seven(tmp_path, capsys):
    bad = tmp_path / "bad_patients.jsonl"
    payload = {
        "patient_id": "P1",
        "snapshot_date": "2026-01-01",
        "source": "synthea",
        "demographics": {"age": 60, "sex": "male"},
        "documents": [
            {
                "doc_id": "P1:observation:0000",
                "patient_id": "P1",
                "date": "2026-06-01",
                "source_type": "observation",
                "text": "x",
                "structured": {"value": 1.0, "unit": "u"},
            }
        ],
    }
    bad.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    exit_code = main(
        ["prescreen", "validate", "--patients", str(bad)],
    )
    capsys.readouterr()
    assert exit_code == 7


def test_prescreen_validate_without_inputs_exits_two(capsys):
    exit_code = main(["prescreen", "validate"])
    capsys.readouterr()
    assert exit_code == 2


def test_prescreen_export_explorer_exits_zero(tmp_path, capsys):
    out_dir = tmp_path / "prescreen"
    exit_code = main(["prescreen", "export-explorer", "--out", str(out_dir)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "exported" in captured.out
    assert (out_dir / "index.json").is_file()
    assert (out_dir / "trials.json").is_file()

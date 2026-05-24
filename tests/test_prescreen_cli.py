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


def test_prescreen_atomize_exits_zero(capsys):
    exit_code = main(["prescreen", "atomize", "--trials", str(TRIALS)])
    capsys.readouterr()
    assert exit_code == 0


def test_prescreen_screen_exits_zero(tmp_path, capsys):
    from prescreen_helpers import TABLES
    from clinique.prescreen.normalizer import normalize_synthea

    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    patients = tmp_path / "patients.jsonl"
    patients.write_text(json.dumps(corpus.to_dict()) + "\n", encoding="utf-8")
    exit_code = main(
        [
            "prescreen",
            "screen",
            "--trial-id",
            "NCT02578680",
            "--patient-id",
            "P1",
            "--trials",
            str(TRIALS),
            "--patients",
            str(patients),
        ]
    )
    capsys.readouterr()
    assert exit_code == 0


def test_prescreen_eval_exits_zero(tmp_path, capsys):
    from prescreen_helpers import TABLES
    from clinique.prescreen.normalizer import normalize_synthea

    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    patients = tmp_path / "patients.jsonl"
    patients.write_text(json.dumps(corpus.to_dict()) + "\n", encoding="utf-8")
    reports = tmp_path / "reports"
    exit_code = main(
        [
            "prescreen",
            "eval",
            "--cases",
            ".workstream/prescreen-copilot/l0_cases.jsonl",
            "--trials",
            str(TRIALS),
            "--synthea-patients",
            str(patients),
            "--pmc-patients",
            "tests/fixtures/prescreen/pmc_patients.jsonl",
            "--reports-dir",
            str(reports),
        ]
    )
    capsys.readouterr()
    assert exit_code == 0


def test_prescreen_export_explorer_exits_zero(tmp_path, capsys):
    out_dir = tmp_path / "prescreen"
    exit_code = main(["prescreen", "export-explorer", "--out", str(out_dir)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "exported" in captured.out
    assert (out_dir / "index.json").is_file()
    assert (out_dir / "trials.json").is_file()

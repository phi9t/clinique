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
    from clinique.prescreen.normalizer import normalize_synthea
    from prescreen_helpers import TABLES

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
    from clinique.prescreen.normalizer import normalize_synthea
    from prescreen_helpers import TABLES

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


def test_prescreen_agent_judge_exits_zero_with_mock(capsys):
    from unittest.mock import patch

    from clinique.prescreen.schemas import CriterionJudgment, Evidence

    mock_judgment = CriterionJudgment(
        criterion_id="I-002",
        criterion_type="inclusion",
        prediction="met",
        evidence=(Evidence(criterion_id="I-002", doc_id="D1", quote="Stage IV NSCLC"),),
        rationale="Matched NSCLC. [Agent: Codex CLI (gpt-5.4-mini)]",
        confidence=0.9,
    )

    with (
        patch("clinique.prescreen.judge.codex_available", return_value=True),
        patch("clinique.prescreen.judge.LLMJudge.judge", return_value=mock_judgment),
    ):
        exit_code = main(
            [
                "prescreen",
                "agent-judge",
                "--criterion-id",
                "I-002",
                "--no-show-prompt",
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["trial_id"] == "NCT02578680"
    assert payload["patient_id"] == "P1"
    assert payload["agent"] == "codex"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["judgment"]["prediction"] == "met"
    assert "retrieved_evidence" in payload["results"][0]


def test_prescreen_agent_judge_default_limit_without_criterion_filter(capsys):
    from unittest.mock import patch

    from clinique.prescreen.schemas import CriterionJudgment

    def _mock_judge(criterion, evidence, corpus, **kwargs):
        return CriterionJudgment(
            criterion_id=criterion.criterion_id,
            criterion_type=criterion.criterion_type,
            prediction="unknown",
            rationale=f"Checked {criterion.criterion_id}. [Agent: Codex CLI (gpt-5.4-mini)]",
        )

    with (
        patch("clinique.prescreen.judge.codex_available", return_value=True),
        patch("clinique.prescreen.judge.LLMJudge.judge", side_effect=_mock_judge),
    ):
        exit_code = main(
            [
                "prescreen",
                "agent-judge",
                "--limit",
                "3",
                "--no-show-prompt",
                "--no-show-evidence",
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert len(payload["results"]) == 3


def test_prescreen_agent_judge_no_channels_exits_two(capsys):
    from unittest.mock import patch

    with patch("clinique.prescreen.judge.codex_available", return_value=False):
        exit_code = main(["prescreen", "agent-judge", "--no-show-prompt"])

    capsys.readouterr()
    assert exit_code == 2

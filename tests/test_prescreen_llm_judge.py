"""Tests for LLMJudge via Codex CLI."""

import json
from unittest.mock import MagicMock, patch

import pytest

from clinique.prescreen.judge import LLMJudge
from clinique.prescreen.schemas import Criterion, Evidence, PatientCorpus, PatientDocument


@pytest.fixture
def mock_criterion():
    return Criterion(
        criterion_id="I-002",
        trial_id="NCT123",
        criterion_type="inclusion",
        raw_text="Must have Stage IV NSCLC",
        clinical_domain="condition",
    )


@pytest.fixture
def mock_corpus():
    return PatientCorpus(
        patient_id="P1",
        snapshot_date="2026-03-01",
        source="synthea",
        documents=(
            PatientDocument(
                doc_id="D1",
                patient_id="P1",
                date="2026-01-01",
                source_type="condition",
                text="The patient has Stage IV NSCLC.",
            ),
        ),
    )


@pytest.fixture
def mock_evidence():
    return [Evidence(criterion_id="I-002", doc_id="D1", quote="Stage IV NSCLC")]


def test_llm_judge_codex_success(mock_criterion, mock_evidence, mock_corpus):
    judge = LLMJudge()

    with (
        patch("shutil.which", side_effect=lambda cmd: "/bin/codex" if cmd == "codex" else None),
        patch("subprocess.run") as mock_run,
    ):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(
            {
                "prediction": "met",
                "evidence": [{"criterion_id": "I-002", "doc_id": "D1", "quote": "Stage IV NSCLC"}],
                "rationale": "Codex matched NSCLC.",
                "confidence": 0.9,
                "human_review_required": False,
            }
        )
        mock_run.return_value = mock_proc

        judgment = judge.judge(mock_criterion, mock_evidence, mock_corpus)

        assert judgment.prediction == "met"
        assert "[Agent: Codex CLI (gpt-5.4-mini)]" in judgment.rationale

        called_args = mock_run.call_args[0][0]
        assert "codex" in called_args
        assert "exec" in called_args
        assert "gpt-5.4-mini" in called_args


def test_llm_judge_no_codex_raises_runtime_error(mock_criterion, mock_evidence, mock_corpus):
    judge = LLMJudge()

    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="Codex CLI not found"):
            judge.judge(mock_criterion, mock_evidence, mock_corpus)

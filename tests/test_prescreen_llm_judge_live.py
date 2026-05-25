"""Real integration/E2E tests for LLMJudge via Codex CLI.

These tests invoke the local Codex CLI agent.
They are skipped by default unless CLINIQUE_LIVE_LLM=1 is set in the environment.
"""

import os
import shutil

import pytest

from clinique.prescreen.judge import LLMJudge
from clinique.prescreen.schemas import Criterion, Evidence, PatientCorpus, PatientDocument

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("CLINIQUE_LIVE_LLM") != "1",
        reason="Set environment variable CLINIQUE_LIVE_LLM=1 to run live LLM integration tests",
    ),
]


@pytest.fixture
def sample_criterion():
    return Criterion(
        criterion_id="I-002",
        trial_id="NCT123",
        criterion_type="inclusion",
        raw_text="Must have ECOG performance status of 0 or 1",
        clinical_domain="status",
    )


@pytest.fixture
def sample_corpus():
    return PatientCorpus(
        patient_id="P_LIVE_001",
        snapshot_date="2026-05-24",
        source="synthea",
        documents=(
            PatientDocument(
                doc_id="D_LIVE_01",
                patient_id="P_LIVE_001",
                date="2026-05-20",
                source_type="observation",
                text="The patient has an ECOG performance status of 1 (fully active).",
            ),
        ),
    )


@pytest.fixture
def sample_evidence():
    return [
        Evidence(
            criterion_id="I-002",
            doc_id="D_LIVE_01",
            quote="ECOG performance status of 1",
        )
    ]


def test_live_agent_diagnostics_match():
    """Verify that troubleshoot-agents / codex_available finds Codex CLI."""
    if not shutil.which("codex"):
        pytest.skip("Codex CLI is not installed on this system.")

    from clinique.prescreen.judge import codex_available

    assert codex_available() is True


def test_live_codex_cli(sample_criterion, sample_evidence, sample_corpus):
    """Test the real Codex CLI (gpt-5.4-mini) channel."""
    if not shutil.which("codex"):
        pytest.skip("Codex CLI is not installed on this system.")

    judge = LLMJudge()
    prompt = judge._build_prompt(sample_criterion, sample_evidence, sample_corpus)
    judgment = judge._call_codex_cli(sample_criterion, prompt)

    assert judgment is not None
    assert judgment.prediction in ("met", "not_met", "unknown")
    assert "[Agent: Codex CLI (gpt-5.4-mini)]" in judgment.rationale
    assert judgment.confidence is not None


def test_live_full_judge_execution(sample_criterion, sample_evidence, sample_corpus):
    """Test the top-level LLMJudge.judge() method with Codex CLI."""
    if not shutil.which("codex"):
        pytest.skip("Codex CLI is not installed on this system.")

    judge = LLMJudge()
    judgment = judge.judge(sample_criterion, sample_evidence, sample_corpus)

    assert judgment is not None
    assert judgment.prediction in ("met", "not_met", "unknown")
    assert "[Agent: Codex CLI (gpt-5.4-mini)]" in judgment.rationale

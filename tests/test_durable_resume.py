"""Tests for Temporal workflow resume and LLM judge failure handling."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("temporalio")

from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.activities.prescreen import judge_criterion
from clinique.durable.converter import DATA_CONVERTER
from clinique.durable.models import (
    CriterionJudgmentModel,
    CriterionModel,
    EvidenceModel,
    PatientCorpusModel,
    ScreenPatientInput,
    TrialModel,
)
from clinique.durable.workflows import ALL_WORKFLOWS
from clinique.durable.workflows.prescreen import ScreenPatientWorkflow
from clinique.prescreen.atomizer import ReferenceAtomizer
from durable_e2e_harness import run_with_worker


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_judge_criterion_activity_raises_retryable_on_llm_failure(
    trial_and_corpus,
):
    """Test that judge_criterion activity raises a retryable ApplicationError on LLM failure."""
    trial, corpus = trial_and_corpus
    criteria = ReferenceAtomizer().atomize(trial)
    crit_model = CriterionModel.from_domain(criteria[0])
    corp_model = PatientCorpusModel.from_domain(corpus)

    # Mock LLMJudge to return a judgment that failed fallback (Agent: None)
    mock_judgment = MagicMock()
    mock_judgment.rationale = "LLM judgment failed via Codex CLI. [Agent: None]"
    mock_judgment.prediction = "unknown"
    mock_judgment.criterion_id = crit_model.criterion_id
    mock_judgment.criterion_type = crit_model.criterion_type
    mock_judgment.evidence = ()
    mock_judgment.confidence = 0.0
    mock_judgment.human_review_required = True

    with patch("clinique.prescreen.judge.LLMJudge.judge", return_value=mock_judgment):
        with pytest.raises(ApplicationError, match="LLM Judge failed via Codex CLI"):
            judge_criterion(crit_model, [], corp_model, judge_type="llm")


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_workflow_fails_on_persistent_llm_failure(trial_and_corpus):
    """Test that ScreenPatientWorkflow fails when LLM judge has persistent failures."""
    trial, corpus = trial_and_corpus

    @activity.defn(name="judge_criterion")
    def failing_evaluate(
        criterion: CriterionModel,
        evidence: list[EvidenceModel],
        corpus_model: PatientCorpusModel,
        judge_type: str = "rule",
    ) -> CriterionJudgmentModel:
        raise ApplicationError("Simulated LLM key/connection failure", non_retryable=False)

    from clinique.durable.activities.prescreen import judge_criterion as real_judge_activity

    activities = [a for a in ALL_ACTIVITIES if a is not real_judge_activity] + [failing_evaluate]

    async with await WorkflowEnvironment.start_time_skipping(data_converter=DATA_CONVERTER) as env:

        async def run(client, task_queue):
            payload = ScreenPatientInput(
                trial=TrialModel.from_domain(trial),
                corpus=PatientCorpusModel.from_domain(corpus),
                judge="llm",
            )
            with pytest.raises(WorkflowFailureError):
                await client.execute_workflow(
                    ScreenPatientWorkflow.run,
                    payload,
                    id=f"test-fail-{uuid.uuid4()}",
                    task_queue=task_queue,
                )

        await run_with_worker(env.client, ALL_WORKFLOWS, activities, run)


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_resume_cli_command():
    """Test that CLI resume subcommand describes workflow and calls temporal CLI reset."""
    from clinique.cli.parser import build_parser
    from clinique.cli.prescreen import handle_prescreen

    parser = build_parser()
    args = parser.parse_args(
        [
            "prescreen",
            "resume",
            "--workflow-id",
            "test-wf-123",
            "--host",
            "localhost:7233",
        ]
    )

    # Mock temporalio Client
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_desc = MagicMock()
    mock_desc.status.name = "FAILED"

    # We want handle.result() to return a real PrescreeningPacketModel
    from clinique.durable.models import PrescreeningPacketModel

    mock_packet = PrescreeningPacketModel(
        trial_id="T1",
        patient_id="P1",
        recommendation="needs_review",
    )

    async def mock_describe():
        return mock_desc

    async def mock_result():
        return mock_packet

    mock_handle.describe = mock_describe
    mock_handle.result = mock_result
    mock_client.get_workflow_handle.return_value = mock_handle

    async def mock_connect(host, data_converter):
        return mock_client

    with (
        patch("temporalio.client.Client.connect", side_effect=mock_connect),
        patch("shutil.which", return_value="/usr/local/bin/temporal"),
        patch("subprocess.run") as mock_subrun,
    ):
        mock_subrun.return_value.returncode = 0
        mock_subrun.return_value.stdout = "Reset run ID: abc-123"

        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            loop = asyncio.get_running_loop()
            code = await loop.run_in_executor(executor, handle_prescreen, args)
        assert code == 0
        assert mock_subrun.called
        called_args = mock_subrun.call_args[0][0]
        assert "temporal" in called_args
        assert "reset" in called_args
        assert "test-wf-123" in called_args
        assert "LastWorkflowTask" in called_args

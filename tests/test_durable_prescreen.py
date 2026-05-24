"""Temporal durable prescreen workflow tests (embedded WorkflowEnvironment)."""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("temporalio")

from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.activities.prescreen import (
    assert_evidence_provenance_activity as gate_activity,
)
from clinique.durable.activities.prescreen import (
    atomize_trial,
    evaluate_criterion,
)
from clinique.durable.converter import DATA_CONVERTER
from clinique.durable.models import (
    CriterionModel,
    PatientCorpusModel,
    PrescreeningPacketModel,
    ScreenPatientInput,
    TrialModel,
)
from clinique.durable.workflows import ALL_WORKFLOWS
from clinique.durable.workflows.prescreen import ScreenPatientWorkflow
from clinique.prescreen.orchestrator import PrescreenOrchestrator, packet_fingerprint
from durable_e2e_harness import run_with_worker


def _screen_input(trial, corpus) -> ScreenPatientInput:
    return ScreenPatientInput(
        trial=TrialModel.from_domain(trial),
        corpus=PatientCorpusModel.from_domain(corpus),
    )


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_screen_workflow_matches_sync_orchestrator(trial_and_corpus):
    trial, corpus = trial_and_corpus
    sync_packet = PrescreenOrchestrator().screen(trial, corpus)
    async with await WorkflowEnvironment.start_local(data_converter=DATA_CONVERTER) as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                ScreenPatientWorkflow.run,
                _screen_input(trial, corpus),
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )

        result = await run_with_worker(env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run)
    assert isinstance(result, PrescreeningPacketModel)
    assert packet_fingerprint(result.to_domain()) == packet_fingerprint(sync_packet)


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_temporal_screen_surfaces_condition_evidence(trial_and_corpus):
    """Copilot Phase 10: Temporal path surfaces NSCLC evidence on I-002."""
    trial, corpus = trial_and_corpus
    async with await WorkflowEnvironment.start_local(data_converter=DATA_CONVERTER) as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                ScreenPatientWorkflow.run,
                _screen_input(trial, corpus),
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )

        packet = await run_with_worker(env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run)
    i002 = next(j for j in packet.to_domain().judgments if j.criterion_id == "I-002")
    assert i002.prediction == "unknown"
    assert i002.evidence
    assert any("lung cancer" in ev.quote.lower() for ev in i002.evidence)


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_screen_workflow_is_deterministic(trial_and_corpus):
    trial, corpus = trial_and_corpus
    payload = _screen_input(trial, corpus)
    async with await WorkflowEnvironment.start_local(data_converter=DATA_CONVERTER) as env:

        async def run(client, task_queue):
            first = await client.execute_workflow(
                ScreenPatientWorkflow.run,
                payload,
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )
            second = await client.execute_workflow(
                ScreenPatientWorkflow.run,
                payload,
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )
            return first, second

        first, second = await run_with_worker(env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run)
    assert packet_fingerprint(first.to_domain()) == packet_fingerprint(second.to_domain())


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_evidence_gate_failure_is_non_retryable(trial_and_corpus):
    trial, corpus = trial_and_corpus

    @activity.defn(name="assert_evidence_provenance_activity")
    async def failing_gate(_packet: PrescreeningPacketModel, _corpus: PatientCorpusModel) -> None:
        raise ApplicationError("gate failed", type="EvidenceProvenanceError", non_retryable=True)

    activities = [a for a in ALL_ACTIVITIES if a is not gate_activity] + [failing_gate]
    async with await WorkflowEnvironment.start_local(data_converter=DATA_CONVERTER) as env:

        async def run(client, task_queue):
            with pytest.raises(WorkflowFailureError):
                await client.execute_workflow(
                    ScreenPatientWorkflow.run,
                    _screen_input(trial, corpus),
                    id=str(uuid.uuid4()),
                    task_queue=task_queue,
                )

        await run_with_worker(env.client, [ScreenPatientWorkflow], activities, run)


@pytest.mark.temporal
def test_atomize_activity_offline(trial_and_corpus):
    trial, _ = trial_and_corpus
    criteria = ActivityEnvironment().run(atomize_trial, TrialModel.from_domain(trial))
    assert criteria
    assert all(isinstance(c, CriterionModel) for c in criteria)


@pytest.mark.temporal
def test_evaluate_criterion_activity_offline(trial_and_corpus):
    trial, corpus = trial_and_corpus
    env = ActivityEnvironment()
    criteria = env.run(atomize_trial, TrialModel.from_domain(trial))
    judgment = env.run(
        evaluate_criterion,
        criteria[0],
        PatientCorpusModel.from_domain(corpus),
    )
    assert judgment.criterion_id == criteria[0].criterion_id
    assert judgment.prediction in {
        "met",
        "not_met",
        "unknown",
        "not_applicable",
        "conflicting_evidence",
    }

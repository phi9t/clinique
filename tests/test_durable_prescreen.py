"""Temporal durable prescreen workflow tests."""

from __future__ import annotations

import concurrent.futures
import uuid
from pathlib import Path

import pytest

pytest.importorskip("temporalio")

from temporalio.client import WorkflowFailureError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.activities.prescreen import atomize_trial, evaluate_criterion
from clinique.durable.serde import corpus_to_dict, packet_from_dict, trial_to_dict
from clinique.durable.workflows import ALL_WORKFLOWS
from clinique.durable.workflows.prescreen import ScreenPatientInput, ScreenPatientWorkflow
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.orchestrator import PrescreenOrchestrator, packet_fingerprint

TRIALS = Path("tests/fixtures/prescreen/trials.jsonl")
SYNTHEA_CSV = Path("tests/fixtures/prescreen/synthea")


@pytest.fixture
def trial_and_corpus():
    trial = load_recorded_studies(TRIALS)[0]
    tables = read_synthea_csv_dir(SYNTHEA_CSV)
    corpus = normalize_synthea_corpus(tables, snapshot_date="2026-03-01")[0]
    return trial, corpus


async def _run_with_worker(client, workflows, activities, fn):
    task_queue = str(uuid.uuid4())
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as activity_executor:
        async with Worker(
            client,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            activity_executor=activity_executor,
        ):
            return await fn(client, task_queue)


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_screen_workflow_matches_sync_orchestrator(trial_and_corpus):
    trial, corpus = trial_and_corpus
    sync_packet = PrescreenOrchestrator().screen(trial, corpus)
    async with await WorkflowEnvironment.start_local() as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                ScreenPatientWorkflow.run,
                ScreenPatientInput(trial=trial_to_dict(trial), corpus=corpus_to_dict(corpus)),
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )

        result = await _run_with_worker(
            env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run
        )
    assert packet_fingerprint(packet_from_dict(result)) == packet_fingerprint(sync_packet)


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_screen_workflow_is_deterministic(trial_and_corpus):
    trial, corpus = trial_and_corpus
    payload = ScreenPatientInput(trial=trial_to_dict(trial), corpus=corpus_to_dict(corpus))
    async with await WorkflowEnvironment.start_local() as env:

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

        first, second = await _run_with_worker(
            env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run
        )
    assert packet_fingerprint(packet_from_dict(first)) == packet_fingerprint(
        packet_from_dict(second)
    )


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_evidence_gate_failure_is_non_retryable(trial_and_corpus):
    from temporalio import activity
    from temporalio.exceptions import ApplicationError

    trial, corpus = trial_and_corpus

    @activity.defn(name="assert_evidence_provenance_activity")
    async def failing_gate(_packet: dict, _corpus: dict) -> None:
        raise ApplicationError("gate failed", type="EvidenceProvenanceError", non_retryable=True)

    from clinique.durable.activities.prescreen import (
        assert_evidence_provenance_activity as gate_activity,
    )

    activities = [a for a in ALL_ACTIVITIES if a is not gate_activity] + [failing_gate]

    async with await WorkflowEnvironment.start_local() as env:

        async def run(client, task_queue):
            with pytest.raises(WorkflowFailureError):
                await client.execute_workflow(
                    ScreenPatientWorkflow.run,
                    ScreenPatientInput(
                        trial=trial_to_dict(trial), corpus=corpus_to_dict(corpus)
                    ),
                    id=str(uuid.uuid4()),
                    task_queue=task_queue,
                )

        await _run_with_worker(env.client, [ScreenPatientWorkflow], activities, run)


@pytest.mark.temporal
def test_atomize_activity_offline(trial_and_corpus):
    trial, _ = trial_and_corpus
    env = ActivityEnvironment()
    criteria = env.run(atomize_trial, trial_to_dict(trial))
    assert criteria
    assert all("criterion_id" in c for c in criteria)


@pytest.mark.temporal
def test_evaluate_criterion_activity_offline(trial_and_corpus):
    trial, corpus = trial_and_corpus
    env = ActivityEnvironment()
    criteria = env.run(atomize_trial, trial_to_dict(trial))
    judgment = env.run(evaluate_criterion, criteria[0], corpus_to_dict(corpus))
    assert judgment["criterion_id"] == criteria[0]["criterion_id"]
    assert judgment["prediction"] in {
        "met",
        "not_met",
        "unknown",
        "not_applicable",
        "conflicting_evidence",
    }

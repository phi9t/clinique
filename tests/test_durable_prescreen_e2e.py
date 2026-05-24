"""Real Temporal dev-server E2E and failure-injection tests."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest

pytest.importorskip("temporalio")

from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.activities.prescreen import (
    assert_evidence_provenance_activity as gate_activity,
)
from clinique.durable.activities.prescreen import (
    atomize_trial,
)
from clinique.durable.client import connect_client, execute_batch_eval, execute_screen
from clinique.durable.config import DEFAULT_HOST
from clinique.durable.serde import corpus_to_dict, packet_from_dict, trial_to_dict
from clinique.durable.workflows import ALL_WORKFLOWS
from clinique.durable.workflows.eval import BatchEvalInput, BatchEvalWorkflow
from clinique.durable.workflows.prescreen import ScreenPatientInput, ScreenPatientWorkflow
from clinique.prescreen.orchestrator import PrescreenOrchestrator, packet_fingerprint
from clinique.substrate.provenance import ProvenanceLedger
from durable_e2e_harness import port_open, prescreen_worker, run_with_worker, temporal_dev_server

TRIALS = Path("tests/fixtures/prescreen/trials.jsonl")
CASES = Path(".workstream/prescreen-copilot/l0_cases.jsonl")


def _require_temporal_cli() -> None:
    if not shutil.which("temporal") and not port_open():
        pytest.skip("Temporal CLI not available and no server on :7233")


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_transient_activity_failure_retries_then_succeeds(trial_and_corpus):
    trial, corpus = trial_and_corpus
    calls = {"n": 0}

    @activity.defn(name="atomize_trial")
    def flaky_atomize(trial_dict: dict) -> list[dict]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ApplicationError("transient atomize failure", non_retryable=False)
        return atomize_trial(trial_dict)

    activities = [a for a in ALL_ACTIVITIES if a is not atomize_trial] + [flaky_atomize]
    async with await WorkflowEnvironment.start_local() as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                ScreenPatientWorkflow.run,
                ScreenPatientInput(trial=trial_to_dict(trial), corpus=corpus_to_dict(corpus)),
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )

        result = await run_with_worker(env.client, [ScreenPatientWorkflow], activities, run)
    assert calls["n"] == 3
    assert result["recommendation"] in {
        "likely_ineligible",
        "needs_review",
        "potentially_eligible",
    }


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_batch_eval_collects_missing_patient_errors(tmp_path, synthea_patients_jsonl):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "trial_id": "NCT02578680",
                "patient_id": "P1",
                "snapshot_date": "2026-03-01",
                "patient_source": "synthea",
                "gold_judgments": [{"criterion_id": "I-001", "prediction": "met"}],
            }
        )
        + "\n"
        + json.dumps(
            {
                "trial_id": "NCT02578680",
                "patient_id": "MISSING",
                "snapshot_date": "2026-03-01",
                "patient_source": "synthea",
                "gold_judgments": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    async with await WorkflowEnvironment.start_local() as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                BatchEvalWorkflow.run,
                BatchEvalInput(
                    cases_path=str(cases_path),
                    trials_path=str(TRIALS),
                    synthea_patients_path=str(synthea_patients_jsonl),
                    reports_dir=str(tmp_path / "reports"),
                ),
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )

        report = await run_with_worker(env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run)
    assert report["cases_run"] == 1
    assert report["errors"]


@pytest.mark.temporal
@pytest.mark.temporal_e2e
@pytest.mark.asyncio
async def test_real_dev_server_screen_workflow(trial_and_corpus):
    _require_temporal_cli()
    trial, corpus = trial_and_corpus
    sync_packet = PrescreenOrchestrator().screen(trial, corpus)
    with temporal_dev_server():
        with prescreen_worker():
            client = await connect_client(DEFAULT_HOST)
            result = await execute_screen(
                client,
                trial=trial_to_dict(trial),
                corpus=corpus_to_dict(corpus),
                workflow_id=f"e2e-screen/{uuid.uuid4()}",
            )
    assert packet_fingerprint(packet_from_dict(result)) == packet_fingerprint(sync_packet)


@pytest.mark.temporal
@pytest.mark.temporal_e2e
@pytest.mark.asyncio
async def test_real_dev_server_screen_with_ledger(tmp_path, trial_and_corpus):
    _require_temporal_cli()
    trial, corpus = trial_and_corpus
    ledger_path = tmp_path / "prescreen-ledger.jsonl"
    with temporal_dev_server():
        with prescreen_worker():
            client = await connect_client(DEFAULT_HOST)
            result = await execute_screen(
                client,
                trial=trial_to_dict(trial),
                corpus=corpus_to_dict(corpus),
                append_ledger=True,
                ledger_path=str(ledger_path),
                workflow_id=f"e2e-ledger/{uuid.uuid4()}",
            )
    assert result["recommendation"]
    records = ProvenanceLedger(ledger_path).all()
    assert len(records) == 1
    assert records[0]["capability"] == "prescreen"


@pytest.mark.temporal
@pytest.mark.temporal_e2e
@pytest.mark.asyncio
async def test_real_dev_server_batch_eval(tmp_path, synthea_patients_jsonl):
    if not CASES.is_file():
        pytest.skip("workstream l0_cases.jsonl not present")
    _require_temporal_cli()
    with temporal_dev_server():
        with prescreen_worker():
            client = await connect_client(DEFAULT_HOST)
            report = await execute_batch_eval(
                client,
                BatchEvalInput(
                    cases_path=str(CASES),
                    trials_path=str(TRIALS),
                    synthea_patients_path=str(synthea_patients_jsonl),
                    reports_dir=str(tmp_path / "reports"),
                ),
                workflow_id=f"e2e-batch/{uuid.uuid4()}",
            )
    assert report["cases_run"] >= 1
    assert report.get("errors")
    assert (tmp_path / "reports" / "l0-eval-temporal.json").is_file()


@pytest.mark.temporal
@pytest.mark.temporal_e2e
@pytest.mark.asyncio
async def test_real_dev_server_gate_failure_non_retryable(trial_and_corpus):
    _require_temporal_cli()
    trial, corpus = trial_and_corpus
    task_queue = f"prescreen-e2e-fail-{uuid.uuid4().hex[:8]}"

    @activity.defn(name="assert_evidence_provenance_activity")
    async def failing_gate(_packet: dict, _corpus: dict) -> None:
        raise ApplicationError(
            "injected gate failure",
            type="EvidenceProvenanceError",
            non_retryable=True,
        )

    activities = [a for a in ALL_ACTIVITIES if a is not gate_activity] + [failing_gate]
    with temporal_dev_server():
        client = await connect_client(DEFAULT_HOST)

        async def run(c, tq):
            with pytest.raises(WorkflowFailureError):
                await c.execute_workflow(
                    ScreenPatientWorkflow.run,
                    ScreenPatientInput(
                        trial=trial_to_dict(trial), corpus=corpus_to_dict(corpus)
                    ),
                    id=f"e2e-gate-fail/{uuid.uuid4()}",
                    task_queue=tq,
                )

        await run_with_worker(
            client,
            [ScreenPatientWorkflow],
            activities,
            run,
            task_queue=task_queue,
        )

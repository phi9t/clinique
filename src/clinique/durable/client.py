"""Temporal client helpers for prescreen workflows."""

from __future__ import annotations

import uuid

from temporalio.client import Client

from clinique.durable.config import DEFAULT_HOST, PRESCREEN_TASK_QUEUE
from clinique.durable.converter import DATA_CONVERTER
from clinique.durable.models import (
    BatchEvalInput,
    PatientCorpusModel,
    PrescreeningPacketModel,
    ScreenPatientInput,
    TrialModel,
)
from clinique.durable.workflows.eval import BatchEvalWorkflow
from clinique.durable.workflows.prescreen import ScreenPatientWorkflow, screen_workflow_id


async def connect_client(host: str = DEFAULT_HOST) -> Client:
    return await Client.connect(host, data_converter=DATA_CONVERTER)


async def execute_screen(
    client: Client,
    *,
    trial: TrialModel,
    corpus: PatientCorpusModel,
    append_ledger: bool = False,
    ledger_path: str | None = None,
    workflow_id: str | None = None,
) -> PrescreeningPacketModel:
    payload = ScreenPatientInput(
        trial=trial,
        corpus=corpus,
        append_ledger=append_ledger,
        ledger_path=ledger_path,
    )
    wf_id = workflow_id or screen_workflow_id(
        trial.trial_id,
        corpus.patient_id,
        corpus.snapshot_date,
    )
    return await client.execute_workflow(
        ScreenPatientWorkflow.run,
        payload,
        id=wf_id,
        task_queue=PRESCREEN_TASK_QUEUE,
    )


async def execute_batch_eval(
    client: Client,
    payload: BatchEvalInput,
    *,
    workflow_id: str | None = None,
) -> dict:
    wf_id = workflow_id or f"batch-eval/{uuid.uuid4()}"
    report = await client.execute_workflow(
        BatchEvalWorkflow.run,
        payload,
        id=wf_id,
        task_queue=PRESCREEN_TASK_QUEUE,
    )
    return report.model_dump()

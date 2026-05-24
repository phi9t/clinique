"""Temporal client helpers for prescreen workflows."""

from __future__ import annotations

import uuid
from typing import Any

from temporalio.client import Client

from clinique.durable.config import DEFAULT_HOST, PRESCREEN_TASK_QUEUE
from clinique.durable.workflows.eval import BatchEvalInput, BatchEvalWorkflow
from clinique.durable.workflows.prescreen import (
    ScreenPatientInput,
    ScreenPatientWorkflow,
    screen_workflow_id,
)


async def connect_client(host: str = DEFAULT_HOST) -> Client:
    return await Client.connect(host)


async def execute_screen(
    client: Client,
    *,
    trial: dict[str, Any],
    corpus: dict[str, Any],
    append_ledger: bool = False,
    ledger_path: str | None = None,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    payload = ScreenPatientInput(
        trial=trial,
        corpus=corpus,
        append_ledger=append_ledger,
        ledger_path=ledger_path,
    )
    wf_id = workflow_id or screen_workflow_id(
        trial["trial_id"],
        corpus["patient_id"],
        corpus.get("snapshot_date"),
    )
    return await client.execute_workflow(
        ScreenPatientWorkflow.run,
        payload,
        id=wf_id,
        task_queue=PRESCREEN_TASK_QUEUE,
    )


async def execute_batch_eval(
    client: Client,
    payload: BatchEvalInput | dict[str, Any],
    *,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    wf_id = workflow_id or f"batch-eval/{uuid.uuid4()}"
    return await client.execute_workflow(
        BatchEvalWorkflow.run,
        payload,
        id=wf_id,
        task_queue=PRESCREEN_TASK_QUEUE,
    )

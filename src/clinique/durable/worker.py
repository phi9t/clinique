"""Temporal worker entrypoint for prescreen durable execution."""

from __future__ import annotations

import asyncio
import concurrent.futures
import os

from temporalio.client import Client
from temporalio.worker import Worker

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.config import DEFAULT_HOST, PRESCREEN_TASK_QUEUE, prescreen_task_queue
from clinique.durable.converter import DATA_CONVERTER
from clinique.durable.workflows import ALL_WORKFLOWS


async def run_worker(*, host: str = DEFAULT_HOST, task_queue: str = PRESCREEN_TASK_QUEUE) -> None:
    client = await Client.connect(host, data_converter=DATA_CONVERTER)
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=ALL_WORKFLOWS,
            activities=ALL_ACTIVITIES,
            activity_executor=activity_executor,
        )
        await worker.run()


def main() -> None:
    host = os.environ.get("CLINIQUE_DURABLE_HOST", DEFAULT_HOST)
    task_queue = prescreen_task_queue()
    asyncio.run(run_worker(host=host, task_queue=task_queue))


if __name__ == "__main__":
    main()

"""Temporal worker entrypoint for prescreen durable execution."""

from __future__ import annotations

import asyncio
import concurrent.futures

from temporalio.client import Client
from temporalio.worker import Worker

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.config import DEFAULT_HOST, PRESCREEN_TASK_QUEUE
from clinique.durable.workflows import ALL_WORKFLOWS


async def run_worker(*, host: str = DEFAULT_HOST, task_queue: str = PRESCREEN_TASK_QUEUE) -> None:
    client = await Client.connect(host)
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
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

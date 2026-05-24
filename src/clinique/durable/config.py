"""Temporal local-dev defaults for prescreen workflows."""

from __future__ import annotations

import os
from datetime import timedelta

DEFAULT_HOST = "localhost:7233"
PRESCREEN_TASK_QUEUE = "prescreen"


def prescreen_task_queue() -> str:
    """Task queue name; override in tests via CLINIQUE_DURABLE_TASK_QUEUE."""
    return os.environ.get("CLINIQUE_DURABLE_TASK_QUEUE", PRESCREEN_TASK_QUEUE)


ACTIVITY_TIMEOUT = timedelta(seconds=60)
GATE_TIMEOUT = timedelta(seconds=30)
LEDGER_TIMEOUT = timedelta(seconds=30)

ACTIVITY_RETRY_MAX = 3
LEDGER_RETRY_MAX = 2
GATE_RETRY_MAX = 1

BATCH_EVAL_CONCURRENCY = 10

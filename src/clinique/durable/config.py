"""Temporal local-dev defaults for prescreen workflows."""

from __future__ import annotations

from datetime import timedelta

DEFAULT_HOST = "localhost:7233"
PRESCREEN_TASK_QUEUE = "prescreen"

ACTIVITY_TIMEOUT = timedelta(seconds=60)
GATE_TIMEOUT = timedelta(seconds=30)
LEDGER_TIMEOUT = timedelta(seconds=30)

ACTIVITY_RETRY_MAX = 3
LEDGER_RETRY_MAX = 2
GATE_RETRY_MAX = 1

BATCH_EVAL_CONCURRENCY = 10

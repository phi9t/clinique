"""Harness for prescreen durable E2E against a real Temporal dev server."""

from __future__ import annotations

import concurrent.futures
import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from temporalio.worker import Worker

from clinique.durable.config import DEFAULT_HOST

_TEMPORAL_UNAVAILABLE = "Temporal CLI not available and no server on :7233"


def skip_or_fail(reason: str) -> None:
    """Skip in ad-hoc runs; fail when CLINIQUE_REQUIRE_TEMPORAL=1 (pre-commit / CI strict)."""
    if os.environ.get("CLINIQUE_REQUIRE_TEMPORAL") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def temporal_available() -> bool:
    return bool(shutil.which("temporal")) or port_open()


def _host_port(host: str = DEFAULT_HOST) -> tuple[str, int]:
    if ":" in host:
        h, p = host.rsplit(":", 1)
        return h, int(p)
    return host, 7233


def port_open(host: str = DEFAULT_HOST, timeout: float = 1.0) -> bool:
    h, p = _host_port(host)
    try:
        with socket.create_connection((h, p), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str = DEFAULT_HOST, *, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_open(host, timeout=0.5):
            return
        time.sleep(0.25)
    raise TimeoutError(f"Temporal server not reachable at {host} after {timeout}s")


@contextlib.contextmanager
def temporal_dev_server(*, log_dir: Path | None = None) -> Iterator[subprocess.Popen[str] | None]:
    """Start `temporal server start-dev` when nothing listens on the gRPC port."""
    if port_open():
        yield None
        return
    if not shutil.which("temporal"):
        skip_or_fail(_TEMPORAL_UNAVAILABLE)
    log_dir = log_dir or Path("/tmp/clinique-temporal-e2e")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "temporal-dev.log"
    with log_path.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(  # noqa: S603
            ["temporal", "server", "start-dev", "--ip", "127.0.0.1"],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    try:
        wait_for_port()
        yield proc
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


@contextlib.contextmanager
def prescreen_worker(*, host: str = DEFAULT_HOST) -> Iterator[subprocess.Popen[str]]:
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["CLINIQUE_DURABLE_HOST"] = host
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "clinique.durable.worker"],
        cwd=repo,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(2.0)
        if proc.poll() is not None:
            raise RuntimeError("prescreen worker exited before becoming ready")
        yield proc
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()


async def run_with_worker(
    client: Any,
    workflows: list[Any],
    activities: list[Any],
    fn: Callable[[Any, str], Awaitable[Any]],
    *,
    task_queue: str | None = None,
) -> Any:
    tq = task_queue or str(uuid.uuid4())
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as activity_executor:
        async with Worker(
            client,
            task_queue=tq,
            workflows=workflows,
            activities=activities,
            activity_executor=activity_executor,
        ):
            return await fn(client, tq)

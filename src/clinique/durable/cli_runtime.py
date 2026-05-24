"""Shared Temporal CLI helpers for prescreen commands."""

from __future__ import annotations

import sys

from clinique.durable._import_guard import TEMPORAL_INSTALL_HINT, require_temporalio
from clinique.durable.converter import DATA_CONVERTER


def temporal_import_error(exc: ImportError) -> int:
    print(f"prescreen temporal: {exc}", file=sys.stderr)
    return 2


def ensure_temporalio() -> None:
    require_temporalio()


async def connect_client(host: str):
    from temporalio.client import Client

    ensure_temporalio()
    try:
        return await Client.connect(host, data_converter=DATA_CONVERTER)
    except ImportError as exc:
        raise ImportError(TEMPORAL_INSTALL_HINT) from exc

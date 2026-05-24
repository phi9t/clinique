"""Append-only provenance ledger (RFC-0000 §5).

The ledger is the audit trail. It is append-only *by design*: there is no update or delete API.
Each record is one JSON object per line (JSONL).
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HumanReview:
    required: bool = True
    role: str = "biostatistician"
    status: str = "pending"  # pending | approved | rejected
    reviewer: str | None = None
    at: str | None = None


@dataclass
class LedgerRecord:
    capability: str
    inputs: list[str] = field(default_factory=list)
    model: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, str]] = field(default_factory=list)
    prompt_hash: str | None = None
    output_ref: str | None = None
    human_review: HumanReview = field(default_factory=HumanReview)
    record_id: str = ""
    produced_at: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class ProvenanceLedger:
    """JSONL append-only ledger. No update/delete by design."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: LedgerRecord) -> str:
        if not record.record_id:
            record.record_id = str(uuid.uuid4())
        if not record.produced_at:
            record.produced_at = _utc_now()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(record.to_json() + "\n")
        return record.record_id

    def all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self.all())

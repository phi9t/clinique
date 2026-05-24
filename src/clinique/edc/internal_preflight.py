from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_SOURCES = ("edc_snapshots", "query_logs", "edit_check_history")


@dataclass(frozen=True)
class InternalPreflightResult:
    ok: bool
    present_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    duplicate_sources: tuple[str, ...]
    unblinded_sources: tuple[str, ...]
    non_read_only_sources: tuple[str, ...]
    incomplete_sources: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "present_sources": list(self.present_sources),
            "missing_required_sources": list(self.missing_required_sources),
            "duplicate_sources": list(self.duplicate_sources),
            "unblinded_sources": list(self.unblinded_sources),
            "non_read_only_sources": list(self.non_read_only_sources),
            "incomplete_sources": list(self.incomplete_sources),
        }


def preflight_internal_manifest(path: str | Path) -> InternalPreflightResult:
    with Path(path).open() as handle:
        manifest = json.load(handle)
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("manifest sources must be a list")

    present: list[str] = []
    seen: set[str] = set()
    duplicate: list[str] = []
    unblinded: list[str] = []
    non_read_only: list[str] = []
    incomplete: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("each manifest source must be an object")
        source_type = str(source.get("source_type", ""))
        if not source_type:
            raise ValueError("each manifest source requires source_type")
        present.append(source_type)
        if source_type in seen and source_type not in duplicate:
            duplicate.append(source_type)
        seen.add(source_type)
        if source.get("blinding_status") == "unblinded":
            unblinded.append(source_type)
        if source.get("read_only") is not True:
            non_read_only.append(source_type)
        if not _source_complete(source):
            incomplete.append(source_type)

    missing = tuple(source for source in REQUIRED_SOURCES if source not in set(present))
    ok = not missing and not duplicate and not unblinded and not non_read_only and not incomplete
    return InternalPreflightResult(
        ok=ok,
        present_sources=tuple(sorted(set(present))),
        missing_required_sources=missing,
        duplicate_sources=tuple(duplicate),
        unblinded_sources=tuple(unblinded),
        non_read_only_sources=tuple(non_read_only),
        incomplete_sources=tuple(incomplete),
    )


def _source_complete(source: dict[str, Any]) -> bool:
    required_keys = {
        "source_type",
        "owner",
        "export_path",
        "schema_sketch",
        "date_coverage",
        "sensitivity",
        "blinding_status",
        "read_only",
    }
    if any(not source.get(key) for key in required_keys):
        return False
    return isinstance(source.get("schema_sketch"), list) and bool(source["schema_sketch"])

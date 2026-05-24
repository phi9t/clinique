from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


SUPPORTED_MANIFEST_VERSION = "1"
REQUIRED_SOURCES = ("edc_snapshots", "query_logs", "edit_check_history")
ALLOWED_SOURCES = set(REQUIRED_SOURCES)
ALLOWED_SENSITIVITY = {"phi", "pii", "no_phi"}
ALLOWED_BLINDING_STATUS = {"blinded"}


@dataclass(frozen=True)
class InternalPreflightResult:
    ok: bool
    present_sources: tuple[str, ...]
    missing_required_sources: tuple[str, ...]
    duplicate_sources: tuple[str, ...]
    unknown_sources: tuple[str, ...]
    unblinded_sources: tuple[str, ...]
    non_read_only_sources: tuple[str, ...]
    incomplete_sources: tuple[str, ...]
    invalid_metadata: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "present_sources": list(self.present_sources),
            "missing_required_sources": list(self.missing_required_sources),
            "duplicate_sources": list(self.duplicate_sources),
            "unknown_sources": list(self.unknown_sources),
            "unblinded_sources": list(self.unblinded_sources),
            "non_read_only_sources": list(self.non_read_only_sources),
            "incomplete_sources": list(self.incomplete_sources),
            "invalid_metadata": list(self.invalid_metadata),
        }


def preflight_internal_manifest(path: str | Path) -> InternalPreflightResult:
    with Path(path).open() as handle:
        manifest = json.load(handle)
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("manifest sources must be a list")
    invalid_metadata = _invalid_manifest_metadata(manifest)

    present: list[str] = []
    seen: set[str] = set()
    duplicate: list[str] = []
    unknown: list[str] = []
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
        if source_type not in ALLOWED_SOURCES and source_type not in unknown:
            unknown.append(source_type)
        if source.get("blinding_status") == "unblinded":
            unblinded.append(source_type)
        if source.get("read_only") is not True:
            non_read_only.append(source_type)
        if not _source_complete(source):
            incomplete.append(source_type)

    missing = tuple(source for source in REQUIRED_SOURCES if source not in set(present))
    ok = (
        not missing
        and not duplicate
        and not unknown
        and not unblinded
        and not non_read_only
        and not incomplete
        and not invalid_metadata
    )
    return InternalPreflightResult(
        ok=ok,
        present_sources=tuple(sorted(set(present))),
        missing_required_sources=missing,
        duplicate_sources=tuple(duplicate),
        unknown_sources=tuple(unknown),
        unblinded_sources=tuple(unblinded),
        non_read_only_sources=tuple(non_read_only),
        incomplete_sources=tuple(incomplete),
        invalid_metadata=invalid_metadata,
    )


def _invalid_manifest_metadata(manifest: dict[str, Any]) -> tuple[str, ...]:
    invalid: list[str] = []
    if manifest.get("generated_at") is None or _parse_timestamp(manifest.get("generated_at")) is None:
        invalid.append("generated_at")
    if manifest.get("manifest_version") != SUPPORTED_MANIFEST_VERSION:
        invalid.append("manifest_version")
    return tuple(invalid)


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
    return (
        isinstance(source.get("schema_sketch"), list)
        and bool(source["schema_sketch"])
        and source.get("sensitivity") in ALLOWED_SENSITIVITY
        and source.get("blinding_status") in ALLOWED_BLINDING_STATUS
        and _date_coverage_complete(source.get("date_coverage"))
    )


def _date_coverage_complete(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    start = _parse_date(value.get("start"))
    end = _parse_date(value.get("end"))
    return start is not None and end is not None and start <= end


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

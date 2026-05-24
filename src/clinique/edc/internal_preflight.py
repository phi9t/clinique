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
REQUIRED_SCHEMA_FIELDS = {
    "edc_snapshots": {
        "snapshot_id",
        "snapshot_at",
        "contains_phi",
        "contains_unblinded",
        "record_id",
        "study_id",
        "site_id",
        "subject_id",
        "form",
        "field",
        "value",
        "collected_at",
    },
    "query_logs": {
        "query_id",
        "snapshot_id",
        "study_id",
        "site_id",
        "subject_id",
        "form",
        "field",
        "query_text",
        "query_category",
        "opened_at",
        "closed_at",
        "status",
        "resolution",
    },
    "edit_check_history": {
        "rule_id",
        "kind",
        "form",
        "field",
        "query_category",
        "message",
        "effective_at",
    },
}


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
    missing_schema_fields: dict[str, tuple[str, ...]]
    duplicate_schema_fields: dict[str, tuple[str, ...]]
    escaped_export_paths: tuple[str, ...]
    invalid_source_metadata: dict[str, tuple[str, ...]]
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
            "missing_schema_fields": {
                source_type: list(fields)
                for source_type, fields in self.missing_schema_fields.items()
            },
            "duplicate_schema_fields": {
                source_type: list(fields)
                for source_type, fields in self.duplicate_schema_fields.items()
            },
            "escaped_export_paths": list(self.escaped_export_paths),
            "invalid_source_metadata": {
                source_type: list(fields)
                for source_type, fields in self.invalid_source_metadata.items()
            },
            "invalid_metadata": list(self.invalid_metadata),
        }


def preflight_internal_manifest(path: str | Path) -> InternalPreflightResult:
    manifest_path = Path(path)
    with manifest_path.open() as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
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
    missing_schema_fields: dict[str, tuple[str, ...]] = {}
    duplicate_schema_fields: dict[str, tuple[str, ...]] = {}
    invalid_source_metadata: dict[str, tuple[str, ...]] = {}
    escaped_export_paths: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("each manifest source must be an object")
        source_type_value = source.get("source_type")
        if not isinstance(source_type_value, str) or not source_type_value.strip():
            raise ValueError("each manifest source requires source_type to be a nonblank string")
        source_type = source_type_value.strip()
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
        missing_fields = _missing_schema_fields(source.get("schema_sketch"), source_type)
        if missing_fields:
            missing_schema_fields[source_type] = missing_fields
        duplicate_fields = _duplicate_schema_fields(source.get("schema_sketch"), source_type)
        if duplicate_fields:
            duplicate_schema_fields[source_type] = duplicate_fields
        invalid_fields = _invalid_source_metadata(source)
        if invalid_fields:
            invalid_source_metadata[source_type] = invalid_fields
        if _relative_export_path_escapes_manifest_dir(
            source.get("export_path"),
            manifest_path.parent,
        ):
            escaped_export_paths.append(source_type)

    missing = tuple(source for source in REQUIRED_SOURCES if source not in set(present))
    ok = (
        not missing
        and not duplicate
        and not unknown
        and not unblinded
        and not non_read_only
        and not incomplete
        and not missing_schema_fields
        and not duplicate_schema_fields
        and not escaped_export_paths
        and not invalid_source_metadata
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
        missing_schema_fields=missing_schema_fields,
        duplicate_schema_fields=duplicate_schema_fields,
        escaped_export_paths=tuple(escaped_export_paths),
        invalid_source_metadata=invalid_source_metadata,
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
    if not all(
        _nonblank_string(source.get(key)) for key in ("source_type", "owner", "export_path")
    ):
        return False
    if not all(source.get(key) for key in ("schema_sketch", "date_coverage", "read_only")):
        return False
    return (
        _schema_sketch_complete(source.get("schema_sketch"), source.get("source_type"))
        and not _duplicate_schema_fields(source.get("schema_sketch"), source.get("source_type"))
        and source.get("sensitivity") in ALLOWED_SENSITIVITY
        and source.get("blinding_status") in ALLOWED_BLINDING_STATUS
        and _date_coverage_complete(source.get("date_coverage"))
    )


def _invalid_source_metadata(source: dict[str, Any]) -> tuple[str, ...]:
    invalid: list[str] = []
    if not _nonblank_string(source.get("owner")):
        invalid.append("owner")
    if not _nonblank_string(source.get("export_path")):
        invalid.append("export_path")
    if source.get("read_only") is not True:
        invalid.append("read_only")
    if source.get("sensitivity") not in ALLOWED_SENSITIVITY:
        invalid.append("sensitivity")
    if source.get("blinding_status") not in ALLOWED_BLINDING_STATUS:
        invalid.append("blinding_status")
    if not _date_coverage_complete(source.get("date_coverage")):
        invalid.append("date_coverage")
    return tuple(sorted(invalid))


def _nonblank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _schema_sketch_complete(value: Any, source_type: Any) -> bool:
    if not (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(field, str) and field.strip() for field in value)
    ):
        return False
    return not _missing_schema_fields(value, source_type)


def _missing_schema_fields(value: Any, source_type: Any) -> tuple[str, ...]:
    required = REQUIRED_SCHEMA_FIELDS.get(source_type)
    if required is None or not isinstance(value, list):
        return ()
    present = {field.strip() for field in value if isinstance(field, str)}
    return tuple(sorted(required - present))


def _duplicate_schema_fields(value: Any, source_type: Any) -> tuple[str, ...]:
    if source_type not in REQUIRED_SCHEMA_FIELDS or not isinstance(value, list):
        return ()
    seen: set[str] = set()
    duplicates: set[str] = set()
    for field in value:
        if not isinstance(field, str):
            continue
        normalized = field.strip()
        if not normalized:
            continue
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    return tuple(sorted(duplicates))


def _relative_export_path_escapes_manifest_dir(value: Any, root: Path) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    export_path = Path(value)
    if export_path.is_absolute():
        return False
    return not (root / export_path).resolve().is_relative_to(root.resolve())


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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed

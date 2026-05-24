from __future__ import annotations

import json
from pathlib import Path

from clinique.edc.internal_preflight import preflight_internal_manifest
from clinique.edc.records import (
    DatabaseLockIssue,
    EditCheckRule,
    EdcSnapshot,
    FixtureBundle,
    QueryLabel,
    QueryLog,
    validate_lock_issue_record_references,
    validate_snapshot_references,
    validate_unique_label_keys,
    validate_unique_lock_issue_ids,
    validate_unique_query_log_ids,
    validate_unique_rule_ids,
    validate_unique_snapshot_ids,
)


def load_internal_export_bundle(
    manifest_path: str | Path,
    *,
    labels_path: str | Path,
    lock_issues_path: str | Path | None = None,
) -> FixtureBundle:
    preflight = preflight_internal_manifest(manifest_path)
    if not preflight.ok:
        raise ValueError(_preflight_error_message(preflight))

    sources = _source_paths(manifest_path)
    snapshots_path = sources["edc_snapshots"] / "snapshots.json"
    query_logs_path = sources["query_logs"] / "query_logs.json"
    rules_path = sources["edit_check_history"] / "rules.json"
    labels_file = Path(labels_path)
    lock_issues_file = Path(lock_issues_path) if lock_issues_path is not None else None
    snapshots = tuple(
        sorted(
            _parse_payload_items(
                snapshots_path,
                EdcSnapshot.from_json,
            ),
            key=lambda snapshot: snapshot.snapshot_at,
        )
    )
    _validate_payload(snapshots_path, validate_unique_snapshot_ids, snapshots)
    for snapshot in snapshots:
        if snapshot.contains_unblinded:
            raise ValueError(
                f"invalid internal export payload: {snapshots_path}: "
                f"Snapshot {snapshot.snapshot_id} is marked as unblinded"
            )

    lock_issues = ()
    if lock_issues_file is not None:
        lock_issues = _parse_payload_items(
            lock_issues_file,
            DatabaseLockIssue.from_json,
        )
    if lock_issues_file is not None:
        _validate_payload(lock_issues_file, validate_unique_lock_issue_ids, lock_issues)
        _validate_payload(
            lock_issues_file,
            validate_lock_issue_record_references,
            snapshots,
            lock_issues,
        )

    labels = _parse_payload_items(labels_file, QueryLabel.from_json)
    _validate_payload(labels_file, validate_unique_label_keys, labels)
    query_logs = _parse_payload_items(
        query_logs_path,
        QueryLog.from_json,
    )
    _validate_payload(query_logs_path, validate_unique_query_log_ids, query_logs)
    _validate_payload(
        f"{labels_file}; {query_logs_path}",
        validate_snapshot_references,
        snapshots,
        labels,
        query_logs,
    )
    rules = _parse_payload_items(
        rules_path,
        EditCheckRule.from_json,
    )
    _validate_payload(rules_path, validate_unique_rule_ids, rules)

    return FixtureBundle(
        snapshots=snapshots,
        rules=rules,
        query_logs=query_logs,
        labels=labels,
        lock_issues=lock_issues,
    )


def _preflight_error_message(preflight: object) -> str:
    details = []
    for field in (
        "missing_required_sources",
        "duplicate_sources",
        "unknown_sources",
        "unblinded_sources",
        "non_read_only_sources",
        "incomplete_sources",
        "escaped_export_paths",
        "invalid_metadata",
    ):
        values = getattr(preflight, field, ())
        if values:
            if field == "escaped_export_paths":
                details.append(
                    f"relative export_path escapes manifest directory={','.join(values)}"
                )
                continue
            details.append(f"{field}={','.join(values)}")
    for field in ("missing_schema_fields", "duplicate_schema_fields"):
        values_by_source = getattr(preflight, field, {})
        for source_type, values in values_by_source.items():
            if values:
                details.append(f"{field}.{source_type}={','.join(values)}")
    prefix = "internal export manifest failed preflight"
    return f"{prefix}: {'; '.join(details)}" if details else prefix


def _source_paths(manifest_path: str | Path) -> dict[str, Path]:
    manifest_file = Path(manifest_path)
    with manifest_file.open() as handle:
        manifest = json.load(handle)
    root = manifest_file.parent
    paths: dict[str, Path] = {}
    for source in manifest["sources"]:
        export_path = Path(source["export_path"])
        if export_path.is_absolute():
            paths[source["source_type"]] = export_path
            continue
        resolved_root = root.resolve()
        resolved_export_path = (root / export_path).resolve()
        if not resolved_export_path.is_relative_to(resolved_root):
            raise ValueError(
                f"relative export_path escapes manifest directory: {source['source_type']}"
            )
        paths[source["source_type"]] = resolved_export_path
    return paths


def _parse_payload_items(path: Path, parser):
    items = []
    for index, raw in enumerate(_read_json(path)):
        try:
            items.append(parser(raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid internal export payload: {path}: item {index}: {exc}"
            ) from exc
    return tuple(items)


def _validate_payload(path: object, validator, *args) -> None:
    try:
        validator(*args)
    except ValueError as exc:
        raise ValueError(f"invalid internal export payload: {path}: {exc}") from exc


def _read_json(path: Path) -> list[dict]:
    try:
        with path.open() as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"missing internal export payload: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in internal export payload: {path}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"{path} must contain JSON objects: item {index}")
    return data

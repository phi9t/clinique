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
        raise ValueError("internal export manifest failed preflight")

    sources = _source_paths(manifest_path)
    snapshots = tuple(
        sorted(
            (
                EdcSnapshot.from_json(raw)
                for raw in _read_json(sources["edc_snapshots"] / "snapshots.json")
            ),
            key=lambda snapshot: snapshot.snapshot_at,
        )
    )
    validate_unique_snapshot_ids(snapshots)
    for snapshot in snapshots:
        if snapshot.contains_unblinded:
            raise ValueError(f"Snapshot {snapshot.snapshot_id} is marked as unblinded")

    lock_issues = ()
    if lock_issues_path is not None:
        lock_issues = tuple(
            DatabaseLockIssue.from_json(raw) for raw in _read_json(Path(lock_issues_path))
        )
    validate_unique_lock_issue_ids(lock_issues)
    validate_lock_issue_record_references(snapshots, lock_issues)

    labels = tuple(QueryLabel.from_json(raw) for raw in _read_json(Path(labels_path)))
    validate_unique_label_keys(labels)
    query_logs = tuple(
        QueryLog.from_json(raw) for raw in _read_json(sources["query_logs"] / "query_logs.json")
    )
    validate_unique_query_log_ids(query_logs)
    validate_snapshot_references(snapshots, labels, query_logs)
    rules = tuple(
        EditCheckRule.from_json(raw)
        for raw in _read_json(sources["edit_check_history"] / "rules.json")
    )
    validate_unique_rule_ids(rules)

    return FixtureBundle(
        snapshots=snapshots,
        rules=rules,
        query_logs=query_logs,
        labels=labels,
        lock_issues=lock_issues,
    )


def _source_paths(manifest_path: str | Path) -> dict[str, Path]:
    manifest_file = Path(manifest_path)
    with manifest_file.open() as handle:
        manifest = json.load(handle)
    root = manifest_file.parent
    paths: dict[str, Path] = {}
    for source in manifest["sources"]:
        export_path = Path(source["export_path"])
        paths[source["source_type"]] = export_path if export_path.is_absolute() else root / export_path
    return paths


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
    return data

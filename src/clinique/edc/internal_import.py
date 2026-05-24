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
    for snapshot in snapshots:
        if snapshot.contains_unblinded:
            raise ValueError(f"Snapshot {snapshot.snapshot_id} is marked as unblinded")

    lock_issues = ()
    if lock_issues_path is not None:
        lock_issues = tuple(
            DatabaseLockIssue.from_json(raw) for raw in _read_json(Path(lock_issues_path))
        )

    return FixtureBundle(
        snapshots=snapshots,
        rules=tuple(
            EditCheckRule.from_json(raw)
            for raw in _read_json(sources["edit_check_history"] / "rules.json")
        ),
        query_logs=tuple(
            QueryLog.from_json(raw) for raw in _read_json(sources["query_logs"] / "query_logs.json")
        ),
        labels=tuple(QueryLabel.from_json(raw) for raw in _read_json(Path(labels_path))),
        lock_issues=lock_issues,
    )


def _source_paths(manifest_path: str | Path) -> dict[str, Path]:
    with Path(manifest_path).open() as handle:
        manifest = json.load(handle)
    return {
        source["source_type"]: Path(source["export_path"])
        for source in manifest["sources"]
    }


def _read_json(path: Path) -> list[dict]:
    with path.open() as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list")
    return data

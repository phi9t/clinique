from __future__ import annotations

import json
from pathlib import Path

from clinique.edc.records import (
    DatabaseLockIssue,
    EditCheckRule,
    EdcSnapshot,
    FixtureBundle,
    QueryLabel,
    QueryLog,
    validate_unique_label_keys,
    validate_unique_query_log_ids,
)


def _read_json(path: Path) -> list[dict]:
    with path.open() as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a JSON list")
    return data


def load_fixture_bundle(path: str | Path) -> FixtureBundle:
    fixture_dir = Path(path)
    snapshots = tuple(
        sorted(
            (EdcSnapshot.from_json(raw) for raw in _read_json(fixture_dir / "snapshots.json")),
            key=lambda snapshot: snapshot.snapshot_at,
        )
    )
    for snapshot in snapshots:
        if snapshot.contains_phi:
            raise ValueError(f"Snapshot {snapshot.snapshot_id} is marked as containing PHI")
        if snapshot.contains_unblinded:
            raise ValueError(f"Snapshot {snapshot.snapshot_id} is marked as unblinded")

    labels = tuple(QueryLabel.from_json(raw) for raw in _read_json(fixture_dir / "labels.json"))
    validate_unique_label_keys(labels)
    query_logs = tuple(
        QueryLog.from_json(raw) for raw in _read_json(fixture_dir / "query_logs.json")
    )
    validate_unique_query_log_ids(query_logs)

    return FixtureBundle(
        snapshots=snapshots,
        rules=tuple(EditCheckRule.from_json(raw) for raw in _read_json(fixture_dir / "rules.json")),
        query_logs=query_logs,
        labels=labels,
        lock_issues=tuple(
            DatabaseLockIssue.from_json(raw)
            for raw in _read_json(fixture_dir / "lock_issues.json")
        )
        if (fixture_dir / "lock_issues.json").exists()
        else (),
    )

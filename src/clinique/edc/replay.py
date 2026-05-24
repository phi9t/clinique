from __future__ import annotations

from datetime import datetime, timezone

from clinique.edc.records import FixtureBundle, ReplayEvidence, SourceRef


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def evidence_at(bundle: FixtureBundle, replayed_at: datetime) -> ReplayEvidence:
    replayed_at = _utc(replayed_at)
    eligible_snapshots = [
        snapshot for snapshot in bundle.snapshots if snapshot.snapshot_at <= replayed_at
    ]
    if not eligible_snapshots:
        raise ValueError(f"No snapshot available at {replayed_at.isoformat()}")

    snapshot = max(eligible_snapshots, key=lambda item: item.snapshot_at)
    active_rules = tuple(
        rule
        for rule in bundle.rules
        if rule.effective_at <= replayed_at
        and (rule.retired_at is None or rule.retired_at > replayed_at)
    )
    sources = (
        SourceRef("snapshot", snapshot.snapshot_id, snapshot.snapshot_at),
        *(
            SourceRef("rule", rule.rule_id, rule.effective_at)
            for rule in sorted(active_rules, key=lambda item: item.rule_id)
        ),
    )
    return ReplayEvidence(
        replayed_at=replayed_at,
        snapshot=snapshot,
        active_rules=active_rules,
        sources=sources,
    )

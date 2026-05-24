from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.audit import audit_release_checklist
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.reports import build_offline_report, build_retrospective_report


DEFAULT_REPLAY_AT = datetime(2026, 3, 8, tzinfo=timezone.utc)


def run_validation(
    *,
    fixtures: str | Path,
    reports_dir: str | Path,
    checklist_path: str | Path = ".workstreams/edc-query-validation/release-readiness-checklist.md",
    replayed_at: datetime = DEFAULT_REPLAY_AT,
) -> dict[str, object]:
    bundle = load_fixture_bundle(fixtures)
    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    offline = build_offline_report(bundle, replayed_at=replayed_at, generated_at=replayed_at)
    retrospective = build_retrospective_report(bundle, generated_at=replayed_at)
    offline_path = output_dir / "offline-benchmark.json"
    retrospective_path = output_dir / "retrospective-replay.json"
    audit_path = output_dir / "audit-summary.json"

    offline.write_json(offline_path)
    retrospective.write_json(retrospective_path)

    local_complete = all(offline.gates.values()) and all(retrospective.gates.values())
    checklist_audit = audit_release_checklist(checklist_path)
    audit = {
        "local_synthetic_validation_complete": local_complete,
        "goal_complete": local_complete and checklist_audit.goal_complete,
        "checklist": checklist_audit.as_dict(),
        "blocked_requirements": list(checklist_audit.blocked_requirements),
        "reports": {
            "offline_benchmark": str(offline_path),
            "retrospective_replay": str(retrospective_path),
        },
        "gates": {
            "offline": offline.gates,
            "retrospective": retrospective.gates,
        },
        "metrics": {
            "offline": offline.metrics,
            "retrospective": retrospective.metrics,
        },
        "reason_goal_not_complete": (
            "Local synthetic validation is complete, but internal EDC data and prospective "
            "approval/run evidence are not available."
        ),
    }
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    return {"offline": asdict(offline), "retrospective": asdict(retrospective), "audit": audit}

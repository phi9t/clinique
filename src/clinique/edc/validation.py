from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.audit import audit_release_checklist
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.internal_import import load_internal_export_bundle
from clinique.edc.internal_preflight import preflight_internal_manifest
from clinique.edc.reports import build_offline_report, build_retrospective_report
from clinique.edc.rollout import evaluate_rollout_gate, load_rollout_gate
from clinique.edc.silent import evaluate_silent_log, load_silent_log


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


def verify_workstream(
    *,
    fixtures: str | Path,
    manifest: str | Path,
    silent_log: str | Path,
    rollout_gate: str | Path,
    reports_dir: str | Path,
    checklist_path: str | Path = ".workstreams/edc-query-validation/release-readiness-checklist.md",
    internal_export_manifest: str | Path | None = None,
    internal_labels: str | Path | None = None,
    internal_lock_issues: str | Path | None = None,
) -> dict[str, object]:
    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if bool(internal_export_manifest) != bool(internal_labels):
        raise ValueError("internal export verification requires both manifest and labels")

    validation = run_validation(
        fixtures=fixtures,
        reports_dir=output_dir,
        checklist_path=checklist_path,
    )
    preflight = preflight_internal_manifest(manifest)
    preflight_path = output_dir / "internal-preflight-template.json"
    preflight_path.write_text(json.dumps(preflight.as_dict(), indent=2, sort_keys=True) + "\n")
    if not preflight.ok:
        raise ValueError("internal-data manifest failed preflight readiness gate")

    silent = evaluate_silent_log(
        load_silent_log(silent_log),
        false_positive_tolerance_per_reviewer_week=1.0,
    )
    silent_path = output_dir / "silent-log-evaluation.json"
    silent.write_json(silent_path)

    rollout = evaluate_rollout_gate(load_rollout_gate(rollout_gate))
    rollout_path = output_dir / "controlled-rollout-gate.json"
    rollout.write_json(rollout_path)

    reports = {
        "audit_summary": str(output_dir / "audit-summary.json"),
        "controlled_rollout_gate": str(rollout_path),
        "internal_preflight": str(preflight_path),
        "offline_benchmark": str(output_dir / "offline-benchmark.json"),
        "retrospective_replay": str(output_dir / "retrospective-replay.json"),
        "silent_log_evaluation": str(silent_path),
    }
    internal_export_result = None
    if internal_export_manifest and internal_labels:
        internal_export_result = validate_internal_exports(
            manifest=internal_export_manifest,
            labels=internal_labels,
            lock_issues=internal_lock_issues,
            reports_dir=output_dir,
        )
        reports.update(internal_export_result["reports"])
    local_reports_complete = all(Path(path).exists() for path in reports.values())
    local_internal_export_reports_complete = (
        internal_export_result is not None
        and all(Path(path).exists() for path in internal_export_result["reports"].values())
    )
    audit = validation["audit"]
    local_gate_failures = _local_gate_failures(
        offline_gates=audit["gates"]["offline"],
        retrospective_gates=audit["gates"]["retrospective"],
        preflight_gates={"ok": preflight.ok},
        silent_gates=silent.gates,
        rollout_gates=rollout.gates,
        internal_export_result=internal_export_result,
    )
    local_gates_passed = not local_gate_failures
    evidence = {
        "local_reports_complete": local_reports_complete,
        "local_internal_export_reports_complete": local_internal_export_reports_complete,
        "local_gates_passed": local_gates_passed,
        "local_gate_failures": local_gate_failures,
        "goal_complete": bool(audit["goal_complete"]) and local_gates_passed,
        "blocked_requirements": audit["blocked_requirements"],
        "reports": reports,
        "gates": {
            "offline": audit["gates"]["offline"],
            "retrospective": audit["gates"]["retrospective"],
            "internal_preflight": preflight.as_dict(),
            "silent_log": silent.gates,
            "controlled_rollout": rollout.gates,
        },
    }
    if internal_export_result is not None:
        evidence["gates"]["internal_export_offline"] = internal_export_result["offline"]["gates"]
        evidence["gates"]["internal_export_retrospective"] = internal_export_result[
            "retrospective"
        ]["gates"]
    (output_dir / "workstream-verification.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    )
    return evidence


def _local_gate_failures(
    *,
    offline_gates: dict[str, bool],
    retrospective_gates: dict[str, bool],
    preflight_gates: dict[str, bool],
    silent_gates: dict[str, bool],
    rollout_gates: dict[str, bool],
    internal_export_result: dict[str, object] | None,
) -> list[str]:
    failures = []
    failures.extend(_false_gate_names("offline", offline_gates))
    failures.extend(_false_gate_names("retrospective", retrospective_gates))
    failures.extend(_false_gate_names("internal_preflight", preflight_gates))
    failures.extend(_silent_gate_failures(silent_gates))
    failures.extend(_false_gate_names("controlled_rollout", rollout_gates))
    if internal_export_result is not None:
        failures.extend(
            _false_gate_names(
                "internal_export_offline",
                internal_export_result["offline"]["gates"],
            )
        )
        failures.extend(
            _false_gate_names(
                "internal_export_retrospective",
                internal_export_result["retrospective"]["gates"],
            )
        )
    return failures


def _false_gate_names(prefix: str, gates: dict[str, bool]) -> list[str]:
    return [f"{prefix}.{name}" for name, passed in gates.items() if not passed]


def _silent_gate_failures(gates: dict[str, bool]) -> list[str]:
    failures = []
    if not gates["no_operational_impact"]:
        failures.append("silent_log.no_operational_impact")
    if not gates["false_positive_burden_controlled"]:
        failures.append("silent_log.false_positive_burden_controlled")
    if gates["stop_criteria_triggered"]:
        failures.append("silent_log.stop_criteria_triggered")
    return failures


def validate_internal_exports(
    *,
    manifest: str | Path,
    labels: str | Path,
    reports_dir: str | Path,
    lock_issues: str | Path | None = None,
    replayed_at: datetime = DEFAULT_REPLAY_AT,
) -> dict[str, object]:
    bundle = load_internal_export_bundle(
        manifest,
        labels_path=labels,
        lock_issues_path=lock_issues,
    )
    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    offline = build_offline_report(bundle, replayed_at=replayed_at, generated_at=replayed_at)
    retrospective = build_retrospective_report(bundle, generated_at=replayed_at)
    offline_path = output_dir / "internal-offline-benchmark.json"
    retrospective_path = output_dir / "internal-retrospective-replay.json"
    offline.write_json(offline_path)
    retrospective.write_json(retrospective_path)
    return {
        "offline": asdict(offline),
        "retrospective": asdict(retrospective),
        "reports": {
            "internal_offline_benchmark": str(offline_path),
            "internal_retrospective_replay": str(retrospective_path),
        },
    }

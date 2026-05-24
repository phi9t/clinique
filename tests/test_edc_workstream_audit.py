import json
from pathlib import Path

from clinique.edc.audit import audit_release_checklist
from clinique.edc.validation import verify_workstream


def test_audit_release_checklist_derives_open_items_by_section():
    audit = audit_release_checklist(
        Path(".workstreams/edc-query-validation/release-readiness-checklist.md")
    )

    assert audit.complete_sections == ("Synthetic Validation",)
    assert "Internal Data Validation" in audit.incomplete_sections
    assert "Prospective Validation" in audit.incomplete_sections
    assert "internal_data_validation__internal_edc_snapshots_approved_and_connected" in (
        audit.blocked_requirements
    )
    assert "prospective_validation__silent_prospective_run_completed" in (
        audit.blocked_requirements
    )
    assert audit.goal_complete is False


def test_audit_release_checklist_marks_goal_complete_when_all_items_checked(tmp_path):
    checklist = tmp_path / "checklist.md"
    checklist.write_text(
        "# Checklist\n\n"
        "## Synthetic Validation\n\n"
        "- [x] PHI-free fixtures exist.\n\n"
        "## Internal Data Validation\n\n"
        "- [x] Internal EDC snapshots approved and connected.\n\n"
        "## Prospective Validation\n\n"
        "- [x] Silent prospective run completed.\n"
    )

    audit = audit_release_checklist(checklist)

    assert audit.blocked_requirements == ()
    assert audit.goal_complete is True


def test_annotation_manual_uses_study_and_site_scoped_annotation_unit():
    manual = Path(".workstreams/edc-query-validation/annotation-manual.md").read_text()

    assert "(snapshot_id, study_id, site_id, subject_id, form, field)" in manual


def test_verify_workstream_blocks_completion_on_local_gate_failures(tmp_path):
    checklist = tmp_path / "complete-checklist.md"
    checklist.write_text(
        "# Checklist\n\n"
        "## Synthetic Validation\n\n"
        "- [x] PHI-free fixtures exist.\n\n"
        "## Internal Data Validation\n\n"
        "- [x] Internal EDC snapshots approved and connected.\n"
        "- [x] Internal L1 offline report generated.\n\n"
        "## Prospective Validation\n\n"
        "- [x] Silent prospective run completed.\n"
        "- [x] Controlled rollout gate approved.\n"
    )

    evidence = verify_workstream(
        fixtures="tests/fixtures/edc_query",
        manifest=".workstreams/edc-query-validation/internal-data-manifest.template.json",
        silent_log="tests/fixtures/edc_query/silent_log.json",
        rollout_gate="tests/fixtures/edc_query/controlled_rollout_gate.json",
        reports_dir=tmp_path / "reports",
        checklist_path=checklist,
    )

    assert evidence["goal_complete"] is False
    assert evidence["local_gates_passed"] is False
    assert "silent_log.stop_criteria_triggered" in evidence["local_gate_failures"]


def test_verify_workstream_blocks_completion_without_internal_export_evidence(tmp_path):
    checklist = tmp_path / "complete-checklist.md"
    checklist.write_text(
        "# Checklist\n\n"
        "## Synthetic Validation\n\n"
        "- [x] PHI-free fixtures exist.\n\n"
        "## Internal Data Validation\n\n"
        "- [x] Internal EDC snapshots approved and connected.\n"
        "- [x] Internal query logs approved and connected.\n"
        "- [x] Internal edit-check history approved and connected.\n"
        "- [x] Internal L1 offline report generated.\n"
        "- [x] Internal L2 retrospective replay report generated.\n\n"
        "## Prospective Validation\n\n"
        "- [x] Silent prospective protocol approved.\n"
        "- [x] Silent prospective run completed.\n"
        "- [x] Controlled rollout gate approved.\n"
        "- [x] Human approval path validated.\n"
    )
    silent_log = tmp_path / "passing-silent-log.json"
    silent_log.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "SIL-PASS-001",
                    "logged_at": "2026-04-01T00:00:00Z",
                    "study_id": "STUDY-EDC-001",
                    "site_id": "SITE-01",
                    "subject_id": "SUBJ-001",
                    "form": "AE",
                    "field": "term",
                    "query_category": "missing",
                    "agent_recommendation": "Draft query for missing AE term.",
                    "agent_evidence": ["rec-ae-001", "RULE-MISSING-AE"],
                    "human_action": "opened_query",
                    "human_action_at": "2026-04-02T00:00:00Z",
                    "ground_truth": "true_positive",
                    "reviewer_id": "DM-001",
                    "affected_operations": False,
                    "safety_risk": False,
                }
            ]
        )
    )

    evidence = verify_workstream(
        fixtures="tests/fixtures/edc_query",
        manifest=".workstreams/edc-query-validation/internal-data-manifest.template.json",
        silent_log=silent_log,
        rollout_gate="tests/fixtures/edc_query/controlled_rollout_gate.json",
        reports_dir=tmp_path / "reports",
        checklist_path=checklist,
    )

    assert evidence["goal_complete"] is False
    assert evidence["local_internal_export_reports_complete"] is False
    assert evidence["local_gate_failures"] == ["internal_export.reports_missing"]


def test_verify_workstream_blocks_completion_on_synthetic_internal_export_evidence(tmp_path):
    checklist = tmp_path / "complete-checklist.md"
    checklist.write_text(
        "# Checklist\n\n"
        "## Synthetic Validation\n\n"
        "- [x] PHI-free fixtures exist.\n\n"
        "## Internal Data Validation\n\n"
        "- [x] Internal EDC snapshots approved and connected.\n"
        "- [x] Internal query logs approved and connected.\n"
        "- [x] Internal edit-check history approved and connected.\n"
        "- [x] Internal L1 offline report generated.\n"
        "- [x] Internal L2 retrospective replay report generated.\n\n"
        "## Prospective Validation\n\n"
        "- [x] Silent prospective protocol approved.\n"
        "- [x] Silent prospective run completed.\n"
        "- [x] Controlled rollout gate approved.\n"
        "- [x] Human approval path validated.\n"
    )
    silent_log = tmp_path / "passing-silent-log.json"
    silent_log.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "SIL-PASS-001",
                    "logged_at": "2026-04-01T00:00:00Z",
                    "study_id": "STUDY-EDC-001",
                    "site_id": "SITE-01",
                    "subject_id": "SUBJ-001",
                    "form": "AE",
                    "field": "term",
                    "query_category": "missing",
                    "agent_recommendation": "Draft query for missing AE term.",
                    "agent_evidence": ["rec-ae-001", "RULE-MISSING-AE"],
                    "human_action": "opened_query",
                    "human_action_at": "2026-04-02T00:00:00Z",
                    "ground_truth": "true_positive",
                    "reviewer_id": "DM-001",
                    "affected_operations": False,
                    "safety_risk": False,
                }
            ]
        )
    )

    evidence = verify_workstream(
        fixtures="tests/fixtures/edc_query",
        manifest=".workstreams/edc-query-validation/internal-data-manifest.template.json",
        silent_log=silent_log,
        rollout_gate="tests/fixtures/edc_query/controlled_rollout_gate.json",
        reports_dir=tmp_path / "reports",
        checklist_path=checklist,
        internal_export_manifest="tests/fixtures/edc_query/internal_export_manifest.json",
        internal_labels="tests/fixtures/edc_query/labels.json",
        internal_lock_issues="tests/fixtures/edc_query/lock_issues.json",
    )

    assert evidence["goal_complete"] is False
    assert evidence["local_internal_export_reports_complete"] is True
    assert evidence["internal_export_evidence_kind"] == "synthetic_fixture"
    assert evidence["local_gate_failures"] == ["internal_export.synthetic_fixture_evidence"]


def test_verify_workstream_blocks_completion_on_unverified_internal_export_kind(tmp_path):
    checklist = tmp_path / "complete-checklist.md"
    checklist.write_text(
        "# Checklist\n\n"
        "## Synthetic Validation\n\n"
        "- [x] PHI-free fixtures exist.\n\n"
        "## Internal Data Validation\n\n"
        "- [x] Internal EDC snapshots approved and connected.\n"
        "- [x] Internal query logs approved and connected.\n"
        "- [x] Internal edit-check history approved and connected.\n"
        "- [x] Internal L1 offline report generated.\n"
        "- [x] Internal L2 retrospective replay report generated.\n\n"
        "## Prospective Validation\n\n"
        "- [x] Silent prospective protocol approved.\n"
        "- [x] Silent prospective run completed.\n"
        "- [x] Controlled rollout gate approved.\n"
        "- [x] Human approval path validated.\n"
    )
    silent_log = tmp_path / "passing-silent-log.json"
    silent_log.write_text(
        json.dumps(
            [
                {
                    "recommendation_id": "SIL-PASS-001",
                    "logged_at": "2026-04-01T00:00:00Z",
                    "study_id": "STUDY-EDC-001",
                    "site_id": "SITE-01",
                    "subject_id": "SUBJ-001",
                    "form": "AE",
                    "field": "term",
                    "query_category": "missing",
                    "agent_recommendation": "Draft query for missing AE term.",
                    "agent_evidence": ["rec-ae-001", "RULE-MISSING-AE"],
                    "human_action": "opened_query",
                    "human_action_at": "2026-04-02T00:00:00Z",
                    "ground_truth": "true_positive",
                    "reviewer_id": "DM-001",
                    "affected_operations": False,
                    "safety_risk": False,
                }
            ]
        )
    )
    export_root = tmp_path / "relabeled-export"
    export_root.mkdir()
    for name in ("snapshots.json", "query_logs.json", "rules.json"):
        source = {
            "snapshots.json": Path("tests/fixtures/edc_query/snapshots.json"),
            "query_logs.json": Path("tests/fixtures/edc_query/query_logs.json"),
            "rules.json": Path("tests/fixtures/edc_query/rules.json"),
        }[name]
        (export_root / name).write_text(source.read_text())
    manifest_payload = json.loads(
        Path("tests/fixtures/edc_query/internal_export_manifest.json").read_text()
    )
    manifest_payload.pop("evidence_kind", None)
    for source in manifest_payload["sources"]:
        source["owner"] = "data-management@example.test"
        source["export_path"] = str(export_root)
        source["sensitivity"] = "phi"
    manifest = tmp_path / "relabeled-manifest.json"
    manifest.write_text(json.dumps(manifest_payload))

    evidence = verify_workstream(
        fixtures="tests/fixtures/edc_query",
        manifest=".workstreams/edc-query-validation/internal-data-manifest.template.json",
        silent_log=silent_log,
        rollout_gate="tests/fixtures/edc_query/controlled_rollout_gate.json",
        reports_dir=tmp_path / "reports",
        checklist_path=checklist,
        internal_export_manifest=manifest,
        internal_labels="tests/fixtures/edc_query/labels.json",
        internal_lock_issues="tests/fixtures/edc_query/lock_issues.json",
    )

    assert evidence["goal_complete"] is False
    assert evidence["internal_export_evidence_kind"] == "unknown"
    assert evidence["local_gate_failures"] == ["internal_export.unverified_evidence_kind"]

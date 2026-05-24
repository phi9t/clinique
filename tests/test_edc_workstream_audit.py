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

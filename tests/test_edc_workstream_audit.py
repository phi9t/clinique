from pathlib import Path

from clinique.edc.audit import audit_release_checklist


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

"""RFC-0001 estimand-spine checker: seeded-defect recall + zero false positives + read-only."""

from clinique.estimand import (
    check_consistency,
    consistent_bundle,
    mutate_population,
    mutate_timepoint,
    mutate_unbacked_shell,
)
from clinique.estimand import checker as checker_mod
from clinique.estimand.graph import ArtifactGraph


def test_clean_bundle_has_zero_findings():
    # false-positive rate = 0 on the unmutated consistent bundle
    assert check_consistency(consistent_bundle()) == []


def test_timepoint_defect_detected():
    findings = check_consistency(mutate_timepoint(consistent_bundle()))
    assert any(f.rule_id == "EST-TIMEPOINT-ALIGN" for f in findings)


def test_population_defect_detected():
    findings = check_consistency(mutate_population(consistent_bundle()))
    assert any(f.rule_id == "POP-DEF-CONSISTENT" for f in findings)


def test_unbacked_shell_defect_detected():
    findings = check_consistency(mutate_unbacked_shell(consistent_bundle()))
    assert any(f.rule_id == "SHELL-BACKED" and f.severity == "blocker" for f in findings)


def test_seeded_defect_recall_is_one():
    # each single-defect mutation must be caught by its rule (recall = 1.0)
    base = consistent_bundle()
    expected = {
        "EST-TIMEPOINT-ALIGN": mutate_timepoint,
        "POP-DEF-CONSISTENT": mutate_population,
        "SHELL-BACKED": mutate_unbacked_shell,
    }
    for rule_id, mutate in expected.items():
        findings = check_consistency(mutate(base))
        assert any(f.rule_id == rule_id for f in findings), f"missed seeded defect for {rule_id}"


def test_mutators_do_not_mutate_in_place():
    base = consistent_bundle()
    mutate_timepoint(base)
    assert check_consistency(base) == []  # original untouched


def test_finding_schema_complete():
    f = check_consistency(mutate_timepoint(consistent_bundle()))[0]
    assert f.finding_id and f.rule_id and f.severity and f.estimand_attribute
    assert f.artifacts_involved and f.explanation and f.suggested_resolution
    assert 0.0 <= f.confidence <= 1.0
    assert isinstance(f.needs_human_review, bool)


def test_read_only_no_artifact_write_api():
    # the checker must not expose any way to modify source artifacts
    for forbidden in ("write", "edit", "fix", "apply", "save", "patch"):
        assert not hasattr(checker_mod, forbidden)
    # the graph exposes only a copy-on-change helper, never an in-place setter
    assert not hasattr(ArtifactGraph, "set")
    assert not hasattr(ArtifactGraph, "update")

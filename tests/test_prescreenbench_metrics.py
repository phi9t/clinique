"""Unit tests for the shared prescreening metrics (single source of truth)."""

from clinique.prescreen import metrics as M
from clinique.prescreen.metrics import CriterionOutcome


def _o(ctype, gold, pred, **kw):
    return CriterionOutcome(criterion_id="X", criterion_type=ctype, gold=gold, pred=pred, **kw)


def test_unsafe_clearance_exclusion_from_silence_and_from_meeting():
    # gold unknown cleared as not_met, and gold met cleared as not_met, are both unsafe
    assert M.is_unsafe_clearance(_o("exclusion", "unknown", "not_met"))
    assert M.is_unsafe_clearance(_o("exclusion", "met", "not_met"))
    # correctly clearing an exclusion that truly is not_met is not unsafe
    assert not M.is_unsafe_clearance(_o("exclusion", "not_met", "not_met"))


def test_unsafe_clearance_inclusion_requires_safety_critical():
    assert M.is_unsafe_clearance(_o("inclusion", "unknown", "met", is_safety_critical=True))
    assert not M.is_unsafe_clearance(_o("inclusion", "unknown", "met", is_safety_critical=False))


def test_unsafe_clearance_rate_denominator_is_clearance_eligible():
    outcomes = [
        _o("exclusion", "unknown", "not_met"),  # unsafe
        _o("exclusion", "not_met", "not_met"),  # safe clearance
        _o("inclusion", "unknown", "unknown"),  # not clearance-eligible (non-safety inclusion)
    ]
    # 1 unsafe / 2 clearance-eligible (the two exclusions)
    assert M.unsafe_clearance_rate(outcomes) == 0.5
    assert M.unsafe_clearance_count(outcomes) == 1


def test_macro_f1_perfect_and_per_class():
    outcomes = [
        _o("inclusion", "met", "met"),
        _o("exclusion", "unknown", "unknown"),
    ]
    assert M.macro_f1(outcomes) == 1.0
    per = M.per_class_f1(outcomes)
    assert set(per) == {"met", "unknown"}
    assert per["met"]["f1"] == 1.0


def test_evidence_support_only_counts_met_not_met():
    outcomes = [
        _o("inclusion", "met", "met", evidence_present=True, quotes_verbatim=True),
        _o("inclusion", "met", "met", evidence_present=False),  # unsupported
        _o("exclusion", "unknown", "unknown"),  # ignored (no evidence required)
    ]
    assert M.evidence_support_accuracy(outcomes) == 0.5
    assert M.unsupported_decision_count(outcomes) == 1


def test_blocking_recall():
    outcomes = [
        _o("exclusion", "met", "met"),  # gold blocking, predicted blocking -> hit
        _o("inclusion", "not_met", "unknown"),  # gold blocking, missed
    ]
    assert M.blocking_criterion_recall(outcomes) == 0.5


def test_hard_gate_breaches_and_composite_penalty():
    breaches = M.hard_gate_breaches(
        unsafe_clearance_rate=0.5,
        unsupported_decision_rate=0.0,
        fabricated_quotes=0,
        schema_valid_rate=1.0,
    )
    assert breaches == ["unsafe_clearance_rate"]
    # a single breach must collapse an otherwise-perfect score
    high = M.composite_score(
        criterion_macro_f1=1.0,
        evidence_support_accuracy=1.0,
        blocking_criterion_recall=1.0,
        overall_recommendation_accuracy=1.0,
        unknown_actionability=1.0,
        safety_breaches=0,
    )
    penalized = M.composite_score(
        criterion_macro_f1=1.0,
        evidence_support_accuracy=1.0,
        blocking_criterion_recall=1.0,
        overall_recommendation_accuracy=1.0,
        unknown_actionability=1.0,
        safety_breaches=1,
    )
    assert high == 1.0
    assert penalized <= 0.5


def test_clean_gates_pass():
    assert (
        M.hard_gate_breaches(
            unsafe_clearance_rate=0.0,
            unsupported_decision_rate=0.0,
            fabricated_quotes=0,
            schema_valid_rate=1.0,
        )
        == []
    )


def test_multiclass_summary_reports_accuracy_per_label_and_confusion_matrix():
    summary = M.multiclass_summary(
        [("needs_review", "needs_review"), ("likely_ineligible", "needs_review")],
        labels=("likely_ineligible", "needs_review", "potentially_eligible"),
    )

    assert summary["total"] == 2
    assert summary["accuracy"] == 0.5
    assert summary["per_class"]["needs_review"] == {
        "precision": 0.5,
        "recall": 1.0,
        "f1": 2 * 0.5 * 1.0 / 1.5,
        "support": 1.0,
    }
    assert summary["confusion_matrix"]["likely_ineligible"]["needs_review"] == 1
    assert summary["confusion_matrix"]["needs_review"]["needs_review"] == 1


def test_multiclass_summary_explicitly_reports_no_eligible_items():
    summary = M.multiclass_summary(
        [],
        labels=("likely_ineligible", "needs_review", "potentially_eligible"),
    )

    assert summary["total"] == 0
    assert summary["accuracy"] is None
    assert summary["per_class"] == {}
    assert summary["confusion_matrix"] == {}

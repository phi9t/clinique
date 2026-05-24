from __future__ import annotations

import pytest

from clinique.prescreen.aggregator import aggregate
from clinique.prescreen.schemas import CriterionJudgment


def _j(criterion_id: str, criterion_type: str, prediction: str) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_id=criterion_id,
        criterion_type=criterion_type,
        prediction=prediction,
    )


def test_exclusion_met_is_likely_ineligible():
    assert aggregate([_j("E-1", "exclusion", "met")]) == "likely_ineligible"


def test_inclusion_not_met_is_likely_ineligible():
    assert aggregate([_j("I-1", "inclusion", "not_met")]) == "likely_ineligible"


def test_unknown_triggers_needs_review():
    assert aggregate([_j("I-1", "inclusion", "unknown")]) == "needs_review"


def test_conflicting_evidence_triggers_needs_review():
    assert aggregate([_j("I-1", "inclusion", "conflicting_evidence")]) == "needs_review"


def test_clean_pass_is_potentially_eligible():
    judgments = [
        _j("I-1", "inclusion", "met"),
        _j("E-1", "exclusion", "not_met"),
    ]
    assert aggregate(judgments) == "potentially_eligible"


def test_exclusion_not_met_does_not_override_failed_inclusion():
    judgments = [
        _j("I-1", "inclusion", "not_met"),
        _j("E-1", "exclusion", "not_met"),
    ]
    assert aggregate(judgments) == "likely_ineligible"


def test_not_applicable_is_ignored():
    judgments = [
        _j("I-1", "inclusion", "met"),
        _j("N-1", "inclusion", "not_applicable"),
    ]
    assert aggregate(judgments) == "potentially_eligible"


def test_empty_judgments_is_potentially_eligible():
    assert aggregate([]) == "potentially_eligible"


def test_invalid_criterion_type_raises():
    with pytest.raises(ValueError, match="criterion_type"):
        aggregate([_j("X-1", "maybe", "met")])


def test_invalid_prediction_raises():
    with pytest.raises(ValueError, match="prediction"):
        aggregate([_j("I-1", "inclusion", "maybe")])


def test_aggregate_is_deterministic():
    judgments = [_j("I-1", "inclusion", "met"), _j("E-1", "exclusion", "unknown")]
    assert aggregate(judgments) == aggregate(list(judgments))

"""Deterministic overall recommendation from criterion-level judgments."""

from __future__ import annotations

from collections.abc import Sequence

from clinique.prescreen.schemas import (
    CRITERION_TYPES,
    PREDICTIONS,
    CriterionJudgment,
)


def _validate(judgment: CriterionJudgment) -> None:
    if judgment.criterion_type not in CRITERION_TYPES:
        raise ValueError(f"invalid criterion_type: {judgment.criterion_type!r}")
    if judgment.prediction not in PREDICTIONS:
        raise ValueError(f"invalid prediction: {judgment.prediction!r}")


def aggregate(judgments: Sequence[CriterionJudgment]) -> str:
    """Return likely_ineligible, needs_review, or potentially_eligible.

    ``not_applicable`` judgments are ignored. An empty sequence returns
    ``potentially_eligible`` (vacuous pass).
    """
    for judgment in judgments:
        _validate(judgment)

    applicable = [j for j in judgments if j.prediction != "not_applicable"]

    if any(j.criterion_type == "exclusion" and j.prediction == "met" for j in applicable):
        return "likely_ineligible"
    if any(j.criterion_type == "inclusion" and j.prediction == "not_met" for j in applicable):
        return "likely_ineligible"
    if any(j.prediction in {"unknown", "conflicting_evidence"} for j in applicable):
        return "needs_review"
    return "potentially_eligible"

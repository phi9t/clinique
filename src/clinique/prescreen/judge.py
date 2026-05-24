"""Per-criterion judge — Protocol + deterministic RuleJudge."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .schemas import Criterion, CriterionJudgment, Evidence, PatientCorpus, PatientDocument
from .temporal import evidence_within_window
from .units import compare_threshold
from .vocab import is_anti_pd1_mention, medication_matches_class


class Judge(Protocol):
    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> CriterionJudgment: ...


def _doc_by_id(corpus: PatientCorpus) -> dict[str, PatientDocument]:
    return {doc.doc_id: doc for doc in corpus.documents}


def _base_judgment(
    criterion: Criterion, *, prediction: str, rationale: str, **kwargs
) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_id=criterion.criterion_id,
        criterion_type=criterion.criterion_type,
        prediction=prediction,
        rationale=rationale,
        human_review_required=bool(kwargs.get("human_review_required", False)),
        evidence=tuple(kwargs.get("evidence", ())),
        confidence=kwargs.get("confidence"),
    )


class RuleJudge:
    """Deterministic stand-in for demographic, lab, and medication-class criteria."""

    name = "rule-judge"
    version = "0.1.0"

    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> CriterionJudgment:
        if criterion.ambiguity_flags and criterion.clinical_domain not in {
            "demographic",
            "laboratory",
        }:
            return _base_judgment(
                criterion,
                prediction="unknown",
                rationale="Criterion flagged as ambiguous; abstaining.",
                human_review_required=True,
            )

        if criterion.clinical_domain == "demographic" and criterion.operator == ">=":
            age = corpus.demographics.get("age")
            threshold = criterion.threshold.value if criterion.threshold else None
            if age is None or threshold is None:
                return _base_judgment(
                    criterion,
                    prediction="unknown",
                    rationale="Age or threshold missing.",
                    human_review_required=True,
                )
            met = age >= threshold
            return _base_judgment(
                criterion,
                prediction="met" if met else "not_met",
                rationale=f"Patient age {age} vs minimum {threshold}.",
            )

        if criterion.clinical_domain == "laboratory" and criterion.threshold and criterion.operator:
            docs = _doc_by_id(corpus)
            for ev in evidence:
                doc = docs.get(ev.doc_id)
                if doc is None:
                    continue
                value = doc.structured.get("value")
                unit = doc.structured.get("unit")
                if value is None:
                    continue
                if criterion.temporal_constraint:
                    ok = evidence_within_window(
                        doc.date,
                        corpus.snapshot_date,
                        window_value=criterion.temporal_constraint.window_value,
                        window_unit=criterion.temporal_constraint.window_unit,
                    )
                    if ok is False:
                        continue
                    if ok is None:
                        return _base_judgment(
                            criterion,
                            prediction="unknown",
                            rationale="Temporal window could not be evaluated.",
                            human_review_required=True,
                        )
                cmp = compare_threshold(
                    float(value),
                    unit,
                    operator=criterion.operator,
                    threshold_value=criterion.threshold.value,
                    threshold_unit=criterion.threshold.unit,
                )
                if cmp is None:
                    continue
                prediction = "met" if cmp else "not_met"
                if criterion.criterion_type == "exclusion":
                    prediction = "met" if cmp else "not_met"
                fact = f"{value} {unit or ''}".strip()
                enriched = Evidence(
                    criterion_id=ev.criterion_id,
                    doc_id=ev.doc_id,
                    quote=ev.quote,
                    normalized_fact=fact,
                )
                return _base_judgment(
                    criterion,
                    prediction=prediction,
                    rationale=f"Structured lab comparison: {fact} {criterion.operator} "
                    f"{criterion.threshold.value} {criterion.threshold.unit or ''}".strip(),
                    evidence=(enriched,),
                )
            return _base_judgment(
                criterion,
                prediction="unknown",
                rationale="No in-window structured lab evidence found.",
                human_review_required=True,
            )

        if criterion.clinical_domain == "medication" and criterion.criterion_type == "exclusion":
            if is_anti_pd1_mention(criterion.raw_text):
                docs = _doc_by_id(corpus)
                hits: list[Evidence] = []
                for doc in corpus.documents:
                    if doc.source_type != "medication":
                        continue
                    desc = doc.structured.get("description") or doc.text
                    if medication_matches_class(desc, "anti_pd1"):
                        hits.append(
                            Evidence(
                                criterion_id=criterion.criterion_id,
                                doc_id=doc.doc_id,
                                quote=doc.text[:240],
                                normalized_fact=desc,
                            )
                        )
                if hits:
                    return _base_judgment(
                        criterion,
                        prediction="met",
                        rationale="Anti-PD-1/PD-L1 agent documented.",
                        evidence=tuple(hits[:3]),
                    )
                return _base_judgment(
                    criterion,
                    prediction="unknown",
                    rationale="No conclusive prior immunotherapy history found.",
                    human_review_required=True,
                )

        if criterion.criterion_type == "exclusion" and criterion.requires_absence_evidence:
            return _base_judgment(
                criterion,
                prediction="unknown",
                rationale="Exclusion requires explicit negative evidence; none found.",
                human_review_required=True,
            )

        return _base_judgment(
            criterion,
            prediction="unknown",
            rationale="No deterministic rule applies; human review required.",
            human_review_required=True,
        )

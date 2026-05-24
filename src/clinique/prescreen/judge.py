"""Per-criterion judge — Protocol + deterministic RuleJudge."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .schemas import Criterion, CriterionJudgment, Evidence, PatientCorpus, PatientDocument
from .temporal import evidence_within_window
from .units import compare_threshold
from .vocab import (
    is_anti_pd1_mention,
    is_ecog_criterion,
    is_nsclc_mention,
    is_prior_systemic_criterion,
    is_squamous_mention,
    medication_matches_class,
    truncate_quote,
)

EVIDENCE_LIMIT = 3


class Judge(Protocol):
    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> CriterionJudgment: ...


def _doc_by_id(corpus: PatientCorpus) -> dict[str, PatientDocument]:
    return {doc.doc_id: doc for doc in corpus.documents}


def _evidence_from_doc(criterion_id: str, doc: PatientDocument) -> Evidence:
    return Evidence(
        criterion_id=criterion_id,
        doc_id=doc.doc_id,
        quote=truncate_quote(doc.text),
        normalized_fact=doc.structured.get("description") or doc.text,
    )


def _enrich_evidence(
    criterion_id: str,
    evidence: Sequence[Evidence],
    docs: dict[str, PatientDocument],
) -> tuple[Evidence, ...]:
    hits: list[Evidence] = []
    for ev in evidence[:EVIDENCE_LIMIT]:
        doc = docs.get(ev.doc_id)
        if doc is None:
            hits.append(ev)
            continue
        hits.append(
            Evidence(
                criterion_id=criterion_id,
                doc_id=ev.doc_id,
                quote=ev.quote,
                normalized_fact=ev.normalized_fact
                or doc.structured.get("description")
                or doc.text,
            )
        )
    return tuple(hits)


def _medication_hits(
    criterion_id: str,
    evidence: Sequence[Evidence],
    docs: dict[str, PatientDocument],
    *,
    drug_class: str,
) -> tuple[Evidence, ...]:
    hits: list[Evidence] = []
    for ev in evidence:
        doc = docs.get(ev.doc_id)
        if doc is None or doc.source_type != "medication":
            continue
        desc = doc.structured.get("description") or doc.text
        if medication_matches_class(desc, drug_class):
            hits.append(_evidence_from_doc(criterion_id, doc))
    return tuple(hits[:EVIDENCE_LIMIT])


def _base_judgment(
    criterion: Criterion,
    *,
    prediction: str,
    rationale: str,
    human_review_required: bool = False,
    evidence: Sequence[Evidence] = (),
    confidence: float | None = None,
) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_id=criterion.criterion_id,
        criterion_type=criterion.criterion_type,
        prediction=prediction,
        rationale=rationale,
        human_review_required=human_review_required,
        evidence=tuple(evidence),
        confidence=confidence,
    )


def _abstain(
    criterion: Criterion,
    evidence: Sequence[Evidence],
    rationale: str,
    *,
    human_review_required: bool = True,
) -> CriterionJudgment:
    return _base_judgment(
        criterion,
        prediction="unknown",
        rationale=rationale,
        human_review_required=human_review_required,
        evidence=evidence[:EVIDENCE_LIMIT],
    )


def _judge_condition(
    criterion: Criterion,
    evidence: Sequence[Evidence],
    docs: dict[str, PatientDocument],
) -> CriterionJudgment:
    hits = _enrich_evidence(criterion.criterion_id, evidence, docs)
    if not hits:
        return _abstain(criterion, evidence, "No matching condition evidence found.")
    raw = criterion.raw_text.lower()
    if criterion.criterion_type == "inclusion" and is_nsclc_mention(raw):
        return _abstain(
            criterion,
            hits,
            "NSCLC documented; stage/histology details not confirmed in record.",
        )
    if criterion.criterion_type == "exclusion" and is_squamous_mention(raw):
        if any(is_squamous_mention(h.normalized_fact or h.quote) for h in hits):
            return _base_judgment(
                criterion,
                prediction="met",
                rationale="Squamous histology suggested in condition record.",
                evidence=hits,
            )
        return _abstain(
            criterion,
            hits,
            "Lung cancer documented; squamous histology not confirmed.",
        )
    return _abstain(
        criterion,
        hits,
        "Relevant condition evidence found; criterion not fully evaluable.",
    )


class RuleJudge:
    """Deterministic judge for demographic, lab, medication-class, and condition criteria."""

    name = "rule-judge"
    version = "0.2.0"

    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> CriterionJudgment:
        docs = _doc_by_id(corpus)

        if criterion.ambiguity_flags and criterion.clinical_domain not in {
            "demographic",
            "laboratory",
        }:
            return _abstain(
                criterion,
                evidence,
                "Criterion flagged as ambiguous; abstaining.",
            )

        if criterion.clinical_domain == "demographic" and criterion.operator == ">=":
            age = corpus.demographics.get("age")
            threshold = criterion.threshold.value if criterion.threshold else None
            if age is None or threshold is None:
                return _abstain(criterion, evidence, "Age or threshold missing.")
            met = age >= threshold
            return _base_judgment(
                criterion,
                prediction="met" if met else "not_met",
                rationale=f"Patient age {age} vs minimum {threshold}.",
            )

        if criterion.clinical_domain == "laboratory" and criterion.threshold and criterion.operator:
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
                        return _abstain(
                            criterion,
                            evidence,
                            "Temporal window could not be evaluated.",
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
                fact = f"{value} {unit or ''}".strip()
                enriched = Evidence(
                    criterion_id=ev.criterion_id,
                    doc_id=ev.doc_id,
                    quote=ev.quote,
                    normalized_fact=fact,
                )
                return _base_judgment(
                    criterion,
                    prediction="met" if cmp else "not_met",
                    rationale=f"Structured lab comparison: {fact} {criterion.operator} "
                    f"{criterion.threshold.value} {criterion.threshold.unit or ''}".strip(),
                    evidence=(enriched,),
                )
            return _abstain(
                criterion,
                evidence,
                "No in-window structured lab evidence found.",
            )

        if criterion.clinical_domain == "condition":
            return _judge_condition(criterion, evidence, docs)

        if criterion.clinical_domain == "medication":
            if (
                criterion.criterion_type == "inclusion"
                and is_prior_systemic_criterion(criterion.raw_text)
            ):
                oncology = _medication_hits(
                    criterion.criterion_id,
                    evidence,
                    docs,
                    drug_class="systemic_oncology",
                )
                if oncology:
                    return _base_judgment(
                        criterion,
                        prediction="not_met",
                        rationale="Prior systemic oncology therapy documented.",
                        evidence=oncology,
                    )
                med_evidence = _enrich_evidence(criterion.criterion_id, evidence, docs)
                if not med_evidence:
                    med_evidence = tuple(
                        _evidence_from_doc(criterion.criterion_id, doc)
                        for doc in corpus.documents
                        if doc.source_type == "medication"
                    )[:EVIDENCE_LIMIT]
                return _abstain(
                    criterion,
                    med_evidence,
                    "No systemic oncology therapy in medication list; "
                    "complete history not verified.",
                )

            if criterion.criterion_type == "exclusion" and is_anti_pd1_mention(criterion.raw_text):
                hits = _medication_hits(
                    criterion.criterion_id,
                    evidence,
                    docs,
                    drug_class="anti_pd1",
                )
                if hits:
                    return _base_judgment(
                        criterion,
                        prediction="met",
                        rationale="Anti-PD-1/PD-L1 agent documented.",
                        evidence=hits,
                    )
                return _abstain(
                    criterion,
                    evidence,
                    "No conclusive prior immunotherapy history found.",
                )

        if criterion.clinical_domain == "performance_status" and is_ecog_criterion(
            criterion.raw_text
        ):
            for ev in evidence:
                doc = docs.get(ev.doc_id)
                if doc is None:
                    continue
                value = doc.structured.get("value")
                if value is not None and "ecog" in doc.text.lower():
                    enriched = Evidence(
                        criterion_id=ev.criterion_id,
                        doc_id=ev.doc_id,
                        quote=ev.quote,
                        normalized_fact=f"ECOG {value}",
                    )
                    if float(value) in {0.0, 1.0}:
                        return _base_judgment(
                            criterion,
                            prediction="met",
                            rationale=f"ECOG performance status {value} (0 or 1 required).",
                            evidence=(enriched,),
                        )
                    return _base_judgment(
                        criterion,
                        prediction="not_met",
                        rationale=f"ECOG performance status {value} outside required 0–1.",
                        evidence=(enriched,),
                    )
            return _abstain(
                criterion,
                evidence,
                "No structured ECOG performance status found.",
            )

        if criterion.criterion_type == "exclusion" and criterion.requires_absence_evidence:
            return _abstain(
                criterion,
                evidence,
                "Exclusion requires explicit negative evidence; none found.",
            )

        return _abstain(
            criterion,
            evidence,
            "No deterministic rule applies; human review required.",
        )

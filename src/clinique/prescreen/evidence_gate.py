"""Evidence-provenance hard gate (quote fidelity + derived-fact sanity)."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import PatientCorpus, PrescreeningPacket
from .units import to_cells_per_ul


@dataclass(frozen=True)
class EvidenceViolation:
    criterion_id: str
    code: str
    message: str


class EvidenceProvenanceError(Exception):
    def __init__(self, violations: list[EvidenceViolation]):
        self.violations = violations
        joined = "; ".join(f"{v.criterion_id}: {v.message}" for v in violations)
        super().__init__(f"{len(violations)} evidence violation(s): {joined}")


def _requires_evidence(prediction: str) -> bool:
    return prediction in {"met", "not_met"}


def check_evidence_provenance(
    packet: PrescreeningPacket,
    corpus: PatientCorpus,
) -> list[EvidenceViolation]:
    doc_text = {doc.doc_id: doc.text for doc in corpus.documents}
    doc_structured = {doc.doc_id: doc.structured for doc in corpus.documents}
    violations: list[EvidenceViolation] = []

    for judgment in packet.judgments:
        if not _requires_evidence(judgment.prediction):
            continue
        criterion = next(
            (c for c in packet.criteria if c.criterion_id == judgment.criterion_id),
            None,
        )
        if criterion and criterion.clinical_domain == "demographic" and judgment.rationale:
            continue
        if not judgment.evidence:
            violations.append(
                EvidenceViolation(
                    judgment.criterion_id,
                    "missing_evidence",
                    f"{judgment.prediction} without evidence quote",
                )
            )
            continue
        for ev in judgment.evidence:
            text = doc_text.get(ev.doc_id, "")
            if ev.quote not in text:
                violations.append(
                    EvidenceViolation(
                        judgment.criterion_id,
                        "quote_fidelity",
                        f"quote not found verbatim in doc {ev.doc_id}",
                    )
                )
            if ev.normalized_fact:
                structured = doc_structured.get(ev.doc_id, {})
                value = structured.get("value")
                unit = structured.get("unit")
                if value is not None:
                    converted = to_cells_per_ul(float(value), unit)
                    if converted is not None and str(value) not in ev.normalized_fact:
                        # derived fact should mention source value or conversion
                        if str(int(converted)) not in ev.rationale and str(value) not in ev.quote:
                            violations.append(
                                EvidenceViolation(
                                    judgment.criterion_id,
                                    "derived_fact",
                                    "normalized_fact does not trace to structured value",
                                )
                            )
    return violations


def assert_evidence_provenance(packet: PrescreeningPacket, corpus: PatientCorpus) -> None:
    violations = check_evidence_provenance(packet, corpus)
    if violations:
        raise EvidenceProvenanceError(violations)

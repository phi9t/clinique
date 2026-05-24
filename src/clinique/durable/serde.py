"""Dict round-trip helpers for Temporal workflow payloads."""

from __future__ import annotations

from typing import Any

from clinique.prescreen.schemas import (
    AgeBound,
    Criterion,
    CriterionJudgment,
    Evidence,
    PatientCorpus,
    PrescreeningPacket,
    TemporalConstraint,
    Threshold,
    Trial,
)


def threshold_from_dict(raw: dict[str, Any] | None) -> Threshold | None:
    if raw is None:
        return None
    return Threshold(value=float(raw["value"]), unit=raw.get("unit"))


def temporal_constraint_from_dict(raw: dict[str, Any] | None) -> TemporalConstraint | None:
    if raw is None:
        return None
    return TemporalConstraint(
        window_value=int(raw["window_value"]),
        window_unit=str(raw["window_unit"]),
        anchor=str(raw.get("anchor", "enrollment")),
    )


def criterion_from_dict(raw: dict[str, Any]) -> Criterion:
    return Criterion(
        criterion_id=raw["criterion_id"],
        trial_id=raw["trial_id"],
        criterion_type=raw["criterion_type"],
        raw_text=raw["raw_text"],
        clinical_domain=raw.get("clinical_domain", "other"),
        operator=raw.get("operator"),
        threshold=threshold_from_dict(raw.get("threshold")),
        temporal_constraint=temporal_constraint_from_dict(raw.get("temporal_constraint")),
        requires_absence_evidence=bool(raw.get("requires_absence_evidence", False)),
        is_safety_critical=bool(raw.get("is_safety_critical", False)),
        ambiguity_flags=tuple(raw.get("ambiguity_flags", ())),
    )


def evidence_from_dict(raw: dict[str, Any]) -> Evidence:
    return Evidence(
        criterion_id=raw["criterion_id"],
        doc_id=raw["doc_id"],
        quote=raw["quote"],
        normalized_fact=raw.get("normalized_fact"),
    )


def judgment_from_dict(raw: dict[str, Any]) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_id=raw["criterion_id"],
        criterion_type=raw["criterion_type"],
        prediction=raw["prediction"],
        evidence=tuple(evidence_from_dict(e) for e in raw.get("evidence", [])),
        rationale=raw.get("rationale", ""),
        confidence=raw.get("confidence"),
        human_review_required=bool(raw.get("human_review_required", False)),
    )


def age_bound_from_dict(raw: dict[str, Any] | AgeBound) -> AgeBound:
    if isinstance(raw, AgeBound):
        return raw
    return AgeBound(raw=raw.get("raw"), years=raw.get("years"))


def trial_from_dict(raw: dict[str, Any]) -> Trial:
    return Trial(
        trial_id=raw["trial_id"],
        source=raw["source"],
        title=raw.get("title", ""),
        conditions=tuple(raw.get("conditions", ())),
        phase=raw.get("phase"),
        recruitment_status=raw.get("recruitment_status"),
        eligibility_text=raw.get("eligibility_text", ""),
        sex=raw.get("sex"),
        accepts_healthy_volunteers=raw.get("accepts_healthy_volunteers"),
        minimum_age=age_bound_from_dict(raw.get("minimum_age", {"raw": None, "years": None})),
        maximum_age=age_bound_from_dict(raw.get("maximum_age", {"raw": None, "years": None})),
        std_ages=tuple(raw.get("std_ages", ())),
        sponsor=raw.get("sponsor"),
        metadata=dict(raw.get("metadata", {})),
    )


def trial_to_dict(trial: Trial) -> dict[str, Any]:
    return trial.to_dict()


def corpus_to_dict(corpus: PatientCorpus) -> dict[str, Any]:
    return corpus.to_dict()


def corpus_from_dict(raw: dict[str, Any]) -> PatientCorpus:
    from clinique.prescreen.validation import corpus_from_dict as _corpus_from_dict

    return _corpus_from_dict(raw)


def packet_from_dict(raw: dict[str, Any]) -> PrescreeningPacket:
    return PrescreeningPacket(
        trial_id=raw["trial_id"],
        patient_id=raw["patient_id"],
        snapshot_date=raw.get("snapshot_date"),
        criteria=tuple(criterion_from_dict(c) for c in raw.get("criteria", [])),
        judgments=tuple(judgment_from_dict(j) for j in raw.get("judgments", [])),
        recommendation=raw["recommendation"],
        model=dict(raw.get("model", {})),
        tools=tuple(dict(t) for t in raw.get("tools", [])),
    )


def packet_to_dict(packet: PrescreeningPacket) -> dict[str, Any]:
    return packet.to_dict()

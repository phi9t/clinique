"""Frozen data contracts for PrescreenBench: case inputs, gold labels, and agent submissions.

Three artifacts make up a split (one JSONL each):

- ``cases.jsonl``  — :class:`BenchmarkCase`, the task binding (which trial + which patient).
- ``labels.jsonl`` — :class:`GoldLabel`, the adjudicated answer (held private for hidden splits).
- a submission ``predictions.jsonl`` — :class:`SubmissionPacket`, the agent's output per case.

The submission schema is intentionally *flatter* than the internal ``PrescreeningPacket`` (criteria
carry their prediction inline) so third-party agents can emit it without importing clinique types.
:func:`packet_to_submission` adapts the internal packet to this wire format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clinique.prescreen.schemas import PREDICTIONS, RECOMMENDATIONS, PrescreeningPacket

SUBMISSION_VERSION = "prescreenbench_v0"
_CRITERION_TYPES = frozenset({"inclusion", "exclusion"})


# ---------------------------------------------------------------------------
# Case inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    trial_id: str
    patient_id: str
    patient_source: str
    snapshot_date: str | None
    task: str = "end_to_end_packet"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BenchmarkCase:
        return cls(
            case_id=raw["case_id"],
            trial_id=raw["trial_id"],
            patient_id=raw["patient_id"],
            patient_source=raw.get("patient_source", "synthea"),
            snapshot_date=raw.get("snapshot_date"),
            task=raw.get("task", "end_to_end_packet"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "trial_id": self.trial_id,
            "patient_id": self.patient_id,
            "patient_source": self.patient_source,
            "snapshot_date": self.snapshot_date,
            "task": self.task,
        }


# ---------------------------------------------------------------------------
# Gold labels
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GoldEvidence:
    doc_id: str
    quote: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GoldEvidence:
        return cls(doc_id=raw["doc_id"], quote=raw["quote"])

    def to_dict(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "quote": self.quote}


@dataclass(frozen=True)
class GoldCriterionLabel:
    criterion_id: str
    label: str
    criterion_type: str
    clinical_domain: str = "other"
    is_safety_critical: bool = False
    gold_evidence: tuple[GoldEvidence, ...] = ()
    missing_information: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GoldCriterionLabel:
        return cls(
            criterion_id=raw["criterion_id"],
            label=raw["label"],
            criterion_type=raw["criterion_type"],
            clinical_domain=raw.get("clinical_domain", "other"),
            is_safety_critical=bool(raw.get("is_safety_critical", False)),
            gold_evidence=tuple(GoldEvidence.from_dict(e) for e in raw.get("gold_evidence", [])),
            missing_information=raw.get("missing_information"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "label": self.label,
            "criterion_type": self.criterion_type,
            "clinical_domain": self.clinical_domain,
            "is_safety_critical": self.is_safety_critical,
            "gold_evidence": [e.to_dict() for e in self.gold_evidence],
            "missing_information": self.missing_information,
        }


@dataclass(frozen=True)
class GoldLabel:
    case_id: str
    overall_label: str
    criterion_labels: tuple[GoldCriterionLabel, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GoldLabel:
        return cls(
            case_id=raw["case_id"],
            overall_label=raw["overall_label"],
            criterion_labels=tuple(
                GoldCriterionLabel.from_dict(c) for c in raw.get("criterion_labels", [])
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "overall_label": self.overall_label,
            "criterion_labels": [c.to_dict() for c in self.criterion_labels],
        }


# ---------------------------------------------------------------------------
# Agent submission
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PredEvidence:
    doc_id: str
    quote: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PredEvidence:
        return cls(doc_id=raw["doc_id"], quote=raw["quote"])

    def to_dict(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "quote": self.quote}


@dataclass(frozen=True)
class PredCriterion:
    criterion_id: str
    criterion_type: str
    prediction: str
    raw_text: str = ""
    clinical_domain: str = "other"
    evidence: tuple[PredEvidence, ...] = ()
    rationale: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PredCriterion:
        return cls(
            criterion_id=raw["criterion_id"],
            criterion_type=raw["criterion_type"],
            prediction=raw["prediction"],
            raw_text=raw.get("raw_text", ""),
            clinical_domain=raw.get("clinical_domain", "other"),
            evidence=tuple(PredEvidence.from_dict(e) for e in raw.get("evidence", [])),
            rationale=raw.get("rationale", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_type": self.criterion_type,
            "prediction": self.prediction,
            "raw_text": self.raw_text,
            "clinical_domain": self.clinical_domain,
            "evidence": [e.to_dict() for e in self.evidence],
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class SubmissionPacket:
    case_id: str
    overall_recommendation: str
    criteria: tuple[PredCriterion, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SubmissionPacket:
        return cls(
            case_id=raw["case_id"],
            overall_recommendation=raw["overall_recommendation"],
            criteria=tuple(PredCriterion.from_dict(c) for c in raw.get("criteria", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "overall_recommendation": self.overall_recommendation,
            "criteria": [c.to_dict() for c in self.criteria],
        }


def packet_to_submission(case_id: str, packet: PrescreeningPacket) -> SubmissionPacket:
    """Adapt an internal ``PrescreeningPacket`` (criteria + judgments) to the flat wire form."""
    criteria_by_id = {c.criterion_id: c for c in packet.criteria}
    preds: list[PredCriterion] = []
    for judgment in packet.judgments:
        crit = criteria_by_id.get(judgment.criterion_id)
        preds.append(
            PredCriterion(
                criterion_id=judgment.criterion_id,
                criterion_type=judgment.criterion_type,
                prediction=judgment.prediction,
                raw_text=crit.raw_text if crit else "",
                clinical_domain=crit.clinical_domain if crit else "other",
                evidence=tuple(PredEvidence(e.doc_id, e.quote) for e in judgment.evidence),
                rationale=judgment.rationale,
            )
        )
    return SubmissionPacket(
        case_id=case_id,
        overall_recommendation=packet.recommendation,
        criteria=tuple(preds),
    )


def validate_submission(raw: dict[str, Any]) -> list[str]:
    """Return a list of schema errors for one submission record (empty == valid).

    Feeds ``schema_valid_rate``; a malformed record is a hard-gate signal, not a crash.
    """
    errors: list[str] = []
    if not isinstance(raw, dict):
        return ["record is not an object"]
    if not raw.get("case_id"):
        errors.append("missing case_id")
    rec = raw.get("overall_recommendation")
    if rec not in RECOMMENDATIONS:
        errors.append(f"invalid overall_recommendation: {rec!r}")
    criteria = raw.get("criteria")
    if not isinstance(criteria, list):
        errors.append("criteria must be a list")
        return errors

    seen_criterion_ids: set[str] = set()
    for i, crit in enumerate(criteria):
        if not isinstance(crit, dict):
            errors.append(f"criteria[{i}] is not an object")
            continue
        criterion_id = crit.get("criterion_id")
        if not criterion_id:
            errors.append(f"criteria[{i}] missing criterion_id")
        elif criterion_id in seen_criterion_ids:
            errors.append(f"criteria[{i}] duplicate criterion_id: {criterion_id!r}")
        else:
            seen_criterion_ids.add(criterion_id)
        if crit.get("criterion_type") not in _CRITERION_TYPES:
            errors.append(f"criteria[{i}] invalid criterion_type: {crit.get('criterion_type')!r}")
        if crit.get("prediction") not in PREDICTIONS:
            errors.append(f"criteria[{i}] invalid prediction: {crit.get('prediction')!r}")
        for j, ev in enumerate(crit.get("evidence", []) or []):
            if not isinstance(ev, dict):
                errors.append(f"criteria[{i}].evidence[{j}] must be an object")
                continue
            if not isinstance(ev.get("doc_id"), str):
                errors.append(f"criteria[{i}].evidence[{j}] doc_id must be a string")
            if not isinstance(ev.get("quote"), str):
                errors.append(f"criteria[{i}].evidence[{j}] quote must be a string")
    return errors

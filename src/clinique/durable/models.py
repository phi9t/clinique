"""Pydantic wire models for Temporal prescreen payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from clinique.prescreen.schemas import (
    AgeBound,
    Criterion,
    CriterionJudgment,
    Evidence,
    PatientCorpus,
    PatientDocument,
    PrescreeningPacket,
    TemporalConstraint,
    Threshold,
    Trial,
)


class ThresholdModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: float
    unit: str | None = None

    def to_domain(self) -> Threshold:
        return Threshold(value=self.value, unit=self.unit)

    @classmethod
    def from_domain(cls, value: Threshold) -> ThresholdModel:
        return cls(value=value.value, unit=value.unit)


class TemporalConstraintModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    window_value: int
    window_unit: str
    anchor: str = "enrollment"

    def to_domain(self) -> TemporalConstraint:
        return TemporalConstraint(
            window_value=self.window_value,
            window_unit=self.window_unit,
            anchor=self.anchor,
        )

    @classmethod
    def from_domain(cls, value: TemporalConstraint) -> TemporalConstraintModel:
        return cls(
            window_value=value.window_value,
            window_unit=value.window_unit,
            anchor=value.anchor,
        )


class AgeBoundModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw: str | None = None
    years: float | None = None

    def to_domain(self) -> AgeBound:
        return AgeBound(raw=self.raw, years=self.years)

    @classmethod
    def from_domain(cls, value: AgeBound) -> AgeBoundModel:
        return cls(raw=value.raw, years=value.years)


class CriterionModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: str
    trial_id: str
    criterion_type: str
    raw_text: str
    clinical_domain: str = "other"
    operator: str | None = None
    threshold: ThresholdModel | None = None
    temporal_constraint: TemporalConstraintModel | None = None
    requires_absence_evidence: bool = False
    is_safety_critical: bool = False
    ambiguity_flags: tuple[str, ...] = ()

    def to_domain(self) -> Criterion:
        return Criterion(
            criterion_id=self.criterion_id,
            trial_id=self.trial_id,
            criterion_type=self.criterion_type,
            raw_text=self.raw_text,
            clinical_domain=self.clinical_domain,
            operator=self.operator,
            threshold=self.threshold.to_domain() if self.threshold else None,
            temporal_constraint=(
                self.temporal_constraint.to_domain() if self.temporal_constraint else None
            ),
            requires_absence_evidence=self.requires_absence_evidence,
            is_safety_critical=self.is_safety_critical,
            ambiguity_flags=self.ambiguity_flags,
        )

    @classmethod
    def from_domain(cls, value: Criterion) -> CriterionModel:
        return cls(
            criterion_id=value.criterion_id,
            trial_id=value.trial_id,
            criterion_type=value.criterion_type,
            raw_text=value.raw_text,
            clinical_domain=value.clinical_domain,
            operator=value.operator,
            threshold=ThresholdModel.from_domain(value.threshold) if value.threshold else None,
            temporal_constraint=(
                TemporalConstraintModel.from_domain(value.temporal_constraint)
                if value.temporal_constraint
                else None
            ),
            requires_absence_evidence=value.requires_absence_evidence,
            is_safety_critical=value.is_safety_critical,
            ambiguity_flags=value.ambiguity_flags,
        )


class EvidenceModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: str
    doc_id: str
    quote: str
    normalized_fact: str | None = None

    def to_domain(self) -> Evidence:
        return Evidence(
            criterion_id=self.criterion_id,
            doc_id=self.doc_id,
            quote=self.quote,
            normalized_fact=self.normalized_fact,
        )

    @classmethod
    def from_domain(cls, value: Evidence) -> EvidenceModel:
        return cls(
            criterion_id=value.criterion_id,
            doc_id=value.doc_id,
            quote=value.quote,
            normalized_fact=value.normalized_fact,
        )


class CriterionJudgmentModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: str
    criterion_type: str
    prediction: str
    evidence: tuple[EvidenceModel, ...] = ()
    rationale: str = ""
    confidence: float | None = None
    human_review_required: bool = False

    def to_domain(self) -> CriterionJudgment:
        return CriterionJudgment(
            criterion_id=self.criterion_id,
            criterion_type=self.criterion_type,
            prediction=self.prediction,
            evidence=tuple(e.to_domain() for e in self.evidence),
            rationale=self.rationale,
            confidence=self.confidence,
            human_review_required=self.human_review_required,
        )

    @classmethod
    def from_domain(cls, value: CriterionJudgment) -> CriterionJudgmentModel:
        return cls(
            criterion_id=value.criterion_id,
            criterion_type=value.criterion_type,
            prediction=value.prediction,
            evidence=tuple(EvidenceModel.from_domain(e) for e in value.evidence),
            rationale=value.rationale,
            confidence=value.confidence,
            human_review_required=value.human_review_required,
        )


class PatientDocumentModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc_id: str
    patient_id: str
    date: str | None = None
    source_type: str
    text: str
    structured: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> PatientDocument:
        return PatientDocument(
            doc_id=self.doc_id,
            patient_id=self.patient_id,
            date=self.date,
            source_type=self.source_type,
            text=self.text,
            structured=dict(self.structured),
        )

    @classmethod
    def from_domain(cls, value: PatientDocument) -> PatientDocumentModel:
        return cls(
            doc_id=value.doc_id,
            patient_id=value.patient_id,
            date=value.date,
            source_type=value.source_type,
            text=value.text,
            structured=dict(value.structured),
        )


class TrialModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_id: str
    source: str
    title: str = ""
    conditions: tuple[str, ...] = ()
    phase: str | None = None
    recruitment_status: str | None = None
    eligibility_text: str = ""
    sex: str | None = None
    accepts_healthy_volunteers: bool | None = None
    minimum_age: AgeBoundModel = Field(default_factory=AgeBoundModel)
    maximum_age: AgeBoundModel = Field(default_factory=AgeBoundModel)
    std_ages: tuple[str, ...] = ()
    sponsor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> Trial:
        return Trial(
            trial_id=self.trial_id,
            source=self.source,
            title=self.title,
            conditions=self.conditions,
            phase=self.phase,
            recruitment_status=self.recruitment_status,
            eligibility_text=self.eligibility_text,
            sex=self.sex,
            accepts_healthy_volunteers=self.accepts_healthy_volunteers,
            minimum_age=self.minimum_age.to_domain(),
            maximum_age=self.maximum_age.to_domain(),
            std_ages=self.std_ages,
            sponsor=self.sponsor,
            metadata=dict(self.metadata),
        )

    @classmethod
    def from_domain(cls, value: Trial) -> TrialModel:
        return cls(
            trial_id=value.trial_id,
            source=value.source,
            title=value.title,
            conditions=value.conditions,
            phase=value.phase,
            recruitment_status=value.recruitment_status,
            eligibility_text=value.eligibility_text,
            sex=value.sex,
            accepts_healthy_volunteers=value.accepts_healthy_volunteers,
            minimum_age=AgeBoundModel.from_domain(value.minimum_age),
            maximum_age=AgeBoundModel.from_domain(value.maximum_age),
            std_ages=value.std_ages,
            sponsor=value.sponsor,
            metadata=dict(value.metadata),
        )


class PatientCorpusModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    patient_id: str
    snapshot_date: str | None = None
    source: str
    demographics: dict[str, Any] = Field(default_factory=dict)
    documents: tuple[PatientDocumentModel, ...] = ()

    def to_domain(self) -> PatientCorpus:
        return PatientCorpus(
            patient_id=self.patient_id,
            snapshot_date=self.snapshot_date,
            source=self.source,
            demographics=dict(self.demographics),
            documents=tuple(d.to_domain() for d in self.documents),
        )

    @classmethod
    def from_domain(cls, value: PatientCorpus) -> PatientCorpusModel:
        return cls(
            patient_id=value.patient_id,
            snapshot_date=value.snapshot_date,
            source=value.source,
            demographics=dict(value.demographics),
            documents=tuple(PatientDocumentModel.from_domain(d) for d in value.documents),
        )


class PrescreeningPacketModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_id: str
    patient_id: str
    snapshot_date: str | None = None
    criteria: tuple[CriterionModel, ...] = ()
    judgments: tuple[CriterionJudgmentModel, ...] = ()
    recommendation: str
    model: dict[str, Any] = Field(default_factory=dict)
    tools: tuple[dict[str, str], ...] = ()

    def to_domain(self) -> PrescreeningPacket:
        return PrescreeningPacket(
            trial_id=self.trial_id,
            patient_id=self.patient_id,
            snapshot_date=self.snapshot_date,
            criteria=tuple(c.to_domain() for c in self.criteria),
            judgments=tuple(j.to_domain() for j in self.judgments),
            recommendation=self.recommendation,
            model=dict(self.model),
            tools=self.tools,
        )

    @classmethod
    def from_domain(cls, value: PrescreeningPacket) -> PrescreeningPacketModel:
        return cls(
            trial_id=value.trial_id,
            patient_id=value.patient_id,
            snapshot_date=value.snapshot_date,
            criteria=tuple(CriterionModel.from_domain(c) for c in value.criteria),
            judgments=tuple(CriterionJudgmentModel.from_domain(j) for j in value.judgments),
            recommendation=value.recommendation,
            model=dict(value.model),
            tools=value.tools,
        )


class ScreenPatientInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial: TrialModel
    corpus: PatientCorpusModel
    append_ledger: bool = False
    ledger_path: str | None = None
    judge: str = "rule"


class BuildPacketInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial: TrialModel
    corpus: PatientCorpusModel
    criteria: tuple[CriterionModel, ...]
    judgments: tuple[CriterionJudgmentModel, ...]
    recommendation: str
    judge: str = "rule"


class GoldJudgmentModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    criterion_id: str
    prediction: str


class EvalCaseModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    trial_id: str
    patient_id: str
    snapshot_date: str | None = None
    patient_source: str = "synthea"
    gold_judgments: tuple[GoldJudgmentModel, ...] = ()


class LoadEvalInputsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    cases: tuple[EvalCaseModel, ...]
    trials: tuple[TrialModel, ...]
    corpora_by_source: dict[str, tuple[PatientCorpusModel, ...]]


class ResolveScreenCaseInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    case: EvalCaseModel
    trials: tuple[TrialModel, ...]
    corpora_by_source: dict[str, tuple[PatientCorpusModel, ...]]


class ResolvedCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial: TrialModel
    corpus: PatientCorpusModel
    gold_judgments: tuple[GoldJudgmentModel, ...] = ()


class EvalCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    gold_judgments: tuple[GoldJudgmentModel, ...] = ()
    packet: PrescreeningPacketModel | None = None
    corpus: PatientCorpusModel | None = None
    error: str | None = None


class ScoreEvalInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_results: tuple[EvalCaseResult, ...]
    reports_dir: str = "reports/prescreen"


class EvalReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_path: str
    cases_run: int
    criterion_total: int
    criterion_correct: int
    criterion_accuracy: float
    evidence_violations: int
    exclusion_false_negatives: int
    errors: tuple[str, ...] = ()


class BatchEvalInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    cases_path: str
    trials_path: str
    synthea_patients_path: str | None = None
    pmc_patients_path: str | None = None
    mimic_patients_path: str | None = None
    reports_dir: str = "reports/prescreen"
    judge: str = "rule"

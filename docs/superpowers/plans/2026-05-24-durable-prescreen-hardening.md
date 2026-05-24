# Durable Prescreen Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Temporal prescreen layer with Pydantic wire types, parallel criterion fan-out, real batch-eval concurrency, CLI dedup, and session-scoped E2E fixtures — while keeping `prescreen/` stdlib-only.

**Architecture:** Pydantic v2 models in `durable/models.py` bridge to frozen prescreen dataclasses at activity boundaries; `pydantic_data_converter` registered on client/worker/tests. Workflows use `asyncio.gather` for parallel criteria and batch cases. Single-activity orchestrator remains rejected.

**Tech Stack:** Python 3.12, temporalio ≥1.9, pydantic ≥2, pytest, pytest-asyncio, ruff.

**Spec:** [2026-05-24-durable-prescreen-hardening-design.md](../specs/2026-05-24-durable-prescreen-hardening-design.md)

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `pyproject.toml` | Add `pydantic>=2` to `temporal` group |
| Create | `src/clinique/durable/converter.py` | `DATA_CONVERTER = pydantic_data_converter` |
| Create | `src/clinique/durable/models.py` | Pydantic wire models + domain bridges |
| Create | `src/clinique/durable/cli_runtime.py` | Shared Temporal import/connect helper |
| Delete | `src/clinique/durable/serde.py` | Replaced by models |
| Modify | `src/clinique/durable/activities/prescreen.py` | Typed activity signatures |
| Modify | `src/clinique/durable/activities/io.py` | Typed eval I/O activities |
| Modify | `src/clinique/durable/workflows/prescreen.py` | Pydantic I/O + parallel criteria |
| Modify | `src/clinique/durable/workflows/eval.py` | Pydantic I/O + parallel batch cases |
| Modify | `src/clinique/durable/client.py` | `data_converter=DATA_CONVERTER` |
| Modify | `src/clinique/durable/worker.py` | `data_converter=DATA_CONVERTER` |
| Modify | `src/clinique/cli/prescreen.py` | Use `cli_runtime` |
| Create | `tests/test_durable_models.py` | Domain ↔ Pydantic round-trip tests |
| Modify | `tests/conftest.py` | Session-scoped Temporal fixtures |
| Modify | `tests/durable_e2e_harness.py` | Pass `DATA_CONVERTER` to test Worker |
| Modify | `tests/test_durable_prescreen.py` | Typed workflow inputs |
| Modify | `tests/test_durable_prescreen_e2e.py` | Session fixtures |
| Create | `tests/test_durable_batch_concurrency.py` | Batch gather smoke test |
| Modify | `docs/design/temporal-prescreen.md` | Parallelism, Pydantic, non-goal note |
| Modify | `CLAUDE.md`, `AGENTS.md` | pydantic in temporal group |

---

### Task 1: Pydantic dependency and converter module

**Files:**
- Modify: `pyproject.toml`
- Create: `src/clinique/durable/converter.py`

- [ ] **Step 1: Add pydantic to temporal group**

In `pyproject.toml`, update the `temporal` dependency group:

```toml
temporal = [
    "temporalio>=1.9",
    "pydantic>=2",
    "pytest-asyncio>=0.24",
]
```

Run: `uv sync --group temporal`

- [ ] **Step 2: Create converter module**

Create `src/clinique/durable/converter.py`:

```python
"""Temporal data converter for prescreen Pydantic payloads."""

from __future__ import annotations

from temporalio.contrib.pydantic import pydantic_data_converter

DATA_CONVERTER = pydantic_data_converter

__all__ = ["DATA_CONVERTER"]
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock src/clinique/durable/converter.py
git commit -m "feat(durable): add pydantic dependency and data converter"
```

---

### Task 2: Record models and round-trip tests (TDD)

**Files:**
- Create: `src/clinique/durable/models.py` (record models only — first slice)
- Create: `tests/test_durable_models.py`
- Test: `tests/test_durable_prescreen.py` fixtures (unchanged domain fixtures)

- [ ] **Step 1: Write failing round-trip tests**

Create `tests/test_durable_models.py`:

```python
"""Pydantic durable models round-trip against prescreen domain types."""

from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.orchestrator import PrescreenOrchestrator
from clinique.durable.models import (
    CriterionJudgmentModel,
    CriterionModel,
    PatientCorpusModel,
    PrescreeningPacketModel,
    TrialModel,
)

TRIALS = "tests/fixtures/prescreen/trials.jsonl"
SYNTHEA = "tests/fixtures/prescreen/synthea"


@pytest.fixture
def trial_and_corpus():
    trial = load_recorded_studies(TRIALS)[0]
    tables = read_synthea_csv_dir(SYNTHEA)
    corpus = normalize_synthea_corpus(tables, snapshot_date="2026-03-01")[0]
    return trial, corpus


def test_trial_model_roundtrip():
    trial = load_recorded_studies(TRIALS)[0]
    wire = TrialModel.from_domain(trial)
    assert TrialModel.model_validate(trial.to_dict()) == wire
    assert wire.to_domain() == trial


def test_corpus_model_roundtrip(trial_and_corpus):
    _, corpus = trial_and_corpus
    wire = PatientCorpusModel.from_domain(corpus)
    assert PatientCorpusModel.model_validate(corpus.to_dict()) == wire
    assert wire.to_domain() == corpus


def test_packet_model_roundtrip(trial_and_corpus):
    trial, corpus = trial_and_corpus
    packet = PrescreenOrchestrator().screen(trial, corpus)
    wire = PrescreeningPacketModel.from_domain(packet)
    assert PrescreeningPacketModel.model_validate(packet.to_dict()) == wire
    assert wire.to_domain() == packet


def test_criterion_and_judgment_roundtrip(trial_and_corpus):
    trial, corpus = trial_and_corpus
    packet = PrescreenOrchestrator().screen(trial, corpus)
    for criterion in packet.criteria:
        cwire = CriterionModel.from_domain(criterion)
        assert CriterionModel.model_validate(criterion.to_dict()).to_domain() == criterion
    for judgment in packet.judgments:
        assert (
            CriterionJudgmentModel.model_validate(judgment.to_dict()).to_domain() == judgment
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_durable_models.py -v`

Expected: FAIL — `ModuleNotFoundError: clinique.durable.models`

- [ ] **Step 3: Implement record models in `models.py`**

Create `src/clinique/durable/models.py` with nested record models. Each implements `to_domain()` and `from_domain()`. Use `model_config = ConfigDict(frozen=True)` on all models.

```python
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
    minimum_age: AgeBoundModel = Field(default_factory=lambda: AgeBoundModel())
    maximum_age: AgeBoundModel = Field(default_factory=lambda: AgeBoundModel())
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
```

Append composite models at the bottom of the same file (Task 3 content can be merged here):

```python
class ScreenPatientInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    trial: TrialModel
    corpus: PatientCorpusModel
    append_ledger: bool = False
    ledger_path: str | None = None


class BuildPacketInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    trial: TrialModel
    corpus: PatientCorpusModel
    criteria: tuple[CriterionModel, ...]
    judgments: tuple[CriterionJudgmentModel, ...]
    recommendation: str


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
```

- [ ] **Step 4: Run round-trip tests**

Run: `uv run pytest tests/test_durable_models.py -v`

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/clinique/durable/models.py tests/test_durable_models.py
git commit -m "feat(durable): add Pydantic wire models with domain bridges"
```

---

### Task 3: Migrate prescreen activities to Pydantic

**Files:**
- Modify: `src/clinique/durable/activities/prescreen.py`

- [ ] **Step 1: Rewrite activity signatures**

Replace dict-based signatures with Pydantic types. Example final `prescreen.py` activity bodies:

```python
@activity.defn
def atomize_trial(trial: TrialModel) -> list[CriterionModel]:
    domain = trial.to_domain()
    return [CriterionModel.from_domain(c) for c in ReferenceAtomizer().atomize(domain)]


@activity.defn
def evaluate_criterion(
    criterion: CriterionModel,
    corpus: PatientCorpusModel,
) -> CriterionJudgmentModel:
    crit = criterion.to_domain()
    corp = corpus.to_domain()
    evidence = retrieve(crit, corp)
    judgment = RuleJudge().judge(crit, evidence, corp)
    return CriterionJudgmentModel.from_domain(judgment)


@activity.defn
def aggregate_judgments(judgments: list[CriterionJudgmentModel]) -> str:
    domain = tuple(j.to_domain() for j in judgments)
    return aggregate(domain)


@activity.defn
def build_packet(payload: BuildPacketInput) -> PrescreeningPacketModel:
    trial = payload.trial.to_domain()
    corpus = payload.corpus.to_domain()
    tools = default_prescreen_tools()
    packet = PrescreeningPacket(
        trial_id=trial.trial_id,
        patient_id=corpus.patient_id,
        snapshot_date=corpus.snapshot_date,
        criteria=tuple(c.to_domain() for c in payload.criteria),
        judgments=tuple(j.to_domain() for j in payload.judgments),
        recommendation=payload.recommendation,
        model={"atomizer": tools[0], "judge": tools[1]},
        tools=tuple(tools),
    )
    return PrescreeningPacketModel.from_domain(packet)


@activity.defn
def assert_evidence_provenance_activity(
    packet: PrescreeningPacketModel,
    corpus: PatientCorpusModel,
) -> None:
    try:
        assert_evidence_provenance(packet.to_domain(), corpus.to_domain())
    except EvidenceProvenanceError as exc:
        raise ApplicationError(
            str(exc), type="EvidenceProvenanceError", non_retryable=True
        ) from exc


@activity.defn
def append_ledger(packet: PrescreeningPacketModel, ledger_path: str) -> str:
    domain = packet.to_domain()
    ledger = ProvenanceLedger(ledger_path)
    ref = packet_fingerprint(domain)
    ledger.append(
        LedgerRecord(
            capability="prescreen",
            inputs=[domain.trial_id, domain.patient_id],
            model=dict(domain.model),
            tools=list(domain.tools),
            output_ref=ref,
            human_review=HumanReview(required=True, status="pending"),
        )
    )
    return ref


@activity.defn
def resolve_screen_case(payload: ResolveScreenCaseInput) -> ResolvedCase:
    case = payload.case
    trial = next((t for t in payload.trials if t.trial_id == case.trial_id), None)
    if trial is None:
        raise ValueError(f"missing trial {case.trial_id}")
    corpora = payload.corpora_by_source.get(case.patient_source, ())
    corpus = next((c for c in corpora if c.patient_id == case.patient_id), None)
    if corpus is None:
        raise ValueError(f"missing patient {case.patient_id} source={case.patient_source}")
    if case.snapshot_date and corpus.snapshot_date != case.snapshot_date:
        corpus = PatientCorpusModel(
            patient_id=corpus.patient_id,
            snapshot_date=case.snapshot_date,
            source=corpus.source,
            demographics=corpus.demographics,
            documents=corpus.documents,
        )
    return ResolvedCase(trial=trial, corpus=corpus, gold_judgments=case.gold_judgments)
```

Remove all imports from `clinique.durable.serde`.

- [ ] **Step 2: Run offline activity tests**

Run: `uv run pytest tests/test_durable_prescreen.py::test_atomize_activity_offline tests/test_durable_prescreen.py::test_evaluate_criterion_activity_offline -v`

Expected: FAIL until workflows/tests updated — proceed to Task 4–6, then re-run full suite.

- [ ] **Step 3: Commit**

```bash
git add src/clinique/durable/activities/prescreen.py
git commit -m "refactor(durable): type prescreen activities with Pydantic models"
```

---

### Task 4: Migrate I/O activities to Pydantic

**Files:**
- Modify: `src/clinique/durable/activities/io.py`

- [ ] **Step 1: Rewrite `load_eval_inputs` and `score_eval_results`**

```python
@activity.defn
def load_eval_inputs(payload: BatchEvalInput) -> LoadEvalInputsResult:
    cases = load_eval_cases(payload.cases_path)
    trials = tuple(
        TrialModel.from_domain(t) for t in load_recorded_studies(payload.trials_path)
    )
    corpora_by_source: dict[str, tuple[PatientCorpusModel, ...]] = {}
    if payload.synthea_patients_path:
        corpora_by_source["synthea"] = tuple(
            PatientCorpusModel.from_domain(c)
            for c in load_patient_corpora(payload.synthea_patients_path, source="synthea")
        )
    if payload.pmc_patients_path:
        corpora_by_source["pmc"] = tuple(
            PatientCorpusModel.from_domain(c)
            for c in load_patient_corpora(payload.pmc_patients_path, source="pmc")
        )
    if payload.mimic_patients_path:
        corpora_by_source["mimic"] = tuple(
            PatientCorpusModel.from_domain(c)
            for c in load_patient_corpora(payload.mimic_patients_path, source="mimic")
        )
    return LoadEvalInputsResult(
        cases=tuple(
            EvalCaseModel(
                case_id=c.trial_id + "/" + c.patient_id,
                trial_id=c.trial_id,
                patient_id=c.patient_id,
                snapshot_date=c.snapshot_date,
                patient_source=c.patient_source,
                gold_judgments=tuple(
                    GoldJudgmentModel(criterion_id=g["criterion_id"], prediction=g["prediction"])
                    for g in c.gold_judgments
                ),
            )
            for c in cases
        ),
        trials=trials,
        corpora_by_source=corpora_by_source,
    )


@activity.defn
def score_eval_results(payload: ScoreEvalInput) -> EvalReport:
    metrics = EvalMetrics()
    for item in payload.case_results:
        if item.error:
            metrics.errors.append(item.error)
            continue
        if item.packet is None:
            metrics.errors.append(f"missing packet for {item.case_id}")
            continue
        metrics.cases_run += 1
        packet = item.packet.to_domain()
        if item.corpus is not None:
            metrics.evidence_violations += len(
                check_evidence_provenance(packet, item.corpus.to_domain())
            )
        gold = {g.criterion_id: g.prediction for g in item.gold_judgments}
        pred_by_id = {j.criterion_id: j for j in packet.judgments}
        for cid, expected in gold.items():
            metrics.criterion_total += 1
            actual = pred_by_id.get(cid)
            if actual and actual.prediction == expected:
                metrics.criterion_correct += 1
            elif (
                actual
                and actual.criterion_type == "exclusion"
                and actual.prediction == "not_met"
                and expected == "unknown"
            ):
                metrics.exclusion_false_negatives += 1
    report_dict = metrics.to_dict()
    out_dir = Path(payload.reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "l0-eval-temporal.json"
    out_path.write_text(json.dumps(report_dict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EvalReport(report_path=str(out_path), errors=tuple(metrics.errors), **report_dict)
```

Note: `EvalReport` needs fields matching `metrics.to_dict()` keys (`cases_run`, `criterion_total`, etc.).

- [ ] **Step 2: Commit**

```bash
git add src/clinique/durable/activities/io.py
git commit -m "refactor(durable): type eval I/O activities with Pydantic models"
```

---

### Task 5: Migrate workflows, client, and worker

**Files:**
- Modify: `src/clinique/durable/workflows/prescreen.py`
- Modify: `src/clinique/durable/workflows/eval.py`
- Modify: `src/clinique/durable/client.py`
- Modify: `src/clinique/durable/worker.py`
- Delete: `src/clinique/durable/serde.py`

- [ ] **Step 1: Update `ScreenPatientWorkflow` (typed, sequential first — parallelism in Task 6)**

In `workflows/prescreen.py`:

- Remove `ScreenPatientInput` dataclass (now in `models.py`); import from `clinique.durable.models`
- Change `run` signature to accept `ScreenPatientInput` only (drop dict coersion branch)
- Pass `BuildPacketInput(...)` to `build_packet`
- Return `PrescreeningPacketModel` (Temporal serializes; CLI converts via `.model_dump()` for JSON output)

```python
@workflow.defn
class ScreenPatientWorkflow:
    @workflow.run
    async def run(self, data: ScreenPatientInput) -> PrescreeningPacketModel:
        retry = RetryPolicy(maximum_attempts=ACTIVITY_RETRY_MAX)
        gate_retry = RetryPolicy(maximum_attempts=GATE_RETRY_MAX)

        criteria = await workflow.execute_activity(atomize_trial, data.trial, ...)
        judgments: list[CriterionJudgmentModel] = []
        for criterion in criteria:
            judgments.append(
                await workflow.execute_activity(
                    evaluate_criterion, args=[criterion, data.corpus], ...
                )
            )
        recommendation = await workflow.execute_activity(aggregate_judgments, judgments, ...)
        packet = await workflow.execute_activity(
            build_packet,
            BuildPacketInput(
                trial=data.trial,
                corpus=data.corpus,
                criteria=tuple(criteria),
                judgments=tuple(judgments),
                recommendation=recommendation,
            ),
            ...,
        )
        await workflow.execute_activity(
            assert_evidence_provenance_activity, args=[packet, data.corpus], ...
        )
        if data.append_ledger and data.ledger_path:
            await workflow.execute_activity(append_ledger, args=[packet, data.ledger_path], ...)
        return packet
```

- [ ] **Step 2: Update `BatchEvalWorkflow`**

In `workflows/eval.py`:

- Import `BatchEvalInput`, `EvalCaseResult`, `ScoreEvalInput` from `models.py`
- Remove dataclass `BatchEvalInput` from this file
- `load_eval_inputs` receives `BatchEvalInput` directly
- `_run_case` returns `EvalCaseResult`
- `score_eval_results` receives `ScoreEvalInput(case_results=tuple(case_results), ...)`

- [ ] **Step 3: Wire `DATA_CONVERTER` in client and worker**

`client.py`:

```python
from clinique.durable.converter import DATA_CONVERTER

async def connect_client(host: str = DEFAULT_HOST) -> Client:
    return await Client.connect(host, data_converter=DATA_CONVERTER)
```

Update `execute_screen` / `execute_batch_eval` signatures to use Pydantic models. CLI prints `result.model_dump()` instead of raw dict.

`worker.py`:

```python
from clinique.durable.converter import DATA_CONVERTER

async def run_worker(...):
    client = await Client.connect(host, data_converter=DATA_CONVERTER)
    worker = Worker(..., data_converter=DATA_CONVERTER, ...)
```

- [ ] **Step 4: Delete `serde.py` and fix imports**

Run: `rg 'durable\.serde|from clinique\.durable\.serde' src tests`

Replace all usages with `models` imports. Delete `src/clinique/durable/serde.py`.

- [ ] **Step 5: Update durable tests for typed inputs**

In `tests/test_durable_prescreen.py` and `tests/test_durable_prescreen_e2e.py`:

```python
from clinique.durable.models import (
    PatientCorpusModel,
    PrescreeningPacketModel,
    ScreenPatientInput,
    TrialModel,
)

# Replace trial_to_dict/corpus_to_dict with:
ScreenPatientInput(
    trial=TrialModel.from_domain(trial),
    corpus=PatientCorpusModel.from_domain(corpus),
)

# Replace packet_from_dict(result) with:
result if isinstance(result, PrescreeningPacketModel) else PrescreeningPacketModel.model_validate(result)
packet = result  # when workflow returns PrescreeningPacketModel
packet_fingerprint(packet.to_domain())
```

Update `tests/durable_e2e_harness.py` `run_with_worker` to pass `data_converter=DATA_CONVERTER` to `Worker(...)`.

- [ ] **Step 6: Run durable test suite**

Run: `uv run pytest tests/test_durable_models.py tests/test_durable_prescreen.py tests/test_durable_prescreen_e2e.py -v`

Expected: PASS (may need gold_judgments dict access fixes in tests)

- [ ] **Step 7: Commit**

```bash
git add src/clinique/durable/ tests/
git rm src/clinique/durable/serde.py
git commit -m "refactor(durable): migrate workflows and client to Pydantic payloads"
```

---

### Task 6: Parallel criterion fan-out

**Files:**
- Modify: `src/clinique/durable/workflows/prescreen.py`

- [ ] **Step 1: Add `import asyncio` and replace sequential loop**

```python
import asyncio

judgments = list(
    await asyncio.gather(
        *[
            workflow.execute_activity(
                evaluate_criterion,
                args=[criterion, data.corpus],
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=retry,
            )
            for criterion in criteria
        ]
    )
)
```

- [ ] **Step 2: Run parity and determinism tests**

Run: `uv run pytest tests/test_durable_prescreen.py::test_screen_workflow_matches_sync_orchestrator tests/test_durable_prescreen.py::test_screen_workflow_is_deterministic -v`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/clinique/durable/workflows/prescreen.py
git commit -m "feat(durable): parallel criterion evaluation via asyncio.gather"
```

---

### Task 7: Real batch-eval concurrency

**Files:**
- Modify: `src/clinique/durable/workflows/eval.py`
- Create: `tests/test_durable_batch_concurrency.py`

- [ ] **Step 1: Write concurrency smoke test**

Create `tests/test_durable_batch_concurrency.py`:

```python
"""Verify BatchEvalWorkflow runs cases concurrently within a batch."""

from __future__ import annotations

import asyncio
import uuid

import pytest

pytest.importorskip("temporalio")

from temporalio import activity
from temporalio.testing import WorkflowEnvironment

from clinique.durable.activities import ALL_ACTIVITIES
from clinique.durable.activities.prescreen import resolve_screen_case
from clinique.durable.models import BatchEvalInput, EvalCaseModel, LoadEvalInputsResult
from clinique.durable.workflows.eval import BatchEvalWorkflow
from durable_e2e_harness import run_with_worker


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_batch_eval_runs_cases_concurrently(monkeypatch):
    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    @activity.defn(name="resolve_screen_case")
    async def slow_resolve(payload):
        nonlocal in_flight, max_in_flight
        async with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        async with lock:
            in_flight -= 1
        return resolve_screen_case(payload)

    # Stub load_eval_inputs to return 3 cases without disk I/O
    @activity.defn(name="load_eval_inputs")
    async def stub_load(_payload: BatchEvalInput) -> LoadEvalInputsResult:
        case = EvalCaseModel(
            case_id="NCT/X",
            trial_id="NCT02578680",
            patient_id="P1",
            snapshot_date="2026-03-01",
        )
        return LoadEvalInputsResult(cases=(case, case, case), trials=(), corpora_by_source={})

    activities = [
        a
        for a in ALL_ACTIVITIES
        if getattr(a, "__name__", "") not in {"resolve_screen_case", "load_eval_inputs"}
    ] + [slow_resolve, stub_load]

    async with await WorkflowEnvironment.start_local() as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                BatchEvalWorkflow.run,
                BatchEvalInput(
                    cases_path="unused",
                    trials_path="unused",
                    reports_dir="/tmp/clinique-batch-concurrency",
                ),
                id=str(uuid.uuid4()),
                task_queue=task_queue,
            )

        await run_with_worker(env.client, [BatchEvalWorkflow], activities, run)

    assert max_in_flight >= 2
```

Adjust stub to include minimal trial/corpus data so child workflows can start, or mock child workflow — if child workflow makes test too heavy, assert concurrency at resolve activity only with `BATCH_EVAL_CONCURRENCY=3` monkeypatched.

- [ ] **Step 2: Replace sequential batch loop with gather**

In `workflows/eval.py`:

```python
import asyncio

for batch_start in range(0, len(cases), BATCH_EVAL_CONCURRENCY):
    batch = cases[batch_start : batch_start + BATCH_EVAL_CONCURRENCY]
    batch_results = list(
        await asyncio.gather(
            *[self._run_case(case, inputs, parent_id, retry) for case in batch]
        )
    )
    case_results.extend(batch_results)
```

Update `_run_case` to return `EvalCaseResult(...)` Pydantic model.

- [ ] **Step 3: Run batch tests**

Run: `uv run pytest tests/test_durable_batch_concurrency.py tests/test_durable_prescreen_e2e.py::test_batch_eval_collects_missing_patient_errors -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/clinique/durable/workflows/eval.py tests/test_durable_batch_concurrency.py
git commit -m "feat(durable): concurrent batch eval case execution"
```

---

### Task 8: CLI runtime deduplication

**Files:**
- Create: `src/clinique/durable/cli_runtime.py`
- Modify: `src/clinique/cli/prescreen.py`

- [ ] **Step 1: Create cli_runtime module**

```python
"""Shared Temporal CLI helpers for prescreen commands."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from clinique.durable._import_guard import TEMPORAL_INSTALL_HINT, require_temporalio
from clinique.durable.converter import DATA_CONVERTER

if TYPE_CHECKING:
    from temporalio.client import Client


def temporal_import_error(exc: ImportError) -> int:
    print(f"prescreen temporal: {exc}", file=sys.stderr)
    return 2


def ensure_temporalio() -> None:
    require_temporalio()


async def connect_client(host: str) -> Client:
    from temporalio.client import Client

    ensure_temporalio()
    try:
        return await Client.connect(host, data_converter=DATA_CONVERTER)
    except ImportError as exc:
        raise ImportError(TEMPORAL_INSTALL_HINT) from exc
```

- [ ] **Step 2: Refactor prescreen CLI handlers**

Replace three duplicated try/import blocks with:

```python
from clinique.durable.cli_runtime import connect_client, ensure_temporalio, temporal_import_error

# screen --temporal:
try:
    from temporalio.client import WorkflowFailureError
    from clinique.durable.client import execute_screen
    from clinique.durable.models import PatientCorpusModel, TrialModel
except ImportError as exc:
    return temporal_import_error(exc)
ensure_temporalio()
client = await connect_client(args.temporal_host)
result = await execute_screen(
    client,
    trial=TrialModel.from_domain(trial),
    corpus=PatientCorpusModel.from_domain(corpus),
    ...
)
text = json.dumps(result.model_dump(), indent=2, sort_keys=True) + "\n"
```

Apply same pattern to `worker` and `eval-temporal`.

- [ ] **Step 3: Run CLI tests**

Run: `uv run pytest tests/test_prescreen_cli.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/clinique/durable/cli_runtime.py src/clinique/cli/prescreen.py
git commit -m "refactor(durable): deduplicate Temporal CLI import and connect logic"
```

---

### Task 9: Session-scoped E2E fixtures

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_durable_prescreen_e2e.py`
- Modify: `tests/durable_e2e_harness.py`

- [ ] **Step 1: Add session fixtures to conftest**

```python
import pytest
from durable_e2e_harness import prescreen_worker, temporal_dev_server


@pytest.fixture(scope="session")
def temporal_dev_server_session():
    with temporal_dev_server() as proc:
        yield proc


@pytest.fixture(scope="session")
def prescreen_worker_session(temporal_dev_server_session):
    with prescreen_worker() as proc:
        yield proc
```

- [ ] **Step 2: Update real-server E2E tests**

Replace per-test `with temporal_dev_server(): with prescreen_worker():` with fixture params:

```python
async def test_real_dev_server_screen_workflow(
    temporal_dev_server_session, prescreen_worker_session, trial_and_corpus
):
    ...
    client = await connect_client(DEFAULT_HOST)
    ...
```

Remove nested context managers from the four `@pytest.mark.temporal_e2e` tests.

- [ ] **Step 3: Run E2E suite and note timing**

Run: `uv run pytest tests/test_durable_prescreen_e2e.py -v`

Expected: PASS; total time noticeably lower than ~60s

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_durable_prescreen_e2e.py
git commit -m "test(durable): session-scoped Temporal E2E server and worker"
```

---

### Task 10: Documentation updates

**Files:**
- Modify: `docs/design/temporal-prescreen.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update temporal-prescreen.md**

Add sections:

- **Parallel execution:** criteria via `asyncio.gather`; batch cases up to `BATCH_EVAL_CONCURRENCY`
- **Pydantic payloads:** `durable/models.py`, `pydantic_data_converter`, `uv sync --group temporal` installs pydantic
- **Single-activity non-goal:** why `PrescreenOrchestrator.screen()` is not a Temporal activity
- **Testing:** mention `test_durable_models.py`, session E2E fixtures

- [ ] **Step 2: Update CLAUDE.md and AGENTS.md**

In temporal dependency / prescreen durable sections, note:

```bash
uv sync --group temporal  # installs temporalio, pydantic, pytest-asyncio
```

- [ ] **Step 3: Run full test suite and lint**

Run: `uv run ruff check src tests && uv run pytest -q`

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add docs/design/temporal-prescreen.md CLAUDE.md AGENTS.md
git commit -m "docs: document durable prescreen hardening (Pydantic, parallelism)"
```

---

## Spec Coverage Checklist

| Spec § | Task |
|---|---|
| §4.1 Parallel criteria | Task 6 |
| §4.2 Batch concurrency | Task 7 |
| §4.3 Single-activity non-goal | Task 10 |
| §5 Batch eval flow | Tasks 4–5, 7 |
| §6 Pydantic payloads | Tasks 1–5 |
| §7 CLI dedup | Task 8 |
| §8 E2E session fixtures | Task 9 |
| §10 Testing | Tasks 2, 6, 7, 9 |
| §11 Documentation | Task 10 |

## Execution Notes

- Run `uv sync --group temporal` before any durable work.
- Keep `prescreen/` domain modules stdlib-only — all Pydantic imports stay under `durable/`.
- `EvalReport` field names must match `EvalMetrics.to_dict()` output exactly.
- When stubbing activities in concurrency tests, match activity **names** (`@activity.defn(name=...)`) not just function names.
- Full suite baseline before starting: `uv run pytest -q` (276 tests).

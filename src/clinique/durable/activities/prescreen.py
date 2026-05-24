"""Prescreen pipeline activities — thin wrappers over existing deterministic modules."""

from __future__ import annotations

from temporalio import activity
from temporalio.exceptions import ApplicationError

from clinique.durable.models import (
    BuildPacketInput,
    CriterionJudgmentModel,
    CriterionModel,
    PatientCorpusModel,
    PrescreeningPacketModel,
    ResolvedCase,
    ResolveScreenCaseInput,
    TrialModel,
)
from clinique.prescreen.aggregator import aggregate
from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.evidence_gate import EvidenceProvenanceError, assert_evidence_provenance
from clinique.prescreen.judge import RuleJudge
from clinique.prescreen.orchestrator import default_prescreen_tools, packet_fingerprint
from clinique.prescreen.retrieval import retrieve
from clinique.prescreen.schemas import PrescreeningPacket
from clinique.substrate.provenance import HumanReview, LedgerRecord, ProvenanceLedger


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
            str(exc),
            type="EvidenceProvenanceError",
            non_retryable=True,
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

"""Prescreen pipeline activities — thin wrappers over existing deterministic modules."""

from __future__ import annotations

from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from clinique.durable.serde import (
    criterion_from_dict,
    judgment_from_dict,
    packet_from_dict,
    packet_to_dict,
    trial_from_dict,
)
from clinique.prescreen.aggregator import aggregate
from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.evidence_gate import EvidenceProvenanceError, assert_evidence_provenance
from clinique.prescreen.judge import RuleJudge
from clinique.prescreen.orchestrator import _packet_fingerprint
from clinique.prescreen.retrieval import retrieve
from clinique.prescreen.schemas import PrescreeningPacket
from clinique.prescreen.validation import corpus_from_dict
from clinique.substrate.provenance import HumanReview, LedgerRecord, ProvenanceLedger


def _tool_meta(component: object) -> dict[str, str]:
    return {
        "name": getattr(component, "name", type(component).__name__),
        "version": getattr(component, "version", "0.0.0"),
    }


def _default_tools() -> list[dict[str, str]]:
    return [
        _tool_meta(ReferenceAtomizer()),
        _tool_meta(RuleJudge()),
        {"name": "aggregator", "version": "0.1.0"},
        {"name": "evidence-gate", "version": "0.1.0"},
    ]


@activity.defn
def atomize_trial(trial_dict: dict[str, Any]) -> list[dict[str, Any]]:
    trial = trial_from_dict(trial_dict)
    atomizer = ReferenceAtomizer()
    return [c.to_dict() for c in atomizer.atomize(trial)]


@activity.defn
def retrieve_evidence(
    criterion_dict: dict[str, Any],
    corpus_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    criterion = criterion_from_dict(criterion_dict)
    corpus = corpus_from_dict(corpus_dict)
    return [e.to_dict() for e in retrieve(criterion, corpus)]


@activity.defn
def judge_criterion(
    criterion_dict: dict[str, Any],
    evidence_list: list[dict[str, Any]],
    corpus_dict: dict[str, Any],
) -> dict[str, Any]:
    criterion = criterion_from_dict(criterion_dict)
    corpus = corpus_from_dict(corpus_dict)
    from clinique.durable.serde import evidence_from_dict

    evidence = tuple(evidence_from_dict(e) for e in evidence_list)
    judge = RuleJudge()
    return judge.judge(criterion, evidence, corpus).to_dict()


@activity.defn
def evaluate_criterion(
    criterion_dict: dict[str, Any],
    corpus_dict: dict[str, Any],
) -> dict[str, Any]:
    criterion = criterion_from_dict(criterion_dict)
    corpus = corpus_from_dict(corpus_dict)
    evidence = retrieve(criterion, corpus)
    judge = RuleJudge()
    return judge.judge(criterion, evidence, corpus).to_dict()


@activity.defn
def aggregate_judgments(judgment_dicts: list[dict[str, Any]]) -> str:
    judgments = tuple(judgment_from_dict(j) for j in judgment_dicts)
    return aggregate(judgments)


@activity.defn
def build_packet(payload: dict[str, Any]) -> dict[str, Any]:
    trial = trial_from_dict(payload["trial_dict"])
    corpus = corpus_from_dict(payload["corpus_dict"])
    criteria = payload["criteria"]
    judgment_dicts = payload["judgment_dicts"]
    recommendation = payload["recommendation"]
    tools = _default_tools()
    packet = PrescreeningPacket(
        trial_id=trial.trial_id,
        patient_id=corpus.patient_id,
        snapshot_date=corpus.snapshot_date,
        criteria=tuple(criterion_from_dict(c) for c in criteria),
        judgments=tuple(judgment_from_dict(j) for j in judgment_dicts),
        recommendation=recommendation,
        model={"atomizer": tools[0], "judge": tools[1]},
        tools=tuple(tools),
    )
    return packet_to_dict(packet)


@activity.defn
def assert_evidence_provenance_activity(
    packet_dict: dict[str, Any],
    corpus_dict: dict[str, Any],
) -> None:
    packet = packet_from_dict(packet_dict)
    corpus = corpus_from_dict(corpus_dict)
    try:
        assert_evidence_provenance(packet, corpus)
    except EvidenceProvenanceError as exc:
        raise ApplicationError(
            str(exc),
            type="EvidenceProvenanceError",
            non_retryable=True,
        ) from exc


@activity.defn
def append_ledger(packet_dict: dict[str, Any], ledger_path: str) -> str:
    packet = packet_from_dict(packet_dict)
    ledger = ProvenanceLedger(ledger_path)
    ref = _packet_fingerprint(packet)
    ledger.append(
        LedgerRecord(
            capability="prescreen",
            inputs=[packet.trial_id, packet.patient_id],
            model=dict(packet.model),
            tools=list(packet.tools),
            output_ref=ref,
            human_review=HumanReview(required=True, status="pending"),
        )
    )
    return ref


@activity.defn
def resolve_screen_case(payload: dict[str, Any]) -> dict[str, Any]:
    case = payload["case"]
    trials = payload["trials"]
    corpora_by_source = payload["corpora_by_source"]
    trial = next((t for t in trials if t["trial_id"] == case["trial_id"]), None)
    if trial is None:
        raise ValueError(f"missing trial {case['trial_id']}")
    source = case.get("patient_source", "synthea")
    corpora = corpora_by_source.get(source, [])
    corpus = next((c for c in corpora if c["patient_id"] == case["patient_id"]), None)
    if corpus is None:
        raise ValueError(f"missing patient {case['patient_id']} source={source}")
    if case.get("snapshot_date") and corpus.get("snapshot_date") != case["snapshot_date"]:
        corpus = dict(corpus)
        corpus["snapshot_date"] = case["snapshot_date"]
    return {"trial": trial, "corpus": corpus, "gold_judgments": case.get("gold_judgments", [])}

"""Prescreening orchestrator — typed graph from trial + patient to ledger packet."""

from __future__ import annotations

import hashlib
import json

from clinique.substrate.provenance import HumanReview, LedgerRecord, ProvenanceLedger

from .aggregator import aggregate
from .atomizer import Atomizer, ReferenceAtomizer
from .evidence_gate import assert_evidence_provenance
from .judge import Judge, RuleJudge
from .retrieval import retrieve
from .schemas import PatientCorpus, PrescreeningPacket, Trial


def _packet_fingerprint(packet: PrescreeningPacket) -> str:
    payload = json.dumps(packet.to_dict(), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def packet_fingerprint(packet: PrescreeningPacket) -> str:
    return _packet_fingerprint(packet)


class PrescreenOrchestrator:
    def __init__(
        self,
        *,
        atomizer: Atomizer | None = None,
        judge: Judge | None = None,
    ) -> None:
        self._atomizer = atomizer or ReferenceAtomizer()
        self._judge = judge or RuleJudge()

    @property
    def tools(self) -> list[dict[str, str]]:
        atom = getattr(self._atomizer, "name", type(self._atomizer).__name__)
        atom_v = getattr(self._atomizer, "version", "0.0.0")
        judge = getattr(self._judge, "name", type(self._judge).__name__)
        judge_v = getattr(self._judge, "version", "0.0.0")
        return [
            {"name": atom, "version": atom_v},
            {"name": judge, "version": judge_v},
            {"name": "aggregator", "version": "0.1.0"},
            {"name": "evidence-gate", "version": "0.1.0"},
        ]

    def screen(self, trial: Trial, corpus: PatientCorpus) -> PrescreeningPacket:
        criteria = self._atomizer.atomize(trial)
        judgments = []
        for criterion in criteria:
            evidence = retrieve(criterion, corpus)
            judgments.append(self._judge.judge(criterion, evidence, corpus))
        recommendation = aggregate(judgments)
        packet = PrescreeningPacket(
            trial_id=trial.trial_id,
            patient_id=corpus.patient_id,
            snapshot_date=corpus.snapshot_date,
            criteria=criteria,
            judgments=tuple(judgments),
            recommendation=recommendation,
            model={"atomizer": self.tools[0], "judge": self.tools[1]},
            tools=tuple(self.tools),
        )
        assert_evidence_provenance(packet, corpus)
        return packet

    def screen_and_append(
        self,
        trial: Trial,
        corpus: PatientCorpus,
        ledger: ProvenanceLedger,
        *,
        output_ref: str | None = None,
    ) -> PrescreeningPacket:
        packet = self.screen(trial, corpus)
        ref = output_ref or _packet_fingerprint(packet)
        ledger.append(
            LedgerRecord(
                capability="prescreen",
                inputs=[trial.trial_id, corpus.patient_id],
                model=dict(packet.model),
                tools=list(packet.tools),
                output_ref=ref,
                human_review=HumanReview(required=True, status="pending"),
            )
        )
        return packet


def screen(trial: Trial, corpus: PatientCorpus) -> PrescreeningPacket:
    return PrescreenOrchestrator().screen(trial, corpus)

"""Tests for evidence-provenance gate and orchestrator."""

from clinique.prescreen.evidence_gate import EvidenceProvenanceError, assert_evidence_provenance
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea
from clinique.prescreen.orchestrator import PrescreenOrchestrator, packet_fingerprint
from clinique.prescreen.schemas import CriterionJudgment, Evidence, PrescreeningPacket
from prescreen_helpers import TABLES


def test_orchestrator_screen_is_deterministic():
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    orch = PrescreenOrchestrator()
    p1 = orch.screen(trials[0], corpus)
    p2 = orch.screen(trials[0], corpus)
    assert packet_fingerprint(p1) == packet_fingerprint(p2)


def test_evidence_gate_rejects_missing_quote():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    packet = PrescreeningPacket(
        trial_id="NCT000",
        patient_id="P1",
        snapshot_date="2026-03-01",
        criteria=(),
        judgments=(
            CriterionJudgment(
                criterion_id="I-1",
                criterion_type="inclusion",
                prediction="met",
                evidence=(Evidence("I-1", "missing", "not in corpus"),),
            ),
        ),
        recommendation="needs_review",
    )
    try:
        assert_evidence_provenance(packet, corpus)
    except EvidenceProvenanceError:
        return
    raise AssertionError("expected EvidenceProvenanceError")

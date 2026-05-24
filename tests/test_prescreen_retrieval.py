"""Tests for evidence retrieval."""

from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea
from clinique.prescreen.retrieval import retrieve
from clinique.prescreen.schemas import Criterion
from prescreen_helpers import TABLES


def test_retrieval_finds_anc_observation():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    criterion = Criterion(
        criterion_id="I-ANC",
        trial_id="NCT000",
        criterion_type="inclusion",
        raw_text="ANC >= 1500/uL within 14 days",
        clinical_domain="laboratory",
    )
    evidence = retrieve(criterion, corpus)
    assert evidence
    assert any("Neutrophil" in ev.quote or "2.1" in ev.quote for ev in evidence)


def test_retrieval_respects_snapshot_leakage():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-01-01")
    criterion = Criterion(
        criterion_id="I-1",
        trial_id="NCT000",
        criterion_type="inclusion",
        raw_text="Absolute Neutrophil Count",
        clinical_domain="laboratory",
    )
    evidence = retrieve(criterion, corpus)
    doc_ids = {ev.doc_id for ev in evidence}
    for doc in corpus.documents:
        if doc.doc_id in doc_ids and doc.date:
            assert doc.date <= "2026-01-01"


def test_retrieval_on_keynote_lab_criterion():
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    trial = next(t for t in trials if t.trial_id == "NCT02578680")
    criteria = [c for c in ReferenceAtomizer().atomize(trial) if c.clinical_domain == "laboratory"]
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    if criteria:
        evidence = retrieve(criteria[0], corpus)
        assert isinstance(evidence, tuple)

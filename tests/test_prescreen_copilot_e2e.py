"""End-to-end prescreen copilot tests — criteria-to-context matching."""

from __future__ import annotations

import pytest

from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.judge import RuleJudge
from clinique.prescreen.normalizer import normalize_synthea
from clinique.prescreen.orchestrator import PrescreenOrchestrator, packet_fingerprint
from clinique.prescreen.retrieval import retrieve
from prescreen_helpers import TABLES

KEYNOTE = "NCT02578680"


def _keynote_p1():
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    trial = next(t for t in trials if t.trial_id == KEYNOTE)
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    return trial, corpus


def _criterion(trial, criterion_id: str):
    criteria = ReferenceAtomizer().atomize(trial)
    return next(c for c in criteria if c.criterion_id == criterion_id)


def _judgment(packet, criterion_id: str):
    return next(j for j in packet.judgments if j.criterion_id == criterion_id)


def test_i002_domain_is_condition_not_demographic():
    trial, _ = _keynote_p1()
    criterion = _criterion(trial, "I-002")
    assert criterion.clinical_domain == "condition"


def test_i008_domain_is_performance_status():
    trial, _ = _keynote_p1()
    criterion = _criterion(trial, "I-008")
    assert criterion.clinical_domain == "performance_status"


def test_i002_retrieves_nsclc_condition():
    trial, corpus = _keynote_p1()
    criterion = _criterion(trial, "I-002")
    evidence = retrieve(criterion, corpus)
    assert evidence
    assert any("lung cancer" in ev.quote.lower() for ev in evidence)


def test_e001_retrieves_nsclc_and_surfaces_evidence_on_unknown():
    trial, corpus = _keynote_p1()
    criterion = _criterion(trial, "E-001")
    judgment = RuleJudge().judge(criterion, retrieve(criterion, corpus), corpus)
    assert judgment.prediction == "unknown"
    assert judgment.evidence
    assert any("lung cancer" in ev.quote.lower() for ev in judgment.evidence)


def test_medication_criteria_do_not_retrieve_observations():
    trial, corpus = _keynote_p1()
    criterion = _criterion(trial, "E-006")
    assert criterion.clinical_domain == "medication"
    evidence = retrieve(criterion, corpus)
    doc_ids = {ev.doc_id for ev in evidence}
    for doc in corpus.documents:
        if doc.doc_id in doc_ids:
            assert doc.source_type in {"medication", "note"}


def test_unknown_judgments_include_retrieved_evidence():
    trial, corpus = _keynote_p1()
    packet = PrescreenOrchestrator().screen(trial, corpus)
    i002 = _judgment(packet, "I-002")
    assert i002.prediction == "unknown"
    assert i002.evidence
    assert "NSCLC documented" in i002.rationale or "stage/histology" in i002.rationale


def test_i005_surfaces_medication_list_on_unknown():
    trial, corpus = _keynote_p1()
    criterion = _criterion(trial, "I-005")
    assert criterion.clinical_domain == "medication"
    packet = PrescreenOrchestrator().screen(trial, corpus)
    i005 = _judgment(packet, "I-005")
    assert i005.prediction == "unknown"
    assert i005.evidence
    assert any("metformin" in ev.quote.lower() for ev in i005.evidence)


def test_synthea_summary_note_document_present():
    _, corpus = _keynote_p1()
    notes = [d for d in corpus.documents if d.source_type == "note"]
    assert len(notes) == 1
    assert "Non-small cell lung cancer" in notes[0].text


def test_keynote_screen_packet_is_deterministic():
    trial, corpus = _keynote_p1()
    orch = PrescreenOrchestrator()
    assert packet_fingerprint(orch.screen(trial, corpus)) == packet_fingerprint(
        orch.screen(trial, corpus)
    )


@pytest.mark.temporal
@pytest.mark.asyncio
async def test_temporal_screen_surfaces_condition_evidence(trial_and_corpus):
    pytest.importorskip("temporalio")
    from temporalio.testing import WorkflowEnvironment

    from clinique.durable.activities import ALL_ACTIVITIES
    from clinique.durable.converter import DATA_CONVERTER
    from clinique.durable.models import PatientCorpusModel, ScreenPatientInput, TrialModel
    from clinique.durable.workflows import ALL_WORKFLOWS
    from clinique.durable.workflows.prescreen import ScreenPatientWorkflow
    from durable_e2e_harness import run_with_worker

    trial, corpus = trial_and_corpus
    if trial.trial_id != KEYNOTE:
        pytest.skip("fixture trial is not KEY-NOTE")

    async with await WorkflowEnvironment.start_local(data_converter=DATA_CONVERTER) as env:

        async def run(client, task_queue):
            return await client.execute_workflow(
                ScreenPatientWorkflow.run,
                ScreenPatientInput(
                    trial=TrialModel.from_domain(trial),
                    corpus=PatientCorpusModel.from_domain(corpus),
                ),
                id="copilot-e2e-keynote",
                task_queue=task_queue,
            )

        packet = await run_with_worker(env.client, ALL_WORKFLOWS, ALL_ACTIVITIES, run)
    i002 = _judgment(packet.to_domain(), "I-002")
    assert i002.prediction == "unknown"
    assert i002.evidence
    assert any("lung cancer" in ev.quote.lower() for ev in i002.evidence)


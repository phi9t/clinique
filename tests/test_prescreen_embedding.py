"""Tests for EmbeddingRetriever and hybrid retrieval."""

from clinique.prescreen.retrieval import EmbeddingRetriever, retrieve
from clinique.prescreen.schemas import Criterion, PatientCorpus, PatientDocument


def test_embedding_retriever_similarity():
    docs = [
        PatientDocument(
            doc_id="D1",
            patient_id="P1",
            date="2026-01-01",
            source_type="condition",
            text="The patient has advanced metastatic non-small cell lung cancer (NSCLC).",
        ),
        PatientDocument(
            doc_id="D2",
            patient_id="P1",
            date="2026-01-01",
            source_type="condition",
            text="The patient is undergoing treatment for diabetes mellitus.",
        ),
    ]

    retriever = EmbeddingRetriever()
    query = ["nsclc", "lung", "cancer"]

    scores = {doc.doc_id: score for doc, score in retriever.score(query, docs)}

    assert scores["D1"] > scores["D2"]
    assert scores["D1"] > 0.0
    assert scores["D2"] == 0.0  # diabetes has no terms overlapping with query


def test_hybrid_retrieve():
    corpus = PatientCorpus(
        patient_id="P1",
        snapshot_date="2026-03-01",
        source="synthea",
        documents=(
            PatientDocument(
                doc_id="D1",
                patient_id="P1",
                date="2026-01-01",
                source_type="condition",
                text="Diagnosis of squamous cell carcinoma of the lung.",
            ),
        ),
    )

    crit = Criterion(
        criterion_id="I-002",
        trial_id="NCT123",
        criterion_type="inclusion",
        raw_text="histologically confirmed squamous cell carcinoma",
        clinical_domain="condition",
    )

    hits = retrieve(crit, corpus)
    assert len(hits) == 1
    assert hits[0].doc_id == "D1"

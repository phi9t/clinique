"""Pydantic durable models round-trip against prescreen domain types."""

from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from clinique.durable.models import (
    CriterionJudgmentModel,
    CriterionModel,
    PatientCorpusModel,
    PrescreeningPacketModel,
    TrialModel,
)
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.orchestrator import PrescreenOrchestrator

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
        assert CriterionModel.model_validate(criterion.to_dict()).to_domain() == criterion
    for judgment in packet.judgments:
        assert CriterionJudgmentModel.model_validate(judgment.to_dict()).to_domain() == judgment

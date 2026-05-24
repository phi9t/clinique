"""Shared fixtures for prescreen durable tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir

TRIALS = Path("tests/fixtures/prescreen/trials.jsonl")
SYNTHEA_CSV = Path("tests/fixtures/prescreen/synthea")


@pytest.fixture
def trial_and_corpus():
    trial = load_recorded_studies(TRIALS)[0]
    tables = read_synthea_csv_dir(SYNTHEA_CSV)
    corpus = normalize_synthea_corpus(tables, snapshot_date="2026-03-01")[0]
    return trial, corpus


@pytest.fixture
def synthea_patients_jsonl(tmp_path):
    tables = read_synthea_csv_dir(SYNTHEA_CSV)
    corpora = normalize_synthea_corpus(tables, snapshot_date="2026-03-01")
    out = tmp_path / "synthea_patients.jsonl"
    with out.open("w", encoding="utf-8") as handle:
        for corpus in corpora:
            handle.write(json.dumps(corpus.to_dict(), sort_keys=True) + "\n")
    return out


@pytest.fixture(scope="session")
def temporal_dev_server_session():
    from durable_e2e_harness import temporal_dev_server

    with temporal_dev_server() as proc:
        yield proc


@pytest.fixture(scope="session")
def prescreen_worker_session(temporal_dev_server_session):
    from durable_e2e_harness import prescreen_worker

    with prescreen_worker() as proc:
        yield proc

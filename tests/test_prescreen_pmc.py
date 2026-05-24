"""Offline tests for the PMC-Patients normalizer.

Runs against a synthetic JSONL fixture shaped like PMC-Patients records (no real patient text).
The network sample-fetch path is not exercised; ``parse_pmc_record`` is the pure half.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clinique.prescreen.pmc_patients import load_pmc_corpora, parse_pmc_record
from clinique.prescreen.schemas import PMC_PATIENTS

FIXTURE = Path("tests/fixtures/prescreen/pmc_patients.jsonl")


def test_loads_all_records_with_demographics():
    corpora = load_pmc_corpora(FIXTURE)
    assert {c.patient_id for c in corpora} == {"SYN-PMC-1", "SYN-PMC-2"}
    assert all(c.source == PMC_PATIENTS for c in corpora)
    man = next(c for c in corpora if c.patient_id == "SYN-PMC-1")
    assert man.demographics == {"age": 62.0, "sex": "male"}
    # Case reports have no enrollment as-of time.
    assert man.snapshot_date is None


def test_summary_becomes_a_single_undated_note():
    corpus = next(c for c in load_pmc_corpora(FIXTURE) if c.patient_id == "SYN-PMC-1")
    assert len(corpus.documents) == 1
    note = corpus.documents[0]
    assert note.source_type == "note"
    assert note.date is None
    assert note.doc_id == "SYN-PMC-1:note:0000"
    assert "non-small cell lung carcinoma" in note.text.lower()


def test_parse_is_deterministic():
    raw = {
        "patient_id": "X",
        "patient": "A 50-year-old patient.",
        "age": [[50.0, "year"]],
        "gender": "F",
    }
    assert parse_pmc_record(raw).to_dict() == parse_pmc_record(raw).to_dict()


def test_missing_patient_id_raises():
    with pytest.raises(ValueError, match="patient_id"):
        parse_pmc_record({"patient": "text", "age": [[1.0, "year"]], "gender": "M"})

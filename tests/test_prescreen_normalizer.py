"""Offline tests for the Synthea patient normalizer.

Tables are built inline (Synthea-shaped row dicts) so the test documents the exact input contract
without shipping a Synthea export. Synthetic, no PHI.
"""

from __future__ import annotations

import pytest

from clinique.prescreen.normalizer import normalize_synthea
from clinique.prescreen.schemas import SYNTHEA

TABLES = {
    "patients": [
        {"Id": "P1", "BIRTHDATE": "1963-07-01", "GENDER": "M"},
        {"Id": "P2", "BIRTHDATE": "1990-01-01", "GENDER": "F"},
    ],
    "conditions": [
        {
            "PATIENT": "P1",
            "START": "2025-09-10",
            "CODE": "254637007",
            "DESCRIPTION": "Non-small cell lung cancer",
        },
        {
            "PATIENT": "P2",
            "START": "2024-01-01",
            "CODE": "999",
            "DESCRIPTION": "Other patient condition",
        },
    ],
    "observations": [
        {
            "PATIENT": "P1",
            "DATE": "2026-02-20T09:00:00Z",
            "CODE": "751-8",
            "DESCRIPTION": "Absolute Neutrophil Count",
            "VALUE": "2.1",
            "UNITS": "10*3/uL",
        },
        {
            "PATIENT": "P1",
            "DATE": "2026-02-20T09:00:00Z",
            "CODE": "718-7",
            "DESCRIPTION": "Hemoglobin",
            "VALUE": "11.2",
            "UNITS": "g/dL",
        },
    ],
    "medications": [
        {"PATIENT": "P1", "START": "2025-10-01", "CODE": "860975", "DESCRIPTION": "metformin"},
    ],
}


def test_demographics_and_patient_filtering():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    assert corpus.source == SYNTHEA
    assert corpus.demographics["sex"] == "male"
    assert corpus.demographics["age"] == 62  # born 1963-07-01, as of 2026-03-01
    # Only P1's rows are included.
    assert all(doc.patient_id == "P1" for doc in corpus.documents)
    assert not any("Other patient condition" in doc.text for doc in corpus.documents)


def test_observation_renders_value_and_structured_facts():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    anc = next(d for d in corpus.documents if d.structured.get("code") == "751-8")
    assert anc.source_type == "observation"
    assert anc.text == "Absolute Neutrophil Count: 2.1 10*3/uL"
    assert anc.structured["value"] == 2.1
    assert anc.structured["unit"] == "10*3/uL"
    assert anc.date == "2026-02-20"  # timestamp truncated to date


def test_documents_are_deterministic_and_stably_identified():
    first = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    second = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    assert [d.to_dict() for d in first.documents] == [d.to_dict() for d in second.documents]
    ids = [d.doc_id for d in first.documents]
    assert len(ids) == len(set(ids))
    assert all(doc_id.startswith("P1:") for doc_id in ids)


def test_unknown_patient_raises():
    with pytest.raises(ValueError, match="not found"):
        normalize_synthea(TABLES, patient_id="P404", snapshot_date="2026-03-01")

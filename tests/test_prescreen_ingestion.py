"""Offline tests for ClinicalTrials.gov ingestion.

These run against the recorded JSONL fixture (real API v2 payloads frozen in version control), so
there is no network dependency — the same discipline that makes the eval reproducible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clinique.prescreen.ingestion import (
    iter_raw_studies,
    load_recorded_studies,
    parse_study,
)
from clinique.prescreen.schemas import CLINICALTRIALS_GOV

FIXTURE = Path("tests/fixtures/prescreen/trials.jsonl")


def _keynote() -> dict:
    return next(
        raw
        for raw in iter_raw_studies(FIXTURE)
        if raw["protocolSection"]["identificationModule"]["nctId"] == "NCT02578680"
    )


def test_corpus_loads_all_recorded_studies():
    trials = load_recorded_studies(FIXTURE)
    assert {t.trial_id for t in trials} == {"NCT02578680", "NCT06123754"}
    assert all(t.source == CLINICALTRIALS_GOV for t in trials)


def test_parse_extracts_eligibility_and_metadata():
    trial = parse_study(_keynote())
    assert trial.trial_id == "NCT02578680"
    assert trial.phase == "PHASE3"
    assert trial.recruitment_status == "COMPLETED"
    assert "Non-Small-Cell Lung Carcinoma" in trial.conditions
    # Eligibility text is preserved verbatim for the atomizer.
    assert "Inclusion Criteria" in trial.eligibility_text


def test_parse_normalizes_demographics():
    trial = parse_study(_keynote())
    assert trial.sex == "ALL"
    assert trial.accepts_healthy_volunteers is False
    assert trial.minimum_age.raw == "18 Years"
    assert trial.minimum_age.years == 18.0
    # Open-ended upper bound must be None, not zero.
    assert trial.maximum_age.years is None


def test_parse_is_deterministic():
    raw = _keynote()
    assert parse_study(raw).to_dict() == parse_study(raw).to_dict()


def test_parse_rejects_payload_without_nct_id():
    with pytest.raises(ValueError, match="nctId"):
        parse_study({"protocolSection": {"identificationModule": {}}})

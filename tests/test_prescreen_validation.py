"""Tests for the prescreening conformance gate.

The committed fixtures are expected to be clean; the failure cases are constructed directly so each
invariant is exercised in isolation.
"""

from __future__ import annotations

from pathlib import Path

from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.schemas import (
    SYNTHEA,
    AgeBound,
    PatientCorpus,
    PatientDocument,
    Trial,
)
from clinique.prescreen.validation import (
    report_for,
    validate_patient_corpus,
    validate_trial,
)

TRIALS = Path("tests/fixtures/prescreen/trials.jsonl")
SYNTHEA_FIXTURE = Path("tests/fixtures/prescreen/synthea")


def _codes(issues, severity):
    return {i.code for i in issues if i.severity == severity}


def test_committed_fixtures_are_conformant():
    trials = load_recorded_studies(TRIALS)
    corpora = normalize_synthea_corpus(
        read_synthea_csv_dir(SYNTHEA_FIXTURE), snapshot_date="2026-03-01"
    )
    report = report_for(trials=trials, corpora=corpora)
    assert report.ok, [i.to_dict() for i in report.issues if i.severity == "error"]


def _trial(**overrides) -> Trial:
    base = {
        "trial_id": "NCT12345678",
        "source": "clinicaltrials_gov",
        "title": "t",
        "conditions": ("Lung Cancer",),
        "phase": "PHASE3",
        "recruitment_status": "RECRUITING",
        "eligibility_text": "Inclusion Criteria: age 18+",
        "sex": "ALL",
        "accepts_healthy_volunteers": False,
        "minimum_age": AgeBound("18 Years", 18.0),
        "maximum_age": AgeBound(None, None),
        "std_ages": ("ADULT",),
        "sponsor": "s",
    }
    base.update(overrides)
    return Trial(**base)


def test_clean_trial_has_no_errors():
    assert not _codes(validate_trial(_trial()), "error")


def test_bad_enum_is_an_error():
    issues = validate_trial(_trial(sex="UNISEX", phase="PHASE9"))
    assert "sex_vocab" in _codes(issues, "error")
    assert "phase_vocab" in _codes(issues, "error")


def test_min_age_above_max_age_is_an_error():
    issues = validate_trial(
        _trial(minimum_age=AgeBound("80 Years", 80.0), maximum_age=AgeBound("50 Years", 50.0))
    )
    assert "age_bounds" in _codes(issues, "error")


def test_empty_eligibility_is_a_warning_not_an_error():
    issues = validate_trial(_trial(eligibility_text="   "))
    assert "eligibility_empty" in _codes(issues, "warning")
    assert not _codes(issues, "error")


def test_unparsed_age_bound_is_a_warning():
    # A raw string that AgeBound could not turn into years (years is None despite a raw value).
    issues = validate_trial(_trial(minimum_age=AgeBound("N/A", None)))
    assert "age_unparsed" in _codes(issues, "warning")
    assert not _codes(issues, "error")


def _corpus(snapshot, doc_date) -> PatientCorpus:
    return PatientCorpus(
        patient_id="P1",
        snapshot_date=snapshot,
        source=SYNTHEA,
        demographics={"age": 60, "sex": "male"},
        documents=(
            PatientDocument(
                doc_id="P1:observation:0000",
                patient_id="P1",
                date=doc_date,
                source_type="observation",
                text="x",
                structured={"value": 1.0, "unit": "u"},
            ),
        ),
    )


def test_future_dated_document_is_leakage_error():
    issues = validate_patient_corpus(_corpus("2026-01-01", "2026-06-01"))
    assert "leakage" in _codes(issues, "error")


def test_document_on_snapshot_date_is_allowed():
    issues = validate_patient_corpus(_corpus("2026-06-01", "2026-06-01"))
    assert "leakage" not in _codes(issues, "error")


def test_duplicate_doc_id_is_an_error():
    dup = PatientDocument(
        doc_id="P1:condition:0000",
        patient_id="P1",
        date=None,
        source_type="condition",
        text="x",
        structured={},
    )
    corpus = PatientCorpus(
        patient_id="P1",
        snapshot_date=None,
        source=SYNTHEA,
        demographics={},
        documents=(dup, dup),
    )
    assert "doc_id_duplicate" in _codes(validate_patient_corpus(corpus), "error")


def test_observation_without_value_is_a_warning():
    corpus = PatientCorpus(
        patient_id="P1",
        snapshot_date=None,
        source=SYNTHEA,
        demographics={},
        documents=(
            PatientDocument(
                doc_id="P1:observation:0000",
                patient_id="P1",
                date=None,
                source_type="observation",
                text="ANC",
                structured={"code": "x", "description": "ANC"},  # no "value"
            ),
        ),
    )
    issues = validate_patient_corpus(corpus)
    assert "observation_no_value" in _codes(issues, "warning")
    assert not _codes(issues, "error")


def test_bad_patient_source_and_sex_are_errors():
    corpus = PatientCorpus(
        patient_id="P1",
        snapshot_date=None,
        source="not_a_real_source",
        demographics={"sex": "unknown"},
        documents=(),
    )
    issues = validate_patient_corpus(corpus)
    assert "source_vocab" in _codes(issues, "error")
    assert "sex_vocab" in _codes(issues, "error")

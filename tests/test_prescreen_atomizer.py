"""Tests for ReferenceAtomizer."""

from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.ingestion import load_recorded_studies


def test_keynote_produces_age_and_pd1_exclusion():
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    trial = next(t for t in trials if t.trial_id == "NCT02578680")
    criteria = ReferenceAtomizer().atomize(trial)
    assert criteria[0].criterion_id == "I-001"
    assert criteria[0].clinical_domain == "demographic"
    pd1 = [c for c in criteria if "PD-1" in c.raw_text or "PD-L1" in c.raw_text]
    assert pd1
    assert any(
        "adequate organ function" in c.raw_text.lower() and c.ambiguity_flags for c in criteria
    )


def test_atomize_is_deterministic():
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    trial = trials[0]
    a = ReferenceAtomizer().atomize(trial)
    b = ReferenceAtomizer().atomize(trial)
    assert [c.criterion_id for c in a] == [c.criterion_id for c in b]

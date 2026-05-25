"""Tests for compound criterion splitting in ReferenceAtomizer."""

from clinique.prescreen.atomizer import ReferenceAtomizer, _split_compound_text
from clinique.prescreen.ingestion import load_recorded_studies


def test_split_compound_text_logic():
    text = (
        "Before the first dose of study medication: "
        "a) Has received prior systemic cytotoxic chemotherapy for metastatic disease, "
        "b) Has received antineoplastic biological therapy, "
        "c) Had major surgery (<3 weeks prior to first dose)"
    )
    res = _split_compound_text(text)
    assert len(res) == 3
    assert res[0] == (
        "a",
        "Before the first dose of study medication: a) Has received prior "
        "systemic cytotoxic chemotherapy for metastatic disease",
    )
    assert res[1] == (
        "b",
        "Before the first dose of study medication: b) Has received "
        "antineoplastic biological therapy",
    )
    assert res[2] == (
        "c",
        "Before the first dose of study medication: c) Had major surgery "
        "(<3 weeks prior to first dose)",
    )


def test_keynote_splitting_atomization():
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    trial = next(t for t in trials if t.trial_id == "NCT02578680")
    criteria = ReferenceAtomizer().atomize(trial)

    # E-003 should be split into a, b, c
    e003a = next((c for c in criteria if c.criterion_id == "E-003a"), None)
    e003b = next((c for c in criteria if c.criterion_id == "E-003b"), None)
    e003c = next((c for c in criteria if c.criterion_id == "E-003c"), None)

    assert e003a is not None
    assert e003b is not None
    assert e003c is not None
    assert " cytotoxic chemotherapy" in e003a.raw_text
    assert " antineoplastic biological therapy" in e003b.raw_text
    assert " major surgery" in e003c.raw_text

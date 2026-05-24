"""Tests for eval harness."""

from pathlib import Path

from clinique.prescreen.eval import load_eval_cases, run_eval_cases
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea
from clinique.prescreen.pmc_patients import load_pmc_corpora
from prescreen_helpers import TABLES


def test_run_l0_cases_on_fixtures():
    cases = load_eval_cases(".workstream/prescreen-copilot/l0_cases.jsonl")
    trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    synthea = [normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")]
    pmc = load_pmc_corpora("tests/fixtures/prescreen/pmc_patients.jsonl")
    metrics = run_eval_cases(
        cases,
        trials=trials,
        corpora_by_source={"synthea": synthea, "pmc": pmc},
    )
    assert metrics.cases_run == len(cases)
    assert metrics.criterion_accuracy >= 0.90
    assert metrics.evidence_violations == 0


def test_load_eval_cases():
    cases = load_eval_cases(".workstream/prescreen-copilot/l0_cases.jsonl")
    assert len(cases) >= 2
    assert Path(".workstream/prescreen-copilot/l0_cases.jsonl").is_file()

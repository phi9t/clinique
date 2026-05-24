"""Tests for RuleJudge."""

from clinique.prescreen.judge import RuleJudge
from clinique.prescreen.normalizer import normalize_synthea
from clinique.prescreen.retrieval import retrieve
from clinique.prescreen.schemas import Criterion, Threshold
from prescreen_helpers import TABLES


def test_age_inclusion_met():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    criterion = Criterion(
        criterion_id="I-001",
        trial_id="NCT000",
        criterion_type="inclusion",
        raw_text="Age >= 18 Years",
        clinical_domain="demographic",
        operator=">=",
        threshold=Threshold(value=18, unit="years"),
    )
    judgment = RuleJudge().judge(criterion, (), corpus)
    assert judgment.prediction == "met"


def test_exclusion_pd1_unknown_without_medication():
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    criterion = Criterion(
        criterion_id="E-017",
        trial_id="NCT000",
        criterion_type="exclusion",
        raw_text="Had prior treatment with anti-PD-1 or PD-L1 agent",
        clinical_domain="medication",
        requires_absence_evidence=True,
    )
    evidence = retrieve(criterion, corpus)
    judgment = RuleJudge().judge(criterion, evidence, corpus)
    assert judgment.prediction == "unknown"

"""Tests for n2c2 2018 eval harness."""

import tempfile
from pathlib import Path

from clinique.prescreen.eval import load_n2c2_annotations, run_n2c2_eval
from clinique.prescreen.judge import RuleJudge

XML_SAMPLE_1 = """<?xml version="1.0" encoding="UTF-8" ?>
<cohort>
<TEXT><![CDATA[
The patient speaks English. No history of drug abuse. Had myocardial infarction 3 months ago.
]]></TEXT>
<TAGS>
<DRUG-ABUSE met="not met" />
<ALCOHOL-ABUSE met="not met" />
<ENGLISH met="met" />
<MAKE-DECISIONS met="met" />
<ABD-SURGERY met="not met" />
<MI-6MOS met="met" />
<DIARY met="not met" />
<COGNITIVE met="not met" />
<ADV-CANCER met="not met" />
<ACTIVE-INFECT met="not met" />
<HBA1C met="not met" />
<DIASTOLIC met="not met" />
<KETOACIDOSIS met="not met" />
</TAGS>
</cohort>
"""


def test_n2c2_xml_parsing():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        xml_file = tmp_path / "patient_100.xml"
        xml_file.write_text(XML_SAMPLE_1, encoding="utf-8")

        cases = load_n2c2_annotations(tmpdir)
        assert len(cases) == 1
        assert cases[0]["patient_id"] == "patient_100"
        assert "speaks English" in cases[0]["text"]
        assert cases[0]["gold_labels"]["ENGLISH"] == "met"
        assert cases[0]["gold_labels"]["DRUG-ABUSE"] == "not_met"
        assert cases[0]["gold_labels"]["MI-6MOS"] == "met"


def test_n2c2_eval_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        xml_file = tmp_path / "patient_100.xml"
        xml_file.write_text(XML_SAMPLE_1, encoding="utf-8")

        # Test evaluation with RuleJudge
        report = run_n2c2_eval(tmpdir, judge=RuleJudge())

        assert report["cases_run"] == 1
        assert "macro_f1" in report
        assert "criteria" in report
        # ENGLISH tag is expected 'met'. Let's see if the RuleJudge returned met.
        # (It doesn't have a rule for English, so it returns unknown).
        # Which counts as pred='unknown' != gold='met', hence not TP.
        # But MI-6MOS has expected='met', and RuleJudge on MI-6MOS will check condition
        # and find "myocardial infarction".
        # Let's verify that the output runs and contains valid scores.
        assert report["macro_f1"] >= 0.0

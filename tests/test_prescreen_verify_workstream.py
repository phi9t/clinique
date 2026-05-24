"""Tests for verify-workstream and temporal eval parity."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from clinique.prescreen.eval import (
    EvalMetrics,
    eval_metrics_parity,
    eval_metrics_passes_gates,
    load_eval_cases,
    run_eval_cases,
    verify_workstream,
)
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea
from prescreen_helpers import TABLES


def test_eval_metrics_parity_detects_mismatch():
    sync = EvalMetrics(
        cases_run=3,
        criterion_total=3,
        criterion_correct=3,
    )
    temporal = sync.to_dict()
    temporal["criterion_correct"] = 2
    ok, issues = eval_metrics_parity(sync, temporal)
    assert not ok
    assert any("criterion_correct" in issue for issue in issues)


def test_eval_metrics_parity_matches():
    sync = EvalMetrics(
        cases_run=2,
        criterion_total=2,
        criterion_correct=2,
        evidence_violations=0,
        exclusion_false_negatives=0,
    )
    ok, issues = eval_metrics_parity(sync, sync.to_dict())
    assert ok
    assert not issues


def test_eval_metrics_passes_gates():
    good = EvalMetrics(cases_run=1, criterion_total=1, criterion_correct=1)
    bad = EvalMetrics(cases_run=1, criterion_total=1, criterion_correct=0)
    assert eval_metrics_passes_gates(good)
    assert not eval_metrics_passes_gates(bad)


def test_verify_workstream_temporal_with_mock_runner(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    datasets = tmp_path / "datasets" / "prescreen-copilot"
    datasets.mkdir(parents=True)

    shutil.copy(
        Path("tests/fixtures/prescreen/trials.jsonl"),
        datasets / "trials.jsonl",
    )
    shutil.copy(
        Path(".workstream/prescreen-copilot/l0_cases.jsonl"),
        ws / "l0_cases.jsonl",
    )
    shutil.copy(
        Path(".workstream/prescreen-copilot/datasets.manifest.json"),
        ws / "datasets.manifest.json",
    )

    synthea_out = datasets / "synthea_patients.jsonl"
    corpus = normalize_synthea(TABLES, patient_id="P1", snapshot_date="2026-03-01")
    synthea_out.write_text(json.dumps(corpus.to_dict()) + "\n", encoding="utf-8")
    shutil.copy(
        Path("tests/fixtures/prescreen/pmc_patients.jsonl"),
        datasets / "pmc_patients.jsonl",
    )
    shutil.copy(
        Path("tests/fixtures/prescreen/pmc_patients.jsonl"),
        datasets / "mimic_demo_patients.jsonl",
    )

    cases = load_eval_cases(ws / "l0_cases.jsonl")
    trials = load_recorded_studies(datasets / "trials.jsonl")
    from clinique.prescreen.pmc_patients import load_pmc_corpora

    sync_metrics = run_eval_cases(
        cases,
        trials=trials,
        corpora_by_source={
            "synthea": [corpus],
            "pmc": load_pmc_corpora(datasets / "pmc_patients.jsonl"),
            "mimic": load_pmc_corpora(datasets / "mimic_demo_patients.jsonl"),
        },
    )

    def mock_temporal_runner(**_kwargs):
        return sync_metrics.to_dict()

    report = verify_workstream(
        workstream_dir=ws,
        datasets_dir=tmp_path / "datasets",
        reports_dir=tmp_path / "reports",
        temporal=True,
        temporal_eval_runner=mock_temporal_runner,
    )
    assert report["temporal"]["ran"]
    assert report["temporal"]["parity_ok"]
    assert report["temporal"]["temporal_goal_complete"]
    assert report["eval"]["cases_run"] == sync_metrics.cases_run
    if report["goal_complete"]:
        assert report["verification_complete"]

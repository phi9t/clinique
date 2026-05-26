"""Tests for PrescreenBench static explorer export."""

from __future__ import annotations

import json

from clinique.benchmarks.prescreenbench.explorer_export import (
    DEFAULT_DEMO_AGENTS,
    build_definitions,
    build_split_bundle,
    export_explorer,
)
from clinique.benchmarks.prescreenbench.load import load_split

EXPECTED_FILES = {
    "index.json",
    "definitions.json",
    "synthetic.json",
    "lite.json",
}


def test_definitions_include_metric_and_label_help():
    definitions = build_definitions()
    assert definitions["labels"]["unknown"]["plain"]
    assert definitions["metrics"]["unsafe_clearance_rate"]["plain"]
    assert definitions["primer"]["eligibility_criteria"]


def test_build_split_bundle_contains_cases_agents_and_annotations():
    split = load_split("synthetic")
    bundle = build_split_bundle(split, agents=DEFAULT_DEMO_AGENTS)
    assert bundle["split"] == "synthetic"
    assert {a["agent"] for a in bundle["agents"]} == set(DEFAULT_DEMO_AGENTS)
    assert bundle["cases"]
    first = bundle["cases"][0]
    assert first.keys() >= {"case", "trial", "patient", "gold", "agent_outputs", "grader"}
    for agent in DEFAULT_DEMO_AGENTS:
        assert agent in first["agent_outputs"]
        assert agent in first["grader"]
        assert first["grader"][agent]["criteria"]


def test_export_writes_expected_files(tmp_path):
    written = export_explorer(tmp_path, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    assert set(written) == EXPECTED_FILES
    for name in EXPECTED_FILES:
        assert (tmp_path / name).is_file()


def test_export_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    export_explorer(a, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    export_explorer(b, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    for name in EXPECTED_FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_exported_quote_offsets_match_documents(tmp_path):
    export_explorer(tmp_path, splits=("synthetic",), agents=("clinique_rule",))
    bundle = json.loads((tmp_path / "synthetic.json").read_text())
    checks = [
        check
        for case in bundle["cases"]
        for criterion in case["grader"]["clinique_rule"]["criteria"]
        for check in criterion["evidence_checks"]
        if check["quote_found"]
    ]
    assert checks
    check = checks[0]
    docs = {
        doc["doc_id"]: doc["text"]
        for case in bundle["cases"]
        for doc in case["patient"]["documents"]
    }
    assert docs[check["doc_id"]][check["start_char"] : check["end_char"]] == check["quote"]

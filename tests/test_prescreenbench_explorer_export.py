"""Tests for PrescreenBench static explorer export."""

from __future__ import annotations

import json

import pytest

from clinique.benchmarks.prescreenbench.explorer_export import (
    DEFAULT_DEMO_AGENTS,
    build_definitions,
    build_split_bundle,
    default_out_dir,
    export_explorer,
)
from clinique.benchmarks.prescreenbench.load import load_split
from clinique.benchmarks.prescreenbench.score import run

EXPECTED_FILES = {
    "index.json",
    "definitions.json",
    "synthetic.json",
    "lite.json",
}


def _without_codex(payload):
    """Remove live Codex benchmark outputs before deterministic snapshot comparison."""
    if isinstance(payload, list):
        return [
            {
                **entry,
                "agents": [agent for agent in entry.get("agents", []) if agent != "codex_cli"],
            }
            for entry in payload
        ]

    if not isinstance(payload, dict) or "cases" not in payload:
        return payload

    cleaned = dict(payload)
    cleaned["agents"] = [
        agent for agent in cleaned.get("agents", []) if agent.get("agent") != "codex_cli"
    ]
    cleaned_cases = []
    for case in cleaned.get("cases", []):
        case_copy = dict(case)
        case_copy["agent_outputs"] = {
            agent: output
            for agent, output in case_copy.get("agent_outputs", {}).items()
            if agent != "codex_cli"
        }
        case_copy["grader"] = {
            agent: grader
            for agent, grader in case_copy.get("grader", {}).items()
            if agent != "codex_cli"
        }
        cleaned_cases.append(case_copy)
    cleaned["cases"] = cleaned_cases
    return cleaned


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


def test_build_split_bundle_uses_custom_report_when_supplied():
    split = load_split("synthetic")
    rows, _ = run(split, "clinique_rule")
    predictions = {row["case_id"]: row for row in rows}
    custom_report = {"agent": "custom", "score": 0.123}
    bundle = build_split_bundle(
        split,
        agents=(),
        custom_predictions={"custom": predictions},
        custom_reports={"custom": custom_report},
    )
    assert bundle["agents"] == [{"agent": "custom", "report": custom_report}]


def test_build_split_bundle_rejects_report_without_predictions():
    split = load_split("synthetic")
    with pytest.raises(ValueError, match="custom report without predictions.*orphan"):
        build_split_bundle(
            split,
            agents=(),
            custom_reports={"orphan": {"agent": "orphan"}},
        )


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


def test_committed_prescreenbench_explorer_snapshot_matches_export(tmp_path):
    export_explorer(tmp_path, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    committed = default_out_dir()
    for name in EXPECTED_FILES:
        exported = json.loads((tmp_path / name).read_text())
        checked_in = json.loads((committed / name).read_text())
        assert exported == _without_codex(checked_in), name


def test_committed_prescreenbench_explorer_includes_codex_outputs():
    committed = default_out_dir()
    for split_name in ("synthetic", "lite"):
        bundle = json.loads((committed / f"{split_name}.json").read_text())
        assert "codex_cli" in {agent["agent"] for agent in bundle["agents"]}
        first = bundle["cases"][0]
        assert "codex_cli" in first["agent_outputs"]
        assert "codex_cli" in first["grader"]
        rationales = [
            criterion["rationale"]
            for case in bundle["cases"]
            for criterion in case["grader"]["codex_cli"]["criteria"]
        ]
        assert any("Codex CLI" in rationale for rationale in rationales)


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

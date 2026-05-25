"""Argument parser for the clinique CLI."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clinique")
    subparsers = parser.add_subparsers(dest="command")

    edc = subparsers.add_parser("edc-query")
    edc_subparsers = edc.add_subparsers(dest="edc_command")
    validate = edc_subparsers.add_parser("validate")
    validate.add_argument("--fixtures", default="tests/fixtures/edc_query")
    validate.add_argument("--reports-dir", default="reports/edc-query")
    preflight = edc_subparsers.add_parser("preflight-internal-data")
    preflight.add_argument("--manifest", required=True)
    preflight.add_argument("--output")
    silent = edc_subparsers.add_parser("evaluate-silent-log")
    silent.add_argument("--log", required=True)
    silent.add_argument("--output", required=True)
    silent.add_argument("--false-positive-tolerance", type=float, default=1.0)
    rollout = edc_subparsers.add_parser("evaluate-rollout-gate")
    rollout.add_argument("--gate", required=True)
    rollout.add_argument("--output", required=True)
    verify = edc_subparsers.add_parser("verify-workstream")
    verify.add_argument("--fixtures", default="tests/fixtures/edc_query")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--silent-log", required=True)
    verify.add_argument("--rollout-gate", required=True)
    verify.add_argument("--reports-dir", default="reports/edc-query")
    verify.add_argument("--internal-export-manifest")
    verify.add_argument("--internal-labels")
    verify.add_argument("--internal-lock-issues")
    internal = edc_subparsers.add_parser("validate-internal-exports")
    internal.add_argument("--manifest", required=True)
    internal.add_argument("--labels", required=True)
    internal.add_argument("--lock-issues")
    internal.add_argument("--reports-dir", default="reports/edc-query")

    prescreen = subparsers.add_parser("prescreen")
    prescreen_subparsers = prescreen.add_subparsers(dest="prescreen_command")
    ingest = prescreen_subparsers.add_parser("ingest")
    ingest.add_argument("--nct-ids", required=True, help="comma-separated NCT ids")
    ingest.add_argument("--out", required=True, help="output JSONL fixture path")
    search = prescreen_subparsers.add_parser("search")
    search.add_argument("--cond", help="query.cond condition term")
    search.add_argument("--term", help="query.term free-text term")
    search.add_argument("--status", help="comma-separated overallStatus filter")
    search.add_argument("--max", type=int, default=None, help="max studies to record")
    search.add_argument("--out", required=True, help="output JSONL fixture path")
    norm_synthea = prescreen_subparsers.add_parser("normalize-synthea")
    norm_synthea.add_argument("--csv-dir", required=True, help="Synthea CSV export directory")
    norm_synthea.add_argument("--snapshot", help="as-of date (YYYY-MM-DD)")
    norm_synthea.add_argument("--out", required=True, help="output PatientCorpus JSONL path")
    ingest_pmc = prescreen_subparsers.add_parser("ingest-pmc")
    ingest_pmc.add_argument("--limit", type=int, default=100, help="number of records to fetch")
    ingest_pmc.add_argument("--out", required=True, help="output JSONL fixture path")
    validate_p = prescreen_subparsers.add_parser("validate")
    validate_p.add_argument("--trials", help="trials JSONL to validate")
    validate_p.add_argument("--patients", help="patient JSONL to validate")
    validate_p.add_argument(
        "--source",
        choices=["synthea", "mimic", "pmc"],
        help="how to load --patients (pmc=raw records; else normalized corpus JSONL)",
    )
    validate_p.add_argument("--out", help="optional path to write the JSON report")
    show = prescreen_subparsers.add_parser("show")
    show.add_argument("--fixtures", default="tests/fixtures/prescreen/trials.jsonl")
    export_explorer = prescreen_subparsers.add_parser("export-explorer")
    export_explorer.add_argument(
        "--fixtures-dir",
        default=None,
        help="prescreen L0 fixture directory (default: repo tests/fixtures/prescreen)",
    )
    export_explorer.add_argument(
        "--out",
        default=None,
        help=(
            "output directory for prescreen explorer JSON (default: explorer/public/data/prescreen)"
        ),
    )
    norm_mimic = prescreen_subparsers.add_parser("normalize-mimic-demo")
    norm_mimic.add_argument("--csv-dir", required=True, help="MIMIC-IV demo hosp CSV directory")
    norm_mimic.add_argument("--snapshot", help="as-of date (YYYY-MM-DD)")
    norm_mimic.add_argument("--out", required=True, help="output PatientCorpus JSONL path")
    atomize = prescreen_subparsers.add_parser("atomize")
    atomize.add_argument("--trials", required=True, help="trials JSONL path")
    atomize.add_argument("--trial-id", help="optional single trial filter")
    atomize.add_argument("--out", help="optional criteria JSONL output path")
    screen = prescreen_subparsers.add_parser("screen")
    screen.add_argument("--trial-id", required=True)
    screen.add_argument("--patient-id", required=True)
    screen.add_argument("--trials", required=True)
    screen.add_argument("--patients", required=True)
    screen.add_argument("--source", choices=["synthea", "mimic", "pmc"], default="synthea")
    screen.add_argument("--ledger", help="optional provenance ledger JSONL path")
    screen.add_argument("--out", help="optional packet JSON output path")
    screen.add_argument(
        "--temporal",
        action="store_true",
        help="run via Temporal ScreenPatientWorkflow (requires worker + dev server)",
    )
    screen.add_argument(
        "--temporal-host",
        default="localhost:7233",
        help="Temporal server address when --temporal is set",
    )
    screen.add_argument(
        "--judge",
        choices=["rule", "llm"],
        default="rule",
        help="Specify which judge engine to use",
    )
    worker = prescreen_subparsers.add_parser("worker")
    worker.add_argument("--host", default="localhost:7233", help="Temporal server address")
    eval_temporal = prescreen_subparsers.add_parser("eval-temporal")
    eval_temporal.add_argument(
        "--cases",
        default=".workstream/prescreen-copilot/l0_cases.jsonl",
    )
    eval_temporal.add_argument("--trials", default="tests/fixtures/prescreen/trials.jsonl")
    eval_temporal.add_argument("--synthea-patients", help="synthea patient JSONL")
    eval_temporal.add_argument("--pmc-patients", help="pmc patient JSONL")
    eval_temporal.add_argument("--mimic-patients", help="mimic patient JSONL")
    eval_temporal.add_argument("--reports-dir", default="reports/prescreen")
    eval_temporal.add_argument("--host", default="localhost:7233", help="Temporal server address")
    eval_temporal.add_argument(
        "--judge",
        choices=["rule", "llm"],
        default="rule",
        help="Specify which judge engine to use",
    )
    eval_p = prescreen_subparsers.add_parser("eval")
    eval_p.add_argument(
        "--cases",
        default=".workstream/prescreen-copilot/l0_cases.jsonl",
    )
    eval_p.add_argument("--trials", default="tests/fixtures/prescreen/trials.jsonl")
    eval_p.add_argument("--patients", help="default synthea patient JSONL")
    eval_p.add_argument("--synthea-patients", help="synthea patient JSONL")
    eval_p.add_argument("--pmc-patients", help="pmc patient JSONL")
    eval_p.add_argument("--mimic-patients", help="mimic patient JSONL")
    eval_p.add_argument("--reports-dir", default="reports/prescreen")
    eval_p.add_argument(
        "--judge",
        choices=["rule", "llm"],
        default="rule",
        help="Specify which judge engine to use",
    )
    verify_ws = prescreen_subparsers.add_parser("verify-workstream")
    verify_ws.add_argument("--workstream", default=".workstream/prescreen-copilot")
    verify_ws.add_argument("--datasets-dir", help="defaults to ~/.clinique/datasets")
    verify_ws.add_argument("--reports-dir", default="reports/prescreen")
    verify_ws.add_argument("--cases", help="override l0_cases.jsonl path")
    verify_ws.add_argument(
        "--temporal",
        action="store_true",
        help="also run eval-temporal and require parity with sync eval",
    )
    verify_ws.add_argument(
        "--temporal-host",
        default="localhost:7233",
        help="Temporal server when --temporal is set (worker must be running)",
    )
    verify_ws.add_argument(
        "--judge",
        choices=["rule", "llm"],
        default="rule",
        help="Specify which judge engine to use",
    )
    prescreen_subparsers.add_parser("troubleshoot-agents")

    agent_judge = prescreen_subparsers.add_parser(
        "agent-judge",
        help=(
            "run LLMJudge for fast iteration (default demo: P1 + NCT02578680 from repo fixtures)"
        ),
    )
    agent_judge.add_argument(
        "--trial-id",
        default="NCT02578680",
        help="trial NCT id (default: NCT02578680)",
    )
    agent_judge.add_argument(
        "--patient-id",
        default="P1",
        help="patient id (default: P1)",
    )
    agent_judge.add_argument(
        "--trials",
        default="tests/fixtures/prescreen/trials.jsonl",
        help="trials JSONL path (default: repo NSCLC demo trial)",
    )
    agent_judge.add_argument(
        "--patients",
        help="patient JSONL path (default: normalize --patient-id from --synthea-csv-dir)",
    )
    agent_judge.add_argument(
        "--synthea-csv-dir",
        default="tests/fixtures/prescreen/synthea",
        help="Synthea CSV directory when --patients is omitted",
    )
    agent_judge.add_argument(
        "--snapshot",
        default="2026-03-01",
        help="as-of date when loading from --synthea-csv-dir (default: 2026-03-01)",
    )
    agent_judge.add_argument("--source", choices=["synthea", "mimic", "pmc"], default="synthea")
    agent_judge.add_argument(
        "--criterion-id",
        help="comma-separated criterion IDs to judge (default: all atomized criteria)",
    )
    agent_judge.add_argument(
        "--limit",
        type=int,
        default=5,
        help="judge at most this many criteria (default: 5; use --all for every criterion)",
    )
    agent_judge.add_argument(
        "--all",
        action="store_true",
        help="judge all atomized criteria (ignores --limit)",
    )
    agent_judge.add_argument(
        "--show-evidence",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include retrieved evidence in JSON output (default: on)",
    )
    agent_judge.add_argument(
        "--show-prompt",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="print the LLM prompt for each criterion to stderr (default: on)",
    )
    agent_judge.add_argument("--out", help="optional JSON output path")

    resume = prescreen_subparsers.add_parser("resume")
    resume.add_argument("--workflow-id", required=True, help="Workflow ID to resume")
    resume.add_argument("--host", default="localhost:7233", help="Temporal server address")

    return parser

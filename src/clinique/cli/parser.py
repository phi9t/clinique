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
            "output directory for prescreen explorer JSON "
            "(default: explorer/public/data/prescreen)"
        ),
    )
    return parser

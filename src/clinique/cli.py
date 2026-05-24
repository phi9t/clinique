"""CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

from clinique.edc.internal_preflight import preflight_internal_manifest
from clinique.edc.rollout import evaluate_rollout_gate, load_rollout_gate
from clinique.edc.silent import evaluate_silent_log, load_silent_log
from clinique.edc.validation import run_validation, validate_internal_exports, verify_workstream
from clinique.prescreen.ingestion import (
    load_recorded_studies,
    record_search,
    record_studies,
)
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.pmc_patients import load_pmc_corpora, record_pmc
from clinique.prescreen.validation import corpus_from_dict, report_for


def _build_parser() -> argparse.ArgumentParser:
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "edc-query" and args.edc_command == "validate":
        try:
            run_validation(fixtures=args.fixtures, reports_dir=args.reports_dir)
        except ValueError as exc:
            print(f"edc-query validation failed: {exc}", file=sys.stderr)
            return 2
        print(f"EDC query validation reports written to {args.reports_dir}")
        return 0
    if args.command == "edc-query" and args.edc_command == "preflight-internal-data":
        try:
            result = preflight_internal_manifest(args.manifest)
        except ValueError as exc:
            print(f"edc-query internal-data preflight failed: {exc}", file=sys.stderr)
            return 2
        payload = result.as_dict()
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.output:
            Path(args.output).write_text(text)
        else:
            print(text, end="")
        return 0 if result.ok else 3
    if args.command == "edc-query" and args.edc_command == "evaluate-silent-log":
        try:
            entries = load_silent_log(args.log)
        except ValueError as exc:
            print(f"edc-query silent-log evaluation failed: {exc}", file=sys.stderr)
            return 2
        try:
            report = evaluate_silent_log(
                entries,
                false_positive_tolerance_per_reviewer_week=args.false_positive_tolerance,
            )
        except ValueError as exc:
            print(f"edc-query silent-log evaluation failed: {exc}", file=sys.stderr)
            return 2
        report.write_json(args.output)
        print(f"EDC query silent-log report written to {args.output}")
        silent_gates_passed = (
            report.gates["no_operational_impact"]
            and report.gates["false_positive_burden_controlled"]
            and not report.gates["stop_criteria_triggered"]
        )
        return 0 if silent_gates_passed else 6
    if args.command == "edc-query" and args.edc_command == "evaluate-rollout-gate":
        try:
            gate = load_rollout_gate(args.gate)
        except ValueError as exc:
            print(f"edc-query rollout-gate evaluation failed: {exc}", file=sys.stderr)
            return 2
        report = evaluate_rollout_gate(gate)
        report.write_json(args.output)
        print(f"EDC query rollout-gate report written to {args.output}")
        return 0 if report.gates["rollout_gate_passed"] else 4
    if args.command == "edc-query" and args.edc_command == "verify-workstream":
        try:
            evidence = verify_workstream(
                fixtures=args.fixtures,
                manifest=args.manifest,
                silent_log=args.silent_log,
                rollout_gate=args.rollout_gate,
                reports_dir=args.reports_dir,
                internal_export_manifest=args.internal_export_manifest,
                internal_labels=args.internal_labels,
                internal_lock_issues=args.internal_lock_issues,
            )
        except ValueError as exc:
            print(f"edc-query workstream verification failed: {exc}", file=sys.stderr)
            return 2
        print(f"EDC query workstream evidence written to {args.reports_dir}")
        return 0 if evidence["goal_complete"] else 5
    if args.command == "edc-query" and args.edc_command == "validate-internal-exports":
        try:
            validate_internal_exports(
                manifest=args.manifest,
                labels=args.labels,
                lock_issues=args.lock_issues,
                reports_dir=args.reports_dir,
            )
        except ValueError as exc:
            print(f"edc-query internal export validation failed: {exc}", file=sys.stderr)
            return 2
        print(f"EDC query internal export reports written to {args.reports_dir}")
        return 0
    if args.command == "prescreen" and args.prescreen_command == "ingest":
        nct_ids = [n.strip() for n in args.nct_ids.split(",") if n.strip()]
        try:
            recorded = record_studies(nct_ids, args.out)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen ingest failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {len(recorded)} studies to {args.out}: {', '.join(recorded)}")
        return 0
    if args.command == "prescreen" and args.prescreen_command == "search":
        status = [s.strip() for s in args.status.split(",") if s.strip()] if args.status else None
        try:
            recorded = record_search(
                args.out, cond=args.cond, term=args.term, status=status, max_studies=args.max
            )
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen search failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {len(recorded)} studies to {args.out}")
        return 0
    if args.command == "prescreen" and args.prescreen_command == "normalize-synthea":
        try:
            tables = read_synthea_csv_dir(args.csv_dir)
            corpora = normalize_synthea_corpus(tables, snapshot_date=args.snapshot)
        except (OSError, ValueError) as exc:
            print(f"prescreen normalize-synthea failed: {exc}", file=sys.stderr)
            return 2
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            for corpus in corpora:
                handle.write(json.dumps(corpus.to_dict(), sort_keys=True) + "\n")
        print(f"normalized {len(corpora)} patients to {args.out}")
        return 0
    if args.command == "prescreen" and args.prescreen_command == "ingest-pmc":
        try:
            count = record_pmc(args.out, limit=args.limit)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen ingest-pmc failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {count} PMC-Patients records to {args.out}")
        return 0
    if args.command == "prescreen" and args.prescreen_command == "validate":
        if not args.trials and not args.patients:
            print("prescreen validate: pass --trials and/or --patients", file=sys.stderr)
            return 2
        try:
            trials = load_recorded_studies(args.trials) if args.trials else []
            corpora = []
            if args.patients:
                if args.source == "pmc":
                    corpora = load_pmc_corpora(args.patients)
                else:
                    with Path(args.patients).open(encoding="utf-8") as handle:
                        corpora = [
                            corpus_from_dict(json.loads(line)) for line in handle if line.strip()
                        ]
        except (OSError, ValueError) as exc:
            print(f"prescreen validate failed: {exc}", file=sys.stderr)
            return 2
        report = report_for(trials=trials, corpora=corpora)
        text = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(text)
        else:
            print(text, end="")
        print(
            f"checked {report.records_checked} records: "
            f"{report.error_count} errors, {report.warning_count} warnings",
            file=sys.stderr,
        )
        return 0 if report.ok else 7
    if args.command == "prescreen" and args.prescreen_command == "show":
        try:
            trials = load_recorded_studies(args.fixtures)
        except (OSError, ValueError) as exc:
            print(f"prescreen show failed: {exc}", file=sys.stderr)
            return 2
        for trial in trials:
            age = trial.minimum_age.years
            print(
                f"{trial.trial_id}  [{trial.phase or '-'}] {trial.recruitment_status or '-'}  "
                f"min_age={age if age is not None else '-'}  {trial.title[:70]}"
            )
        return 0

    print("clinique — biostatistician agent suite.")
    print("Design: docs/design/  |  Index: docs/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

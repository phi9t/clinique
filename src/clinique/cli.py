"""CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clinique.edc.internal_preflight import preflight_internal_manifest
from clinique.edc.rollout import evaluate_rollout_gate, load_rollout_gate
from clinique.edc.silent import evaluate_silent_log, load_silent_log
from clinique.edc.validation import run_validation, validate_internal_exports, verify_workstream


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

    print("clinique — biostatistician agent suite.")
    print("Design: docs/design/  |  Index: docs/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""EDC query validation CLI handlers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clinique.edc.internal_preflight import preflight_internal_manifest
from clinique.edc.rollout import evaluate_rollout_gate, load_rollout_gate
from clinique.edc.silent import evaluate_silent_log, load_silent_log
from clinique.edc.validation import run_validation, validate_internal_exports, verify_workstream


def handle_edc(args: argparse.Namespace) -> int | None:
    if args.command != "edc-query":
        return None
    if args.edc_command == "validate":
        try:
            run_validation(fixtures=args.fixtures, reports_dir=args.reports_dir)
        except ValueError as exc:
            print(f"edc-query validation failed: {exc}", file=sys.stderr)
            return 2
        print(f"EDC query validation reports written to {args.reports_dir}")
        return 0
    if args.edc_command == "preflight-internal-data":
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
    if args.edc_command == "evaluate-silent-log":
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
    if args.edc_command == "evaluate-rollout-gate":
        try:
            gate = load_rollout_gate(args.gate)
        except ValueError as exc:
            print(f"edc-query rollout-gate evaluation failed: {exc}", file=sys.stderr)
            return 2
        report = evaluate_rollout_gate(gate)
        report.write_json(args.output)
        print(f"EDC query rollout-gate report written to {args.output}")
        return 0 if report.gates["rollout_gate_passed"] else 4
    if args.edc_command == "verify-workstream":
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
    if args.edc_command == "validate-internal-exports":
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
    return None

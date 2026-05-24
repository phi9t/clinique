"""CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clinique.edc.internal_preflight import preflight_internal_manifest
from clinique.edc.validation import run_validation


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

    print("clinique — biostatistician agent suite.")
    print("Design: docs/rfcs/  |  Workstreams: .workstreams/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Trial prescreening CLI handlers."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

from clinique.prescreen.explorer_export import export_explorer as write_explorer_json
from clinique.prescreen.ingestion import (
    load_recorded_studies,
    record_search,
    record_studies,
)
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.pmc_patients import load_pmc_corpora, record_pmc
from clinique.prescreen.validation import corpus_from_dict, report_for


def handle_prescreen(args: argparse.Namespace) -> int | None:
    if args.command != "prescreen":
        return None
    if args.prescreen_command == "ingest":
        nct_ids = [n.strip() for n in args.nct_ids.split(",") if n.strip()]
        try:
            recorded = record_studies(nct_ids, args.out)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen ingest failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {len(recorded)} studies to {args.out}: {', '.join(recorded)}")
        return 0
    if args.prescreen_command == "search":
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
    if args.prescreen_command == "normalize-synthea":
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
    if args.prescreen_command == "ingest-pmc":
        try:
            count = record_pmc(args.out, limit=args.limit)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen ingest-pmc failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {count} PMC-Patients records to {args.out}")
        return 0
    if args.prescreen_command == "validate":
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
    if args.prescreen_command == "show":
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
    if args.prescreen_command == "export-explorer":
        try:
            written = write_explorer_json(args.out)
        except (OSError, ValueError) as exc:
            print(f"prescreen export-explorer failed: {exc}", file=sys.stderr)
            return 2
        print(f"exported {len(written)} files to {args.out}: {', '.join(written)}")
        return 0
    return None

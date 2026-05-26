"""CLI handlers for agent benchmarks (PrescreenBench).

Exit codes (consistent with the prescreen CLI): 0 ok · 2 input/IO error · 9 hard safety gate fail.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def handle_benchmark(args: argparse.Namespace) -> int | None:
    if getattr(args, "command", None) != "benchmark":
        return None
    if args.benchmark_command != "prescreen":
        print("usage: clinique benchmark prescreen run|score|export-explorer", file=sys.stderr)
        return 2
    if args.prescreenbench_command == "run":
        return _run(args)
    if args.prescreenbench_command == "score":
        return _score(args)
    if args.prescreenbench_command == "export-explorer":
        return _export_explorer(args)
    print("usage: clinique benchmark prescreen run|score|export-explorer", file=sys.stderr)
    return 2


def _run(args: argparse.Namespace) -> int:
    from clinique.benchmarks.prescreenbench.baselines import BASELINES
    from clinique.benchmarks.prescreenbench.load import load_split
    from clinique.benchmarks.prescreenbench.score import run, write_predictions

    agent = args.agent.replace("-", "_")
    if agent not in BASELINES:
        print(
            f"benchmark prescreen run failed: unknown agent {agent!r}; "
            f"choose from {', '.join(sorted(BASELINES))}",
            file=sys.stderr,
        )
        return 2
    try:
        split = load_split(args.split, base=args.data_dir)
    except (OSError, FileNotFoundError) as exc:
        print(f"benchmark prescreen run failed: {exc}", file=sys.stderr)
        return 2
    rows, errors = run(split, agent)
    for err in errors:
        print(f"  run error: {err}", file=sys.stderr)
    if not rows:
        print("benchmark prescreen run produced no predictions", file=sys.stderr)
        return 2
    write_predictions(rows, args.out)
    print(
        f"wrote {len(rows)} predictions to {args.out} ({len(errors)} case errors)", file=sys.stderr
    )
    return 0


def _score(args: argparse.Namespace) -> int:
    from clinique.benchmarks.prescreenbench.load import load_split
    from clinique.benchmarks.prescreenbench.report import write_html, write_json
    from clinique.benchmarks.prescreenbench.score import load_predictions, score

    try:
        split = load_split(args.split, base=args.data_dir)
        predictions = load_predictions(args.pred)
    except (OSError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"benchmark prescreen score failed: {exc}", file=sys.stderr)
        return 2
    report = score(split, predictions)
    out_path = Path(args.out) if args.out else Path("reports/prescreenbench") / f"{args.split}.json"
    write_json(report, out_path, agent=args.agent)
    if args.html:
        write_html(report, args.html, agent=args.agent)
    gate = "PASS" if report.passed_hard_gates else f"FAIL {report.hard_gate_breaches}"
    print(
        f"score={report.score:.3f} macro_f1={report.criterion_macro_f1:.3f} "
        f"unsafe_clearance_rate={report.unsafe_clearance_rate:.3f} "
        f"gates={gate} -> {out_path}",
        file=sys.stderr,
    )
    return 0 if report.passed_hard_gates else 9


def _parse_mapping(items: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected agent=path, got {item!r}")
        agent, path = item.split("=", 1)
        if not agent or not path:
            raise ValueError(f"expected agent=path, got {item!r}")
        parsed[agent.replace("-", "_")] = Path(path)
    return parsed


def _export_explorer(args: argparse.Namespace) -> int:
    from clinique.benchmarks.prescreenbench import SPLITS
    from clinique.benchmarks.prescreenbench.explorer_export import export_explorer

    try:
        agents = tuple(
            a.strip().replace("-", "_") for a in (args.agents or "").split(",") if a.strip()
        )
        splits = tuple(args.split or SPLITS)
        prediction_paths = _parse_mapping(args.prediction)
        report_paths = _parse_mapping(args.report)
        written = export_explorer(
            args.out,
            splits=splits,
            agents=agents or (),
            custom_prediction_paths=prediction_paths,
            custom_report_paths=report_paths,
            base=args.data_dir,
        )
    except (OSError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"benchmark prescreen export-explorer failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"wrote PrescreenBench explorer bundle ({len(written)} files) to {args.out or 'default'}",
        file=sys.stderr,
    )
    return 0

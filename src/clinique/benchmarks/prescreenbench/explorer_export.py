"""Static JSON export for the PrescreenBench Explorer UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinique.prescreen import metrics as M
from clinique.prescreen.explorer_export import FIELD_DOCS, find_repo_root
from clinique.prescreen.schemas import PREDICTIONS, RECOMMENDATIONS

from . import BENCHMARK_ID, SPLITS
from .load import SplitData, load_split
from .report import to_json
from .score import annotate_case, load_predictions, run, score

DEFAULT_DEMO_AGENTS = ("always_unknown", "keyword_rule", "clinique_rule")


def default_out_dir() -> Path:
    """Default explorer output directory, resolved from the repo root."""
    return find_repo_root() / "explorer/public/data/prescreenbench"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_definitions() -> dict[str, Any]:
    """Build the UI-facing dictionary of field labels and metric definitions."""
    return {
        "labels": {
            "met": {"plain": "The patient satisfies this criterion."},
            "not_met": {"plain": "The patient does not satisfy this criterion."},
            "unknown": {
                "plain": (
                    "Available records do not support a definite call; this is the safe default."
                )
            },
            "not_applicable": {"plain": "The criterion does not apply to this patient/case."},
            "conflicting_evidence": {
                "plain": "The record contains evidence pointing in incompatible directions."
            },
        },
        "recommendations": {
            "potentially_eligible": {"plain": "No known blocking criterion was found."},
            "needs_review": {"plain": "Human review is needed before any screening decision."},
            "likely_ineligible": {"plain": "At least one blocking criterion appears present."},
        },
        "metrics": {
            "score": {"plain": "Weighted summary score after hard-gate penalties."},
            "criterion_macro_f1": {
                "plain": "Unweighted mean F1 across labels present in gold or prediction."
            },
            "evidence_support_accuracy": {
                "plain": (
                    "Among met/not_met predictions, the fraction backed by present verbatim "
                    "evidence."
                )
            },
            "unsafe_clearance_rate": {
                "plain": "Rate of clearing a possibly disqualifying criterion."
            },
            "unsupported_decision_count": {
                "plain": "Number of definite met/not_met predictions without required evidence."
            },
            "fabricated_quote_count": {
                "plain": "Number of cited quotes not found verbatim in the cited document."
            },
            "schema_valid_rate": {
                "plain": "Fraction of submitted case packets passing schema validation."
            },
            "blocking_criterion_recall": {
                "plain": "Fraction of gold blocking criteria predicted as blocking."
            },
        },
        "hard_gates": M.HARD_GATES,
        "primer": {
            "eligibility_criteria": (
                "Clinical-trial criteria are split into inclusion requirements and exclusion "
                "disqualifiers. Prescreening produces a review packet, not an enrollment decision."
            ),
            "evidence_grounding": (
                "Definite calls must cite patient evidence. Unknown is preferable to "
                "unsupported clearance."
            ),
            "biostats_reading": (
                "Macro-F1 treats each prediction label evenly, while safety gates "
                "prevent averaging away clinically risky errors."
            ),
        },
        "field_docs": FIELD_DOCS,
        "prediction_vocab": sorted(PREDICTIONS),
        "recommendation_vocab": sorted(RECOMMENDATIONS),
    }


def _agent_rows(split: SplitData, agent: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, errors = run(split, agent)
    predictions = {row["case_id"]: row for row in rows}
    report = score(split, predictions)
    payload = to_json(report, agent=agent)
    if errors:
        payload["run_errors"] = errors
    return predictions, payload


def build_split_bundle(
    split: SplitData,
    *,
    agents: tuple[str, ...] = DEFAULT_DEMO_AGENTS,
    custom_predictions: dict[str, dict[str, dict[str, Any]]] | None = None,
    custom_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one complete dataset bundle as UI-ready JSON."""
    predictions_by_agent: dict[str, dict[str, dict[str, Any]]] = {}
    reports_by_agent: dict[str, dict[str, Any]] = {}

    for agent in agents:
        predictions, report = _agent_rows(split, agent)
        predictions_by_agent[agent] = predictions
        reports_by_agent[agent] = report

    for agent, predictions in (custom_predictions or {}).items():
        predictions_by_agent[agent] = predictions
        report = custom_reports.get(agent) if custom_reports else None
        reports_by_agent[agent] = report or to_json(score(split, predictions), agent=agent)

    case_payloads: list[dict[str, Any]] = []
    for case in split.cases:
        gold = split.gold.get(case.case_id)
        if gold is None:
            continue
        trial = split.trials_by_id.get(case.trial_id)
        patient = split.corpora_by_id.get(case.patient_id)
        graders = {
            agent: annotate_case(
                case=case,
                gold=gold,
                corpus=patient,
                raw_prediction=predictions.get(case.case_id),
            )
            for agent, predictions in predictions_by_agent.items()
        }
        case_payloads.append(
            {
                "case": case.to_dict(),
                "trial": trial.to_dict() if trial is not None else None,
                "patient": patient.to_dict() if patient is not None else None,
                "gold": gold.to_dict(),
                "agent_outputs": {
                    agent: predictions.get(case.case_id)
                    for agent, predictions in predictions_by_agent.items()
                },
                "grader": graders,
            }
        )

    return {
        "split": split.split,
        "benchmark_id": BENCHMARK_ID,
        "task_types": sorted({case.task for case in split.cases}),
        "agents": [
            {"agent": agent, "report": reports_by_agent[agent]}
            for agent in sorted(predictions_by_agent)
        ],
        "cases": case_payloads,
    }


def export_explorer(
    out_dir: str | Path | None = None,
    *,
    splits: tuple[str, ...] = SPLITS,
    agents: tuple[str, ...] = DEFAULT_DEMO_AGENTS,
    custom_prediction_paths: dict[str, Path] | None = None,
    custom_report_paths: dict[str, Path] | None = None,
    base: str | Path | None = None,
) -> list[str]:
    """Write explorer JSON artifacts and return sorted written filenames."""
    out = Path(out_dir) if out_dir is not None else default_out_dir()
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    index: list[dict[str, Any]] = []

    _write_json(out / "definitions.json", build_definitions())
    written.append("definitions.json")

    custom_predictions = {
        agent: load_predictions(path) for agent, path in (custom_prediction_paths or {}).items()
    }
    custom_reports = {
        agent: json.loads(Path(path).read_text(encoding="utf-8"))
        for agent, path in (custom_report_paths or {}).items()
    }

    for split_name in splits:
        split = load_split(split_name, base=base)
        bundle = build_split_bundle(
            split,
            agents=agents,
            custom_predictions=custom_predictions,
            custom_reports=custom_reports,
        )
        filename = f"{split_name}.json"
        _write_json(out / filename, bundle)
        written.append(filename)
        index.append(
            {
                "split": split_name,
                "benchmark_id": BENCHMARK_ID,
                "case_count": len(bundle["cases"]),
                "agents": [agent["agent"] for agent in bundle["agents"]],
                "task_types": bundle["task_types"],
            }
        )

    _write_json(out / "index.json", index)
    written.append("index.json")
    return sorted(written)

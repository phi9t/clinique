"""File I/O activities for durable prescreen workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temporalio import activity

from clinique.durable.serde import corpus_from_dict, packet_from_dict, trial_to_dict
from clinique.prescreen.eval import EvalMetrics, load_eval_cases, load_patient_corpora
from clinique.prescreen.evidence_gate import check_evidence_provenance
from clinique.prescreen.ingestion import load_recorded_studies


def _load_corpora(path: str | Path, *, source: str) -> list[dict[str, Any]]:
    return [c.to_dict() for c in load_patient_corpora(path, source=source)]


@activity.defn
def load_eval_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    cases_path = payload["cases_path"]
    trials_path = payload["trials_path"]
    synthea_patients_path = payload.get("synthea_patients_path")
    pmc_patients_path = payload.get("pmc_patients_path")
    mimic_patients_path = payload.get("mimic_patients_path")
    cases = load_eval_cases(cases_path)
    trials = [trial_to_dict(t) for t in load_recorded_studies(trials_path)]
    corpora_by_source: dict[str, list[dict[str, Any]]] = {}
    if synthea_patients_path:
        corpora_by_source["synthea"] = _load_corpora(synthea_patients_path, source="synthea")
    if pmc_patients_path:
        corpora_by_source["pmc"] = _load_corpora(pmc_patients_path, source="pmc")
    if mimic_patients_path:
        corpora_by_source["mimic"] = _load_corpora(mimic_patients_path, source="mimic")
    return {
        "cases": [
            {
                "case_id": c.trial_id + "/" + c.patient_id,
                "trial_id": c.trial_id,
                "patient_id": c.patient_id,
                "snapshot_date": c.snapshot_date,
                "patient_source": c.patient_source,
                "gold_judgments": list(c.gold_judgments),
            }
            for c in cases
        ],
        "trials": trials,
        "corpora_by_source": corpora_by_source,
    }


@activity.defn
def score_eval_results(payload: dict[str, Any]) -> dict[str, Any]:
    case_results = payload["case_results"]
    reports_dir = payload["reports_dir"]
    metrics = EvalMetrics()
    for item in case_results:
        if item.get("error"):
            metrics.errors.append(str(item["error"]))
            continue
        packet = item.get("packet")
        if not packet:
            metrics.errors.append(f"missing packet for {item.get('case_id', '?')}")
            continue
        metrics.cases_run += 1
        if corpus_dict := item.get("corpus"):
            metrics.evidence_violations += len(
                check_evidence_provenance(
                    packet_from_dict(packet),
                    corpus_from_dict(corpus_dict),
                )
            )
        gold = {g["criterion_id"]: g["prediction"] for g in item.get("gold_judgments", [])}
        pred_by_id = {j["criterion_id"]: j for j in packet.get("judgments", [])}
        for cid, expected in gold.items():
            metrics.criterion_total += 1
            actual = pred_by_id.get(cid)
            if actual and actual.get("prediction") == expected:
                metrics.criterion_correct += 1
            elif (
                actual
                and actual.get("criterion_type") == "exclusion"
                and actual.get("prediction") == "not_met"
                and expected == "unknown"
            ):
                metrics.exclusion_false_negatives += 1
    report = metrics.to_dict()
    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "l0-eval-temporal.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"report_path": str(out_path), **report}

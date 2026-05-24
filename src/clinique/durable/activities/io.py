"""File I/O activities for durable prescreen workflows."""

from __future__ import annotations

import json
from pathlib import Path

from temporalio import activity

from clinique.durable.models import (
    BatchEvalInput,
    EvalCaseModel,
    EvalReport,
    GoldJudgmentModel,
    LoadEvalInputsResult,
    PatientCorpusModel,
    ScoreEvalInput,
    TrialModel,
)
from clinique.prescreen.eval import EvalMetrics, load_eval_cases, load_patient_corpora
from clinique.prescreen.evidence_gate import check_evidence_provenance
from clinique.prescreen.ingestion import load_recorded_studies


@activity.defn
def load_eval_inputs(payload: BatchEvalInput) -> LoadEvalInputsResult:
    cases = load_eval_cases(payload.cases_path)
    trials = tuple(TrialModel.from_domain(t) for t in load_recorded_studies(payload.trials_path))
    corpora_by_source: dict[str, tuple[PatientCorpusModel, ...]] = {}
    if payload.synthea_patients_path:
        corpora_by_source["synthea"] = tuple(
            PatientCorpusModel.from_domain(c)
            for c in load_patient_corpora(payload.synthea_patients_path, source="synthea")
        )
    if payload.pmc_patients_path:
        corpora_by_source["pmc"] = tuple(
            PatientCorpusModel.from_domain(c)
            for c in load_patient_corpora(payload.pmc_patients_path, source="pmc")
        )
    if payload.mimic_patients_path:
        corpora_by_source["mimic"] = tuple(
            PatientCorpusModel.from_domain(c)
            for c in load_patient_corpora(payload.mimic_patients_path, source="mimic")
        )
    return LoadEvalInputsResult(
        cases=tuple(
            EvalCaseModel(
                case_id=c.trial_id + "/" + c.patient_id,
                trial_id=c.trial_id,
                patient_id=c.patient_id,
                snapshot_date=c.snapshot_date,
                patient_source=c.patient_source,
                gold_judgments=tuple(
                    GoldJudgmentModel(criterion_id=g["criterion_id"], prediction=g["prediction"])
                    for g in c.gold_judgments
                ),
            )
            for c in cases
        ),
        trials=trials,
        corpora_by_source=corpora_by_source,
    )


@activity.defn
def score_eval_results(payload: ScoreEvalInput) -> EvalReport:
    metrics = EvalMetrics()
    for item in payload.case_results:
        if item.error:
            metrics.errors.append(item.error)
            continue
        if item.packet is None:
            metrics.errors.append(f"missing packet for {item.case_id}")
            continue
        metrics.cases_run += 1
        packet = item.packet.to_domain()
        if item.corpus is not None:
            metrics.evidence_violations += len(
                check_evidence_provenance(packet, item.corpus.to_domain())
            )
        gold = {g.criterion_id: g.prediction for g in item.gold_judgments}
        pred_by_id = {j.criterion_id: j for j in packet.judgments}
        for cid, expected in gold.items():
            metrics.criterion_total += 1
            actual = pred_by_id.get(cid)
            if actual and actual.prediction == expected:
                metrics.criterion_correct += 1
            elif (
                actual
                and actual.criterion_type == "exclusion"
                and actual.prediction == "not_met"
                and expected == "unknown"
            ):
                metrics.exclusion_false_negatives += 1
    report_dict = metrics.to_dict()
    out_dir = Path(payload.reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "l0-eval-temporal.json"
    out_path.write_text(json.dumps(report_dict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return EvalReport(
        report_path=str(out_path),
        cases_run=metrics.cases_run,
        criterion_total=metrics.criterion_total,
        criterion_correct=metrics.criterion_correct,
        criterion_accuracy=report_dict["criterion_accuracy"],
        evidence_violations=metrics.evidence_violations,
        exclusion_false_negatives=metrics.exclusion_false_negatives,
        errors=tuple(metrics.errors),
    )

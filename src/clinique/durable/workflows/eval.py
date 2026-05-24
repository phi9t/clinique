"""Batch eval durable workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from clinique.durable.activities.io import load_eval_inputs, score_eval_results
    from clinique.durable.activities.prescreen import resolve_screen_case
    from clinique.durable.config import ACTIVITY_RETRY_MAX, ACTIVITY_TIMEOUT, BATCH_EVAL_CONCURRENCY
    from clinique.durable.workflows.prescreen import ScreenPatientInput, ScreenPatientWorkflow


@dataclass
class BatchEvalInput:
    cases_path: str
    trials_path: str
    synthea_patients_path: str | None = None
    pmc_patients_path: str | None = None
    mimic_patients_path: str | None = None
    reports_dir: str = "reports/prescreen"


@workflow.defn
class BatchEvalWorkflow:
    @workflow.run
    async def run(self, payload: BatchEvalInput | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, dict):
            data = BatchEvalInput(**payload)
        else:
            data = payload

        retry = RetryPolicy(maximum_attempts=ACTIVITY_RETRY_MAX)
        inputs = await workflow.execute_activity(
            load_eval_inputs,
            {
                "cases_path": data.cases_path,
                "trials_path": data.trials_path,
                "synthea_patients_path": data.synthea_patients_path,
                "pmc_patients_path": data.pmc_patients_path,
                "mimic_patients_path": data.mimic_patients_path,
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry,
        )

        case_results: list[dict[str, Any]] = []
        cases = inputs["cases"]
        parent_id = workflow.info().workflow_id
        for batch_start in range(0, len(cases), BATCH_EVAL_CONCURRENCY):
            batch = cases[batch_start : batch_start + BATCH_EVAL_CONCURRENCY]
            batch_results: list[dict[str, Any]] = []
            for case in batch:
                batch_results.append(await self._run_case(case, inputs, parent_id, retry))
            case_results.extend(batch_results)

        return await workflow.execute_activity(
            score_eval_results,
            {"case_results": case_results, "reports_dir": data.reports_dir},
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry,
        )

    async def _run_case(
        self,
        case: dict[str, Any],
        inputs: dict[str, Any],
        parent_id: str,
        retry: RetryPolicy,
    ) -> dict[str, Any]:
        case_id = case.get("case_id", f"{case['trial_id']}/{case['patient_id']}")
        try:
            resolved = await workflow.execute_activity(
                resolve_screen_case,
                {
                    "case": case,
                    "trials": inputs["trials"],
                    "corpora_by_source": inputs["corpora_by_source"],
                },
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=retry,
            )
            packet = await workflow.execute_child_workflow(
                ScreenPatientWorkflow.run,
                ScreenPatientInput(
                    trial=resolved["trial"],
                    corpus=resolved["corpus"],
                ),
                id=f"{parent_id}/screen/{case_id}",
            )
            return {
                "case_id": case_id,
                "gold_judgments": resolved.get("gold_judgments", case.get("gold_judgments", [])),
                "packet": packet,
            }
        except Exception as exc:  # noqa: BLE001 — collect per-case errors for eval report
            return {"case_id": case_id, "error": str(exc)}


__all__ = ["BatchEvalInput", "BatchEvalWorkflow"]

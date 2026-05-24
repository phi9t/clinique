"""Batch eval durable workflow."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from clinique.durable.activities.io import load_eval_inputs, score_eval_results
    from clinique.durable.activities.prescreen import resolve_screen_case
    from clinique.durable.config import ACTIVITY_RETRY_MAX, ACTIVITY_TIMEOUT, BATCH_EVAL_CONCURRENCY
    from clinique.durable.models import (
        BatchEvalInput,
        EvalCaseModel,
        EvalCaseResult,
        EvalReport,
        LoadEvalInputsResult,
        ResolveScreenCaseInput,
        ScoreEvalInput,
        ScreenPatientInput,
    )
    from clinique.durable.workflows.prescreen import ScreenPatientWorkflow


@workflow.defn
class BatchEvalWorkflow:
    @workflow.run
    async def run(self, data: BatchEvalInput) -> EvalReport:
        retry = RetryPolicy(maximum_attempts=ACTIVITY_RETRY_MAX)
        inputs = await workflow.execute_activity(
            load_eval_inputs,
            data,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry,
        )

        case_results: list[EvalCaseResult] = []
        cases = inputs.cases
        parent_id = workflow.info().workflow_id
        for batch_start in range(0, len(cases), BATCH_EVAL_CONCURRENCY):
            batch = cases[batch_start : batch_start + BATCH_EVAL_CONCURRENCY]
            batch_results = list(
                await asyncio.gather(
                    *[self._run_case(case, inputs, parent_id, retry) for case in batch]
                )
            )
            case_results.extend(batch_results)

        return await workflow.execute_activity(
            score_eval_results,
            ScoreEvalInput(case_results=tuple(case_results), reports_dir=data.reports_dir),
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry,
        )

    async def _run_case(
        self,
        case: EvalCaseModel,
        inputs: LoadEvalInputsResult,
        parent_id: str,
        retry: RetryPolicy,
    ) -> EvalCaseResult:
        case_id = case.case_id
        try:
            resolved = await workflow.execute_activity(
                resolve_screen_case,
                ResolveScreenCaseInput(
                    case=case,
                    trials=inputs.trials,
                    corpora_by_source=inputs.corpora_by_source,
                ),
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=retry,
            )
            packet = await workflow.execute_child_workflow(
                ScreenPatientWorkflow.run,
                ScreenPatientInput(
                    trial=resolved.trial,
                    corpus=resolved.corpus,
                ),
                id=f"{parent_id}/screen/{case_id}",
            )
            return EvalCaseResult(
                case_id=case_id,
                gold_judgments=resolved.gold_judgments or case.gold_judgments,
                packet=packet,
                corpus=resolved.corpus,
            )
        except Exception as exc:  # noqa: BLE001 — collect per-case errors for eval report
            return EvalCaseResult(case_id=case_id, error=str(exc))


__all__ = ["BatchEvalWorkflow"]

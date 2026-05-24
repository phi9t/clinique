"""Prescreen durable workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from clinique.durable.activities.prescreen import (
        aggregate_judgments,
        append_ledger,
        assert_evidence_provenance_activity,
        atomize_trial,
        build_packet,
        evaluate_criterion,
    )
    from clinique.durable.config import (
        ACTIVITY_RETRY_MAX,
        ACTIVITY_TIMEOUT,
        GATE_RETRY_MAX,
        GATE_TIMEOUT,
        LEDGER_RETRY_MAX,
        LEDGER_TIMEOUT,
    )
    from clinique.prescreen.orchestrator import tool_fingerprint


@dataclass
class ScreenPatientInput:
    trial: dict[str, Any]
    corpus: dict[str, Any]
    append_ledger: bool = False
    ledger_path: str | None = None


@workflow.defn
class ScreenPatientWorkflow:
    @workflow.run
    async def run(self, payload: ScreenPatientInput | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, dict):
            data = ScreenPatientInput(
                trial=payload["trial"],
                corpus=payload["corpus"],
                append_ledger=bool(payload.get("append_ledger", False)),
                ledger_path=payload.get("ledger_path"),
            )
        else:
            data = payload

        retry = RetryPolicy(maximum_attempts=ACTIVITY_RETRY_MAX)
        gate_retry = RetryPolicy(maximum_attempts=GATE_RETRY_MAX)

        criteria = await workflow.execute_activity(
            atomize_trial,
            data.trial,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=retry,
        )

        judgments: list[dict[str, Any]] = []
        for criterion in criteria:
            judgments.append(
                await workflow.execute_activity(
                    evaluate_criterion,
                    args=[criterion, data.corpus],
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=retry,
                )
            )

        recommendation = await workflow.execute_activity(
            aggregate_judgments,
            judgments,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=retry,
        )

        packet = await workflow.execute_activity(
            build_packet,
            {
                "trial_dict": data.trial,
                "corpus_dict": data.corpus,
                "criteria": criteria,
                "judgment_dicts": judgments,
                "recommendation": recommendation,
            },
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=retry,
        )

        await workflow.execute_activity(
            assert_evidence_provenance_activity,
            args=[packet, data.corpus],
            start_to_close_timeout=GATE_TIMEOUT,
            retry_policy=gate_retry,
        )

        if data.append_ledger and data.ledger_path:
            await workflow.execute_activity(
                append_ledger,
                args=[packet, data.ledger_path],
                start_to_close_timeout=LEDGER_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=LEDGER_RETRY_MAX),
            )

        return packet


def screen_workflow_id(trial_id: str, patient_id: str, snapshot_date: str | None) -> str:
    snap = snapshot_date or "none"
    return f"prescreen/{trial_id}/{patient_id}/{snap}/{tool_fingerprint()}"


__all__ = ["ScreenPatientInput", "ScreenPatientWorkflow", "screen_workflow_id"]

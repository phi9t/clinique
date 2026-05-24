"""Prescreen Temporal activities."""

from __future__ import annotations

from clinique.durable.activities.io import (
    load_eval_inputs,
    load_trial_and_corpus,
    score_eval_results,
)
from clinique.durable.activities.prescreen import (
    aggregate_judgments,
    append_ledger,
    assert_evidence_provenance_activity,
    atomize_trial,
    build_packet,
    evaluate_criterion,
    judge_criterion,
    resolve_screen_case,
    retrieve_evidence,
)

ALL_ACTIVITIES = [
    atomize_trial,
    retrieve_evidence,
    judge_criterion,
    evaluate_criterion,
    aggregate_judgments,
    build_packet,
    assert_evidence_provenance_activity,
    append_ledger,
    load_trial_and_corpus,
    load_eval_inputs,
    score_eval_results,
    resolve_screen_case,
]

__all__ = ["ALL_ACTIVITIES"]

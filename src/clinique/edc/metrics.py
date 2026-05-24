from __future__ import annotations

from datetime import datetime
from statistics import median

from clinique.edc.records import CandidateQuery, EvaluationMetrics, QueryLabel


def _key(item: CandidateQuery | QueryLabel) -> tuple[str, str, str]:
    return (item.subject_id, item.form, item.field)


def evaluate_candidates(
    candidates: tuple[CandidateQuery, ...],
    labels: tuple[QueryLabel, ...],
    *,
    replayed_at: datetime,
) -> EvaluationMetrics:
    labels_by_key = {_key(label): label for label in labels}
    true_detected = 0
    false_queries = 0
    category_matches = 0
    days_earlier: list[float] = []

    for candidate in candidates:
        label = labels_by_key.get(_key(candidate))
        if label and label.gold_query_needed:
            true_detected += 1
            if label.query_category == candidate.query_category:
                category_matches += 1
            if label.opened_at:
                delta = label.opened_at - replayed_at
                days_earlier.append(max(delta.total_seconds() / 86400, 0.0))
        else:
            false_queries += 1

    total = len(candidates)
    duplicate_queries = sum(1 for candidate in candidates if candidate.is_duplicate)
    return EvaluationMetrics(
        candidates_total=total,
        true_discrepancies_detected=true_detected,
        false_queries=false_queries,
        false_query_rate=false_queries / total if total else 0.0,
        duplicate_queries=duplicate_queries,
        duplicate_query_rate=duplicate_queries / total if total else 0.0,
        query_category_accuracy=category_matches / true_detected if true_detected else 0.0,
        evidence_support_accuracy=sum(1 for candidate in candidates if candidate.evidence) / total
        if total
        else 0.0,
        median_days_earlier=median(days_earlier) if days_earlier else 0.0,
    )

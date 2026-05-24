from __future__ import annotations

from datetime import date

from clinique.edc.records import CandidateQuery, EdcRecord, QueryLog, ReplayEvidence, SourceRef


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _record_source(record: EdcRecord) -> SourceRef:
    return SourceRef("record", record.record_id, record.collected_at)


def _candidate(
    evidence: ReplayEvidence,
    record: EdcRecord,
    *,
    query_category: str,
    query_text: str,
    rule_id: str | None,
    is_duplicate: bool = False,
    extra_sources: tuple[SourceRef, ...] = (),
) -> CandidateQuery:
    sources = [
        _record_source(record),
        SourceRef("snapshot", evidence.snapshot.snapshot_id, evidence.snapshot.snapshot_at),
    ]
    if rule_id is not None:
        rule = next(rule for rule in evidence.active_rules if rule.rule_id == rule_id)
        sources.append(SourceRef("rule", rule.rule_id, rule.effective_at))
    sources.extend(extra_sources)
    return CandidateQuery(
        study_id=record.study_id,
        site_id=record.site_id,
        subject_id=record.subject_id,
        form=record.form,
        field=record.field,
        query_category=query_category,
        query_text=query_text,
        evidence=tuple(sources),
        rule_id=rule_id,
        is_duplicate=is_duplicate,
    )


def detect_candidate_queries(
    evidence: ReplayEvidence, *, existing_queries: tuple[QueryLog, ...]
) -> tuple[CandidateQuery, ...]:
    candidates: list[CandidateQuery] = []
    records_by_key = {
        (record.study_id, record.site_id, record.subject_id, record.form, record.field): record
        for record in evidence.snapshot.records
    }

    for record in evidence.snapshot.records:
        for rule in evidence.active_rules:
            if (record.form, record.field) != (rule.form, rule.field):
                continue
            if rule.kind == "required_field" and not record.value.strip():
                candidates.append(
                    _candidate(
                        evidence,
                        record,
                        query_category=rule.query_category,
                        query_text=f"{rule.message} Subject {record.subject_id}, {record.form}.{record.field}.",
                        rule_id=rule.rule_id,
                    )
                )
            elif rule.kind == "date_order" and rule.compare_to_related:
                observed = _parse_date(record.value)
                comparator = _parse_date(record.related.get(rule.compare_to_related, ""))
                if observed and comparator and rule.operator == "<=" and observed > comparator:
                    candidates.append(
                        _candidate(
                            evidence,
                            record,
                            query_category=rule.query_category,
                            query_text=(
                                f"{rule.message} Observed {record.value}; "
                                f"related {rule.compare_to_related} is {comparator.isoformat()}."
                            ),
                            rule_id=rule.rule_id,
                        )
                    )
            elif rule.kind == "future_date":
                observed = _parse_date(record.value)
                if observed and observed > evidence.replayed_at.date():
                    candidates.append(
                        _candidate(
                            evidence,
                            record,
                            query_category=rule.query_category,
                            query_text=(
                                f"{rule.message} Observed {record.value}; "
                                f"snapshot date is {evidence.replayed_at.date().isoformat()}."
                            ),
                            rule_id=rule.rule_id,
                        )
                    )

    for query in existing_queries:
        if query.opened_at > evidence.replayed_at:
            continue
        key = (query.study_id, query.site_id, query.subject_id, query.form, query.field)
        record = records_by_key.get(key)
        if record is None:
            continue
        candidates.append(
            _candidate(
                evidence,
                record,
                query_category="duplicate",
                query_text=f"Existing query {query.query_id} already covers {query.form}.{query.field}.",
                rule_id=None,
                is_duplicate=True,
                extra_sources=(SourceRef("query_log", query.query_id, query.opened_at),),
            )
        )

    return tuple(candidates)

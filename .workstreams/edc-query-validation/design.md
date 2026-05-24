# Workstream: edc-query-validation — implementation design

This workstream turns RFC-0006's validation framework into a concrete, data-rich plan for a
draft-only EDC/data-management query agent. The goal is not to prove that a model is generally
"accurate"; it is to prove that the agent improves data-cleaning workflow outcomes without
increasing participant, data-integrity, blinding, privacy, or compliance risk.

`tracker.org` holds the executable task breakdown, task prompts, metadata, and acceptance
criteria.

## Why this wedge first

EDC query workflows are the preferred first expansion beyond the biostatistician suite when
historical EDC snapshots, query logs, and resolution history are available. Unlike recruitment
or safety agents, this path can begin as operational, draft-only decision support. Labels are
already present in routine trial operations: whether a query was opened, what field it targeted,
how it was resolved, whether it was duplicated or false, and how long resolution took.

## Context of use

The agent drafts candidate data queries for human data managers. It does not write back to EDC,
close queries, modify subject data, contact sites, unblind data, or perform final adjudication.
Every recommendation must be auditable to source fields, rules, snapshots, model/tool versions,
and the human reviewer decision.

## Data inputs

Minimum internal data package:

- Timestamped EDC snapshots or exports at multiple review dates.
- Query logs with subject, site, form, field, query text, open/close timestamps, status, and
  resolution.
- Edit-check rule history and effective dates.
- Database-lock issue logs.
- Source-data verification findings when available.
- Optional: monitoring notes or form completion status to explain delayed or waived queries.

Synthetic fixtures should mirror these structures without PHI and should be sufficient for unit
and offline regression tests.

## Label model

Each candidate discrepancy receives both task and workflow labels:

```json
{
  "snapshot_id": "...",
  "snapshot_at": "2026-03-01T00:00:00Z",
  "study_id": "...",
  "site_id": "...",
  "subject_id": "...",
  "form": "ConMeds",
  "field": "start_date",
  "candidate_query": "...",
  "gold_query_needed": true,
  "query_category": "missing | inconsistent | impossible | source_mismatch | duplicate",
  "human_resolution": "corrected | confirmed | no_query_needed | duplicate | waived",
  "opened_at": "2026-03-03T12:00:00Z",
  "closed_at": "2026-03-05T18:00:00Z",
  "evidence_available_at_agent_time": true
}
```

Retrospective replay must use only fields, rules, and snapshots available at the replay
timestamp. Any label derived from later resolution is allowed only as outcome truth, not as
agent input.

## Validation phases

1. **L0 fixtures and validators** — validate parsers, timestamp handling, rule loading,
   duplicate detection, provenance records, and the no-write-back invariant.
2. **L1 offline replay** — run the agent over frozen historical snapshots and compare against
   known query logs and adjudicated no-query cases.
3. **L2 retrospective replay** — replay multiple historical review dates to measure whether the
   agent would have surfaced true discrepancies earlier than manual review.
4. **L3 silent prospective** — run hidden beside the data-management workflow for 4-12 weeks.
   Humans operate normally; agent outputs are compared later.
5. **L4 controlled draft-only rollout** — human-approved query drafting, randomized by study,
   form family, site, or data-manager queue only after silent-mode gates pass.

## Metrics

Primary metrics:

- True discrepancy detection rate.
- False query rate.
- Duplicate query rate.
- Query-category accuracy.
- Data-manager acceptance rate.
- Median time from discrepancy availability to query surfacing.
- Query resolution time.
- Open queries at database lock.
- Manual review minutes per accepted query.

Safety and compliance metrics:

- Unauthorized write-back attempts: zero.
- Unsupported evidence citations: zero or adjudicated below release threshold.
- Blinding-boundary violations: zero.
- PHI/privacy handling violations: zero.
- False query burden per reviewer/week below predefined tolerance.

## Ship gates

Do not move past silent mode unless the agent finds true discrepancies earlier or with less
manual effort, keeps false and duplicate queries within the workflow tolerance, produces
human-reviewable query text, records complete provenance, and proves that every action remains
draft-only with named human approval before any EDC action.

## Out of scope

This workstream does not implement recruitment, safety reporting, patient contact, automated
query issuance, automated source-data changes, database lock decisions, or access to unblinded
treatment assignment.


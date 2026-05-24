# EDC query validation — design

**Status:** `LOCAL-COMPLETE` (2026-05-24). Local synthetic L0–L2 validation is implemented and
verified. `goal_complete` remains false until internal EDC exports and prospective validation
evidence exist. See [validation summary](../edc-query-validation/validation-summary.md) and
[release-readiness checklist](../edc-query-validation/release-readiness-checklist.md).

Draft-only EDC/data-management query agent. The goal is not to prove that a model is generally
"accurate"; it is to prove that the agent improves data-cleaning workflow outcomes without
increasing participant, data-integrity, blinding, privacy, or compliance risk.

**North-star question:** does the agent improve data-cleaning outcomes without increasing
participant, data-integrity, blinding, privacy, or compliance risk?

## Validation philosophy

**Accuracy is not usefulness.** Two label families answer the ship question:

- **Task labels** — was the output correct?
- **Workflow/outcome labels** — did it save time, raise recall, cut errors, speed lock?

## Why this wedge first

EDC query workflows are the preferred first expansion beyond the biostatistician suite when
historical EDC snapshots, query logs, and resolution history are available. Unlike recruitment
or safety agents, this path can begin as operational, draft-only decision support. Labels are
already present in routine trial operations.

## Context of use

The agent drafts candidate data queries for human data managers. It does not write back to EDC,
close queries, modify subject data, contact sites, unblind data, or perform final adjudication.
Every recommendation must be auditable to source fields, rules, snapshots, model/tool versions,
and the human reviewer decision.

## Validation phases (L0–L4)

| Layer | Question | EDC status |
|---|---|---|
| **L0** Unit / tool validation | Do deterministic pieces work? | Complete on synthetic fixtures |
| **L1** Offline benchmark | Task accuracy on held-out data? | Complete on synthetic fixtures |
| **L2** Retrospective replay | Useful as-of-time without leakage? | Complete on synthetic fixtures |
| **L3** Silent prospective | Real-world utility, zero operational impact? | Protocol documented; no run yet |
| **L4** Controlled rollout | Causal improvement with human approval? | Gate documented; no rollout yet |

## Data inputs

Minimum internal data package:

- Timestamped EDC snapshots or exports at multiple review dates.
- Query logs with subject, site, form, field, query text, open/close timestamps, status, and
  resolution.
- Edit-check rule history and effective dates.
- Database-lock issue logs.
- Source-data verification findings when available.

Synthetic fixtures in `tests/fixtures/edc_query/` mirror these structures without PHI.

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
  "query_category": "missing | inconsistent | impossible | source_mismatch | duplicate | no_query",
  "human_resolution": "corrected | confirmed | no_query_needed | duplicate | waived",
  "opened_at": "2026-03-03T12:00:00Z",
  "closed_at": "2026-03-05T18:00:00Z",
  "evidence_available_at_agent_time": true
}
```

Retrospective replay must use only fields, rules, and snapshots available at the replay
timestamp. Outcome labels from later resolution are evaluation truth only, never agent input.

## Metrics

**Primary:** true discrepancy detection rate, false query rate, duplicate query rate,
query-category accuracy, acceptance rate, time-to-surfacing, resolution time, open queries at
lock, manual review minutes per accepted query.

**Safety:** unauthorized write-back (zero), unsupported evidence citations, blinding violations,
PHI/privacy violations, false query burden per reviewer/week.

## Ship gates

Do not move past silent mode unless the agent finds true discrepancies earlier or with less
manual effort, keeps false and duplicate queries within workflow tolerance, produces
human-reviewable query text, records complete provenance, and remains draft-only with named
human approval before any EDC action.

## Implementation layout

```
src/clinique/edc/
  records.py, fixtures.py, replay.py, detection.py, metrics.py, reports.py
  internal_preflight.py, internal_import.py, silent.py, rollout.py
  validation.py, audit.py
tests/fixtures/edc_query/
reports/edc-query/
```

### CLI

```bash
uv run clinique edc-query validate --fixtures tests/fixtures/edc_query --reports-dir reports/edc-query
uv run clinique edc-query preflight-internal-data \
  --manifest docs/edc-query-validation/internal-data-manifest.template.json
uv run clinique edc-query validate-internal-exports \
  --manifest tests/fixtures/edc_query/internal_export_manifest.json \
  --labels tests/fixtures/edc_query/labels.json \
  --lock-issues tests/fixtures/edc_query/lock_issues.json \
  --reports-dir reports/edc-query
uv run clinique edc-query evaluate-silent-log \
  --log tests/fixtures/edc_query/silent_log.json \
  --output reports/edc-query/silent-log-evaluation.json
uv run clinique edc-query evaluate-rollout-gate \
  --gate tests/fixtures/edc_query/controlled_rollout_gate.json \
  --output reports/edc-query/controlled-rollout-gate.json
uv run clinique edc-query verify-workstream \
  --fixtures tests/fixtures/edc_query \
  --manifest docs/edc-query-validation/internal-data-manifest.template.json \
  --silent-log tests/fixtures/edc_query/silent_log.json \
  --rollout-gate tests/fixtures/edc_query/controlled_rollout_gate.json \
  --reports-dir reports/edc-query \
  --internal-export-manifest tests/fixtures/edc_query/internal_export_manifest.json \
  --internal-labels tests/fixtures/edc_query/labels.json \
  --internal-lock-issues tests/fixtures/edc_query/lock_issues.json
```

`verify-workstream` exits nonzero while operational blockers remain (`goal_complete: false` is
expected until internal/prospective evidence is connected).

## Governance artifacts

Companion files under [`docs/edc-query-validation/`](../edc-query-validation/):

- `release-readiness-checklist.md` — ship gates (read by bundled verifier)
- `validation-summary.md` — evidence record and verification commands
- `annotation-manual.md`, `label-schema.json` — adjudication contract
- `internal-data-manifest.template.json` — approved-export preflight template
- `data-inventory.md`, `access-boundary.md` — data boundary
- `silent-prospective-protocol.md`, `controlled-rollout-gate.md` — L3/L4 protocols

## Not yet proven

Internal EDC snapshots, real query logs, resolution history, and silent prospective data are not
connected. Do not claim production validation.

## Recommendation

Continue to internal data inventory and replay. Do not move to silent prospective or controlled
rollout until internal L1/L2 evidence meets predefined gates.

## Out of scope

Recruitment, safety reporting, patient contact, automated query issuance, automated source-data
changes, database lock decisions, or access to unblinded treatment assignment.

# EDC Query Validation Summary

## Current Evidence

Local synthetic validation is implemented and verified with deterministic tests and reports.

Evidence:

- `tests/fixtures/edc_query/PROVENANCE.md` documents PHI-free synthetic fixtures.
- `reports/edc-query/offline-benchmark.json` reports 4 candidates, 4 true discrepancies, 0 false
  queries, 1 duplicate, evidence support 1.0, category accuracy 1.0, and no-write-back gate true.
- `reports/edc-query/retrospective-replay.json` reports timestamped replay over two synthetic
  snapshots with leakage checks true.
- `reports/edc-query/audit-summary.json` records local synthetic validation as complete and
  derives the remaining blocked requirements from
  `.workstreams/edc-query-validation/release-readiness-checklist.md`.
- `uv run clinique edc-query validate --fixtures tests/fixtures/edc_query --reports-dir
  reports/edc-query` regenerates the reports and audit summary from source fixtures.
- `uv run clinique edc-query preflight-internal-data --manifest
  .workstreams/edc-query-validation/internal-data-manifest.template.json --output
  reports/edc-query/internal-preflight-template.json` validates the internal-data manifest
  contract without reading PHI-bearing exports.
- `uv run clinique edc-query validate-internal-exports --manifest
  tests/fixtures/edc_query/internal_export_manifest.json --labels
  tests/fixtures/edc_query/labels.json --lock-issues tests/fixtures/edc_query/lock_issues.json
  --reports-dir reports/edc-query` validates the approved-export import path on synthetic
  fixture data and returns a controlled validation failure for missing export payloads.
- `uv run clinique edc-query evaluate-silent-log --log tests/fixtures/edc_query/silent_log.json
  --output reports/edc-query/silent-log-evaluation.json --false-positive-tolerance 1.0`
  validates the silent-log evaluation path and produces reviewer-week normalized false-positive
  burden, time-delta, and stop-criteria metrics. It writes the report and exits nonzero when
  silent gates fail, including safety-risk stop criteria, and rejects string values where
  booleans are required, unknown ground-truth labels, malformed or blank evidence citations,
  inconsistent safety-risk ground-truth/flag labels, logs with no recommendations, or negative
  tolerance thresholds.
- `uv run clinique edc-query evaluate-rollout-gate --gate
  tests/fixtures/edc_query/controlled_rollout_gate.json --output
  reports/edc-query/controlled-rollout-gate.json` validates the controlled-rollout gate mechanics
  against structured synthetic evidence and rejects incomplete threshold, observed-metric, or
  safety endpoint packages, including string values where numeric, boolean, or safety-count
  fields are required.
- `uv run clinique edc-query verify-workstream --fixtures tests/fixtures/edc_query --manifest
  .workstreams/edc-query-validation/internal-data-manifest.template.json --silent-log
  tests/fixtures/edc_query/silent_log.json --rollout-gate
  tests/fixtures/edc_query/controlled_rollout_gate.json --reports-dir reports/edc-query
  --internal-export-manifest tests/fixtures/edc_query/internal_export_manifest.json
  --internal-labels tests/fixtures/edc_query/labels.json --internal-lock-issues
  tests/fixtures/edc_query/lock_issues.json` regenerates all local reports, including
  fixture-backed approved-export L1/L2 reports, and writes
  `reports/edc-query/workstream-verification.json`. It exits nonzero while real
  internal/prospective blockers remain.
- `uv run pytest` covers fixture loading, PHI/unblinded rejection, timestamp gating, no-write API
  exposure, duplicate-query timestamp gating, study/site matching, and query-log provenance,
  typed privacy/blinding and label booleans, schema enum enforcement for query categories,
  query-log status, and human resolutions, required replay timestamps, record-vs-snapshot
  chronology, query/label open-close chronology, query-log status/timestamp consistency,
  query-log status/resolution consistency, label no-query semantic consistency,
  snapshot/study/site-scoped task and workflow metric attribution, evidence-availability guards
  for true detections, duplicate snapshot ID, unknown snapshot reference, label/query
  snapshot-record reference validation, label/query event-vs-record chronology, source-record,
  query-log snapshot chronology, query-log ID, and adjudication-label rejection, duplicate
  database-lock issue ID and severity rejection, database-lock issue record-reference and
  event-chronology validation, rule-history ID, chronology, kind, and parameter validation,
  detection, metrics, CLI execution,
  annotation-manual alignment, internal-data preflight, silent-log query-category, evidence, and
  recommendation-ID enforcement, silent evidence-citation validation, safety-label consistency,
  signed timing metrics, and evaluation, controlled-rollout gate rate validation and evaluation,
  approved-export import, bundled workstream verification, and report serialization.

## Not Yet Proven

This work does not prove real operational usefulness because internal EDC snapshots, real query
logs, resolution history, and silent prospective data are not connected. The next decision is to
obtain internal read-only data access or stop before claiming production validation.

## Recommendation

Continue to internal data inventory and replay. Do not move to silent prospective or controlled
rollout until internal L1/L2 evidence meets predefined gates.

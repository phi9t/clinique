# EDC Query Release Readiness Checklist

## Synthetic Validation

- [x] PHI-free fixtures exist.
- [x] Fixture provenance exists.
- [x] Timestamp gating is tested.
- [x] Draft-only/no-write boundary is tested.
- [x] Duplicate-query detection excludes future query logs, matches by study/site identity, and
      cites historical query-log evidence.
- [x] Fixture loaders require typed privacy, blinding, and adjudication-label booleans plus
      schema-defined query category, status, and resolution enums.
- [x] Fixture loaders reject missing required replay timestamps instead of defaulting them.
- [x] Fixture and approved-export loaders reject records with `collected_at` after the containing
      snapshot timestamp.
- [x] Query-log and label loaders reject impossible open/close timestamp chronology.
- [x] Query-log loaders reject status/timestamp mismatches for open and closed queries.
- [x] Query-log loaders use a query-log-specific resolution enum and reject open/closed
      status-resolution mismatches.
- [x] Label loaders reject inconsistent `gold_query_needed`, `no_query`, and
      `no_query_needed` combinations.
- [x] Task and workflow metrics match labels and database-lock issues by study, site, subject,
      form, and field.
- [x] Task metrics match labels by replay snapshot ID as well as study, site, subject, form,
      and field to prevent cross-snapshot label leakage.
- [x] True-detection metrics require label evidence to be available at the replay timestamp.
- [x] Fixture and approved-export loaders reject duplicate snapshot IDs before replay
      provenance can become ambiguous.
- [x] Fixture and approved-export loaders reject label and query-log references to unknown
      snapshot IDs.
- [x] Fixture and approved-export loaders reject labels and query logs whose study/site/subject/
      form/field key is absent from the referenced snapshot.
- [x] Fixture and approved-export loaders reject label and query-log opened timestamps that
      predate the referenced source record collection timestamp.
- [x] Fixture and approved-export loaders reject query logs opened before their referenced
      snapshot timestamp.
- [x] Snapshot loaders reject duplicate source-record keys before detection can overwrite them.
- [x] Fixture and approved-export loaders reject duplicate query-log IDs before provenance can
      become ambiguous.
- [x] Fixture and approved-export loaders reject duplicate adjudication label keys.
- [x] Fixture and approved-export loaders reject duplicate database-lock issue IDs.
- [x] Fixture and approved-export loaders enforce schema-defined database-lock issue severity
      values.
- [x] Fixture and approved-export loaders reject database-lock issues that do not reference any
      record key present in replay snapshots.
- [x] Fixture and approved-export loaders reject database-lock issue discovery timestamps that
      predate referenced source record collection.
- [x] Rule-history loaders reject duplicate rule IDs and impossible effective/retired chronology.
- [x] Rule-history loaders reject unknown rule kinds and incomplete date-order rule parameters.
- [x] Annotation manual defines the same study/site-scoped unit used by loaders and metrics.
- [x] Offline report exists.
- [x] Retrospective replay report exists.
- [x] CLI validation command regenerates reports and audit summary.
- [x] Audit summary explicitly marks the overall goal incomplete until internal/prospective
      evidence exists.
- [x] Internal-data manifest preflight command exists and validates readiness metadata without
      reading PHI-bearing exports, including top-level JSON object, manifest version/timestamp
      checks, and rejection of unknown source types outside `edc_snapshots`, `query_logs`, and
      `edit_check_history`; owner/export path metadata and schema sketches must contain
      nonblank strings and the source-specific fields required by the approved-export importer;
      missing schema fields are reported per source type.
- [x] Silent-log evaluator exists, requires typed boolean gate fields, writes reviewer-week
      burden gate reports, rejects empty logs, evidence-free recommendations, malformed or
      blank evidence citations, unknown query categories and ground-truth labels, inconsistent
      safety-risk ground-truth/flag labels, and duplicate recommendation IDs, and exits nonzero
      for stop criteria or uncontrolled false-positive burden; non-finite or negative burden
      tolerances are rejected as invalid input.
- [x] Silent-log evaluator preserves signed timing deltas so late recommendations are not
      counted as neutral or early.
- [x] Controlled-rollout gate evaluator exists, rejects incomplete gate packages, and validates
      typed finite numeric thresholds, bounded rate values, nonnegative integer count endpoints,
      integer true-discrepancy deltas, improvement-oriented thresholds, allowed randomization
      units, nonnegative safety-count endpoints, and human approval path from structured
      evidence.
- [x] Bundled workstream verifier regenerates local synthetic reports, optional approved-export
      fixture reports, and consolidates remaining blockers in
      `reports/edc-query/workstream-verification.json`.
- [x] Approved-export import path is executable against synthetic fixture exports and generates
      internal-style L1/L2 reports without claiming real operational validation.

## Internal Data Validation

- [ ] Internal EDC snapshots approved and connected.
- [ ] Internal query logs approved and connected.
- [ ] Internal edit-check history approved and connected.
- [ ] Internal L1 offline report generated.
- [ ] Internal L2 retrospective replay report generated.

## Prospective Validation

- [ ] Silent prospective protocol approved.
- [ ] Silent prospective run completed.
- [ ] Controlled rollout gate approved.
- [ ] Human approval path validated.

## Ship Gate

Do not ship until internal and prospective validation show earlier or lower-effort true
discrepancy detection, controlled false and duplicate query burden, evidence-backed query text,
complete auditability, and no write-back without named human approval.

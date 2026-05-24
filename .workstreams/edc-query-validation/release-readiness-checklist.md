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
- [x] Query-log and label loaders reject impossible open/close timestamp chronology.
- [x] Task and workflow metrics match labels and database-lock issues by study, site, subject,
      form, and field.
- [x] True-detection metrics require label evidence to be available at the replay timestamp.
- [x] Snapshot loaders reject duplicate source-record keys before detection can overwrite them.
- [x] Fixture and approved-export loaders reject duplicate query-log IDs before provenance can
      become ambiguous.
- [x] Fixture and approved-export loaders reject duplicate adjudication label keys.
- [x] Rule-history loaders reject duplicate rule IDs and impossible effective/retired chronology.
- [x] Annotation manual defines the same study/site-scoped unit used by loaders and metrics.
- [x] Offline report exists.
- [x] Retrospective replay report exists.
- [x] CLI validation command regenerates reports and audit summary.
- [x] Audit summary explicitly marks the overall goal incomplete until internal/prospective
      evidence exists.
- [x] Internal-data manifest preflight command exists and validates readiness metadata without
      reading PHI-bearing exports.
- [x] Silent-log evaluator exists, requires typed boolean gate fields, writes reviewer-week
      burden gate reports, rejects empty logs and unknown ground-truth labels, and exits nonzero
      for stop criteria or uncontrolled false-positive burden; negative burden tolerances are
      rejected as invalid input.
- [x] Controlled-rollout gate evaluator exists, rejects incomplete gate packages, and validates
      typed numeric thresholds, nonnegative safety-count endpoints, and human approval path from
      structured evidence.
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

# EDC Query Validation Summary

## Current Evidence

Local synthetic validation is implemented and verified with deterministic tests and reports.

Evidence:

- `tests/fixtures/edc_query/PROVENANCE.md` documents PHI-free synthetic fixtures.
- `reports/edc-query/offline-benchmark.json` reports 4 candidates, 4 true discrepancies, 0 false
  queries, 1 duplicate, evidence support 1.0, category accuracy 1.0, and no-write-back gate true.
- `reports/edc-query/retrospective-replay.json` reports timestamped replay over two synthetic
  snapshots with leakage checks true.
- `uv run pytest` covers fixture loading, PHI/unblinded rejection, timestamp gating, no-write API
  exposure, detection, metrics, and report serialization.

## Not Yet Proven

This work does not prove real operational usefulness because internal EDC snapshots, real query
logs, resolution history, and silent prospective data are not connected. The next decision is to
obtain internal read-only data access or stop before claiming production validation.

## Recommendation

Continue to internal data inventory and replay. Do not move to silent prospective or controlled
rollout until internal L1/L2 evidence meets predefined gates.


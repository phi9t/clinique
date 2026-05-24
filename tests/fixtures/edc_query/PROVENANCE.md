# EDC Query Synthetic Fixture Provenance

These fixtures are synthetic and contain no PHI, PII, real subject identifiers, unblinded
treatment fields, source notes, or real clinical-trial exports.

The package models a minimal EDC query validation set:

- `snapshots.json`: two timestamped EDC snapshots for replay leakage checks.
- `rules.json`: active, future-effective, and retired edit-check rules.
- `query_logs.json`: a historical resolved query used to test duplicate detection.
- `labels.json`: adjudicated task and workflow labels for true discrepancies, duplicate
  burden, and a no-query negative case.

The fixture scenarios cover missing required data, cross-form date inconsistency, impossible
future visit date, duplicate query burden, and a record that should not produce a query.

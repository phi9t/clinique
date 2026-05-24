# EDC Query Validation Data Inventory

## Current Local Package

This workstream currently validates against a PHI-free synthetic package in
`tests/fixtures/edc_query/`.

| Source | Path | Coverage | Sensitivity | Status |
|---|---|---|---|---|
| EDC snapshots | `snapshots.json` | 2 replay dates, 5 synthetic records | no PHI, no unblinded data | available |
| Edit-check rules | `rules.json` | active, future-effective, retired rules | no PHI | available |
| Query logs | `query_logs.json` | 1 resolved historical query | no PHI | available |
| Labels | `labels.json` | true, duplicate, and no-query labels | no PHI | available |
| Fixture provenance | `PROVENANCE.md` | synthesis notes | no PHI | available |

## Internal Data Package Required For Operational Validation

| Source | Required fields | Owner | Access state | Impact if missing |
|---|---|---|---|---|
| EDC snapshots/exports | study, site, subject, form, field, value, timestamp | data management lead | not connected | cannot run real replay |
| Query logs | query text, field target, open/close time, status, resolution | data management lead | not connected | no operational labels |
| Edit-check rule history | rule id, effective/retired dates, logic, category | EDC build owner | not connected | cannot reproduce historical rule state |
| Database-lock issue logs | issue, discovery date, severity, resolution | study data lead | not connected | weak usefulness labels |
| SDV findings | source mismatch, field, date, outcome | clinical operations | optional | weaker source-mismatch validation |

Internal data must be read-only, PHI-governed, and screened for unblinded fields before use.


# Synthea Fixture Provenance

## `synthea/*.csv`

Fully **synthetic, hand-authored** Synthea-shaped CSV rows for offline, deterministic tests of
`normalize_synthea` / `normalize_synthea_corpus`. These are *not* a real Synthea export — they
contain no PHI, PII, or real subject data, only the column layout the normalizer consumes.

Files and the columns the normalizer reads (extra columns are ignored by `csv.DictReader`):

| File | Columns used |
|---|---|
| `patients.csv` | `Id`, `BIRTHDATE`, `GENDER` |
| `conditions.csv` | `PATIENT`, `START`, `CODE`, `DESCRIPTION` |
| `medications.csv` | `PATIENT`, `START`, `CODE`, `DESCRIPTION` |
| `observations.csv` | `PATIENT`, `DATE`, `CODE`, `DESCRIPTION`, `VALUE`, `UNITS` |
| `procedures.csv` | `PATIENT`, `START`, `CODE`, `DESCRIPTION` |

Two synthetic patients (P1, P2); P2 exists only to verify per-patient filtering.

To use a **real** Synthea export, generate one with the Synthea tool (Apache-2.0) and point
`read_synthea_csv_dir` at the output `csv/` directory. Synthea output is itself fully synthetic, so
it carries no data-use agreement.

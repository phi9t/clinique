# MIMIC-IV Demo Fixture Provenance

## `mimic_demo/*.csv`

Fully **synthetic, hand-authored** rows shaped like the MIMIC-IV `hosp` module, for offline,
deterministic tests of `read_mimic_csv_dir` / `normalize_mimic` / `normalize_mimic_corpus`.

> **Important:** the real MIMIC-IV demo is *real de-identified* data. Per this repo's
> PHI-free/synthetic fixture rule, **no real MIMIC rows are committed here.** These files only
> reproduce the column layout the normalizer consumes (synthetic subject_ids 10001/10002, synthetic
> codes, no real patient data).

Tables and the columns the normalizer reads:

| File | Columns used |
|---|---|
| `patients.csv` | `subject_id`, `gender`, `anchor_age` |
| `admissions.csv` | `hadm_id`, `admittime` (dates the diagnoses) |
| `diagnoses_icd.csv` | `subject_id`, `hadm_id`, `icd_code`, `icd_version` → `condition` |
| `d_icd_diagnoses.csv` | `icd_code`, `icd_version`, `long_title` |
| `labevents.csv` | `subject_id`, `itemid`, `charttime`, `value`, `valuenum`, `valueuom` → `observation` |
| `d_labitems.csv` | `itemid`, `label` |
| `prescriptions.csv` | `subject_id`, `starttime`, `drug`, `gsn` → `medication` |
| `procedures_icd.csv` | `subject_id`, `chartdate`, `icd_code`, `icd_version` → `procedure` |
| `d_icd_procedures.csv` | `icd_code`, `icd_version`, `long_title` |

To use the **real** demo: download it from PhysioNet
(https://physionet.org/content/mimic-iv-demo/ — Open Database License, no DUA required), and point
`read_mimic_csv_dir` at the extracted `hosp/` directory (`.csv` or `.csv.gz` both work). Keep the
real export in a git-ignored local path; do not commit it.

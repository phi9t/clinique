# Prescreen Copilot — Data Inventory

Large corpora live under **`~/.clinique/datasets/`** (override with `CLINIQUE_DATASETS_DIR`).
The repo holds manifests, gold labels, and tiny CI fixtures only.

## Scale corpus (`~/.clinique/datasets/prescreen-copilot/`)

| Logical name | File | Source | Target scale |
|---|---|---|---|
| `trials` | `trials.jsonl` | ClinicalTrials.gov API v2 search | NSCLC recruiting, up to 1000 |
| `synthea_patients` | `synthea_patients.jsonl` | Synthea CSV → normalizer | Full fixture corpus |
| `pmc_patients` | `pmc_patients.jsonl` | PMC-Patients HF rows | Up to 1000 open rows |
| `mimic_demo_patients` | `mimic_demo_patients.jsonl` | MIMIC-IV demo hosp CSVs | All demo subjects |

## CI micro-fixtures (`tests/fixtures/prescreen/`)

| Path | Role |
|---|---|
| `trials.jsonl` | 2 frozen CT.gov studies (offline unit tests) |
| `synthea/` | Synthetic-shaped CSV rows |
| `pmc_patients.jsonl` | 2 synthetic PMC-shaped rows |
| `mimic_demo/` | Synthetic-shaped MIMIC demo CSVs |

## Fetch recipes

```bash
DATASETS=~/.clinique/datasets/prescreen-copilot
mkdir -p "$DATASETS"

uv run clinique prescreen search --cond "Non-Small Cell Lung Cancer" \
  --status RECRUITING --max 1000 --out "$DATASETS/trials.jsonl"

uv run clinique prescreen ingest-pmc --limit 1000 --out "$DATASETS/pmc_patients.jsonl"

uv run clinique prescreen normalize-synthea \
  --csv-dir tests/fixtures/prescreen/synthea \
  --snapshot 2026-03-01 --out "$DATASETS/synthea_patients.jsonl"

uv run clinique prescreen normalize-mimic-demo \
  --csv-dir tests/fixtures/prescreen/mimic_demo \
  --out "$DATASETS/mimic_demo_patients.jsonl"
```

## Sensitivity

All listed sources are public / synthetic. n2c2 2018 and full MIMIC-IV require DUAs and stay
out of scope.

# Prescreen Copilot Dataset Provenance

Recorded **2026-05-24** under `~/.clinique/datasets/prescreen-copilot/`.

| File | Records | Command / source |
|---|---|---|
| `trials.jsonl` | 1000 | `uv run clinique prescreen search --cond "Non-Small Cell Lung Cancer" --status RECRUITING --max 1000 --out ~/.clinique/datasets/prescreen-copilot/trials.jsonl` |
| `synthea_patients.jsonl` | 2 | `uv run clinique prescreen normalize-synthea --csv-dir tests/fixtures/prescreen/synthea --snapshot 2026-03-01 --out ...` |
| `mimic_demo_patients.jsonl` | 2 | `uv run clinique prescreen normalize-mimic-demo --csv-dir tests/fixtures/prescreen/mimic_demo --out ...` |
| `pmc_patients.jsonl` | 2 | HF datasets-server returned HTTP 500 on 2026-05-24; committed fixture copied as fallback (`tests/fixtures/prescreen/pmc_patients.jsonl`) |

Re-fetch PMC when the HuggingFace rows API is healthy:

```bash
uv run clinique prescreen ingest-pmc --limit 1000 \
  --out ~/.clinique/datasets/prescreen-copilot/pmc_patients.jsonl
```

Gold-label eval trials (`NCT02578680`) are merged from `tests/fixtures/prescreen/trials.jsonl`
during `verify-workstream` even when absent from the scale search corpus.

# PMC-Patients Fixture Provenance

## `pmc_patients.jsonl`

Two **synthetic, hand-authored** records shaped like PMC-Patients rows
(`patient_id`, `patient_uid`, `PMID`, `title`, `patient` summary text, `age` as
`[[value, unit], ...]`, `gender` `M`/`F`). These are *not* real PMC case reports — they contain no
real patient text — they only reproduce the field layout `parse_pmc_record` consumes, so the parser
can be tested offline.

To record a **real** sample, run `record_pmc(out_path, limit=N)` (or
`clinique prescreen ingest-pmc --limit N --out ...`), which pulls from the public HuggingFace
datasets-server endpoint for `zhengyun21/PMC-Patients`. PMC-Patients is derived from the PubMed
Central Open Access subset (CC-licensed); honor the per-article licenses of any real records you
record. A case report has no enrollment as-of time, so each corpus has `snapshot_date=None`.

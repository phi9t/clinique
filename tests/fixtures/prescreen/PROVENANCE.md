# Prescreening Fixture Provenance

## `trials.jsonl`

Real ClinicalTrials.gov API v2 single-study payloads, one per line, fetched 2026-05-24 and frozen
here for offline, reproducible tests. Recorded via:

```bash
uv run clinique prescreen ingest --nct-ids NCT02578680,NCT06123754 \
  --out tests/fixtures/prescreen/trials.jsonl
```

Each line was requested with `fields` limited to the modules the parser consumes
(`identificationModule`, `statusModule`, `conditionsModule`, `designModule`, `eligibilityModule`,
`sponsorCollaboratorsModule`) to keep the snapshot small and stable.

| NCT id | Trial | Why included |
|---|---|---|
| NCT02578680 | KEYNOTE-189 (pembrolizumab + chemo in nonsquamous NSCLC) | Stable completed trial; rich inclusion/exclusion text; matches the design's running oncology example |
| NCT06123754 | Recruiting Phase 3 NSCLC study | A second record so the corpus exercises multi-line JSONL parsing |

ClinicalTrials.gov data is in the public domain (U.S. Government work) and the API requires no key
or data-use agreement. The live API mutates as trials update; this frozen copy is the test of
record. Re-run the `ingest` command to refresh.

## Synthea (patient side)

No Synthea export is committed. The normalizer's input contract is documented inline in
`tests/test_prescreen_normalizer.py` using Synthea-shaped row dicts (fully synthetic, no PHI).
Generate a real export with the Synthea tool (Apache-2.0) and point `read_synthea_csv_dir` at the
output `csv/` directory.

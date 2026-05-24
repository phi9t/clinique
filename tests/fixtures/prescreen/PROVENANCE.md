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

To pull a whole disease area instead of an enumerated id list, use search + pagination:

```bash
uv run clinique prescreen search --cond "Non-Small Cell Lung Cancer" \
  --status RECRUITING --max 200 --out tests/fixtures/prescreen/trials.jsonl
```

## `search_nsclc_page.json`

A single **synthetic** ClinicalTrials.gov v2 *search-response page* (two trimmed studies plus a
`nextPageToken`). It exists to test `parse_search_page` offline — the pure half of the network
search path — without freezing a real, mutating search result.

## Other sources

Per-source synthetic fixtures and their record commands live next to the data:

- Synthea — `synthea/` + `synthea/PROVENANCE.md`
- PMC-Patients — `pmc_patients.jsonl` + `pmc_patients.PROVENANCE.md`
- MIMIC-IV demo — `mimic_demo/` + `mimic_demo/PROVENANCE.md` (real demo is de-identified data; only
  synthetic-shaped rows are committed)

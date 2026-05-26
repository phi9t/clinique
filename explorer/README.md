# Clinique Dataset Explorer

Vite + React dashboard for browsing FDA-pilot CDISC ADaM datasets and prescreen L0 public data (schema, distributions, drill-down, conformance reports).

**New to the domain?** See the [terminology glossary](../docs/primer/terminology-glossary.md) — acronyms for CDISC (ADaM, ADSL, define.xml), prescreen (NCT, PatientCorpus), and the [three-wedge comparison](../docs/primer/terminology-glossary.md#19-three-wedges-compared-for-ml-audiences).

**Live demo:** [https://phi9t.github.io/clinique/](https://phi9t.github.io/clinique/)

## Local development

```bash
npm install && npm run dev
```

## GitHub Pages build

```bash
npm run build:pages
```

## PrescreenBench explorer data

Regenerate committed deterministic PrescreenBench explorer bundles:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --split lite \
  --agents always_unknown,keyword_rule,clinique_rule \
  --out explorer/public/data/prescreenbench
```

Run the browser workflow check:

```bash
npm run test:e2e
```

See the root [README](../README.md) for regeneration commands and deploy setup.

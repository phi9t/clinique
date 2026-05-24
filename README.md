# Clinique

Agentic tooling for regulated clinical-trial workflows — assistive agents with deterministic
gates, not autonomous trial execution. Design docs live in [`docs/`](docs/README.md).

**New here? (ML background)** Start with the [ML onboarding primer](docs/primer/README.md) —
clinical trials explained in ML language, then a map into this repo. For acronyms and jargon (EDC,
CDISC, ADaM, NCT, L0–L4), see the [terminology glossary](docs/primer/terminology-glossary.md).

Capability design docs:

- [Biostatistician agent suite](docs/design/biostat-agent-suite.md) — platform substrate +
  biostat capabilities (provenance, power, programming, conformance, estimand, dry-run)
- [EDC query validation](docs/design/edc-query-validation.md) — draft-only EDC query validation
  (local synthetic phase complete; operational validation blocked on internal/prospective evidence)
- [Trial prescreening agent](docs/design/trial-prescreening.md) — eligibility prescreening copilot
  (L0 public path: CT.gov ingestion/search, Synthea/PMC/MIMIC normalizers, validation gate)

## Quickstart

```bash
uv sync                 # create venv, install dev deps from uv.lock
uv run pytest           # run the test suite
```

R-backed engines (rpact/gsDesign) run in a pinned Docker image; bring up the daemon
(`colima start` or Docker Desktop) and build:

```bash
docker build -t clinique-r-engine:0.1.0 docker/r-engine
```

The pure-Python `ReferenceEngine` runs without Docker and is used as an independent cross-check
oracle; Docker cross-check tests skip automatically when the daemon is unreachable.

## What's implemented

- **Platform substrate:** append-only provenance ledger; numeric-provenance linter.
- **Sample-size orchestrator:** validated-engine-only computation, reproducible records,
  sensitivity sweep, and a hard numeric-provenance gate.
- **Estimand checker, side-lock/dry-run harness, conformance triage** scaffolds (see biostat
  design doc).
- **EDC query validation:** deterministic L0–L2 harness on PHI-free fixtures; approved-export
  import path; silent-log and controlled-rollout gate evaluators; bundled workstream verifier.
  Local synthetic validation is complete; `goal_complete` remains false until internal EDC data
  and prospective runs exist.
- **Trial prescreening (L0):** ClinicalTrials.gov record-and-replay ingestion and search,
  Synthea/PMC-Patients/MIMIC-IV demo normalizers, L0 conformance gate (`prescreen validate`);
  frozen fixture corpus; atomizer/judge proposed (see prescreen design doc).

## Trial prescreening CLI

Show recorded trials offline:

```bash
uv run clinique prescreen show --fixtures tests/fixtures/prescreen/trials.jsonl
```

Record new trials from ClinicalTrials.gov (network):

```bash
uv run clinique prescreen ingest --nct-ids NCT02578680,NCT06123754 \
  --out tests/fixtures/prescreen/trials.jsonl
```

Offline conformance check (exit 7 when records fail vocab / leakage rules):

```bash
uv run clinique prescreen validate \
  --trials tests/fixtures/prescreen/trials.jsonl
```

Synthea CSV → PatientCorpus JSONL (offline; requires a Synthea export directory):

```bash
uv run clinique prescreen normalize-synthea \
  --csv-dir tests/fixtures/prescreen/synthea \
  --snapshot 2026-03-01 \
  --out /tmp/patients.jsonl
```

## EDC query validation CLI

Regenerate local synthetic reports:

```bash
uv run clinique edc-query validate --fixtures tests/fixtures/edc_query --reports-dir reports/edc-query
```

Run bundled workstream verification (exits nonzero while operational blockers remain):

```bash
uv run clinique edc-query verify-workstream \
  --fixtures tests/fixtures/edc_query \
  --manifest docs/edc-query-validation/internal-data-manifest.template.json \
  --silent-log tests/fixtures/edc_query/silent_log.json \
  --rollout-gate tests/fixtures/edc_query/controlled_rollout_gate.json \
  --reports-dir reports/edc-query \
  --internal-export-manifest tests/fixtures/edc_query/internal_export_manifest.json \
  --internal-labels tests/fixtures/edc_query/labels.json \
  --internal-lock-issues tests/fixtures/edc_query/lock_issues.json
```

See [validation summary](docs/edc-query-validation/validation-summary.md) for status.

## Dataset explorer

**Live demo:** [https://phi9t.github.io/clinique/](https://phi9t.github.io/clinique/)

The [`explorer/`](explorer/) app is a Vite + React dashboard with two dataset families:

- **Regulatory CDISC** — FDA-pilot ADaM datasets and Define-XML metadata under `explorer/public/data/`
- **Prescreen L0** — public trial/patient records, schema docs, distributions, and conformance reports under `explorer/public/data/prescreen/`

```bash
cd explorer && npm install && npm run dev
```

Build for production with `npm run build`. For GitHub Pages (project site at `/clinique/`):

```bash
npm run build:pages
```

**One-time setup:** In the GitHub repo, go to **Settings → Pages → Build and deployment** and set **Source** to **GitHub Actions**. Pushes to `main` that touch `explorer/` trigger an automatic deploy via [`.github/workflows/pages.yml`](.github/workflows/pages.yml).

Regenerate prescreen explorer JSON from committed fixtures:

```bash
uv run clinique prescreen export-explorer --out explorer/public/data/prescreen
```

Regenerate CDISC JSON fixtures with the dataset conversion script before deploying if source SAS/define files change.

## Releasing

This is an **internal/private** package (not published to PyPI). See [`RELEASING.md`](RELEASING.md)
for the version-bump, gate, and tag process, and [`CHANGELOG.md`](CHANGELOG.md) for release notes.

## License

Licensed under the [Apache License 2.0](LICENSE).

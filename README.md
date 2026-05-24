# Clinique

Agentic tooling around the **biostatistician persona** in clinical trials. Design docs live in
[`docs/`](docs/README.md):

- [Biostatistician agent suite](docs/design/biostat-agent-suite.md) — platform substrate +
  biostat capabilities (provenance, power, programming, conformance, estimand, dry-run)
- [EDC query validation](docs/design/edc-query-validation.md) — draft-only EDC query validation
  (local synthetic phase complete; operational validation blocked on internal/prospective evidence)

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

The [`explorer/`](explorer/) app is a Vite + React dashboard for browsing FDA-pilot CDISC ADaM
datasets and Define-XML metadata under `explorer/public/data/`.

```bash
cd explorer && npm install && npm run dev
```

Build for production with `npm run build`. Regenerate JSON fixtures with the dataset conversion
script before deploying if source SAS/define files change.

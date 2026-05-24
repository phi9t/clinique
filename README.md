# Clinique

Agentic tooling around the **biostatistician persona** in clinical trials. Design lives in
[`docs/rfcs/`](docs/rfcs/README.md). Implementation workstreams:

- [`.workstreams/biostat-agent-suite/`](.workstreams/biostat-agent-suite/design.md) — RFCs 0000–0006
  (provenance, power, programming, conformance, estimand, dry-run)
- [`.workstreams/edc-query-validation/`](.workstreams/edc-query-validation/design.md) — RFC-0006
  draft-only EDC query validation (local synthetic phase complete; operational validation blocked
  on internal/prospective evidence)

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

- **Substrate (RFC-0000):** append-only provenance ledger; numeric-provenance linter.
- **RFC-0003:** sample-size orchestrator with validated-engine-only computation, reproducible
  records, sensitivity sweep, and a hard numeric-provenance gate.
- **RFC-0001/0002/0004/0005:** estimand checker, side-lock/dry-run harness, conformance triage
  scaffolds (see biostat workstream tracker).
- **EDC query validation (RFC-0006):** deterministic L0–L2 harness on PHI-free fixtures;
  approved-export import path; silent-log and controlled-rollout gate evaluators; bundled
  workstream verifier. Local synthetic validation is complete; `goal_complete` remains false
  until internal EDC data and prospective runs exist.

## EDC query validation CLI

Regenerate local synthetic reports:

```bash
uv run clinique edc-query validate --fixtures tests/fixtures/edc_query --reports-dir reports/edc-query
```

Run bundled workstream verification (exits nonzero while operational blockers remain):

```bash
uv run clinique edc-query verify-workstream \
  --fixtures tests/fixtures/edc_query \
  --manifest .workstreams/edc-query-validation/internal-data-manifest.template.json \
  --silent-log tests/fixtures/edc_query/silent_log.json \
  --rollout-gate tests/fixtures/edc_query/controlled_rollout_gate.json \
  --reports-dir reports/edc-query \
  --internal-export-manifest tests/fixtures/edc_query/internal_export_manifest.json \
  --internal-labels tests/fixtures/edc_query/labels.json \
  --internal-lock-issues tests/fixtures/edc_query/lock_issues.json
```

See [`.workstreams/edc-query-validation/tracker.org`](.workstreams/edc-query-validation/tracker.org)
and [validation summary](.workstreams/edc-query-validation/validation-summary.md) for status.

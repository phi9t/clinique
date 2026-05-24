# Clinique

Agentic tooling around the **biostatistician persona** in clinical trials. Design lives in
[`docs/rfcs/`](docs/rfcs/README.md); the active implementation workstream is
[`.workstreams/biostat-agent-suite/`](.workstreams/biostat-agent-suite/design.md).

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

See the workstream tracker for status and the remaining RFC scaffolds.

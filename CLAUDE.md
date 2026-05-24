# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Agentic tooling for the **biostatistician persona** in clinical trials. The Python package
`clinique` (src layout) is a set of capabilities — sample-size/power, estimand consistency,
statistical-programming side-lock, dry-run, CDISC conformance, EDC query validation, trial
prescreening — built on a shared governance **substrate**. A separate Vite + React app lives in
`explorer/`.

Design intent lives in `docs/design/` (`biostat-agent-suite.md`, `edc-query-validation.md`,
`trial-prescreening.md`); start there for the "why" behind any module. Docstrings reference
`RFC-NNNN §X` markers — these are a naming convention mapping to capabilities in the design docs,
not separate RFC files.

**If you're new to clinical trials:** read `docs/primer/` first — domain mental model, then repo
map and commands.

## Commands

```bash
uv sync                 # create venv, install dev deps from uv.lock
uv run pytest           # full test suite
uv run pytest tests/test_power_orchestrator.py            # one file
uv run pytest tests/test_power_orchestrator.py::test_name # one test
uv run ruff check .     # lint (line-length 100)
uv run ruff format .    # format

# Prescreen L0 (offline tests + fixture summary)
uv run pytest tests/test_prescreen_ingestion.py tests/test_prescreen_normalizer.py \
  tests/test_prescreen_search.py tests/test_prescreen_pmc.py \
  tests/test_prescreen_mimic.py tests/test_prescreen_validation.py -q
uv run clinique prescreen show --fixtures tests/fixtures/prescreen/trials.jsonl
uv run clinique prescreen validate --trials tests/fixtures/prescreen/trials.jsonl \
  --patients tests/fixtures/prescreen/pmc_patients.jsonl --source pmc   # exit 7 on errors

# Prescreen durable execution (optional; requires `uv sync --group temporal`)
# temporal server start-dev   # background
# uv run clinique prescreen worker
# uv run clinique prescreen screen --temporal --trial-id NCT... --patient-id P1 ...
# uv run pytest tests/test_durable_prescreen.py -q
```

R-backed engine (rpact) runs in a pinned Docker image. Bring up the daemon (`colima start` or
Docker Desktop), then:

```bash
docker build -t clinique-r-engine:0.1.0 docker/r-engine
```

Tests that need Docker (`test_rpact_docker.py`) **skip automatically** when the daemon is
unreachable or the image isn't built — they are a cross-check, not a hard dependency.

Explorer app:

```bash
cd explorer && npm install && npm run dev   # dev server; npm run build / npm run lint
```

## Core invariants (treat as pass/fail gates, never soften)

These structural rules are the point of the codebase. Changing code that weakens one is a
regression even if tests pass:

- **Numeric-provenance** (`substrate/numeric_provenance.py`): no number in a `ComputationRecord`'s
  result/narrative may exist unless it traces (within tolerance) to an `EngineResult` output or an
  `Assumption` value. The orchestrator runs this as a HARD GATE before any ledger write. The
  `DEFAULT_WHITELIST` of structural constants is deliberately tiny — don't expand it to paper over
  an untraceable number.
- **Validated-engine-only**: the orchestrator never computes a statistical number itself; only
  registered engines (carrying name+version) do.
- **Append-only ledger** (`substrate/provenance.py`): JSONL, no update/delete API by design.
- **Reproducibility**: same intake → identical `ComputationRecord` (determinism test).
- **Data-wall** (`dryrun/harness.py`): the harness imports no real-data/unblinding path and refuses
  any provider that isn't a `SyntheticDataProvider`; a build-invariant test asserts this.
- **Side-lock** (`programming/side_lock.py`): agent-contributed side per `output_id` is write-once.
- **Read-only estimand**: no artifact-write API exists in `estimand/`.

## Architecture

**`substrate/`** is the foundation every numeric capability builds on: the append-only provenance
ledger, the numeric-provenance linter, and shared dataclasses (`Assumption`, `EngineResult`,
`ComputationRecord` in `records.py`).

**`power/`** is the reference capability and the clearest example of the pattern. The
`orchestrator` pipeline is: select method → assemble assumptions → run a validated engine →
sensitivity sweep → build a record whose narrative is assembled ONLY from blessed numbers → run the
numeric-provenance gate → append to ledger. Two engines implement the `PowerEngine` Protocol:
`RpactDockerEngine` (canonical, regulatory-validated rpact via Docker; records image + package
versions) and `ReferenceEngine` (deterministic pure-Python, stdlib `statistics.NormalDist`),
which doubles as the offline fallback and the independent cross-check oracle. All engines use the
normal (z) approximation.

**`edc/`** (EDC query validation) is a gate-driven workstream exposed through the `clinique`
CLI (`src/clinique/cli.py`, entry point `clinique = clinique.cli:main`). Subcommands under
`edc-query` (`validate`, `verify-workstream`, `evaluate-silent-log`, `evaluate-rollout-gate`,
`preflight-internal-data`, `validate-internal-exports`) read PHI-free fixtures and emit JSON
reports. **Exit codes are meaningful** (0 ok; 2 input/parse error; 3 preflight fail; 4 rollout gate
fail; 5 workstream `goal_complete` false; 6 silent-log gate fail) — preserve them. `goal_complete`
is intentionally `false` until real internal EDC data and prospective runs exist; do not flip
gates to make it pass.

**`prescreen/`** (trial prescreening, L0 public data layer) fetches, parses, and validates the
public data, converging heterogeneous sources onto two typed records: `Trial` (ClinicalTrials.gov)
and `PatientCorpus`/`PatientDocument` (all patient sources). Trial ingestion supports both an
enumerated-id recorder and **search + pagination** (`ingestion.py`). Three patient sources
normalize to the shared corpus: Synthea (`normalizer.py`, corpus-wide), PMC-Patients
(`pmc_patients.py`, real free text → `note` docs), and the MIMIC-IV demo (`mimic_demo.py`, real
de-identified structured data — only synthetic-shaped fixtures are committed). Every source keeps
the **fetch/parse split**: network fetchers record raw snapshots; pure parsers are offline-tested
against committed fixtures. `validation.py` is the **conformance gate** — controlled vocabularies
(in `schemas.py`), age-bound sanity, duplicate-id, and the snapshot **no-leakage** invariant
(`document.date` ≤ `snapshot_date`). CLI: `prescreen ingest` / `search` / `normalize-synthea` /
`ingest-pmc` (record fixtures), `prescreen validate` (exit `7` on error-severity issues), and
`prescreen show` (offline summary). Atomizer, retriever, judge, and evidence gate are design-only
for now — see `docs/design/trial-prescreening.md`.

Other capabilities (`estimand/`, `programming/`, `dryrun/`, `conformance/`, `io/xpt.py`) follow the
same shape: deterministic logic over typed records, validated against synthetic fixtures and, where
available, real FDA-pilot CDISC data in `tests/fixtures/realdata/`.

## Conventions

- Core runtime is **stdlib-only** (Python 3.12+); `uv` manages only dev deps (`pytest`, `ruff`).
  Don't add runtime dependencies to `pyproject.toml` without strong reason.
- Each capability pairs `src/clinique/<cap>/` with `tests/test_<cap>_*.py`.
- Test fixtures must be PHI-free / synthetic; fixture directories carry a `PROVENANCE.md`
  documenting their source.

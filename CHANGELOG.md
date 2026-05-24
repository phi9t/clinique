# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-24

First tagged release. Establishes the governance substrate and the biostatistician-persona
capability set on PHI-free / synthetic fixtures.

### Added

- **Substrate** — append-only JSONL provenance ledger, the numeric-provenance linter, and the
  shared `Assumption` / `EngineResult` / `ComputationRecord` dataclasses.
- **Power / sample-size** — validated-engine-only orchestrator (select method → assemble
  assumptions → run engine → sensitivity sweep → numeric-provenance gate → ledger append) with two
  engines: `RpactDockerEngine` (regulatory-validated rpact via a pinned Docker image) and the
  pure-Python `ReferenceEngine` (offline fallback and independent cross-check oracle).
- **Estimand** — read-only consistency checker (timepoint alignment, population-definition
  consistency, shell-backed derivations) over an artifact graph; Define-XML cross-checks.
- **Statistical programming** — write-once side-lock per `output_id`.
- **Dry-run** — synthetic-only harness with a data-wall build invariant (rejects any non-synthetic
  provider).
- **Conformance** — CDISC conformance triage scaffolding.
- **EDC query validation** — deterministic L0–L2 detection harness, approved-export import path,
  silent-log and controlled-rollout gate evaluators, and a bundled workstream verifier exposed
  through the `clinique edc-query` CLI with meaningful exit codes (0/2/3/4/5/6).
- **Trial prescreening (L0)** — ClinicalTrials.gov ingestion and Synthea normalizer.
- **Explorer** — Vite + React dashboard (`explorer/`) for browsing FDA-pilot CDISC ADaM datasets
  and Define-XML metadata.

### Packaging

- Apache-2.0 license; package marked private (`Private :: Do Not Upload`) — internal distribution
  only, no PyPI publish.
- Single-sourced version (hatchling reads `src/clinique/__init__.py`).
- `py.typed` marker so downstream consumers pick up inline type hints.
- GitHub Actions CI: ruff lint, ruff format check, pytest, and `uv build` on a frozen lockfile.

### Notes

- `goal_complete` for the EDC query-validation workstream is intentionally `false` until real
  internal EDC data and prospective runs exist; gates are not flipped to force a pass.
- Core runtime is stdlib-only (Python 3.12+); `uv` manages dev dependencies only.

[Unreleased]: https://github.com/phi9t/clinique/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/phi9t/clinique/releases/tag/v0.1.0

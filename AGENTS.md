# Repository Guidelines

## Project Structure & Module Organization

`src/clinique/` contains the Python package. Major modules are organized by domain:
`estimand/`, `power/`, `conformance/`, `dryrun/`, `programming/`, `substrate/`, `edc/`,
`prescreen/`, and `io/`.
The CLI entry point is `src/clinique/cli.py`, exposed as `clinique`.

`tests/` holds the pytest suite, with fixtures in `tests/fixtures/`. Design docs live in
`docs/design/`; ML onboarding primer in `docs/primer/`; EDC governance artifacts in
`docs/edc-query-validation/`. R-backed power tooling is isolated under `docker/r-engine/`.

## Build, Test, and Development Commands

- `uv sync`: create/update the virtual environment from `uv.lock` and install dev tools.
- `uv sync --group temporal`: optional Temporal.io SDK + Pydantic for durable prescreen workflows.
- `uv run pytest`: run the full test suite.
- `uv run pytest tests/test_power_engines.py`: run one focused test module.
- `uv run ruff check src tests`: lint Python source and tests.
- `uv run ruff format src tests`: format Python files using project Ruff settings.
- `docker build -t clinique-r-engine:0.1.0 docker/r-engine`: build the pinned R engine image.

Docker-backed tests skip when the Docker daemon is unavailable; start Docker Desktop or
`colima start` before validating R cross-check behavior.

Temporal durable prescreen (optional; see `docs/design/temporal-prescreen.md` — includes ML researcher / MLsys walkthrough):

```bash
temporal server start-dev                              # background
uv sync --group temporal
uv run clinique prescreen worker                       # background
uv run pytest tests/test_durable_prescreen.py -q       # embedded test server
```

## Coding Style & Naming Conventions

This project targets Python 3.12 and uses a `src/` layout. Keep modules small and
domain-oriented, matching the existing package boundaries. Use 4-space indentation,
type hints for public functions, and clear dataclass or record-style objects where they
preserve provenance.

Ruff is the formatter and linter. The configured line length is 100 characters. Use
snake_case for modules, functions, variables, and test names; use PascalCase for classes.

## Testing Guidelines

Tests use pytest and are discovered from `tests/` via `pyproject.toml`. Name tests
`test_*.py` and functions `test_*`. Prefer focused tests near the behavior under change,
and add fixtures under `tests/fixtures/` when reusable clinical data samples are needed.

For power-engine work, cover both the pure-Python reference path and Docker-backed R path
where practical. Preserve skip behavior for environments without Docker.

## Commit & Pull Request Guidelines

Git history uses concise Conventional Commit-style subjects, for example
`feat(rfc-0004): CDISC conformance triage with no-fabrication drafting` and
`docs: add RFC-0006 validation & evaluation framework`.

Use imperative, scoped commits when possible: `feat(edc): ...`, `fix: ...`,
`docs: ...`, or `test: ...`. Pull requests should summarize the change, link the relevant
design doc or issue, list validation commands run, and note Docker/R implications when affected.

## Security & Configuration Tips

Do not commit generated clinical outputs, secrets, or local environment files. Keep sample
data minimal and place intentional fixtures under `tests/fixtures/` with provenance notes
when appropriate.

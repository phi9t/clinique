# Releasing

`clinique` is an **internal/private** package (`Private :: Do Not Upload`). Releases produce a
versioned, reproducible build artifact and a git tag — they are **not** published to PyPI.

## Versioning

- Semantic Versioning (`MAJOR.MINOR.PATCH`).
- The version lives in **one** place: `__version__` in `src/clinique/__init__.py`. Hatchling reads
  it dynamically; `pyproject.toml` has no hardcoded version. Never add one back.

## Pre-release gates

All must pass locally and in CI before tagging. Changing code that weakens a
[core invariant](CLAUDE.md#core-invariants-treat-as-pass-fail-gates-never-soften) is a release
blocker even if tests pass.

```bash
uv sync --frozen          # lockfile must be current
uv run ruff check .       # lint
uv run ruff format --check .
uv run pytest             # full suite (Docker rpact cross-checks skip if no daemon)
uv build                  # sdist + wheel build cleanly
```

Optional but recommended — run the Docker cross-check so the regulatory rpact engine is exercised,
not just the pure-Python oracle:

```bash
colima start   # or start Docker Desktop
docker build -t clinique-r-engine:0.1.0 docker/r-engine
uv run pytest tests/test_rpact_docker.py
```

## Cut a release

1. Bump `__version__` in `src/clinique/__init__.py`.
2. Move the `[Unreleased]` notes in `CHANGELOG.md` under a new dated version heading; refresh the
   compare links at the bottom.
3. Commit: `chore(release): vX.Y.Z`.
4. Confirm all pre-release gates pass (CI on the commit is green).
5. Tag and push:

   ```bash
   git tag -a vX.Y.Z -m "clinique vX.Y.Z"
   git push origin main --follow-tags
   ```

6. Attach the built `dist/clinique-X.Y.Z-*.whl` and `.tar.gz` to the GitHub release (or your
   internal artifact store). Do **not** `twine upload` — the private classifier blocks PyPI, and
   that guard is intentional.

## Installing a built artifact

```bash
uv pip install dist/clinique-X.Y.Z-py3-none-any.whl
# or directly from the repo at a tag:
uv pip install "git+ssh://git@github.com/phi9t/clinique.git@vX.Y.Z"
```

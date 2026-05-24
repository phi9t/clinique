#!/usr/bin/env bash
# Full pytest suite for pre-commit: temporal SDK + hermetic dev-server E2E.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/pre-commit-bootstrap.sh
source "$ROOT/scripts/pre-commit-bootstrap.sh"

if ! PYTHONPATH=tests uv run python -c "from durable_e2e_harness import temporal_available; import sys; sys.exit(0 if temporal_available() else 1)"; then
  echo "pre-commit: Temporal CLI required for hermetic temporal E2E tests." >&2
  echo "Install: brew install temporal  (https://docs.temporal.io/cli)" >&2
  exit 1
fi

export CLINIQUE_REQUIRE_TEMPORAL=1
exec uv run pytest -q

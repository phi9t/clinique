#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/pre-commit-bootstrap.sh
source "$ROOT/scripts/pre-commit-bootstrap.sh"
uv run ruff check .
uv run ruff format --check .

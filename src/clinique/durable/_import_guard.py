"""Optional Temporal.io import guard."""

from __future__ import annotations

TEMPORAL_INSTALL_HINT = "Install Temporal support with: uv sync --group temporal"


def require_temporalio():
    try:
        import temporalio  # noqa: F401
    except ImportError as exc:
        raise ImportError(TEMPORAL_INSTALL_HINT) from exc

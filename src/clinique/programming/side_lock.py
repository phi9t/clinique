"""QC-independence side-lock (RFC-0002 §5.1).

The agent may contribute to exactly ONE side of a double-programming pair for a given output —
production OR QC, never both — so independent double programming is never silently defeated by
correlated errors. The contributed side is write-once per output_id; a request for the opposite
side is refused.
"""

from __future__ import annotations

_SIDES = frozenset({"production", "qc"})


class SideLockViolation(Exception):
    """Raised when the agent is asked to contribute to the side it is locked out of."""


def _normalize(side: str) -> str:
    s = side.strip().lower()
    if s not in _SIDES:
        raise ValueError(f"side must be one of {sorted(_SIDES)}, got {side!r}")
    return s


class SideLockRegistry:
    def __init__(self) -> None:
        self._sides: dict[str, str] = {}

    def claim(self, output_id: str, side: str) -> None:
        """Record that the agent contributed to ``side`` for ``output_id`` (write-once).

        Idempotent for the same side; raises SideLockViolation for the opposite side.
        """
        side = _normalize(side)
        existing = self._sides.get(output_id)
        if existing is None:
            self._sides[output_id] = side
            return
        if existing != side:
            raise SideLockViolation(
                f"agent already contributed to '{existing}' for output {output_id!r}; "
                f"cannot also contribute to '{side}' (double-programming independence)"
            )

    def assert_allowed(self, output_id: str, side: str) -> None:
        """Raise if the agent is locked out of ``side`` for ``output_id`` (without claiming)."""
        side = _normalize(side)
        existing = self._sides.get(output_id)
        if existing is not None and existing != side:
            raise SideLockViolation(
                f"agent is locked to '{existing}' for output {output_id!r}; '{side}' is forbidden"
            )

    def agent_side(self, output_id: str) -> str | None:
        return self._sides.get(output_id)

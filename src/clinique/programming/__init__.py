"""RFC-0002: statistical programming copilot — QC-independence side-lock."""

from .side_lock import SideLockRegistry, SideLockViolation

__all__ = ["SideLockRegistry", "SideLockViolation"]

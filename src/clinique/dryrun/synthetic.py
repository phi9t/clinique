"""Synthetic data provider (RFC-0005 §5.1).

The ONLY data source the dry-run harness is permitted to use. Datasets are flagged synthetic by
construction; there is no connector here to EDC, production ADaM, or any unblinding/RTSM store.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SyntheticDataset:
    name: str
    rows: tuple[dict, ...] = ()
    synthetic: bool = True  # invariant: always True


@dataclass
class SyntheticDataProvider:
    """Generates conformant mock datasets from a spec under a named scenario."""

    is_synthetic: bool = field(default=True, init=False)

    def generate(self, name: str, n: int, scenario: str = "null") -> SyntheticDataset:
        # Minimal placeholder generator; real generation is spec-driven (metacore) at the
        # fixture-wiring task. Scenario tags let later checks exercise estimand/missing-data paths.
        rows = tuple({"subject": f"S{i:04d}", "scenario": scenario} for i in range(n))
        return SyntheticDataset(name=name, rows=rows)

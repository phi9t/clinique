"""Dry-run harness (RFC-0005 §5.2).

Runs analysis programs against SYNTHETIC data only and reports structural checks. The data-wall
(RFC-0005 §5.4) is structural: this module imports nothing but the SyntheticDataProvider, and the
harness refuses any provider that is not a SyntheticDataProvider. A build-invariant test asserts
no real-data / unblinding import path exists here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .synthetic import SyntheticDataProvider, SyntheticDataset


class RealDataForbidden(Exception):
    """Raised if the harness is handed anything other than a SyntheticDataProvider."""


@dataclass(frozen=True)
class StructuralCheck:
    check: str
    target: str
    passed: bool
    detail: str = ""


# A "program" is any callable that maps a synthetic dataset to a tabular output (list of rows).
Program = Callable[[SyntheticDataset], list[dict]]


class DryRunHarness:
    def __init__(self, provider: SyntheticDataProvider):
        if not isinstance(provider, SyntheticDataProvider):
            raise RealDataForbidden(
                "DryRunHarness accepts only SyntheticDataProvider; "
                "real/unblinded data is walled off"
            )
        self.provider = provider

    def run(self, programs: dict[str, Program], dataset: SyntheticDataset) -> list[StructuralCheck]:
        """Execute each program on the synthetic dataset and report structural checks."""
        checks: list[StructuralCheck] = []
        for output_id, program in programs.items():
            try:
                result = program(dataset)
                ran = True
                detail = ""
            except Exception as exc:  # noqa: BLE001 - dry run reports program failures, doesn't raise
                result, ran, detail = [], False, f"{type(exc).__name__}: {exc}"
            checks.append(StructuralCheck("PROGRAM-RUNS", output_id, ran, detail))
            checks.append(
                StructuralCheck(
                    "SHELL-POPULATES",
                    output_id,
                    ran and len(result) > 0,
                    "" if result else "produced no rows",
                )
            )
        return checks

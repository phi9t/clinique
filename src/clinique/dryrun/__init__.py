"""RFC-0005: pre-unblinding dry-run / mock-analysis harness (synthetic data only)."""

from .harness import DryRunHarness, RealDataForbidden, StructuralCheck
from .synthetic import SyntheticDataProvider, SyntheticDataset

__all__ = [
    "DryRunHarness",
    "RealDataForbidden",
    "StructuralCheck",
    "SyntheticDataProvider",
    "SyntheticDataset",
]

"""RFC-0005 dry-run harness: synthetic-only operation + the data-wall build invariant."""

import ast
import pathlib

import pytest

from clinique.dryrun import DryRunHarness, RealDataForbidden, SyntheticDataProvider

_HARNESS_FILE = pathlib.Path(DryRunHarness.__module__.replace(".", "/"))


def test_harness_runs_on_synthetic_data():
    provider = SyntheticDataProvider()
    ds = provider.generate("ADSL", n=5, scenario="null")
    harness = DryRunHarness(provider)
    checks = harness.run({"T-14.2.1": lambda d: list(d.rows)}, ds)
    assert any(c.check == "PROGRAM-RUNS" and c.passed for c in checks)
    assert any(c.check == "SHELL-POPULATES" and c.passed for c in checks)


def test_empty_output_flagged_not_raised():
    harness = DryRunHarness(SyntheticDataProvider())
    ds = SyntheticDataProvider().generate("ADSL", n=3)
    checks = harness.run({"T-empty": lambda d: []}, ds)
    assert any(c.check == "SHELL-POPULATES" and not c.passed for c in checks)


def test_program_crash_reported_not_raised():
    harness = DryRunHarness(SyntheticDataProvider())
    ds = SyntheticDataProvider().generate("ADSL", n=3)

    def boom(_):
        raise RuntimeError("bad merge")

    checks = harness.run({"T-bug": boom}, ds)
    assert any(c.check == "PROGRAM-RUNS" and not c.passed for c in checks)


def test_non_synthetic_provider_refused():
    class FakeEdcProvider:
        is_synthetic = False

    with pytest.raises(RealDataForbidden):
        DryRunHarness(FakeEdcProvider())


def test_data_wall_no_real_data_imports():
    """Build invariant: the harness module imports nothing that could reach real/unblinded data."""
    src = pathlib.Path("src/clinique/dryrun/harness.py").read_text()
    tree = ast.parse(src)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden = ("edc", "rtsm", "unblind", "production_adam", "phi", "ehr", "safety_db")
    flat = " ".join(imported).lower()
    assert not any(tok in flat for tok in forbidden), f"forbidden import in harness: {imported}"
    # the only project import is the synthetic provider
    assert any("synthetic" in m for m in imported)

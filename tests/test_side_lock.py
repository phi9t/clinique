"""RFC-0002 QC-independence side-lock tests."""

import pytest

from clinique.programming import SideLockRegistry, SideLockViolation


def test_claim_then_same_side_is_idempotent():
    reg = SideLockRegistry()
    reg.claim("T-14.2.1", "production")
    reg.claim("T-14.2.1", "production")  # no error
    assert reg.agent_side("T-14.2.1") == "production"


def test_opposite_side_is_refused():
    reg = SideLockRegistry()
    reg.claim("T-14.2.1", "production")
    with pytest.raises(SideLockViolation):
        reg.claim("T-14.2.1", "qc")


def test_assert_allowed_blocks_opposite_side():
    reg = SideLockRegistry()
    reg.claim("T-14.2.1", "qc")
    reg.assert_allowed("T-14.2.1", "qc")  # ok
    with pytest.raises(SideLockViolation):
        reg.assert_allowed("T-14.2.1", "production")


def test_outputs_are_independent():
    reg = SideLockRegistry()
    reg.claim("T-1", "production")
    reg.claim("T-2", "qc")  # different output, fine
    assert reg.agent_side("T-1") == "production"
    assert reg.agent_side("T-2") == "qc"


def test_invalid_side_rejected():
    reg = SideLockRegistry()
    with pytest.raises(ValueError):
        reg.claim("T-1", "both")

"""Tests for temporal window checks."""

from clinique.prescreen.temporal import document_eligible, evidence_within_window


def test_document_after_snapshot_is_not_eligible():
    assert document_eligible("2026-06-01", "2026-03-01") is False


def test_evidence_within_14_day_window():
    assert evidence_within_window("2026-02-20", "2026-03-01", window_value=14, window_unit="days")


def test_evidence_outside_window():
    assert (
        evidence_within_window("2026-01-01", "2026-03-01", window_value=14, window_unit="days")
        is False
    )

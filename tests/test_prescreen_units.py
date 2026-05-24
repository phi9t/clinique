"""Tests for lab unit normalization."""

from clinique.prescreen.units import compare_threshold, to_cells_per_ul


def test_synthea_anc_scale_to_cells_per_ul():
    assert to_cells_per_ul(2.1, "10*3/uL") == 2100.0


def test_anc_threshold_met():
    assert compare_threshold(
        2.1,
        "10*3/uL",
        operator=">=",
        threshold_value=1500,
        threshold_unit="cells/uL",
    )


def test_k_ul_conversion():
    assert to_cells_per_ul(2.1, "K/uL") == 2100.0

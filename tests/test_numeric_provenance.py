"""RFC-0000 §7 numeric-provenance linter tests."""

from clinique.substrate.numeric_provenance import check_numeric_provenance
from clinique.substrate.records import Assumption, ComputationRecord, EngineResult


def _record(narrative: str, result=None) -> ComputationRecord:
    engine = EngineResult(
        engine="reference",
        version="t",
        method="two_sample_means",
        inputs={"delta": 0.5, "sd": 1.0, "alpha": 0.05, "power": 0.8},
        outputs={"n1": 63.0, "n2": 63.0, "n_total": 126.0},
        achieved={"achieved_power": 0.8013},
    )
    return ComputationRecord(
        capability="rfc-0003",
        method="two_sample_means",
        engine=engine,
        assumptions=[
            Assumption("alpha", 0.05, "prob", "protocol", "SAP §3"),
            Assumption("power", 0.80, "prob", "protocol", "SAP §3"),
            Assumption("delta", 0.5, "unit", "literature", "prior trial"),
        ],
        result=result or {"n_total": 126.0, "achieved_power": 0.8013},
        narrative=narrative,
    )


def test_clean_record_has_no_violations():
    rec = _record("Required total: 126 (63 + 63). Achieved power 0.8013 at alpha 0.05, power 0.8.")
    assert check_numeric_provenance(rec) == []


def test_invented_number_is_flagged():
    rec = _record("Approximately 600 participants are needed.")
    violations = check_numeric_provenance(rec)
    assert len(violations) == 1
    assert violations[0].value == 600.0


def test_whitelist_constants_allowed():
    rec = _record("A 2-sided test enrolling 126 across 2 arms; 0 dropouts assumed.")
    assert check_numeric_provenance(rec) == []


def test_display_rounding_tolerated_but_real_drift_caught():
    # 0.80131 vs blessed 0.8013 -> within tolerance (display rounding)
    assert check_numeric_provenance(_record("Achieved power 0.80131.")) == []
    # 0.8100 vs 0.8013 -> real drift, flagged
    flagged = check_numeric_provenance(_record("Achieved power 0.8100."))
    assert any(v.value == 0.81 for v in flagged)


def test_result_dict_numbers_must_trace():
    rec = _record("Total 126.", result={"n_total": 999.0, "achieved_power": 0.8013})
    flagged = check_numeric_provenance(rec)
    assert any(v.value == 999.0 for v in flagged)

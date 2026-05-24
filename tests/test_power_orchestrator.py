"""RFC-0003 orchestrator tests: method selection, end-to-end record, and the hard gate."""

import pytest

import clinique.power.orchestrator as orch
from clinique.power.intake import DesignIntake, select_method
from clinique.power.orchestrator import design_sample_size
from clinique.substrate.numeric_provenance import NumericProvenanceError
from clinique.substrate.provenance import ProvenanceLedger
from clinique.substrate.records import Assumption


def _alpha():
    return Assumption("alpha", 0.05, "prob", "protocol", "SAP §3")


def _power():
    return Assumption("power", 0.80, "prob", "protocol", "SAP §3")


def _means_intake(**kw):
    return DesignIntake(
        endpoint_type="continuous",
        alpha=_alpha(),
        power=_power(),
        params={
            "delta": Assumption("delta", 0.5, "unit", "literature", "prior trial"),
            "sd": Assumption("sd", 1.0, "unit", "literature", "prior trial"),
        },
        **kw,
    )


def _ledger(tmp_path):
    return ProvenanceLedger(tmp_path / "run.ledger.jsonl")


def test_method_selection_corpus():
    cases = {
        "continuous": "two_sample_means",
        "binary": "two_proportions",
        "time_to_event": "survival_logrank",
    }
    for endpoint, expected in cases.items():
        intake = DesignIntake(endpoint_type=endpoint, alpha=_alpha(), power=_power())
        assert select_method(intake) == expected
    with pytest.raises(ValueError):
        select_method(DesignIntake(endpoint_type="ordinal", alpha=_alpha(), power=_power()))


def test_end_to_end_means(tmp_path):
    led = _ledger(tmp_path)
    rec = design_sample_size(_means_intake(), led)
    assert rec.result["n_total"] == 126.0  # 63 + 63
    assert "126" in rec.narrative
    assert rec.ledger_ref
    assert len(led) == 1  # one provenance record written


def test_survival_end_to_end(tmp_path):
    intake = DesignIntake(
        endpoint_type="time_to_event",
        alpha=_alpha(),
        power=_power(),
        params={
            "hazard_ratio": Assumption("hazard_ratio", 0.7, "ratio", "literature", "prior trial")
        },
    )
    rec = design_sample_size(intake, _ledger(tmp_path))
    assert rec.result["events_total"] == 247.0


def test_hard_gate_rejects_untraceable_number(tmp_path, monkeypatch):
    # Simulate a narrative that smuggles in a number with no engine/assumption provenance.
    monkeypatch.setattr(orch, "_narrative", lambda *a, **k: "Total N = 999999 participants.")
    with pytest.raises(NumericProvenanceError):
        design_sample_size(_means_intake(), _ledger(tmp_path))


def test_determinism(tmp_path):
    a = design_sample_size(_means_intake(), _ledger(tmp_path / "a"))
    b = design_sample_size(_means_intake(), _ledger(tmp_path / "b"))
    assert a.result == b.result
    assert a.narrative == b.narrative
    assert a.engine.outputs == b.engine.outputs


def test_unsourced_assumption_flagged(tmp_path):
    intake = _means_intake()
    intake.params["sd"] = Assumption("sd", 1.0, "unit", "assumption", "no source — guess")
    rec = design_sample_size(intake, _ledger(tmp_path))
    flagged = {a.name for a in rec.unsourced_assumptions}
    assert flagged == {"sd"}


def test_sensitivity_numbers_all_trace(tmp_path):
    # If any swept number lacked provenance, the hard gate would have raised; reaching here
    # plus a populated sweep confirms sensitivity numbers trace.
    rec = design_sample_size(_means_intake(), _ledger(tmp_path))
    assert len(rec.sensitivity_runs) == 3
    assert "Sensitivity" in rec.narrative

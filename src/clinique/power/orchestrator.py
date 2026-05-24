"""Sample-size orchestrator (RFC-0003 §5).

Pipeline: select method -> assemble assumptions -> run validated engine -> sensitivity sweep ->
build a reproducible record whose narrative is assembled ONLY from blessed numbers -> run the
numeric-provenance linter as a HARD GATE -> append to the ledger.

The orchestrator never computes a statistical number itself; engines do.
"""

from __future__ import annotations

from ..substrate.numeric_provenance import NumericProvenanceError, check_numeric_provenance
from ..substrate.provenance import LedgerRecord, ProvenanceLedger
from ..substrate.records import Assumption, ComputationRecord, EngineResult
from .engines import PowerEngine, ReferenceEngine
from .intake import DesignIntake, select_method

# Fraction steps for the one-dimensional sensitivity sweep around the swept assumption.
_SWEEP_FRACTIONS = (0.8, 1.0, 1.2)


def _run_engine(
    engine: PowerEngine, method: str, intake: DesignIntake, params: dict[str, float]
) -> EngineResult:
    common = {"alpha": intake.alpha.value, "power": intake.power.value, "sides": intake.sides}
    if method == "two_sample_means":
        return engine.two_sample_means(
            delta=params["delta"], sd=params["sd"], ratio=intake.ratio, **common
        )
    if method == "two_proportions":
        return engine.two_proportions(
            p1=params["p1"], p2=params["p2"], ratio=intake.ratio, **common
        )
    if method == "survival_logrank":
        return engine.survival_logrank(
            hazard_ratio=params["hazard_ratio"],
            allocation=intake.ratio / (1.0 + intake.ratio),
            **common,
        )
    raise ValueError(f"unknown method {method!r}")


# The assumption whose value the sensitivity sweep perturbs, per method.
_SWEEP_KEY = {
    "two_sample_means": "delta",
    "two_proportions": "p2",
    "survival_logrank": "hazard_ratio",
}


def _base_params(method: str, intake: DesignIntake) -> dict[str, float]:
    return {name: a.value for name, a in intake.params.items()}


def _primary_output_key(method: str) -> str:
    return "events_total" if method == "survival_logrank" else "n_total"


def _sensitivity(engine: PowerEngine, method: str, intake: DesignIntake) -> list[EngineResult]:
    key = _SWEEP_KEY[method]
    base = _base_params(method, intake)
    runs: list[EngineResult] = []
    for frac in _SWEEP_FRACTIONS:
        params = dict(base)
        params[key] = round(base[key] * frac, 6)
        runs.append(_run_engine(engine, method, intake, params))
    return runs


def _narrative(
    method: str, intake: DesignIntake, primary: EngineResult, sweep: list[EngineResult]
) -> str:
    out_key = _primary_output_key(method)
    n = int(primary.outputs[out_key])
    ap = primary.achieved["achieved_power"]
    a, p = intake.alpha.value, intake.power.value
    label = {
        "two_sample_means": "two-sample comparison of means",
        "two_proportions": "two-sample comparison of proportions",
        "survival_logrank": "log-rank test (Schoenfeld)",
    }[method]
    unit = "events" if method == "survival_logrank" else "participants"

    lines = [
        f"Sample size for a {intake.design_type} {label} "
        f"({intake.sides}-sided alpha {a}, target power {p}).",
    ]
    if method != "survival_logrank":
        lines.append(
            f"Required total: {n} {unit} ({int(primary.outputs['n1'])} + {int(primary.outputs['n2'])})."
        )
    else:
        lines.append(f"Required total: {n} {unit}.")
    lines.append(f"Achieved power at this size: {ap}.")

    key = _SWEEP_KEY[method]
    lines.append(f"Sensitivity (varying {key}):")
    for run in sweep:
        lines.append(f"  {key} = {run.inputs[key]} -> {int(run.outputs[out_key])} {unit}")
    return "\n".join(lines)


def design_sample_size(
    intake: DesignIntake,
    ledger: ProvenanceLedger,
    engine: PowerEngine | None = None,
) -> ComputationRecord:
    """Produce a reproducible, provenance-gated sample-size computation record."""
    engine = engine or ReferenceEngine()
    method = select_method(intake)

    assumptions: list[Assumption] = [intake.alpha, intake.power, *intake.params.values()]
    primary = _run_engine(engine, method, intake, _base_params(method, intake))
    sweep = _sensitivity(engine, method, intake)

    out_key = _primary_output_key(method)
    result = {
        out_key: primary.outputs[out_key],
        "achieved_power": primary.achieved["achieved_power"],
    }
    narrative = _narrative(method, intake, primary, sweep)

    record = ComputationRecord(
        capability="rfc-0003",
        method=method,
        engine=primary,
        assumptions=assumptions,
        result=result,
        sensitivity_runs=sweep,
        narrative=narrative,
    )

    # HARD GATE: no number in the human-readable output may lack provenance.
    violations = check_numeric_provenance(record)
    if violations:
        raise NumericProvenanceError(violations)

    ledger_record = LedgerRecord(
        capability="rfc-0003",
        inputs=[f"{a.name}={a.value}({a.source_kind})" for a in assumptions],
        model={"id": "rule-based-method-selection", "version": "0", "params": {}},
        tools=primary.tools,
        output_ref="inline",
    )
    record.ledger_ref = ledger.append(ledger_record)
    return record

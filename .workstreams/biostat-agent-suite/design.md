# Workstream: biostat-agent-suite — implementation design

Implements the RFC suite in `docs/rfcs/` (0000–0006). This doc fixes the engineering
decisions; `tracker.org` holds the task breakdown, prompts, and acceptance criteria.

## Build order (validation-feasibility, per the pre-impl data analysis)

The product wedge order is 0001-first; the **validation-feasibility** order is different and
is what we implement, because it lets us prove the core safety patterns on data we already have:

1. **Substrate (RFC-0000)** — provenance ledger + numeric-provenance linter. Everything depends on it.
2. **RFC-0003 sample-size orchestrator** — fully validatable now, no trial data, no PHI. Proves
   the validated-engine-only + numeric-provenance + reproducible-record pattern end to end.
3. **RFC-0002 / RFC-0005** — reproduction + defect-injection harness (needs pharmaverse / R-pilot
   fixtures; scaffolded now, fixtures fetched at their task).
4. **RFC-0004** — conformance triage on CORE/Pinnacle reports.
5. **RFC-0001** — engineering + seeded-defect validation on CDISC Pilot + R-pilots; natural-defect
   benchmark deferred to a partner-data milestone.

## Stack

- **Python 3.14, managed by `uv`** (pyproject.toml + uv.lock). Core runtime is stdlib-only
  (`statistics.NormalDist` covers Φ/Φ⁻¹); uv manages dev deps (`pytest`, `ruff`) and the venv so
  the project is reproducible via `uv sync`.
- **Tests: `pytest`**, run with `uv run pytest`.
- **src layout**, package `clinique`.
- **R engines run in a pinned Docker image** (RFC-0000 §6 version-pinning). gsDesign/rpact are
  genuinely regulatory-validated, so they are the **canonical** sample-size engines. The image
  (`docker/r-engine/Dockerfile`, `rocker/r-ver` pinned + rpact/gsDesign pinned) is invoked via a
  `docker run` adapter; provenance records the image digest + package versions.
- An independent **pure-Python `ReferenceEngine`** is kept as a cross-check oracle and offline
  fallback. Two independent implementations agreeing is itself strong validation (the
  double-programming-independence idea from RFC-0002). Docker cross-check tests **skip** when the
  daemon is unavailable; the reference engine's round-trip + literature-anchor tests always run.

## Package layout

```
src/clinique/
  substrate/
    provenance.py          # RFC-0000 §5 append-only ledger (JSONL)
    numeric_provenance.py  # RFC-0000 §7 linter: every output number must trace to engine/assumption
    records.py             # shared dataclasses: Assumption, EngineResult, LedgerRecord
  power/                    # RFC-0003
    engines.py             # Engine protocol, ReferenceEngine (Python oracle), registry
    rpact_docker.py        # RpactDockerEngine: canonical engine via pinned R Docker image
    orchestrator.py        # method selection, assumption assembly, execution, record, gate
    intake.py              # DesignIntake dataclass + method-selection rules
docker/r-engine/
  Dockerfile               # rocker/r-ver pinned + rpact/gsDesign pinned
  power.R                  # JSON-in/JSON-out rpact wrapper invoked by the adapter
tests/
  test_provenance.py
  test_numeric_provenance.py
  test_power_engines.py        # reproduction suite: round-trip minimality + literature anchors
  test_power_orchestrator.py   # end-to-end incl. numeric-provenance gate (happy + poisoned)
  test_rpact_docker.py         # skipped unless docker daemon reachable; rpact vs ReferenceEngine agreement
```

## Core invariants implemented (these are pass/fail, not metrics)

- **Numeric-provenance (RFC-0000 §7):** no number in a `ComputationRecord`'s result/narrative may
  exist unless it traces to an `EngineResult` output or an `Assumption` value. Enforced by a linter
  that the orchestrator runs as a hard gate before writing to the ledger.
- **Validated-engine-only computation (RFC-0003):** the orchestrator never computes a statistical
  number; only registered engines do. Engines carry name+version recorded in provenance.
- **Reproducibility:** every run emits a `ComputationRecord` with full inputs+provenance; re-running
  the same intake yields an identical result (determinism test).

## Validation approach per the data analysis

- **RFC-0003:** round-trip minimality (engine's N achieves ≥ target power; N−1 does not) + literature
  anchors within tolerance. Self-contained, no external data.
- **RFC-0002/0005:** reproduction vs pharmaverse/R-pilot known-correct outputs; defect-injection.
- **RFC-0004:** classification of real CORE/Pinnacle reports on the public bundles.
- **RFC-0001:** seeded-defect recall on CDISC Pilot + R-pilots + ClinicalTrials.gov protocol/SAP.

## Out of scope for this workstream

PHI-bearing data, unblinded data, write-back to any system of record, LLM API calls (method
selection is rule-based and deterministic here; the LLM slot is an interface to fill later).

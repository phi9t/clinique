# Biostatistician agent suite — design

**Status:** `SCAFFOLD-COMPLETE` (verified 2026-05-23). All platform and biostat capabilities
are implemented and green with real validation where fixtures exist. Deferred items remain in
the backlog below; do not promote to shadow mode without RFC-0006 L3+ evidence.

Agentic tooling built **around the biostatistician persona** in clinical trials. The persona
was chosen because its work is artifact-heavy, traceability-driven, and already protected by
a strong human-QC culture that agents can slot into rather than fight.

## Design stance

Every capability obeys the same posture:

- **Agents draft, triage, and check. Humans decide.** No agent takes a regulated action
  (final analysis, unblinding, submission, database lock) without a named human approver.
- **Read-only and advisory first.** v1 of each capability writes nothing back into a validated
  system of record.
- **Calculators compute; LLMs orchestrate.** No statistical number in any output may originate
  from LLM reasoning — only from a validated engine's return value.
- **Provenance is mandatory.** Every finding/output carries its source spans, model version,
  tool version, and reviewer.

## Build order (validation-feasibility)

The product wedge order is estimand-first; the **validation-feasibility** order is what was
implemented, because it proves core safety patterns on data already available:

1. **Platform substrate** — provenance ledger + numeric-provenance linter. Everything depends on it.
2. **Sample-size orchestrator** — fully validatable now, no trial data, no PHI. Proves the
   validated-engine-only + numeric-provenance + reproducible-record pattern end to end.
3. **Programming side-lock / dry-run harness** — reproduction + defect-injection scaffold
   (pharmaverse / R-pilot fixtures documented; full reproduction deferred).
4. **CDISC conformance triage** — CORE/Pinnacle report classification scaffold.
5. **Estimand-spine checker** — seeded-defect validation on CDISC Pilot + R-pilots; natural-defect
   benchmark deferred to partner data.

## Stack

- **Python 3.12+, managed by `uv`** (pyproject.toml + uv.lock). Core runtime is stdlib-only
  (`statistics.NormalDist` covers Φ/Φ⁻¹); uv manages dev deps (`pytest`, `ruff`).
- **Tests:** `uv run pytest`.
- **src layout**, package `clinique`.
- **R engines** run in a pinned Docker image (`docker/r-engine/Dockerfile`, `rocker/r-ver` +
  rpact pinned). rpact is the **canonical** sample-size engine; provenance records image digest
  + package versions.
- **ReferenceEngine** — independent pure-Python cross-check oracle and offline fallback. Docker
  cross-check tests skip when the daemon is unavailable.

## Package layout

```
src/clinique/
  substrate/          # provenance ledger, numeric-provenance linter, shared records
  power/              # sample-size orchestrator, ReferenceEngine, rpact Docker adapter
  estimand/           # artifact graph, rules, checker, define.xml parser
  programming/        # QC side-lock registry
  dryrun/             # synthetic harness, data-wall invariant
  conformance/        # CORE/Pinnacle report triage and draft
  io/                 # XPT reader for real define.xml validation
  edc/                # EDC query validation (see edc-query-validation design doc)
  cli.py
docker/r-engine/
  Dockerfile
  power.R
tests/
  test_provenance.py, test_numeric_provenance.py
  test_power_engines.py, test_power_orchestrator.py, test_rpact_docker.py
  test_estimand_checker.py, test_realdata_define.py
  test_side_lock.py, test_dryrun_*.py
  test_conformance_triage.py
  test_edc_*.py
```

## Core invariants (pass/fail, not metrics)

- **Numeric-provenance:** no number in a `ComputationRecord`'s result/narrative may exist unless
  it traces to an `EngineResult` output or an `Assumption` value. The orchestrator runs this as
  a hard gate before writing to the ledger.
- **Validated-engine-only computation:** the orchestrator never computes a statistical number;
  only registered engines do. Engines carry name+version recorded in provenance.
- **Reproducibility:** every run emits a full `ComputationRecord`; re-running the same intake
  yields an identical result (determinism test).
- **Side-lock (programming):** agent-contributed side per output_id is write-once.
- **Data-wall (dry-run):** harness module imports no real-data/unblinding path.
- **Read-only (estimand):** no artifact-write API exists.

## Capabilities

### Platform substrate

Append-only JSONL provenance ledger and numeric-provenance linter. Artifact graph model
(estimand spine, claims, edges) shared by estimand and conformance modules.

- **Implementation:** `src/clinique/substrate/`
- **Tests:** `tests/test_provenance.py`, `tests/test_numeric_provenance.py`

### Sample-size & power orchestrator

Deterministic method selection, assumption assembly, engine execution, sensitivity sweep,
narrative assembly from blessed numbers only, numeric-provenance gate, ledger append.

- **Implementation:** `src/clinique/power/`, `docker/r-engine/`
- **Tests:** `tests/test_power_engines.py`, `tests/test_power_orchestrator.py`,
  `tests/test_rpact_docker.py`
- **Validation:** round-trip minimality + literature anchors; rpact cross-check vs ReferenceEngine
  when Docker is available

### Estimand-spine consistency checker

Deterministic rule engine over artifact graph. Seeded-defect recall on injected inconsistencies;
validated on synthetic bundles and real FDA-pilot define.xml + adsl.xpt (51 dangling MethodDef
refs detected; define-vs-ADSL clean, FP=0).

- **Implementation:** `src/clinique/estimand/`, `src/clinique/io/xpt.py`
- **Tests:** `tests/test_estimand_checker.py`, `tests/test_realdata_define.py`

### Statistical programming side-lock & dry-run harness

Write-once side registry and synthetic reproduction harness with data-wall AST invariant.

- **Implementation:** `src/clinique/programming/`, `src/clinique/dryrun/`
- **Tests:** `tests/test_side_lock.py`, `tests/test_dryrun_datawall.py`,
  `tests/test_dryrun_reproduction.py`

### CDISC conformance triage

CORE/Pinnacle report parser, classifier (`true_error` / `expected` / `waiver_candidate`), and
no-fabrication draft guard. Validated on synthetic sample report.

- **Implementation:** `src/clinique/conformance/`
- **Tests:** `tests/test_conformance_triage.py`

## Verification evidence

```bash
uv sync
uv run ruff check src tests
uv run pytest
docker build -t clinique-r-engine:0.1.0 docker/r-engine   # optional; rpact cross-check
```

As of closeout: 187 tests passed, ruff clean. Real infra wired: colima/docker, R image with
rpact 4.1.0, rpact cross-check passes vs ReferenceEngine for means/proportions/survival.

## Deferred / not proven

- Natural-defect benchmark for estimand checker (needs sponsor/CRO or expert-annotated data)
- pharmaverse ADaM reproduction (programming/dry-run)
- Real CORE run on public bundle (conformance uses sample report today)
- LLM method-selection + claim-extraction (rule-based stand-in now)
- t-distribution correction for two_sample_means engine
- CI workflow (uv + docker) and ruff lint gate in CI
- gsDesign in R image (ggplot2 build weight)

## Out of scope

PHI-bearing data, unblinded data, write-back to any system of record, LLM API calls in the
reference implementation (method selection is rule-based and deterministic).

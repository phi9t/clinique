# Prescreen Copilot Workstream — Design

**Status:** Complete (2026-05-24) — `goal_complete: true` on scale verification.
**Capability design:** [`docs/design/trial-prescreening.md`](../../docs/design/trial-prescreening.md)

## Goal

Implement the prescreening copilot pipeline (atomizer → retriever → judge → aggregator →
evidence gate → orchestrator) with deterministic stand-ins for CI, validate at scale against
**complete open public corpora** stored under `~/.clinique/datasets/prescreen-copilot/`, and ship
a bundled `prescreen verify-workstream` gate.

## Architecture

```
Trial + PatientCorpus
  → ReferenceAtomizer → Criterion[]
  → per criterion: retrieve (BM25) → RuleJudge → CriterionJudgment
  → aggregate → PrescreeningPacket
  → evidence-provenance gate → optional ProvenanceLedger append
```

LLM stages use Protocol interfaces; `ReferenceAtomizer` and `RuleJudge` are deterministic stand-ins.

## Data storage

| Tier | Location | Purpose |
|---|---|---|
| CI micro-fixtures | `tests/fixtures/prescreen/` | Fast pytest + offline dev |
| Scale corpus | `~/.clinique/datasets/prescreen-copilot/` | Record-and-replay eval |
| Manifest | `.workstream/prescreen-copilot/datasets.manifest.json` | Logical name → relative path |
| Gold labels | `.workstream/prescreen-copilot/l0_cases.jsonl` | Criterion-level accuracy |

Override dataset root with `CLINIQUE_DATASETS_DIR` or `--datasets-dir`.

## Modules

| Module | Role |
|---|---|
| `schemas.py` | `Criterion`, `Evidence`, `PrescreeningPacket`, extended `CriterionJudgment` |
| `units.py` | Lab unit normalization (ANC K/uL → cells/uL) |
| `temporal.py` | Snapshot leakage filter + evidence windows |
| `vocab.py` | Anti-PD-1/PD-L1 synonym subset |
| `retrieval.py` | Stdlib BM25 + structured boost |
| `atomizer.py` | `ReferenceAtomizer` |
| `judge.py` | `RuleJudge` |
| `evidence_gate.py` | Quote fidelity hard gate |
| `orchestrator.py` | Typed graph + ledger |
| `eval.py` | L0 cases + `verify_workstream()` |
| `datasets.py` | Path resolution |

## CLI

| Command | Exit codes |
|---|---|
| `prescreen atomize` | 0 / 2 |
| `prescreen screen` | 0 / 2 / 8 (evidence gate) |
| `prescreen eval` | 0 / 9 |
| `prescreen verify-workstream` | 0 goal complete / 3 missing datasets / 9 thresholds fail |
| `prescreen normalize-mimic-demo` | 0 / 2 |

## verify-workstream gates

| Gate | Threshold |
|---|---|
| Corpus conformance | 0 errors on full dataset |
| Atomizer coverage | ≥ 95% trials produce ≥ 1 criterion |
| Gold criterion accuracy | ≥ 0.90 on `l0_cases.jsonl` |
| Evidence violations | 0 |
| Exclusion false negatives | 0 |
| Scale smoke | 50 random (trial, patient) screens without crash |
| Determinism | Identical packet hash on re-run |

## Out of scope

n2c2 2018, full MIMIC-IV, embedding retriever, LLM-in-CI, EHR write-back.

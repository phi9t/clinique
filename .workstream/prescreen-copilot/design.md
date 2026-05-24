# Prescreen Copilot Workstream — Design

**Status:** L0 infrastructure complete (2026-05-24). **Phases 10–11 complete**; Phase 12–13 in progress.
**Capability design:** [`docs/design/trial-prescreening.md`](../../docs/design/trial-prescreening.md)

## Goal (original — complete)

Implement the prescreening copilot pipeline (atomizer → retriever → judge → aggregator →
evidence gate → orchestrator) with deterministic stand-ins for CI, validate at scale against
**complete open public corpora** stored under `~/.clinique/datasets/prescreen-copilot/`, and ship
a bundled `prescreen verify-workstream` gate.

`goal_complete: true` on sync verification (2026-05-24) proves **plumbing and gates**, not clinical
utility on real criteria.

## Goal (Phase 10+) — criteria-to-context matching

Make the prescreen packet **useful to a coordinator**: each criterion should surface the best
patient evidence (verbatim quotes + structured facts) and, where facts support it, a reasoned
`met` / `not_met` / `unknown` — not blanket abstention with empty evidence.

**North-star scenario** (KEYNOTE-189 / NCT02578680, Synthea P1):

```bash
uv run clinique prescreen screen --temporal \
  --trial-id NCT02578680 --patient-id P1 \
  --trials tests/fixtures/prescreen/trials.jsonl \
  --patients /tmp/synthea_patients.jsonl
```

Today: 1/36 criteria resolved (age only); 35 `unknown` with **empty evidence**.
Target: every criterion carries top-k retrieved quotes; diagnosis/condition criteria show partial
matches (e.g. NSCLC documented, stage/histology unknown).

### Diagnosis (2026-05-24 deep dive)

| Layer | Finding | Example |
|---|---|---|
| **Atomizer** | Substring domain classifier mis-tags criteria | I-002 NSCLC: `"age"` in `"st**age**"` → `demographic` → zero retrieval |
| **Retrieval** | No synonym expansion; no domain filter; junk hits | Metformin ranks for "study medication"; ANC for unrelated criteria |
| **Judge** | `RuleJudge` stub: age, structured labs, anti-PD-1 only | I-002, E-001, I-005 always `"No deterministic rule applies"` |
| **Packet UX** | Retrieved evidence discarded on `unknown` path | E-001 hits NSCLC doc but judgment shows `evidence: []` |
| **Patient corpus** | P1 has 5 structured Synthea rows, no notes/staging/ECOG | Even perfect matching cannot answer stage IV, prior therapy, ECOG |

Temporal/durable execution is **not** the bottleneck — sync and `--temporal` share the same graph.

## Architecture

```
Trial + PatientCorpus
  → ReferenceAtomizer → Criterion[]
  → per criterion: retrieve (BM25 + structured routing) → Judge → CriterionJudgment
  → aggregate → PrescreeningPacket
  → evidence-provenance gate → optional ProvenanceLedger append
```

LLM stages use Protocol interfaces. `ReferenceAtomizer` and `RuleJudge` remain deterministic CI
stand-ins; Phase 10 hardens them, Phase 13 adds `LLMJudge`.

## Phase roadmap

### Tier 0 — Atomizer & retrieval fixes (Phase 10)

| Task | Module | Success criterion |
|---|---|---|
| Word-boundary domain classifier | `atomizer.py` | I-002 → `condition`; ECOG → `performance_status`; no substring false positives |
| Attach retrieved evidence on `unknown` | `judge.py` / orchestrator | Every judgment with retrieval hits includes top-k quotes |
| Domain-filtered retrieval | `retrieval.py` | Medication criteria search medication docs only; condition → condition |
| Min score threshold | `retrieval.py` | No metformin/ANC spurious hits on unrelated criteria |
| Regression tests + gold cases | `l0_cases.jsonl`, tests | I-002 retrieves NSCLC condition on P1; expanded coverage |

### Tier 1 — Structured clinical matching (Phase 11)

| Task | Module | Success criterion |
|---|---|---|
| Oncology synonym map | `vocab.py` | `NSCLC` ↔ `non-small cell lung cancer`; histology terms |
| Condition matcher | `judge.py` | Diagnosis criteria: quote + partial-match rationale |
| Medication history matcher | `judge.py`, `vocab.py` | Prior systemic / anti-neoplastic therapy from med docs |
| Performance status matcher | `judge.py` | ECOG from structured observations when present |
| Absence exclusions | `judge.py` | Explicit negative evidence objects; silence → `unknown` |

### Tier 2 — Retrieval upgrade (Phase 12)

| Task | Module | Success criterion |
|---|---|---|
| Query expansion from criterion metadata | `retrieval.py`, atomizer | Expanded tokens improve recall on PMC notes |
| Structured-first routing | `retrieval.py` | Code/description lookup before BM25 |
| Compound criterion splitting | `atomizer.py` | E-003 a/b/c → independent predicates |
| Synthea narrative note doc | `normalizer.py` | Aggregated `note` document for retrieval on templated data |

### Tier 3 — LLM judge & L1 eval (Phase 13)

| Task | Module | Success criterion |
|---|---|---|
| `LLMJudge` behind `Judge` Protocol | `judge.py` | General criteria with mandatory quotes; evidence gate passes |
| `--judge rule\|llm` CLI flag | CLI | Swappable without touching Temporal |
| n2c2 2018 judge-only harness | `eval.py` | Real L1 signal; F1 ≥ 0.80 target per design doc |
| Embedding retriever (PMC notes) | `retrieval.py` | Hybrid ranker for free-text sources |

### Phase 10+ gates (new)

These extend but do not replace existing `verify-workstream` gates:

| Gate | Threshold | Phase |
|---|---|---|
| Domain classifier accuracy | 0 false positives on KEY-NOTE fixture criteria | 10 |
| Retrieval recall on P1 | I-002, E-001 retrieve NSCLC condition doc | 10 |
| Evidence surfacing | 100% of criteria with retrieval hits include quotes in packet | 10 |
| Spurious retrieval rate | 0 junk hits (metformin/ANC) on medication-only criteria sample | 10 |
| Partial-match rationales | Condition criteria cite evidence when diagnosis documented | 11 |
| Gold criterion accuracy | ≥ 0.90 on expanded `l0_cases.jsonl` | 11 |
| n2c2 criterion F1 | ≥ 0.80 (judge-only harness) | 13 |

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
| `vocab.py` | Drug-class / oncology synonym lookup (expand in Phase 11) |
| `retrieval.py` | Stdlib BM25 + structured boost → domain filter + synonyms (Phase 10–12) |
| `atomizer.py` | `ReferenceAtomizer` → word-boundary domains (Phase 10) |
| `judge.py` | `RuleJudge` → structured matchers (Phase 11) → `LLMJudge` (Phase 13) |
| `evidence_gate.py` | Quote fidelity hard gate |
| `orchestrator.py` | Typed graph + ledger |
| `eval.py` | L0 cases + `verify_workstream()` |
| `datasets.py` | Path resolution |
| `clinique/durable/` | Temporal.io wrapper — same copilot graph, durable orchestration ([walkthrough](../../docs/design/temporal-prescreen.md)) |

## CLI

| Command | Exit codes |
|---|---|
| `prescreen atomize` | 0 / 2 |
| `prescreen screen` | 0 / 2 / 8 (evidence gate) |
| `prescreen screen --temporal` | 0 / 2 / 3 (requires Temporal worker) |
| `prescreen eval` | 0 / 9 |
| `prescreen eval-temporal` | 0 / 2 / 3 / 9 |
| `prescreen worker` | 0 running / 2 connect or missing SDK |
| `prescreen verify-workstream` | 0 verification complete / 3 missing datasets / 9 fail |
| `prescreen verify-workstream --temporal` | also requires Temporal eval + sync parity; 2 connect/SDK |
| `prescreen normalize-mimic-demo` | 0 / 2 |

Sync commands implement the copilot graph in-process. Temporal commands wrap the **same**
activities over the same `l0_cases.jsonl` gold set — see `data-inventory.md` § Durable eval.

## verify-workstream gates (L0 — complete)

| Gate | Threshold |
|---|---|
| Corpus conformance | 0 errors on full dataset |
| Atomizer coverage | ≥ 95% trials produce ≥ 1 criterion |
| Gold criterion accuracy | ≥ 0.90 on `l0_cases.jsonl` |
| Evidence violations | 0 |
| Exclusion false negatives | 0 |
| Scale smoke | 50 random (trial, patient) screens without crash |
| Determinism | Identical packet hash on re-run |

## Durable execution (Temporal.io — complete)

`verify-workstream` gates above use the **sync** orchestrator — that keeps `goal_complete`
meaningful without a running Temporal cluster. Durable parity and ops behavior are verified
separately:

| Check | Command | Evidence |
|---|---|---|
| Wire model round-trip | `uv run pytest tests/test_durable_models.py -q` | Pydantic ↔ domain |
| Sync parity + determinism | `uv run pytest tests/test_durable_prescreen.py -q` | `packet_fingerprint` vs orchestrator |
| Real server + failure injection | `uv run pytest tests/test_durable_prescreen_e2e.py -v` | dev server, worker, retry/gate cases |
| Gold set under Temporal | `prescreen verify-workstream --temporal` or `prescreen eval-temporal` | parity in verification report |

Design and extension guide: [`docs/design/temporal-prescreen.md`](../../docs/design/temporal-prescreen.md).

## Out of scope (unchanged)

Full MIMIC-IV, EHR write-back, autonomous enrollment decisions. n2c2 2018 moves from
"out of scope" to **Phase 13 target** (credentialed; not committed to repo). Embedding retriever
and LLM-in-CI remain deferred until Phase 12–13.

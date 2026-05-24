# Clinique for ML researchers and MLsys engineers

**Audience:** You read [clinical-trials-for-ml.md](clinical-trials-for-ml.md) and want to know where
the code, tests, and eval harnesses live.

---

## What Clinique is

Clinique is a set of **assistive agents** for regulated clinical-trial workflows — not autonomous
trial execution. Agents draft, retrieve, flag, and summarize; humans approve, decide, enroll, and
sign off. Deterministic gates (provenance linters, replay discipline, no-write-back invariants)
run **before** anything is treated as shippable output.

The active proof-point wedge is **trial prescreening** (criterion-level judgments with evidence).
The repo also ships biostat substrate capabilities and an EDC query validation harness that
demonstrates the same L0–L4 evaluation pattern.

---

## Minimum schema → code mapping

From [primer §13](clinical-trials-for-ml.md#13-how-to-think-about-the-data-model-for-your-proof-point):

| Schema entity | Status in repo | Code |
|---|---|---|
| `Trial` + eligibility text | **Implemented (L0)** | [`src/clinique/prescreen/schemas.py`](../../src/clinique/prescreen/schemas.py) `Trial`, [`ingestion.py`](../../src/clinique/prescreen/ingestion.py) |
| `Patient` / `PatientDocument` | **Implemented (L0)** | `PatientCorpus`, `PatientDocument`, [`normalizer.py`](../../src/clinique/prescreen/normalizer.py) |
| `Criterion` (atomic) | Proposed | [trial-prescreening.md §Pipeline](../design/trial-prescreening.md#pipeline) |
| `Evidence` / `Judgment` | Proposed | [trial-prescreening.md](../design/trial-prescreening.md) |
| Task labels (`met` / `not_met` / `unknown`) | Specified | [trial-prescreening.md §Decision labels](../design/trial-prescreening.md#decision-labels) |
| Frozen eval corpus | **Implemented pattern** | [`tests/fixtures/prescreen/trials.jsonl`](../../tests/fixtures/prescreen/trials.jsonl), [`tests/fixtures/edc_query/`](../../tests/fixtures/edc_query/) |

---

## Validation stack in ML eval terms

Clinique uses a five-layer validation ladder (see EDC and prescreen design docs). Mapped to
familiar ML concepts:

| Layer | Question | ML analogue | Clinique example |
|---|---|---|---|
| **L0** | Do deterministic pieces work? | Unit tests + schema validation | Prescreen parser tests; EDC fixture loaders |
| **L1** | Task accuracy on held-out data? | Offline benchmark | `reports/edc-query/offline-benchmark.json`; future n2c2 judge harness |
| **L2** | Useful as-of-time without leakage? | Temporal / leakage-safe eval | EDC retrospective replay; prescreen `snapshot_date` discipline |
| **L3** | Real-world behavior, zero operational impact? | Shadow mode | EDC silent prospective protocol (documented, not run) |
| **L4** | Causal improvement with controls? | Controlled rollout / A/B | EDC controlled-rollout gate |

**Accuracy ≠ usefulness.** Task labels (was the criterion judgment correct?) are necessary but not
sufficient. Workflow labels (did it save coordinator time? reduce false work?) prove the agent is
worth shipping — see [primer §1](clinical-trials-for-ml.md#1-the-simplest-mental-model).

---

## MLsys architecture notes

### Data flow (the two reference pipelines)

The package map above is the *static* structure; these are the *runtime* DAGs. Each node is tagged
by stage type so the central design claim — **LLM stages are narrow; everything around them is
deterministic and gated** — is legible at a glance:

`[NET]` network / non-deterministic · `[FIXED]` frozen fixture (the test of record) ·
`[PURE]` deterministic pure function · `[ENGINE]` validated, versioned compute ·
`[LLM]` narrow model stage · `[GATE]` hard pass/fail before any write · `[LEDGER]` append-only.

**A. Trial prescreening — record-and-replay** (`src/clinique/prescreen/`)

```
[NET]   ClinicalTrials.gov v2 API
          │  fetch_study_raw()              non-deterministic, rate-limited; not exercised by tests
          ▼
        raw JSON payload
          │  record_studies()              write-once snapshot, reviewable in git
          ▼
[FIXED] tests/fixtures/prescreen/trials.jsonl
          │  load_recorded_studies()       ◀── the eval boundary: everything below is offline
          ▼
[PURE]  Trial records ───────────┐
                                 ├─▶ [LLM]* atomizer ─▶ Criterion (atomic, typed)
[PURE]  PatientCorpus /          │                          │
        PatientDocument ─────────┘                          ▼
        (normalize_synthea())                    [LLM]* criterion judge
                                                            │
                                          [GATE]* evidence-provenance
                                                  (no met/not_met without a locatable quote)
                                                            ▼
                                          Judgment { met | not_met | unknown }
                                                  + evidence quote + rationale
```

`*` proposed (see [trial-prescreening.md](../design/trial-prescreening.md)); **L0 ships the
`[NET]`/`[FIXED]`/`[PURE]` path today** — ingestion, the frozen corpus, and the Synthea normalizer.

**B. Sample-size orchestrator — the validated-engine pattern** (`src/clinique/power/orchestrator.py`)

```
[PURE]   DesignIntake ─ select_method() ─▶ method + typed Assumptions
           ▼
[ENGINE] validated engine: two_sample_means() | two_proportions() | survival_logrank()
           │  RpactDockerEngine (canonical, rpact) ‖ ReferenceEngine (pure-Python oracle)
           │  — engine name + version are recorded; the orchestrator computes no statistic itself
           ▼
         EngineResult outputs
           │  sensitivity sweep ×0.8 / ×1.0 / ×1.2 around the swept assumption
           ▼
[PURE]   ComputationRecord     narrative assembled ONLY from blessed numbers
           │
[GATE]   check_numeric_provenance()   HARD GATE — every number must trace (within tolerance) to
           │                          an EngineResult output or an Assumption value
           ▼
[LEDGER] ProvenanceLedger (append-only JSONL)
```

The same shape recurs across capabilities: typed records → narrow/validated compute → a hard gate →
an append-only or read-only sink. That repetition is the point — it is what makes outputs auditable.

### Deterministic typed pipeline

LLM stages are narrow (future: atomizer, criterion judge). Aggregation, unit conversion, temporal
windows, and provenance gates are **pure functions** — same pattern as the power orchestrator in
[`src/clinique/power/orchestrator.py`](../../src/clinique/power/orchestrator.py).

### Record-and-replay

Network fetch once → versioned JSONL fixture → all CI/tests offline:

- Prescreen: [`record_studies()`](../../src/clinique/prescreen/ingestion.py) → `trials.jsonl`
- EDC: timestamp-gated replay over frozen snapshots

Live APIs mutate; frozen fixtures are the test of record. See
[`tests/fixtures/prescreen/PROVENANCE.md`](../../tests/fixtures/prescreen/PROVENANCE.md).

### Hard gates before write

| Gate | Purpose | Code |
|---|---|---|
| Numeric-provenance | No invented statistics in outputs | [`substrate/numeric_provenance.py`](../../src/clinique/substrate/numeric_provenance.py) |
| Evidence-provenance (prescreen) | No `met`/`not_met` without locatable quote | Proposed in prescreen design |
| No-fabrication | Draft text must not invent facts | [`conformance/draft.py`](../../src/clinique/conformance/draft.py) |
| No-write-back (EDC) | Agent never mutates EDC data | EDC tests + invariants |

### Stdlib-only runtime

`src/clinique/` uses Python stdlib only — no hidden pip dependencies in production code. Dev tools
(`pytest`, `ruff`) come from `uv.lock`. Eval reproducibility = committed fixtures + deterministic
parsers.

### CLI as batch jobs

| Command | Purpose | Exit notes |
|---|---|---|
| `clinique prescreen ingest` | Fetch CT.gov → record JSONL | 2 on failure |
| `clinique prescreen show` | Offline trial summary | 2 on parse failure |
| `clinique edc-query validate` | Regenerate L0–L2 reports | 2 on validation failure |
| `clinique edc-query verify-workstream` | Bundled gate check | 5 when `goal_complete: false` (expected locally) |

EDC exit codes are documented in [CLAUDE.md](../../CLAUDE.md).

---

## Run this first (~15 minutes)

```bash
uv sync

# Prescreen L0: parsers + normalizer (offline, no network)
uv run pytest tests/test_prescreen_ingestion.py tests/test_prescreen_normalizer.py -q
uv run clinique prescreen show --fixtures tests/fixtures/prescreen/trials.jsonl

# EDC L0–L2: deterministic validation reports
uv run clinique edc-query validate \
  --fixtures tests/fixtures/edc_query \
  --reports-dir reports/edc-query

# Full suite
uv run pytest
```

Read fixture provenance cards before trusting any corpus:

- [`tests/fixtures/prescreen/PROVENANCE.md`](../../tests/fixtures/prescreen/PROVENANCE.md)
- [`tests/fixtures/edc_query/PROVENANCE.md`](../../tests/fixtures/edc_query/PROVENANCE.md)

---

## Where each agent wedge lives

| Wedge | Domain primer | Design doc | Best ML entry point |
|---|---|---|---|
| **Prescreening** | [§7–8, §14](clinical-trials-for-ml.md#7-eligibility-criteria-are-the-first-great-mlagent-wedge) | [trial-prescreening.md](../design/trial-prescreening.md) | Prescreen tests + `trials.jsonl` |
| **EDC data quality** | [§4 `DataQuery`, §5 lifecycle](clinical-trials-for-ml.md#4-the-main-entities-in-the-data-model) | [edc-query-validation.md](../design/edc-query-validation.md) | `edc-query validate` reports |
| **Biostat substrate** | [§9 endpoints, §10 blinding](clinical-trials-for-ml.md#9-endpoints-are-the-labels) | [biostat-agent-suite.md](../design/biostat-agent-suite.md) | Power orchestrator + provenance gate |
| **CDISC exploration** | [§4 analysis datasets](clinical-trials-for-ml.md#4-the-main-entities-in-the-data-model) | — | [`explorer/`](../../explorer/) FDA-pilot ADaM JSON |

---

## Agent safety boundary

From [primer §12](clinical-trials-for-ml.md#12-where-foundation-model-agents-can-help), mapped to
this repo:

| Agent task | Clinique status |
|---|---|
| Eligibility parsing / prescreening draft | **L0 scaffold** — ingestion + normalizer; judge proposed |
| Evidence extraction | Proposed (retriever + judge) |
| Data-query drafting | **Implemented (local synthetic)** — EDC validation harness |
| Protocol / estimand consistency checks | **Scaffold** — estimand checker, conformance triage |
| Missing-data / visit-window checks | Partially covered by EDC deterministic detection |
| Safety triage | Out of scope (design stance: conservative human review) |
| Final eligibility decision | **Out of scope** — humans decide |
| Patient outreach / consent | **Out of scope** |
| Randomization / database lock | **Out of scope** |
| Write-back to EDC/EHR/CTMS | **Out of scope** — draft-only, read-only |

---

## Package map

```
src/clinique/
  substrate/     # provenance ledger, numeric-provenance gate, shared records
  power/         # sample-size orchestrator (reference validated-engine pattern)
  prescreen/     # trial ingestion, patient normalizer (L0 public path)
  edc/           # EDC query validation harness (L0–L2 local complete)
  estimand/      # artifact graph + consistency checker
  conformance/   # CDISC report triage
  dryrun/        # synthetic dry-run harness
  programming/   # QC side-lock
  cli.py         # clinique entry point
tests/fixtures/  # PHI-free frozen corpora + PROVENANCE.md per directory
reports/         # generated validation JSON (edc-query/)
docs/design/     # capability design specs
docs/primer/     # you are here
```

---

## Next steps by role

**ML researcher** (models, labels, eval):

1. Read [primer §7–8, §14](clinical-trials-for-ml.md#7-eligibility-criteria-are-the-first-great-mlagent-wedge)
2. Read [trial-prescreening.md](../design/trial-prescreening.md) (datasets, metrics, ship gates)
3. Run prescreen tests; inspect `trials.jsonl` and inline Synthea-shaped test tables

**MLsys engineer** (pipelines, gates, reproducibility):

1. Read this doc's validation stack + record-and-replay sections
2. Trace EDC `verify-workstream` and prescreen `record_studies` / `load_recorded_studies`
3. Read [biostat-agent-suite.md](../design/biostat-agent-suite.md) for substrate invariants

Return to [primer README](README.md) for the full reading order.

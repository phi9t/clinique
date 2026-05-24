# Clinique Terminology Glossary

**Audience:** ML researchers and MLsys engineers new to clinical trials or this repo. Use this as
a **lookup reference** while reading code, fixtures, and design docs.

**Repo-specific** usage is called out where it differs from general industry meaning. For the
domain mental model in ML language, start with [clinical-trials-for-ml.md](clinical-trials-for-ml.md).
For code maps and commands, see [clinique-for-ml.md](clinique-for-ml.md).

---

## Quick acronym index

Jump to the section that matches what you are reading:

| If you see… | Read section |
|---|---|
| EDC, EHR, CTMS, eTMF, CRF | [§9 Systems & regulatory acronyms](#9-systems--regulatory-acronyms) |
| CDISC, SDTM, ADaM, ADSL, define.xml, XPT, CORE | [§15 CDISC & regulatory data](#15-cdisc--regulatory-data) |
| NCT, CT.gov, PMC, MIMIC, n2c2, PHI, DUA | [§8 Public data sources](#8-public-data-sources) |
| L0–L4, F1, FN, FP, leakage | [§6 Validation layers](#6-validation-layers-l0l4) · [§17 ML eval metrics](#17-ml-eval-metrics) |
| met, not_met, unknown, snapshot_date | [§5 Judgment labels](#5-judgment-labels--recommendations) · [§4 Data model](#4-data-model-entities-prescreen-l0) |
| NSCLC, ANC, ECOG, PD-1, AE, SAE, GCP | [§2 Clinical trial fundamentals](#2-clinical-trial-fundamentals) · [§16 Clinical & NLP terms](#16-clinical--nlp-terms) |
| JSONL, CLI, CI, API, BM25 | [§18 Engineering acronyms](#18-engineering-acronyms) |
| Prescreen vs EDC vs CDISC | [§19 Three wedges compared](#19-three-wedges-compared-for-ml-audiences) |

**Table of contents:** [1 Clinique](#1-what-clinique-is) · [2 Trials](#2-clinical-trial-fundamentals) ·
[3 Prescreen pipeline](#3-prescreening-pipeline-terms) · [4 Data model](#4-data-model-entities-prescreen-l0) ·
[5 Labels](#5-judgment-labels--recommendations) · [6 L0–L4](#6-validation-layers-l0l4) ·
[7 Architecture](#7-architecture--engineering-patterns) · [8 Data sources](#8-public-data-sources) ·
[9 Systems](#9-systems--regulatory-acronyms) · [10 Prescreen CLI](#10-prescreen-cli-commands) ·
[11 Explorer UI](#11-explorer-ui-terms) · [12 Ship gates](#12-metrics--ship-gates-future-l1) ·
[13 Inclusion/exclusion](#13-quick-reference-inclusion-vs-exclusion-logic) ·
[14 EDC wedge](#14-edc-query-validation-wedge) · [15 CDISC](#15-cdisc--regulatory-data) ·
[16 Clinical/NLP](#16-clinical--nlp-terms) · [17 ML metrics](#17-ml-eval-metrics) ·
[18 Engineering](#18-engineering-acronyms) · [19 Three wedges](#19-three-wedges-compared-for-ml-audiences)

---

## 1. What Clinique Is

| Term | Meaning |
|---|---|
| **Clinique** | A Python toolkit of **assistive agents** for regulated clinical-trial workflows. Agents draft, retrieve, flag, and summarize; **humans** approve, decide, enroll, and sign off. |
| **Agent / copilot** | Software that produces **review artifacts**, not final decisions. Example: a prescreening copilot says "potentially eligible; these criteria need review" — never "patient is eligible." |
| **Wedge / proof point** | The first capability chosen to prove the platform works end-to-end. Currently **trial prescreening** (criterion-level judgments with evidence). |
| **Draft-only** | Agents never write back to systems of record (EHR, EDC, CTMS). Output is advisory. |
| **Deterministic gate** | A pure, pass/fail check that runs **before** output is treated as shippable. Examples: numeric-provenance gate, conformance validation, evidence-provenance gate (proposed). |
| **Substrate** | Shared platform primitives reused across capabilities: provenance ledger, human-review records, no-fabrication guards. See [`src/clinique/substrate/`](../../src/clinique/substrate/). |

---

## 2. Clinical Trial Fundamentals

| Term | Meaning |
|---|---|
| **Clinical trial** | A controlled experiment on humans to answer whether an intervention works, is safe, and for whom. ML analogy: a high-stakes, regulated data-generation pipeline. |
| **Protocol** | The master spec for a trial — like experiment config + data schema + labeling guide + QC plan + audit log combined. |
| **Eligibility criteria** | Rules defining **who can join** a trial. Split into **inclusion** (must satisfy) and **exclusion** (must not have). This is the core input to prescreening. |
| **Inclusion criterion** | Something the patient **must** have. Example: "Age ≥ 18." If unmet → likely ineligible. |
| **Exclusion criterion** | Something the patient **must not** have. Example: "No prior anti-PD-1 therapy." If the disqualifying condition is present → likely ineligible. |
| **Prescreening / screening** | Checking whether a patient **might** meet trial eligibility before full enrollment work. Coordinators do this today manually; Clinique automates the **draft** packet. |
| **Enrollment** | Formal entry into the trial after all eligibility is confirmed — **out of scope** for the agent. |
| **Phase 1–4** | Trial stages by regulatory purpose: Phase 1 = safety/dose; Phase 2 = early efficacy signal; Phase 3 = large confirmatory; Phase 4 = post-market. Stored as `PHASE1`, `PHASE2`, etc. from ClinicalTrials.gov. |
| **Endpoint** | The outcome the trial measures (e.g. overall survival). ML analogy: **label definition** — but with strict time windows, adjudication, and blinding rules. |
| **Primary / secondary endpoint** | Main outcome vs. additional outcomes. |
| **Randomization** | Assigning patients to treatment arms by chance to reduce bias. |
| **Blinding** | Hiding treatment assignment from participants, investigators, or analysts. |
| **Adverse event (AE)** | Any unfavorable medical occurrence during the trial. |
| **Serious adverse event (SAE)** | AE requiring urgent reporting (death, hospitalization, etc.). |
| **GCP (Good Clinical Practice)** | International quality standard for trials (ICH E6). Emphasizes participant protection and reliable data. |
| **IRB / ethics review** | Institutional review board approval before human research. |

---

## 3. Prescreening Pipeline Terms

The full prescreening pipeline (from [trial-prescreening design](../design/trial-prescreening.md)):

```mermaid
flowchart LR
  ingest[IngestTrial] --> atomize[AtomizeCriteria]
  normalize[NormalizePatient] --> retrieve[RetrieveEvidence]
  atomize --> retrieve
  retrieve --> judge[CriterionJudge]
  judge --> aggregate[Aggregate]
  aggregate --> packet[BuildPacket]
  packet --> gate[EvidenceGate]
  gate --> ledger[ProvenanceLedger]
```

| Term | Status | Meaning |
|---|---|---|
| **Ingestion** | Implemented | Fetch trial metadata from ClinicalTrials.gov API v2, parse into `Trial` records. |
| **Atomizer** | Proposed | LLM stage that splits raw eligibility text into **atomic criteria** — independently adjudicable predicates with operator, threshold, temporal window, etc. |
| **Normalizer** | Implemented | Converts heterogeneous patient sources (Synthea CSV, PMC text, MIMIC tables) into the shared `PatientCorpus` / `PatientDocument` model. |
| **Retriever** | Proposed | Finds patient evidence relevant to one criterion (BM25 + embeddings + structured lookup + temporal filter). |
| **Criterion judge** | Proposed | LLM that reads criterion + evidence and outputs a `CriterionJudgment` (`met`, `not_met`, `unknown`, etc.) with quotes. |
| **Aggregator** | Implemented (library) | **Deterministic** function that combines criterion judgments into an overall recommendation. No LLM. See [`aggregator.py`](../../src/clinique/prescreen/aggregator.py). |
| **Evidence-provenance gate** | Proposed | Hard check: every `met`/`not_met` must cite a quote found **verbatim** in a source document. |
| **Orchestrator** | Proposed | Typed function graph wiring all stages; builds packet, runs gates, appends to ledger. Mirrors the power orchestrator pattern. |
| **Prescreening packet** | Proposed | Final audit artifact: all criterion judgments, evidence, overall recommendation, provenance. |

**Key design rule:** LLM stages are **narrow** (atomizer, judge). Everything else — aggregation, unit conversion, temporal windows, validation — is **deterministic pure functions**.

---

## 4. Data Model Entities (Prescreen L0)

Defined in [`src/clinique/prescreen/schemas.py`](../../src/clinique/prescreen/schemas.py):

| Entity | ML analogy | Meaning |
|---|---|---|
| **`Trial`** | Task instance / prompt | One trial's eligibility specification. Contains `eligibility_text` (raw inclusion/exclusion block), demographics metadata (sex, age bounds), conditions, phase, sponsor. |
| **`AgeBound`** | Parsed feature | Age limit with raw string + normalized value in **years**. `None` means "no constraint" — never treat as zero. |
| **`PatientCorpus`** | One example's feature set | All evidence for one patient at one **`snapshot_date`** (as-of time). |
| **`PatientDocument`** | One evidence unit | A lab, condition, medication, procedure, or note chunk. Has `text` (for retrieval/citation), `structured` (machine facts), and `date` (for temporal reasoning). |
| **`Criterion`** | Atomic sub-task | Proposed. One adjudicable eligibility predicate parsed from `eligibility_text`. |
| **`Evidence`** | Retrieved context | Proposed. Patient document span(s) relevant to a criterion. |
| **`CriterionJudgment`** | Per-criterion prediction | `criterion_id` + `criterion_type` (inclusion/exclusion) + `prediction` label. |
| **`source` field** | Dataset discriminator | Tags where data came from: `clinicaltrials_gov`, `synthea`, `pmc_patients`, `mimic_iv_demo`. |

**Convergence principle:** Four heterogeneous public sources collapse onto **two** typed records — `Trial` (trial side) and `PatientCorpus`/`PatientDocument` (patient side). Validation is one contract, not four.

---

## 5. Judgment Labels & Recommendations

### Per-criterion predictions (`PREDICTIONS`)

| Label | Meaning |
|---|---|
| **`met`** | Criterion is satisfied. For **inclusion**: patient meets requirement. For **exclusion**: patient **has** the disqualifying condition → bad. |
| **`not_met`** | Criterion is not satisfied. For **inclusion**: patient fails requirement. For **exclusion**: exclusion is **cleared** with explicit negative evidence. |
| **`unknown`** | Insufficient evidence. **Never** infer clearance from silence — especially for exclusions. |
| **`not_applicable`** | Criterion doesn't apply to this patient. Ignored by aggregation. |
| **`conflicting_evidence`** | Sources disagree. Triggers human review. |

**Exclusion polarity (most error-prone):** "No evidence of prior anti-PD-1" → **`unknown`**, not `not_met`. Treating absence as clearance is forbidden.

### Overall recommendations (`RECOMMENDATIONS`)

Produced by [`aggregate()`](../../src/clinique/prescreen/aggregator.py) — priority order:

1. Any exclusion `met` OR any inclusion `not_met` → **`likely_ineligible`**
2. Any `unknown` or `conflicting_evidence` → **`needs_review`**
3. Else → **`potentially_eligible`**

Empty input → `potentially_eligible` (vacuous pass).

---

## 6. Validation Layers (L0–L4)

Clinique's **evidence ladder** — same pattern for prescreen and EDC:

| Layer | Question | ML analogue | Prescreen example |
|---|---|---|---|
| **L0** | Do deterministic pieces work? | Unit tests + schema validation | Parsers, normalizers, aggregation, `prescreen validate` |
| **L1** | Task accuracy on held-out labels? | Offline benchmark | n2c2 2018 criterion-level F1 (future judge harness) |
| **L2** | Useful as-of-time without leakage? | Temporal / leakage-safe eval | `snapshot_date` discipline; no future documents |
| **L3** | Real-world behavior, zero operational impact? | Shadow mode | Silent prospective (deferred) |
| **L4** | Causal improvement with controls? | Controlled rollout / A/B | Time-savings study with human approval (deferred) |

**Repo status:** Prescreen is at **`L0-PUBLIC-DATA`** — the data layer (fetch, parse, normalize, validate) is implemented. Atomizer/judge/retrieval are **proposed** (not L1 yet).

**Accuracy ≠ usefulness:** High criterion F1 does not prove the agent saves coordinator time. Workflow metrics (review-time reduction, correction rate) are separate ship gates.

---

## 7. Architecture & Engineering Patterns

| Term | Meaning |
|---|---|
| **Record-and-replay** | Fetch from live API once → freeze raw payload to versioned JSONL fixture → all CI/tests run offline against the fixture. ClinicalTrials.gov mutates; fixtures are the **test of record**. |
| **Fetch vs. parse split** | Network fetch (`fetch_study_raw`) is impure; parsing (`Trial.from_api`) is pure and offline-testable. Same pattern for every source. |
| **Controlled vocabulary** | Allowed enum values for fields (e.g. `TRIAL_SEX`, `DOC_SOURCE_TYPES`). Defined in `schemas.py`; enforced by `validation.py`. Unexpected value = API changed or parser bug. |
| **Conformance gate / validation** | [`validation.py`](../../src/clinique/prescreen/validation.py) checks records conform to the mental model. CLI: `prescreen validate`. Exit code **7** on errors. |
| **Leakage / no-leakage invariant** | For eval, retrieval may only use documents dated **on or before** `snapshot_date`. A document dated after snapshot = **error**. Prevents using future information. |
| **JSONL** | Newline-delimited JSON — the on-disk format for trials, patient corpora, and provenance records. |
| **Provenance ledger** | Append-only audit log of inputs, outputs, model/prompt versions, tool versions. [`substrate/provenance.py`](../../src/clinique/substrate/provenance.py). |
| **Numeric-provenance gate** | No statistic in output unless it traces to a validated engine result. Used in power orchestrator. |
| **No-fabrication guard** | Draft text must not invent facts. [`conformance/draft.py`](../../src/clinique/conformance/draft.py). |
| **HumanReview** | Dataclass recording a named human's sign-off on each packet. |
| **Pipeline stage tags** | From [clinique-for-ml.md](clinique-for-ml.md): `[NET]` network, `[FIXED]` frozen fixture, `[PURE]` deterministic, `[ENGINE]` validated compute, `[LLM]` model stage, `[GATE]` hard pass/fail, `[LEDGER]` append-only sink. |

---

## 8. Public Data Sources

| Source | Provides | Access | Role in prescreen |
|---|---|---|---|
| **ClinicalTrials.gov (CT.gov)** | Real eligibility text, conditions, phase, age/sex | Open, no auth | Trial ingestion + future atomizer input |
| **NCT ID** | Trial identifier (e.g. `NCT02578680`) | Open | Primary key for CT.gov studies |
| **Synthea** | Synthetic patients (conditions, meds, labs, procedures) | Open (Apache-2.0) | Normalizer + retrieval plumbing tests |
| **PMC-Patients** | Real free-text case reports from PubMed Central Open Access | Open (CC subset) | Realistic text for normalizer/judge |
| **MIMIC-IV demo** | 100 real de-identified patients, structured | Open (ODbL) | Structured-fact extraction; synthetic-shaped fixtures only in repo |
| **n2c2 2018 Track 1** | Real records + gold met/not-met labels (13 criteria) | **Credentialed** (Harvard DUA) | Judge benchmark — real L1/L2 signal |
| **MIMIC-IV full** | Real longitudinal records + discharge notes | **Credentialed** (PhysioNet DUA) | Retrieval at scale (deferred) |

**PHI (Protected Health Information):** Real patient identifiers or identifiable health data. Repo fixtures stay **PHI-free** — synthetic or de-identified open subsets only.

**DUA (Data Use Agreement):** Legal agreement required for credentialed datasets (n2c2, full MIMIC). Plan access time; never commit credentialed corpora.

---

## 9. Systems & Regulatory Acronyms

| Acronym | Full name | Meaning | ML analogy |
|---|---|---|---|
| **EDC** | Electronic Data Capture | System sites use to enter trial CRF data. Clinique's **EDC query validation** wedge drafts data-quality queries on snapshots — it never writes back. | Batch job over frozen DB snapshots; draft flags, not mutations. |
| **EHR** | Electronic Health Record | Hospital/clinic chart system (Epic, Cerner, etc.). | Source system for real patient features — out of scope for v1 agents. |
| **CTMS** | Clinical Trial Management System | Sponsor ops: sites, enrollment, monitoring. | Workflow/orchestration layer — agents are read-only to it. |
| **eTMF** | electronic Trial Master File | Regulated document store (protocol, contracts). | Artifact store — agents may draft docs, not lock/submit. |
| **CRF** | Case Report Form | Structured forms filled at each visit. | Schema for per-visit feature collection. |
| **CDISC** | Clinical Data Interchange Standards Consortium | Body defining how trial data is structured for regulators. | Shared schema contract for submission datasets. |
| **FDA** | U.S. Food and Drug Administration | U.S. drug/device regulator. | — |
| **ICH** | International Council for Harmonisation | Publishes global guidelines (e.g. E6 GCP). | — |
| **OMOP CDM** | Observational Medical Outcomes Partnership Common Data Model | Standard schema for observational/EHR data. | Future **feature store** mapping target for patient records. |
| **FHIR** | Fast Healthcare Interoperability Resources | Modern health-data exchange standard. | Future EHR adapter format. |
| **RxNorm** | (Rx + Norm) | NIH normalized drug naming system. | Deterministic drug lookup table (not LLM recall). |
| **ATC** | Anatomical Therapeutic Chemical | WHO drug classification (e.g. anti-PD-1 class). | Hierarchical label space for medication criteria. |

---

## 10. Prescreen CLI Commands

| Command | Purpose |
|---|---|
| `prescreen ingest` | Fetch specific NCT IDs from CT.gov → record JSONL |
| `prescreen search` | Search CT.gov with pagination → record results |
| `prescreen show` | Offline trial summary from JSONL fixture |
| `prescreen normalize-synthea` | Synthea CSV directory → `PatientCorpus` JSONL |
| `prescreen ingest-pmc` | Fetch PMC-Patients sample → record |
| `prescreen validate` | L0 conformance report (exit **7** on errors) |
| `prescreen export-explorer` | Export JSON for the web explorer dashboard |

Exit codes: **0** = success; **2** = load/fetch/parse failure; **7** = conformance errors.

---

## 11. Explorer UI Terms

The [`explorer/`](../../explorer/) app has two modes (see [`App.tsx`](../../explorer/src/App.tsx)):

| Mode | Purpose |
|---|---|
| **Prescreen L0** | Visualize schema, field distributions, patient timelines, conformance stats for prescreen public data |
| **Regulatory CDISC** | Browse FDA-pilot ADaM datasets, metadata, codelists, and row-level data |

Explorer-specific terms:

| Term | Meaning |
|---|---|
| **Schema view** | Documents `Trial`, `PatientCorpus`, `PatientDocument`, `AgeBound` fields and pipeline steps |
| **Vocab gloss** | Inline glossary of controlled-vocabulary terms in the explorer |
| **Pipeline strip** | Visual sequence: source → parse → normalize → validate |
| **Patient timeline** | Chronological view of `PatientDocument` entries for one corpus |
| **Conformance panel** | Validation errors/warnings from L0 gate |
| **Codelist** | CDISC controlled term list (value → label mappings) |
| **Domain** | CDISC dataset category (e.g. ADSL, ADAE) |

---

## 12. Metrics & Ship Gates (Future L1+)

| Term | Meaning |
|---|---|
| **Criterion-level accuracy / macro-F1** | How often per-criterion judgments match gold labels |
| **Inclusion false-negative rate** | Missing eligible patients — safety-critical |
| **Exclusion false-negative rate** | Clearing a disqualifying criterion — **must be ≤ 0.05** at ship |
| **Evidence support accuracy** | Whether cited quotes actually support the judgment |
| **Unknown rate / unknown-actionability** | Fraction of `unknown` judgments; also whether reviewers find them actionable vs. noise |
| **Review-time reduction** | Primary workflow metric — did the agent save coordinator time? |
| **Ship gates** | Pre-registered thresholds (F1 ≥ 0.80, evidence accuracy ≥ 0.85, etc.) before moving past L2 |

---

## 13. Quick Reference: Inclusion vs. Exclusion Logic

```text
INCLUSION "Age ≥ 18"
  evidence: age=62  → met        (good)
  evidence: age=16  → not_met    (likely ineligible)
  evidence: missing → unknown    (needs review)

EXCLUSION "No prior anti-PD-1"
  evidence: pembrolizumab documented → met      (likely ineligible)
  evidence: "no prior IO" explicit   → not_met  (exclusion cleared)
  evidence: nothing found            → unknown  (NOT not_met — silence ≠ clearance)
```

---

## 14. EDC Query Validation Wedge

**Design:** [edc-query-validation.md](../design/edc-query-validation.md) · **Code:** [`src/clinique/edc/`](../../src/clinique/edc/) · **Fixtures:** [`tests/fixtures/edc_query/`](../../tests/fixtures/edc_query/)

The EDC wedge validates a **deterministic data-quality query harness** — not an LLM agent yet. It
answers: given EDC snapshots and edit-check rules, can we draft candidate queries with evidence and
pass L0–L2 gates?

### ML mental model

```text
EDC snapshot (features at time T) + rules (validators) → candidate queries (predictions)
Gold labels (adjudicated)                              → task metrics (precision/recall analogues)
Replay at timestamp T                                  → leakage-safe eval (L2)
```

### Key entities

| Entity | ML analogy | Meaning |
|---|---|---|
| **`EdcSnapshot`** | Example at time T | Frozen view of trial data as of a timestamp. |
| **`EditCheckRule`** | Validator spec | Rule kind: `required_field`, `date_order`, `future_date`. |
| **`CandidateQuery`** | Model prediction | Draft query with evidence `SourceRef` citations; always `draft_only=True`. |
| **`QueryLabel`** | Gold label | Adjudicated outcome: missing, inconsistent, duplicate, no_query, etc. |
| **`SourceRef`** | Provenance pointer | `(source_type, source_id, observed_at)` — local provenance, not substrate ledger yet. |

### CLI commands

| Command | Purpose |
|---|---|
| `edc-query validate` | Generate L0–L2 reports from synthetic fixtures |
| `edc-query preflight-internal-data` | Check manifest readiness (no PHI reads) |
| `edc-query validate-internal-exports` | Approved-export import path |
| `edc-query evaluate-silent-log` | L3 silent prospective evaluator |
| `edc-query evaluate-rollout-gate` | L4 controlled rollout evaluator |
| `edc-query verify-workstream` | Bundled gate check (currently `goal_complete: false`) |

### Exit codes

| Code | Meaning |
|---|---|
| **0** | Success |
| **2** | Validation/input error |
| **3** | Preflight manifest not ready |
| **4** | Rollout gate failed |
| **5** | Workstream incomplete (`goal_complete: false` — **expected locally**) |
| **6** | Silent log gates failed |

### Status

| Layer | Status |
|---|---|
| L0–L2 | **Complete** on PHI-free synthetic fixtures (131 tests) |
| L3–L4 | Evaluators built; **no real operational run** yet |
| LLM query drafter | **Not implemented** — detection is deterministic rules only |

Reports land in [`reports/edc-query/`](../../reports/edc-query/). Read
[`tests/fixtures/edc_query/PROVENANCE.md`](../../tests/fixtures/edc_query/PROVENANCE.md) before trusting the corpus.

---

## 15. CDISC & Regulatory Data

**Explorer UI:** [`explorer/src/cdisc/CdiscExplorer.tsx`](../../explorer/src/cdisc/CdiscExplorer.tsx) ·
**Static JSON:** [`explorer/public/data/`](../../explorer/public/data/) ·
**Source fixtures:** [`tests/fixtures/realdata/`](../../tests/fixtures/realdata/)

CDISC defines how trial data is **structured for regulatory submission**. The explorer's
**Regulatory CDISC** tab browses FDA R Consortium Pilot 1 ADaM datasets — analysis-ready tables
derived from SDTM.

### Core CDISC acronyms

| Acronym | Full name | Meaning | ML analogy |
|---|---|---|---|
| **SDTM** | Study Data Tabulation Model | Standard format for **submitted** tabular trial data. | Normalized raw event tables (one domain per table type). |
| **ADaM** | Analysis Data Model | Standard format for **analysis-ready** datasets. | Feature-engineered tables ready for stats/ML. |
| **define.xml** | Define-XML | Machine-readable metadata: variables, types, codelists, methods. | Dataset **schema + feature spec** file. |
| **XPT** | SAS Transport File | Binary format for SAS datasets. | Serialized columnar store; Python reader gets column names only. |
| **CORE** | CDISC Open Rules Engine | Conformance rule engine for CDISC datasets. | Linter output; Clinique has triage scaffolding in [`conformance/`](../../src/clinique/conformance/). |
| **Codelist** | Controlled terminology | Allowed values for a coded field (value → label). | Enum / label map in a schema. |

### Common ADaM dataset names (FDA pilot)

| Dataset | Typical role |
|---|---|
| **ADSL** | Subject-level analysis dataset (one row per patient — demographics, treatment, flags) |
| **ADAE** | Adverse events analysis dataset |
| **ADLBC / ADLBH** | Lab chemistry / hematology analysis datasets |
| **ADTTE** | Time-to-event analysis dataset |
| **ADVS** | Vital signs analysis dataset |

The explorer loads 12 ADaM datasets (254 subjects). Nine are **sampled to 1,000 rows** in the UI;
`is_sampled: true` flags this.

### Python CDISC modules (not yet wired to explorer export)

| Module | Role |
|---|---|
| [`estimand/define_xml.py`](../../src/clinique/estimand/define_xml.py) | Parse define.xml; integrity checks (dangling OIDs) |
| [`io/xpt.py`](../../src/clinique/io/xpt.py) | Read XPT column names (stdlib, no row data) |
| [`conformance/`](../../src/clinique/conformance/) | CORE/Pinnacle report triage + no-fabrication draft |

Tests: [`test_realdata_define.py`](../../tests/test_realdata_define.py) (51 known MethodDef defects in pilot define.xml),
[`test_conformance_triage.py`](../../tests/test_conformance_triage.py).

**Gap:** Prescreen has `prescreen export-explorer`; CDISC JSON has **no in-repo regenerator** — see
[§19 Three wedges](#19-three-wedges-compared-for-ml-audiences).

---

## 16. Clinical & NLP Terms

Terms you will see in eligibility text, fixtures, and prescreen examples:

| Term | Meaning |
|---|---|
| **NSCLC** | Non-Small Cell Lung Cancer — condition in example trials (KEYNOTE-189, etc.). |
| **ANC** | Absolute Neutrophil Count — common lab eligibility threshold (e.g. ≥ 1500 cells/uL). |
| **ECOG** | Eastern Cooperative Oncology Group performance status (0–4) — fitness scale in oncology trials. |
| **PD-1** | Immune checkpoint protein; **anti-PD-1** drugs (pembrolizumab, nivolumab) appear in exclusion criteria. |
| **Pembrolizumab** | Example anti-PD-1 drug (brand Keytruda) — used in fixture eligibility examples. |
| **Metastatic** | Cancer that has spread beyond the original site — common inclusion qualifier. |
| **Histologically confirmed** | Diagnosis verified by tissue biopsy — common inclusion phrasing. |
| **ConMed** | Concomitant medication — other drugs taken during the trial; EDC fixture tests date consistency vs AE forms. |
| **SDV** | Source Data Verification — monitors compare EDC entries to source charts (mentioned in EDC design, not yet modeled). |

---

## 17. ML Eval Metrics

| Term | Meaning |
|---|---|
| **F1 / macro-F1** | Harmonic mean of precision and recall, averaged across criterion classes. Primary task metric for prescreen judge eval. |
| **FN (false negative)** | Missed positive — e.g. clearing an exclusion that was actually met (**safety-critical**). |
| **FP (false positive)** | Flagged when should not have been — e.g. draft query on clean data. |
| **Precision / recall** | Standard ML definitions; **inclusion FN rate** and **exclusion FN rate** are pre-registered ship gates. |
| **Evidence support accuracy** | Did the cited quote actually support the judgment? Separate from label accuracy. |
| **Unknown rate** | Fraction of `unknown` predictions — high unknown may mean safe but not useful. |
| **Unknown-actionability** | Do reviewers find `unknown` flags helpful or noise? Workflow metric, not task metric. |
| **Review-time reduction** | Primary **workflow** metric — did the agent save coordinator time? |
| **Leakage** | Using information from after the eval cutoff (`snapshot_date` or replay timestamp). ML analogue: train/test temporal leakage. |

---

## 18. Engineering Acronyms

| Acronym | Meaning in this repo |
|---|---|
| **JSONL** | JSON Lines — one JSON object per line; format for trials, patients, provenance. |
| **CLI** | Command-line interface — `uv run clinique prescreen …`, `edc-query …`. |
| **CI** | Continuous integration — GitHub Actions runs `pytest` (+ explorer build for pages). |
| **API** | Application programming interface — e.g. ClinicalTrials.gov API v2. |
| **BM25** | Best Matching 25 — classic sparse text retrieval; proposed for prescreen evidence retriever. |
| **DUA** | Data Use Agreement — required for credentialed datasets (n2c2, full MIMIC). |
| **PHI** | Protected Health Information — identifiable patient data; never commit to repo fixtures. |
| **CC** | Creative Commons — license on some PMC open-access content. |
| **ODbL** | Open Database License — MIMIC-IV demo license. |

---

## 19. Three Wedges Compared (for ML Audiences)

Clinique ships three **data-facing** capabilities that share the same platform pattern:
typed records → deterministic compute → hard gate → read-only output.

```mermaid
flowchart TB
  subgraph prescreen [Prescreen L0]
    PT[Trial + PatientCorpus]
    PV[prescreen validate]
    PE[export-explorer → React UI]
    PT --> PV --> PE
  end

  subgraph edc [EDC query validation]
    ES[EdcSnapshot + rules]
    ED[detection.py]
    ER[reports/edc-query/]
    ES --> ED --> ER
  end

  subgraph cdisc [CDISC exploration]
    RF[tests/fixtures/realdata/]
    CJ[explorer/public/data/*.json]
    CU[CdiscExplorer.tsx]
    RF -.->|no in-repo exporter| CJ --> CU
  end
```

| | **Prescreen** | **EDC** | **CDISC explorer** |
|---|---|---|---|
| **Question** | Can we normalize public trial + patient data? | Can we draft data-quality queries with evidence? | Can we browse FDA-pilot ADaM + define.xml? |
| **ML task analogue** | Retrieval + multi-label classification (future judge) | Rule-based anomaly detection + query drafting | Dataset/schema exploration |
| **Status** | L0 public data **implemented** | L0–L2 synthetic **complete** | Static JSON + UI |
| **Fixtures** | `tests/fixtures/prescreen/` | `tests/fixtures/edc_query/` | `tests/fixtures/realdata/` + committed JSON |
| **Regenerate JSON** | `prescreen export-explorer` | `edc-query validate` → reports | **No CLI yet** |
| **Explorer tab** | Prescreen L0 | — | Regulatory CDISC |
| **Validation in UI** | Yes (conformance panel) | No (reports are JSON files) | No (define.xml defects in tests only) |
| **Uses substrate ledger** | Proposed (orchestrator) | No (local SourceRef) | No |
| **LLM stage** | Proposed (atomizer, judge) | Not implemented | N/A |

### Who should read what

| Role | Start here |
|---|---|
| **ML researcher** (labels, models, eval) | [§5 Labels](#5-judgment-labels--recommendations) · [§8 Data sources](#8-public-data-sources) · [trial-prescreening design](../design/trial-prescreening.md) |
| **MLsys engineer** (pipelines, gates, CI) | [§6 L0–L4](#6-validation-layers-l0l4) · [§7 Architecture](#7-architecture--engineering-patterns) · [§14 EDC](#14-edc-query-validation-wedge) · [clinique-for-ml.md](clinique-for-ml.md) |
| **Browsing regulatory data** | [§15 CDISC](#15-cdisc--regulatory-data) · [`explorer/`](../../explorer/) |

---

## Where to Read More

- Domain mental model: [clinical-trials-for-ml.md](clinical-trials-for-ml.md)
- Repo mapping + commands: [clinique-for-ml.md](clinique-for-ml.md)
- Prescreen design: [trial-prescreening.md](../design/trial-prescreening.md)
- EDC design: [edc-query-validation.md](../design/edc-query-validation.md)
- Biostat / CDISC modules: [biostat-agent-suite.md](../design/biostat-agent-suite.md)
- Schema source of truth: [`schemas.py`](../../src/clinique/prescreen/schemas.py)
- Prescreen fixture provenance: [`PROVENANCE.md`](../../tests/fixtures/prescreen/PROVENANCE.md)
- EDC fixture provenance: [`PROVENANCE.md`](../../tests/fixtures/edc_query/PROVENANCE.md)
- CDISC source provenance: [`PROVENANCE.md`](../../tests/fixtures/realdata/PROVENANCE.md)

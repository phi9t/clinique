# Trial prescreening agent — design

**Background:** [Eligibility criteria primer §7–8](../primer/clinical-trials-for-ml.md#7-eligibility-criteria-are-the-first-great-mlagent-wedge),
[ANC example §14](../primer/clinical-trials-for-ml.md#14-one-concrete-example),
[minimum schema §13](../primer/clinical-trials-for-ml.md#13-how-to-think-about-the-data-model-for-your-proof-point).

**Status:** `L0-PUBLIC-DATA` (2026-05-24). The genuinely-public **data layer** is implemented end to
end: heterogeneous public sources are fetched, parsed, and proven to converge on the internal model.
ClinicalTrials.gov trial ingestion now includes **search + pagination** (pull a whole disease area,
not a hand-typed id list) alongside the single-study recorder. Three patient sources normalize onto
the shared `PatientCorpus`/`PatientDocument` records: **Synthea** (corpus-wide, committed synthetic
fixture), **PMC-Patients** (open real free-text case reports → `note` documents), and the
**MIMIC-IV demo** (real de-identified structured data; only synthetic-shaped fixtures committed). A
dedicated **conformance gate** (`validation.py`, CLI `prescreen validate`, exit code 7) enforces the
controlled vocabularies, age-bound sanity, duplicate-id, and the snapshot **no-leakage** invariant.
All paths are deterministic and offline-tested.

Atomizer, retriever, criterion judge, evidence-provenance gate, and orchestrator remain proposed.
Reuses the platform substrate ([provenance ledger + provenance gate](biostat-agent-suite.md));
nothing ships until L0–L2 evidence meets the gates below.

Evidence-grounded **trial prescreening copilot**. A coordinator, clinician, or trial-ops user
provides a trial eligibility section and a patient record; the agent returns atomic criteria,
retrieved patient evidence per criterion, a criterion-level decision, and an overall prescreening
packet with a complete audit trail. The agent produces a **review artifact, not an eligibility
decision** — its strongest output is "potentially eligible; these criteria are satisfied, these are
not, these need human review," never "patient is eligible."

**North-star question:** does the agent cut coordinator prescreening time while preserving recall
and evidence quality — without ever clearing a disqualifying criterion it cannot support?

## Why this wedge

Prescreening is the natural expansion beyond the [EDC query](edc-query-validation.md) agent: it is
artifact-heavy, traceability-driven, and slots into an existing human-review workflow as draft-only
decision support — the same posture the substrate already enforces. Eligibility criteria and
patient records are publicly benchmarkable (n2c2 2018 Track 1), so L0–L2 can be validated with **no
PHI and no live EHR**, exactly as the power orchestrator was.

## Design stance

Inherits the suite posture ([biostat-agent-suite.md](biostat-agent-suite.md) §Design stance), with
two prescreening-specific additions:

- **Agents draft, triage, and check. Humans decide.** No final eligibility call; no patient
  contact; no enrollment action. Output language is "potentially eligible / needs review."
- **Read-only and advisory.** No write-back to any EHR, EDC, CTMS, or eTMF.
- **Evidence grounds every judgment.** No `met`/`not_met` may exist without a verbatim source quote
  that is found in a patient document — the direct analog of the suite's numeric-provenance gate.
- **Provenance is mandatory.** Every judgment carries source spans, model + prompt version, tool
  versions, and the human reviewer decision.
- **Absence of evidence is `unknown`, not clearance.** The agent may only clear an exclusion with
  explicit negative evidence or an authoritative structured source — never from silence.

## Context of use

The agent drafts a criterion-level screening packet for a human reviewer. It does **not** decide
eligibility, contact patients, automate consent or outreach, write to any system of record, or
access unblinded data. Every recommendation must be auditable to source document spans, atomized
criteria, retrieval scores, rule/vocabulary versions, model/prompt versions, and the reviewer's
decision.

## Substrate reuse

This capability is mostly an application of the existing platform substrate, not new infrastructure.
The mapping is near one-to-one — which is why the "evidence-backed, no-fabrication, audit-logged"
claim is largely inherited and already tested:

| Prescreening need | Substrate component (existing) |
|---|---|
| Audit log of inputs, evidence, outputs, model/tool/prompt versions | `substrate/provenance.py` — append-only `ProvenanceLedger`, `LedgerRecord` |
| Human-in-the-loop sign-off on each packet | `HumanReview` dataclass on every `LedgerRecord` |
| "No `met`/`not_met` without supporting evidence, or it fails validation" | `substrate/numeric_provenance.py` gate pattern, re-specialized as an **evidence-provenance** gate |
| Quote-must-appear-in-source, no fabricated text | `conformance/draft.py` no-fabrication draft guard |
| Deterministic, reproducible aggregation from typed records | `power/orchestrator.py` validated-engine-only / determinism pattern |

New code is the prescreening-specific logic (atomizer, retriever, criterion judge, aggregator) and
its evidence-provenance gate; the ledger, human-review, and no-fabrication primitives are reused.

## Core invariants (pass/fail, not metrics)

- **Evidence-provenance:** every `met` or `not_met` judgment cites ≥1 evidence quote whose text is
  found verbatim in a referenced source document; judgments that assert without a locatable quote
  are violations. Run as a hard gate before the packet is written to the ledger.
- **No-absence-from-silence:** the aggregator and judge treat missing evidence as `unknown`. A
  stale-but-passing lab is `unknown` (current value unknown), never `not_met`.
- **Deterministic aggregation:** the overall recommendation is a pure function of the criterion
  judgments (no LLM); re-running identical judgments yields an identical recommendation.
- **Confidence is display-only:** the LLM judge's `confidence` is metadata; it never gates
  `human_review_required` or aggregation. Review flags derive from *structural* signals
  (safety-critical + unknown, conflicting evidence, stale evidence, ambiguous criterion).
- **Vocabulary-not-model for coded lookups:** drug-class / synonym membership (e.g. "is
  pembrolizumab anti-PD-1") resolves through a deterministic vocabulary (RxNorm/ATC), not LLM
  recall — consistent with "calculators compute; LLMs orchestrate."
- **Draft-only:** no API writes back to any system of record; no final-eligibility language in any
  output.

## Pipeline

A deterministic typed-function graph (no autonomous planner), mirroring the power orchestrator:

```
ingest trial → atomize criteria → normalize patient → per criterion {retrieve evidence →
  judge} → aggregate (deterministic) → build packet → evidence-provenance gate → ledger append
```

Each stage is a typed function with a strict output schema, independently testable:

```python
class EligibilityAtomizer:   def run(trial) -> list[Criterion]: ...
class PatientNormalizer:      def run(patient) -> PatientCorpus: ...
class EvidenceRetriever:      def retrieve(criterion, corpus) -> list[Evidence]: ...
class CriterionJudge:         def judge(criterion, evidence) -> CriterionJudgment: ...   # LLM
class DecisionAggregator:     def aggregate(judgments) -> Recommendation: ...            # deterministic
```

## Data model

JSONL records from the start (eval, debugging, versioning, demos). Core types: `Trial`,
`Criterion` (atomic), `PatientCorpus`, `Evidence`, `CriterionJudgment`, `PrescreeningPacket`. The
key design decision is **atomization**: split compound eligibility text into independently
adjudicable predicates carrying operator, threshold+unit, temporal window+anchor, clinical domain,
`requires_absence_evidence`, `is_safety_critical`, and `ambiguity_flags`.

```json
{
  "criterion_id": "I-003", "criterion_type": "inclusion",
  "raw_text": "ANC >= 1500/uL within 14 days prior to enrollment",
  "clinical_domain": "laboratory", "operator": ">=",
  "threshold": {"value": 1500, "unit": "cells/uL"},
  "temporal_constraint": {"window_value": 14, "window_unit": "days", "anchor": "enrollment"},
  "requires_absence_evidence": false, "is_safety_critical": true, "ambiguity_flags": []
}
```

### Decision labels

`met` · `not_met` · `unknown` · `not_applicable` · `conflicting_evidence`.

**Exclusion polarity is the most error-prone semantic** and is specified explicitly: for an
exclusion criterion, `met` means the patient *meets the exclusion* (likely ineligible) and `not_met`
means the exclusion is *cleared by explicit negative evidence*. Treating "no evidence of exclusion"
as `not_met` is forbidden — it must be `unknown`.

### Aggregation (deterministic)

```python
def aggregate(judgments):
    if any(j.type == "exclusion" and j.prediction == "met" for j in judgments):   return "likely_ineligible"
    if any(j.type == "inclusion" and j.prediction == "not_met" for j in judgments): return "likely_ineligible"
    if any(j.prediction in {"unknown", "conflicting_evidence"} for j in judgments): return "needs_review"
    return "potentially_eligible"
```

## Subtle correctness rules

- **Temporal:** every criterion has an anchor; the proof point uses the patient `snapshot_date` as
  the enrollment proxy. Evidence outside the window does not satisfy the criterion. A passing value
  outside the window → `unknown`, not `met`.
- **Evidence-support has two distinct checks** — keep them separate: (a) *quote fidelity* (the quote
  appears verbatim in the source) and (b) *derived-fact correctness* (e.g. `2.1 K/uL → 2100
  cells/uL` conversion is right). A substring check alone fails valid judgments under unit
  conversion.
- **Ambiguity is a first-class output.** "Adequate organ function" with no thresholds is flagged,
  not guessed — protocol ambiguity is operationally painful and a high-value surfaced signal.

## Validation phases (L0–L4)

Same ladder as the EDC wedge:

| Layer | Question | Target status for proof point |
|---|---|---|
| **L0** Unit / tool | Atomizer, unit conversion, temporal window, aggregation correct? | Build first, synthetic |
| **L1** Offline benchmark | Criterion-level accuracy on held-out labels? | Synthetic + n2c2 2018 |
| **L2** Retrospective replay | Useful as-of snapshot without leakage? | n2c2 2018 |
| **L3** Silent prospective | Real-world utility, zero operational impact? | Deferred to site data |
| **L4** Controlled rollout | Causal time savings with human approval? | Deferred to site data |

### Datasets

- **Synthetic (Dataset A)** — controlled patient profiles rendered to note-like text; gold labels
  fall out of the generator. **Treated as unit tests only**: the generator and the atomizer/judge
  share an ontology, so high scores here prove internal consistency, not capability.
- **n2c2 2018 Track 1 (Dataset B)** — real cohort-selection eligibility + longitudinal records;
  this carries the actual L1/L2 signal and is where conclusions are weighted.
- **Tiny human-labeled set (Dataset C)** — 30–50 patient-trial pairs for the time-savings study.

## Public data sourcing

The defining constraint: **trial eligibility is fully open; patient records with real clinical text
are mostly credentialed.** No single public dataset supplies real eligibility text *and* real
patients *and* gold match labels — so sources are composed, and each one happens to exercise a
different pipeline stage. (For an ML reader: ClinicalTrials.gov supplies *inputs* for the atomizer;
n2c2 supplies *labels* for the judge; they do not overlap, which lets the two hardest stages be
validated independently against the data each suits.)

| Source | Provides | Access | Exercises |
|---|---|---|---|
| ClinicalTrials.gov API v2 | Real eligibility text, conditions, phase, age/sex | **Open**, no auth | Ingestion + atomizer |
| Synthea | Synthetic patients: conditions, meds, labs, procedures | **Open** (Apache-2.0) | Normalizer + retrieval mechanics |
| PMC-Patients (PMC OA case reports) | Real free-text patient narratives | **Open** (CC subset) | Normalizer + judge on realistic text |
| MIMIC-IV demo | 100 real de-identified patients, structured | **Open** (ODbL) | Structured-fact extraction |
| n2c2 2018 Track 1 | Real records + gold met/not-met labels (13 criteria) | **Credentialed** (Harvard DBMI DUA) | Judge — real L1/L2 signal |
| MIMIC-IV full + Note | Real longitudinal records + discharge notes | **Credentialed** (PhysioNet DUA) | Retrieval at scale |

**Per-layer plan.** L0 uses ClinicalTrials.gov + Synthea (or authored profiles) — zero
credentialing, gold labels from controlled generation, so it is unit-test grade only. L1/L2 weight
conclusions on n2c2 2018; because its 13 criteria are pre-atomized and labeled, it wires as a
*judge-only* harness (criterion + record → predicted vs. gold), bypassing atomization. PMC-Patients
is the open stopgap for real-text negation/temporal behavior while the DUA is pending.

**Honesty caveats baked into the design.** Credentialing is the point, not friction: n2c2 and full
MIMIC are gated because they are real de-identified patient data under a DUA — plan around access
time and keep those corpora out of the repo (committed fixtures stay synthetic/open, per the
PHI-free fixture rule). Synthea text is templated, so it proves plumbing, not NLP robustness; never
let strong Synthea numbers stand in for real-text performance.

**Reproducibility (record-and-replay).** The live ClinicalTrials.gov API mutates as trials update,
so the implemented ingestion path *fetches once and records* raw payloads to a versioned JSONL
fixture; all tests and eval run against that frozen snapshot, mirroring the EDC retrospective-replay
discipline. See `tests/fixtures/prescreen/PROVENANCE.md`.

## Metrics

**Primary (task):** criterion-level accuracy, macro-F1, inclusion false-negative rate, evidence
support accuracy, overall-recommendation agreement.

**Primary (workflow):** human review-time reduction, packet correction rate, false positives per
true candidate.

**Abstention quality (the central product risk):** unknown rate *and* the fraction of unknowns a
reviewer rates actionable. Conservative-unknown raises recall safety but can relocate work rather
than remove it — an unknown-heavy packet can pass F1 yet fail the time-savings claim. Pre-register
unknown-actionability as a gate, not just an observation.

**Safety:** exclusion false-negative rate (clearing a disqualifying criterion), unsupported
evidence citations (must be zero), no-decision-language compliance.

## Ship gates

Do not move past L2 / into silent prospective unless: criterion-level F1 ≥ 0.80 and evidence
support accuracy ≥ 0.85 on Dataset B; exclusion false-negative rate ≤ 0.05; human review-time
reduction ≥ 30% on Dataset C with no catastrophic unsupported eligibility call; every judgment
carries complete provenance; and the agent remains draft-only with named human approval.

## Proposed implementation layout

Implemented (L0 public path) marked ✅; proposed marked ◻:

```
src/clinique/prescreen/
  schemas.py        ✅ Trial, AgeBound, PatientDocument, PatientCorpus
  ingestion.py      ✅ ClinicalTrials.gov v2 fetch/parse + JSONL fixture record/replay
  normalizer.py     ✅ Synthea CSV -> PatientCorpus (deterministic)
  atomizer.py       ◻ eligibility text -> atomic criteria (LLM, strict schema)
  retrieval.py      ◻ hybrid BM25 (rank-bm25, in-memory) + embeddings + structured + temporal filter
  judge.py          ◻ per-criterion LLM judge (constrained prompt, evidence-grounded)
  aggregator.py     ◻ deterministic overall recommendation
  evidence_gate.py  ◻ evidence-provenance hard gate (quote fidelity + derived-fact correctness)
  vocab.py          ◻ deterministic drug-class / synonym lookup (RxNorm/ATC subset)
  orchestrator.py   ◻ the typed graph; builds packet, runs gate, appends to ProvenanceLedger
tests/
  test_prescreen_ingestion.py ✅  test_prescreen_normalizer.py ✅
  test_prescreen_atomizer.py ◻ ... _temporal ◻ _aggregation ◻ _unit_conversion ◻ _evidence_gate ◻
tests/fixtures/prescreen/        ✅ trials.jsonl (real, recorded) + PROVENANCE.md
reports/prescreen/               ◻ eval metrics + error cases
```

CLI: `clinique prescreen ingest` (record JSONL fixture) and `prescreen show` (offline summary) are
implemented; `screen|atomize|eval` land with the corresponding stages, mirroring `edc-query`.

**Deferred until after the proof point** (premature for L0–L2): Postgres + pgvector, FastAPI
service, OpenSearch, Streamlit/Next.js UI. JSONL + in-memory retrieval + a CLI packet + offline
eval harness fully validate the north-star claim.

## Deferred / not proven

- Live EHR / FHIR / OMOP adapters (design schemas around these primitives; do not require
  connectivity). Patient docs map later to FHIR Patient/Condition/Observation/MedicationStatement
  and OMOP person/condition_occurrence/drug_exposure/measurement.
- n2c2 2018 ingestion and real L1/L2 numbers (synthetic fixtures only at scaffold time).
- Embedding retriever and learned hybrid ranker (start BM25 + structured + temporal).
- Human time-savings study (Dataset C, crossover design to remove learning-order bias).
- Calibrated confidence; LLM-driven synonym expansion (vocabulary-backed instead).

## Out of scope

Live EHR/EDC/CTMS/eTMF integration, patient outreach, consent automation, randomization, safety
reporting, regulatory submission automation, autonomous enrollment or final eligibility decisions,
and any access to unblinded data.

## References

- ClinicalTrials.gov API — trial protocol + eligibility ingestion. <https://clinicaltrials.gov/data-api/api>
- n2c2 2018 Track 1: Cohort Selection for Clinical Trials. <https://portal.dbmi.hms.harvard.edu/projects/n2c2-2018-t1/>
- OMOP CDM v5.4 (future patient-data mapping). <https://ohdsi.github.io/CommonDataModel/cdm54.html>
- FHIR MedicationStatement (future EHR mapping). <https://build.fhir.org/medicationstatement.html>
- FDA — Electronic Systems, Records, and Signatures in Clinical Investigations (2024). <https://www.fda.gov/regulatory-information/search-fda-guidance-documents/electronic-systems-electronic-records-and-electronic-signatures-clinical-investigations-questions>
- ICH E6(R3) Good Clinical Practice (2025). <https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106.pdf>
</content>

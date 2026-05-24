# RFC-0006: Validation & evaluation framework (full stack + roadmap)

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Cross-cutting (biostatistician now; recruitment/safety/monitoring on expansion) |
| Context of use | Defines how every Clinique agent is proven useful and safe before and after deployment |
| Risk tier | Foundation |
| Touches PHI | no (the framework itself; some future layers require PHI under DUA/IRB) |
| Touches unblinded data | no |
| Write path to system of record | none |

## 1. Summary

This RFC defines the validation stack for **all** Clinique agents, present and future, and
maps each layer to what it can prove. The organizing principle is that **accuracy is not
usefulness**: the question is not "is the model accurate?" but *"does this agent improve a
regulated clinical-trial workflow without increasing participant, data-integrity, blinding,
privacy, or compliance risk?"* Two label families answer that: **task labels** (was the output
correct?) and **workflow/outcome labels** (did it save time, raise recall, cut errors, speed
lock, reduce findings?). The second family is what proves the agent is worth shipping.

Because today's suite (RFC-0001–0005) is the **biostatistician persona** — read-only, no PHI,
no unblinded data, no patient-facing actions — the heavy upper layers (silent prospective
trials, cluster RCTs) are **future state**, gated to when Clinique expands to recruitment,
safety, and monitoring agents. §4 makes that split explicit so we neither over-validate the
current scope nor under-plan the expansion.

## 2. Motivation

A model can be "accurate" and useless:

| Behavior | Accuracy may look fine | Useful? |
|---|---|---|
| Flags 500 candidates/week | maybe | No — coordinators can't review them |
| Finds eligible patients after they enrolled elsewhere | maybe | No — too late |
| Flags drift QC would have caught anyway | maybe | No — no incremental value |
| Right answer with no cited evidence | maybe | No — not auditable/trusted |
| Saves 20 min/patient but misses a safety exclusion | maybe | No — unsafe |

So north-star metrics are **operational**, not statistical. For the current biostatistician
suite that means: *errors caught earlier (before QC / before an FDA reviewer), statistician and
programmer hours saved, fewer reviewer/agency findings, fewer avoidable amendments, faster
database lock — with no increase in data-integrity, blinding, or compliance risk.*

## 3. The five-layer validation stack

| Layer | Question it answers | Proves |
|---|---|---|
| **L0 Unit / tool validation** | Do the deterministic pieces work? | Correctness of parsers, mappers, engines, guards |
| **L1 Offline benchmark** | Can the agent do the task on held-out data? | Task accuracy with calibrated abstention |
| **L2 Retrospective replay** | Would it have helped, *as of the time*, without future leakage? | First evidence of usefulness |
| **L3 Silent prospective** | How does it behave in production, affecting nothing? | Real-world utility + false-positive burden, minimal risk |
| **L4 Live controlled deployment** | Does it causally improve outcomes? | Causal proof (A/B, stepped-wedge, cluster RCT) |

L0 is traditional software QA: golden fixtures, property tests, regression, edge cases, and
audit logs — directly supported by RFC-0000's provenance ledger and the ICH E6(R3) expectation
that computerized systems be fit for purpose with secure, time-stamped audit trails.

## 4. Scope mapping — what applies NOW vs. on expansion

The biostatistician agents are advisory, statistician-facing tools, not patient-facing
systems. Their validation centre of gravity is **L0–L2**; L3 is light (a "shadow" mode over a
statistician's normal workflow) and L4 is an *operational* A/B on statistician productivity, not
a participant-affecting RCT. The patient-facing future personas invert this.

| Layer | Biostat suite (0001–0005) — **now** | Recruitment / safety / monitoring — **future** |
|---|---|---|
| L0 | **Required** (heavy) | Required |
| L1 | **Required** (seeded-defect, reproduction suites) | Required (recall/PPV/F1, evidence-span) |
| L2 | **Recommended** (replay over historical SAP/EDC/lock history) | **Critical** (time-to-impact with timestamps) |
| L3 | Light shadow mode beside a statistician | **Critical** (silent trial, weeks, no workflow change) |
| L4 | Operational A/B on statistician/programmer productivity | **Required** (stepped-wedge / cluster RCT; SPIRIT-AI/CONSORT-AI reporting) |

**Reporting frameworks.** SPIRIT-AI / CONSORT-AI apply when an agent is part of a clinical-trial
*intervention* — i.e., the future patient-facing personas at L4. The biostat suite does not
trigger them; its L4 is internal operational evaluation, reported as such.

## 5. Per-capability validation matrix — current suite

Each row's acceptance gate is the *useful* metric, not raw accuracy.

| RFC | L0 unit target | L1 offline gate | L2 replay question | Ship gate (usefulness) |
|---|---|---|---|---|
| **0001** estimand checker | parsers/extractors on golden artifacts; span anchoring | seeded-defect **recall ≥0.99** (deterministic rules); semantic-diff precision floor; false-positive rate on clean bundles | Would it have caught drift that actually reached QC / a reviewer / an amendment? | Catches real drift **before** QC/reviewer; FP rate low enough that statisticians keep using it |
| **0002** programming copilot | macro-call correctness; **side-lock invariant** (hard) | regression suite reproduces known-correct TLFs on synthetic fixtures; defect-injection catch rate | Would adversarial-test mode have caught historical QC discrepancies? | Reduces rework / QC discrepancies with **zero** independence violations |
| **0003** sample-size orchestrator | engine wrappers; **numeric-provenance linter** (zero violations) | reproduces textbook & precedent cases exactly via engines; method-selection accuracy vs labels | Would assumptions/method have matched the SAP that was actually filed? | Cuts time-to-power-analysis; no LLM-born numbers; SAP cross-check catches real mismatches |
| **0004** submission docs / CDISC | template fills; traceability resolver | conformance classification accuracy (confusion by class); completeness vs required-section lists; **no-fabrication** test | Would it have classified historical validator reports as the programmer did? | Cuts reviewer-guide/CSR drafting time; never mislabels a true error as "expected" |
| **0005** dry-run harness | synthetic generator CDISC-conformance; **data-wall build invariant** | defect-injection detection rate per check class; shell coverage | Would it have surfaced post-lock dry-run defects *before* lock? | Moves defect discovery earlier than the real dry run; provably touches no real/unblinded data |

The four structural invariants from the suite are validated as **hard pass/fail**, not metrics:
0001 read-only, 0002 side-lock, 0003 numeric-provenance, 0005 data-wall. Any violation is a
build-breaking defect.

## 6. Future-persona validation (on expansion beyond biostatistician)

When Clinique adds patient-facing agents, the upper layers become mandatory. Captured here so
the roadmap is honest, not built now.

### 6.1 Usefulness metrics by future agent

- **Recruitment / prescreening** — eligible found/week ↑, time-from-EHR-eligibility-to-awareness ↓,
  screen-failure rate ↓, coordinator review-time/candidate ↓, recall of truly eligible high,
  false-positive burden controlled, candidate-pool diversity not worse, enrollment rate ↑,
  eligibility-deviation rate **not** increased.
- **Safety / AE / SAE pre-review** — SAE sensitivity **very high**, serious-event false-negative
  rate **extremely low**, time-to-escalation ↓, MedDRA agreement high; expectedness/relatedness
  **human-reviewed only**; draft-and-triage only, never final reporting.
- **Monitoring / RBQM** — high-risk-site detection earlier than current monitoring, deviation /
  missed-visit detection high, CRA workload ↓, audit findings ↓, alert fatigue controlled.

### 6.2 Study designs (future L4)

A/B (low-risk ops like query drafting) · stepped-wedge (site rollout) · cluster RCT (site/team
randomization to avoid contamination) · before/after with matched controls (weaker) · pragmatic
trial (mature agent) · human-factors study (workload, trust, alert fatigue).

## 7. Labeling protocol

Label at **criterion / claim level**, not document level, with **two independent annotators**,
**mandatory evidence spans** for every positive/negative judgment, clinician/PI adjudication of
disagreements, and **tracked inter-annotator agreement** (a label without agreement stats is
weaker than it looks — RFC-0000 §9 requires reporting it).

Process: (1) write a task-specific annotation manual; (2) split into atomic units; (3) dual
independent labeling; (4) require evidence spans; (5) adjudicate disagreements; (6) track IAA;
(7) freeze a gold set; (8) keep a separate **challenge set** for future versions.

For the **biostat suite**, the "labels" are mostly seeded defects and known-correct outputs, so
annotation is cheaper and largely synthesizable — but the IAA discipline still applies to the
LLM semantic-diff judgments in 0001 and the conformance classifications in 0004.

Recruitment criterion-label schema (future), retained for the expansion plan:

```json
{
  "case_id": "P001__NCT123",
  "patient_snapshot_date": "2026-03-01",
  "trial_version_date": "2026-02-01",
  "criteria": [
    {"criterion_id": "I-03", "criterion_text": "ANC >= 1500/uL within 14 days",
     "label": "met", "evidence_spans": [{"source_type": "lab", "date": "2026-02-24", "field": "ANC", "value": "2200/uL"}],
     "certainty": "definite"}
  ],
  "overall_decision": "needs_human_review",
  "adjudicator_1": "CRC", "adjudicator_2": "oncology_fellow", "final_adjudicator": "PI"
}
```

## 8. Data & label sources, ranked

Note the **source mismatch**: the public EHR/recruitment corpora below are for the *future*
personas. The biostat suite is fed by **protocols, SAPs, ADaM specs, Define-XML, TLF shells,
EDC query logs, validator reports, and amendment/lock history** — largely internal or
document-level, not patient-level EHR.

**Tier 1 — own operational data (the moat).** Biostat: SAP/protocol versions, amendment history,
EDC query logs, database-lock issue logs, QC discrepancy logs, validator reports. Future:
screening logs, screen-failure reasons, CTMS timelines, monitoring reports, CAPA, eTMF/audit
findings, safety narratives + MedDRA coding.

**Tier 2 — public benchmarks (prototype only, future personas).** TREC Clinical Trials Track
(patient-to-trial retrieval), n2c2 2018 Track 1 (cohort selection from notes), MIMIC-IV
(deidentified EHR), Synthea/SyntheticMass (synthetic FHIR/OMOP fixtures), ClinicalTrials.gov /
AACT (trial metadata/eligibility), TrialGPT (matching baselines; 87.3% criterion-level accuracy
and 42.6% screening-time reduction reported in its user study).

**Tier 3 — controlled-access participant data (downstream stats/safety).** Vivli, YODA, Project
Data Sphere — useful for endpoint/safety/synthetic-control work; weak for recruitment because
they lack pre-enrollment screening context.

**Caution carried forward:** the cited JMIR 2025 study found a **32.7% hallucination rate** in
LLM eligibility-criteria→OMOP-SQL conversion. The mandated pattern for any generative query/code
step (and the spirit of RFC-0000 §7): *LLM proposes → deterministic validator → synthetic
fixture test → terminology check → human review → real-data execution.*

## 9. The MVP usefulness study (recruitment, future) — kept as the expansion template

Four phases, retained so expansion is plan-not-improvisation:

- **Phase A Offline** — 200–500 historical patient snapshots × 5–20 trials, criterion-level +
  evidence-span labels. Pass: no catastrophic false negatives on hard exclusion/safety criteria;
  high recall for potentially eligible; FP low enough for coordinator workload; evidence correct
  enough to trust.
- **Phase B Retrospective replay** — strictly time-gated inputs (no future leakage). Measures:
  eligible found earlier, median days earlier, additional true candidates, false alerts per true
  candidate, review-minutes saved, screen-failure-rate delta.
- **Phase C Silent prospective** — 4–12 weeks, no workflow change; agent recommendations logged
  hidden. Measures misses (human-only, agent-only), FP workload, latency, evidence quality,
  coordinator feedback. (75 silent-AI evaluations 2015–2025 per the cited 2026 scoping review —
  this is the established minimal-risk bridge.)
- **Phase D Controlled rollout** — randomize by site/coordinator/disease/time block. Primary:
  time-to-identify, eligible-candidates/trial-month, coordinator-min/candidate, screen-failure
  rate, enrollment rate, eligibility-deviation rate. Safety endpoints: wrong recommendation
  causing inappropriate contact, missed exclusion, privacy incident, blinding breach, unsupported
  citation, unauthorized tool action.

## 10. Ship gates

**Biostat suite (now).** Do not promote a capability past shadow mode unless: (1) it catches
real defects/drift **before** the existing QC or reviewer step; (2) it does **not** increase
data-integrity, blinding, or compliance risk (structural invariants pass); (3) every output is
auditable to source spans / tool calls; (4) false positives are low enough that the statistician
keeps using it; (5) it can abstain when evidence is insufficient.

**Future patient-facing agents.** Do not ship unless: finds additional true eligible candidates
or finds them earlier; does not increase eligibility deviations; evidence citations correct
enough for fast human review; false positives don't swamp coordinators; every recommendation
auditable; system can abstain.

## 11. Build / validation order

1. **Synthetic harness** (Synthea/OMOP for future; synthetic artifacts for biostat) — validate
   parsing, extraction, queries, code execution, audit logs (L0).
2. **Benchmark harness** — biostat: seeded-defect + reproduction suites; future: TREC/n2c2/TrialGPT (L1).
3. **Human-labeled internal retrospective set** — biostat: historical SAP/EDC/lock defects;
   future: 200–500 real cases, criterion-level labels.
4. **Retrospective replay** — preserve timestamps, no leakage (L2).
5. **Silent / shadow** — beside humans; measure workload, misses, false positives (L3).
6. **Limited live rollout** — draft-only, human approval required.
7. **Controlled deployment study** — operational A/B (biostat) or stepped-wedge / cluster RCT
   (future patient-facing) (L4).

## 12. Drawbacks & open questions

- The framework risks over-validating the biostat suite if L3/L4 patient-trial machinery is
  applied where an operational A/B suffices — §4 exists to prevent that; keep it enforced.
- Internal Tier-1 labels are the moat but gated by IRB/DUA/privacy — sequencing access is a
  program risk for the future personas, not the biostat suite.
- Open: for 0001 semantic-diff and 0004 conformance classification, what IAA threshold qualifies
  a gold set as trustworthy?
- Open: does biostat L4 (operational A/B) need any external reporting standard, or is internal
  documentation sufficient given it's not a participant-facing intervention?

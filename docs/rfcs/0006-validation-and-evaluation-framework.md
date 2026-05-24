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

Concrete L0 examples:

| Component | Validation target |
|---|---|
| Eligibility parser | Every criterion decomposes into atomic computable predicates |
| OMOP / FHIR query generator | Query returns expected cohort on synthetic fixtures |
| Visit-window checker | Correctly flags out-of-window visits and missing required assessments |
| AE / SAE detector | Recognizes reportable events and seriousness triggers |
| CDISC mapper | Produces correct SDTM / ADaM variable and domain mappings |
| Blinding guard | Cannot access treatment assignment unless explicitly authorized |

L1 metrics are task-specific. Recruitment benchmarks emphasize sensitivity, specificity, PPV,
NPV, criterion-level F1, evidence-span accuracy, abstention quality, and ranking recall@K /
NDCG. Protocol, data, safety, and statistics agents need labels for missing required items,
contradictions, true-vs-false discrepancies, AE/SAE classification, MedDRA coding, seriousness /
expectedness flags, sample-size assumptions, and estimand/SAP consistency.

L2 replay labels must be timestamped to prevent future leakage:

```json
{
  "case_id": "...",
  "decision_date": "2025-05-01",
  "ground_truth": "eligible",
  "human_found_date": "2025-05-20",
  "agent_found_date": "2025-05-05",
  "evidence_available_at_agent_time": true
}
```

L3 silent prospective labels add operational burden and safety risk: hidden agent
recommendation, usual human action, later adjudicated truth, time delta, false-positive burden
per coordinator/site/week, and any recommendation that would have been harmful, noncompliant,
privacy-violating, or blinding-breaking.

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

When Clinique expands beyond the biostatistician suite, the first future wedge should be the
workflow with the strongest available labels. If historical EDC query logs and resolution
history are available, **data-management / EDC-query** should precede recruitment: the labels
already exist, the workflow is operational rather than patient-contacting, and draft-only
human approval gives a lower-risk path to proving usefulness. Patient-facing agents still
require the upper layers before live use.

### 6.1 Usefulness metrics by future agent

- **Recruitment / prescreening** — eligible found/week ↑, time-from-EHR-eligibility-to-awareness ↓,
  screen-failure rate ↓, coordinator review-time/candidate ↓, recall of truly eligible high,
  false-positive burden controlled, candidate-pool diversity not worse, enrollment rate ↑,
  eligibility-deviation rate **not** increased.
- **Protocol design / protocol review** — missing protocol elements detected with high recall,
  internal contradictions detected with high precision, time to first draft ↓, avoidable
  amendments ↓, IRB/regulatory review cycles ↓, ambiguous eligibility criteria ↓, protocol
  deviations caused by ambiguity ↓.
- **Eligibility-to-SQL / feasibility** — query semantic correctness high, cohort count agreement
  with expert query high, false inclusion/exclusion low, hallucinated concepts/tables near zero,
  time to feasibility estimate ↓, site feasibility prediction accuracy ↑.
- **Data-management / EDC-query** — true discrepancy detection high, false query rate low, query
  resolution time ↓, open queries at lock ↓, manual data-manager time ↓, duplicate queries ↓,
  generated query text acceptable to a human reviewer.
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

Other minimum future-agent label payloads:

```json
{
  "protocol_review": {
    "protocol_section": "Eligibility",
    "issue_type": "ambiguity | contradiction | missing_item | operational_burden",
    "severity": "minor | major | critical",
    "gold_comment": "...",
    "source": "expert review | IRB comment | amendment history"
  },
  "eligibility_sql": {
    "criterion": "eGFR >= 45 mL/min/1.73m2 within 30 days",
    "logical_form": "...",
    "omop_concepts": ["..."],
    "sql_gold": "...",
    "expected_patient_ids_on_fixture": ["..."],
    "expert_count_on_real_data": 421
  },
  "edc_query": {
    "subject_id": "...",
    "form": "ConMeds",
    "field": "start_date",
    "gold_query_needed": true,
    "query_category": "missing | inconsistent | impossible | source_mismatch",
    "human_resolution": "corrected | confirmed | no_query_needed",
    "time_to_resolution_hours": 36
  }
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
findings, safety narratives + MedDRA coding, EDC query resolution history, monitoring visit
reports, source-data verification findings, protocol amendments, and IRB/IEC comments.

**Tier 2 — public benchmarks (prototype only, future personas).** TREC Clinical Trials Track
(patient-to-trial retrieval), n2c2 2018 Track 1 (cohort selection from notes), MIMIC-IV
(deidentified EHR), Synthea/SyntheticMass (synthetic FHIR/OMOP fixtures), ClinicalTrials.gov /
AACT (trial metadata/eligibility), TrialGPT (matching baselines; 87.3% criterion-level accuracy
and 42.6% screening-time reduction reported in its user study). AACT is especially useful for
trial metadata and eligibility text, but it is not enough for workflow usefulness without
screening, timeline, and outcome labels.

**Tier 3 — controlled-access participant data (downstream stats/safety).** Vivli, YODA, Project
Data Sphere — useful for endpoint/safety/synthetic-control work; weak for recruitment because
they lack pre-enrollment screening context.

**Caution carried forward:** the cited JMIR 2025 study found a **32.7% hallucination rate** in
LLM eligibility-criteria→OMOP-SQL conversion. The mandated pattern for any generative query/code
step (and the spirit of RFC-0000 §7): *LLM proposes → deterministic validator → synthetic
fixture test → terminology check → human review → real-data execution.*

## 9. First future MVP — data-management / EDC-query

Prefer this as the first non-biostat MVP when query logs, resolution history, EDC snapshots,
and data-manager review capacity are available. It has unusually cheap labels: historical
queries show whether a discrepancy was real, how it was resolved, and how long resolution took.

- **Phase A Offline** — replay historical EDC snapshots against known query logs. Measure true
  discrepancy detection, false query rate, duplicate query rate, query-category accuracy, and
  draft-query text acceptability.
- **Phase B Retrospective replay** — preserve snapshot timestamps. Measure whether the agent
  would have found real discrepancies before manual review, reduced open-query time, or surfaced
  database-lock issues earlier without increasing false queries.
- **Phase C Silent prospective** — run hidden beside the data-management workflow for 4-12 weeks.
  Compare silent agent suggestions with actual queries, no-query decisions, resolution outcomes,
  and reviewer burden.
- **Phase D Controlled rollout** — start draft-only, human approval required. Randomize by study,
  site, form family, or data-manager queue. Primary endpoints: manual minutes/query, true
  discrepancies found, false query rate, resolution time, open queries at lock, and data-manager
  acceptance rate.

Recruitment remains the first patient-facing expansion template: 200-500 historical patient
snapshots across 5-20 trials, criterion-level and evidence-span labels, strict timestamped replay,
4-12 week silent prospective evaluation, then site/coordinator/disease/time-block rollout only if
false positives, missed exclusions, privacy risk, and eligibility-deviation risk stay controlled.

## 10. Ship gates

**Biostat suite (now).** Do not promote a capability past shadow mode unless: (1) it catches
real defects/drift **before** the existing QC or reviewer step; (2) it does **not** increase
data-integrity, blinding, or compliance risk (structural invariants pass); (3) every output is
auditable to source spans / tool calls; (4) false positives are low enough that the statistician
keeps using it; (5) it can abstain when evidence is insufficient.

**Future EDC/data-management agents.** Do not ship unless: true discrepancies are found earlier
or with less manual effort; false queries and duplicate queries stay below the workflow's
tolerance; query text remains human-reviewable; every recommendation is auditable; no write-back
to EDC occurs without named human approval.

**Future patient-facing agents.** Do not ship unless: finds additional true eligible candidates
or finds them earlier; does not increase eligibility deviations; evidence citations correct
enough for fast human review; false positives don't swamp coordinators; every recommendation
auditable; system can abstain.

## 11. Build / validation order

1. **Synthetic harness** (Synthea/OMOP for future; synthetic artifacts for biostat) — validate
   parsing, extraction, queries, code execution, audit logs (L0).
2. **Benchmark harness** — biostat: seeded-defect + reproduction suites; future: TREC/n2c2/TrialGPT (L1).
3. **Human-labeled internal retrospective set** — biostat: historical SAP/EDC/lock defects;
   first future MVP: EDC snapshots + query logs + resolution outcomes; later patient-facing:
   200–500 real cases, criterion-level labels.
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

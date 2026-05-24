# Clinical trials for ML researchers

**Audience:** ML researchers and MLsys engineers new to regulated clinical trials.

This doc builds the domain mental model in ML language. It does not describe Clinique
implementation — see [clinique-for-ml.md](clinique-for-ml.md) for repo mapping and commands.

---

## 1. The simplest mental model

A **clinical trial** is a controlled experiment on humans designed to answer:

> Does this intervention work, is it safe, for whom, at what dose, and compared to what?

In ML terms, a clinical trial is like a **high-stakes, regulated data-generation pipeline**.

| ML concept | Clinical-trial analogue |
|---|---|
| Dataset | Participants enrolled in the trial |
| Features | Baseline demographics, labs, diagnosis, biomarkers, prior treatment, etc. |
| Labels | Clinical outcomes: response, survival, adverse events, lab changes, symptoms |
| Train/test leakage | Using future or post-randomization info incorrectly |
| Objective function | Primary endpoint |
| Secondary metrics | Secondary endpoints |
| Data collection protocol | Trial protocol and schedule of assessments |
| Ground truth | Adjudicated endpoint, investigator assessment, lab result, imaging read |
| Bias control | Randomization, blinding, control arm, inclusion/exclusion criteria |
| Monitoring | Safety monitoring, data quality checks, protocol-deviation tracking |
| Governance | IRB/ethics review, informed consent, GCP, audit trail |

The important difference: in ML, bad labels can ruin your model. In clinical trials, bad data can
harm people, invalidate evidence, or fail regulatory review.

Clinical trials are governed by Good Clinical Practice (GCP), which focuses on protecting
participants and ensuring reliable trial data. [ICH E6(R3)](https://database.ich.org/sites/default/files/ICH_E6%28R3%29_Step4_FinalGuideline_2025_0106.pdf)
emphasizes participant rights, safety, well-being, data reliability, quality-by-design, and
risk-based oversight.

---

## 2. What a clinical trial is trying to prove

A trial is usually trying to estimate something like:

```text
Treatment effect = outcome under intervention - outcome under comparator
```

Example:

```text
Drug A improves progression-free survival compared with standard chemotherapy.
```

That sounds simple, but every term needs to be nailed down:

| Question | Clinical-trial version |
|---|---|
| Who is included? | Eligibility criteria |
| What is the intervention? | Investigational product, dose, schedule, route |
| Compared to what? | Placebo, standard of care, active comparator, historical control |
| What is measured? | Primary and secondary endpoints |
| When is it measured? | Schedule of assessments |
| Who decides the outcome? | Investigator, central lab, blinded adjudication committee |
| What happens if data is missing? | Statistical Analysis Plan |
| How are safety issues handled? | AE/SAE reporting, medical monitoring, DSMB/DMC |

The **protocol** is the master spec. It is like the product requirements doc, experiment config,
data-generation contract, and compliance plan all in one.

---

## 3. The phases: Phase 1, 2, 3, 4

Clinical drug trials usually move from small early safety studies to large confirmatory studies.
The [FDA](https://www.fda.gov/patients/drug-development-process/step-3-clinical-research) describes
clinical trials as typically progressing from early Phase 1 studies to larger Phase 3 studies; NIH
gives common participant ranges for each phase.

| Phase | Main question | Typical size | ML analogy |
|---|---|---:|---|
| Phase 1 | Is it safe? What dose can humans tolerate? | Often ~20–100 (NIH: 20–80 for Phase I) | Initial system validation / safety smoke test |
| Phase 2 | Does it show signs of efficacy? What dose/regimen should move forward? | Often ~100–300 | Model selection / signal detection |
| Phase 3 | Does it work compared with standard care or placebo at scale? | Hundreds to thousands (NIH: 1,000–3,000 for Phase III) | Final held-out confirmatory evaluation |
| Phase 4 | What happens after approval in broader real-world use? | Post-market population | Post-deployment monitoring |

Phase 1 is not mainly about proving the treatment works. It is usually about safety,
tolerability, pharmacokinetics, pharmacodynamics, and dose escalation.

Phase 2 is where you start asking, "Is there enough efficacy signal to justify a big expensive trial?"

Phase 3 is the big confirmatory trial that often supports regulatory approval.

Phase 4 happens after approval and looks at longer-term safety, rare events, effectiveness in
broader populations, and real-world use.

---

## 4. The main entities in the data model

At the highest level, a clinical trial data model looks like this:

```text
Study / Trial
  ├── Protocol
  ├── Sites
  ├── Participants
  │     ├── Screening data
  │     ├── Baseline data
  │     ├── Randomization / treatment arm
  │     ├── Visits
  │     │     ├── Labs
  │     │     ├── Vitals
  │     │     ├── Imaging
  │     │     ├── Questionnaires
  │     │     ├── Procedures
  │     │     └── Drug administration
  │     ├── Adverse events
  │     ├── Concomitant medications
  │     └── Outcomes / endpoints
  ├── Data queries
  ├── Protocol deviations
  ├── Safety reports
  └── Analysis datasets
```

Think of it like a highly structured event log.

### Core tables/entities

| Entity | Meaning |
|---|---|
| `Study` | The trial itself |
| `Protocol` | The rules of the trial |
| `Site` | Hospital/clinic running the trial |
| `Investigator` | Doctor responsible at a site |
| `Participant` / `Subject` | Person enrolled or screened |
| `EligibilityCriteria` | Inclusion/exclusion rules |
| `Visit` | Scheduled contact point: screening, baseline, week 4, week 8, etc. |
| `Assessment` | A measurement at a visit |
| `LabResult` | Bloodwork, chemistry, biomarkers |
| `Medication` | Study drug or background/concomitant meds |
| `AdverseEvent` | Any unfavorable medical event during the trial |
| `SeriousAdverseEvent` | Death, hospitalization, life-threatening event, etc. |
| `Endpoint` | Outcome used to judge success |
| `Randomization` | Assignment to treatment/control |
| `DataQuery` | A question about missing/inconsistent data |
| `ProtocolDeviation` | Something happened outside the protocol |
| `AnalysisDataset` | Cleaned dataset used for final stats |

For regulatory submissions, clinical trial data is often transformed into CDISC standards.
[CDISC SDTM](https://www.cdisc.org/standards/foundational/sdtm) is a required standard for FDA and
PMDA submissions; ADaM supports traceability between analysis results, analysis data, and
tabulation data.

---

## 5. What happens operationally

A simplified trial lifecycle:

```text
1. Design the trial
2. Write protocol
3. Get ethics/regulatory approval
4. Select sites
5. Train sites
6. Recruit/screen patients
7. Enroll eligible patients
8. Randomize if applicable
9. Treat/follow participants
10. Collect data at visits
11. Monitor safety and data quality
12. Clean/lock database
13. Analyze data
14. Report results
15. Submit to regulator / publish
```

A trial is not just "run model, get answer." It is a long-running operational system with many
humans and many records.

---

## 6. Key artifacts you'll hear about

| Artifact | What it is |
|---|---|
| Protocol | Full trial spec |
| Informed Consent Form | What participants read/sign before joining |
| Investigator's Brochure | Background evidence about investigational product |
| Case Report Form / eCRF | Structured forms used to collect trial data |
| Statistical Analysis Plan | Exact statistical methods before final analysis |
| Data Management Plan | How data is collected, queried, cleaned, locked |
| Monitoring Plan | How sites and data quality are monitored |
| Safety Management Plan | How adverse events are detected and reported |
| Clinical Study Report | Final detailed report of the trial |
| eTMF | Electronic Trial Master File: the inspection-ready document archive |

As an ML person, you can think of these as the combination of:

```text
experiment config
data schema
labeling guide
quality-control plan
audit log
model card / final report
```

---

## 7. Eligibility criteria are the first great ML/agent wedge

Every trial defines who can join.

Example:

```text
Inclusion:
- Age ≥ 18
- Histologically confirmed metastatic NSCLC
- ECOG performance status 0–1
- ANC ≥ 1500/uL
- Platelets ≥ 100,000/uL

Exclusion:
- Prior anti-PD-1 therapy
- Active uncontrolled infection
- Untreated brain metastases
- Pregnancy
```

This is where agents can help early, because the task is naturally structured:

```text
Trial criteria + patient record → criterion-level judgment
```

For each criterion, the agent can output:

```text
met / not met / unknown
evidence
rationale
missing information
human-review flag
```

That is the proof-of-concept Clinique is building toward in trial prescreening.

---

## 8. The difference between inclusion and exclusion criteria

This is subtle but important.

### Inclusion criterion

Example:

```text
Age ≥ 18
```

The patient must satisfy it.

| Evidence | Judgment |
|---|---|
| Patient is 62 | Met |
| Patient is 16 | Not met |
| Age missing | Unknown |

### Exclusion criterion

Example:

```text
No prior anti-PD-1 therapy
```

The patient must **not** have the disqualifying condition.

| Evidence | Judgment |
|---|---|
| Prior pembrolizumab documented | Exclusion met → likely ineligible |
| Note explicitly says no prior immunotherapy | Exclusion not met |
| Therapy history missing | Unknown |

For agents, this matters a lot. You do **not** want the model to say:

```text
I did not find evidence of prior anti-PD-1 therapy, so the patient is eligible.
```

The safer output is:

```text
Prior anti-PD-1 therapy is unknown; human should verify.
```

That conservative behavior is actually a feature, not a bug.

---

## 9. Endpoints are the labels

The **endpoint** is the outcome the trial is designed to measure.

Examples:

| Endpoint | Meaning |
|---|---|
| Overall survival | Time until death from any cause |
| Progression-free survival | Time until cancer progression or death |
| Objective response rate | Fraction of patients whose tumors shrink enough |
| HbA1c change | Diabetes blood-sugar control |
| Blood pressure reduction | Cardiovascular endpoint |
| Adverse-event rate | Safety endpoint |
| Patient-reported outcome | Symptom or quality-of-life measure |

In ML terms:

```text
endpoint = label definition
```

But unlike many ML labels, clinical endpoints often need:

```text
precise time window
measurement rules
adjudication
handling of missingness
blinding
statistical plan
```

A sloppy endpoint definition is like a bad label-generation pipeline.

---

## 10. Randomization and blinding

Randomization means assigning participants to treatment arms by chance.

Example:

```text
Arm A: new drug
Arm B: placebo or standard of care
```

Why randomize? To reduce confounding.

Blinding means hiding treatment assignment from participants, investigators, outcome assessors, or
analysts.

In ML terms:

| Trial concept | ML analogy |
|---|---|
| Randomization | Preventing selection bias |
| Blinding | Preventing labeler/evaluator bias |
| Allocation concealment | Preventing data leakage |
| Predefined SAP | Preventing p-hacking / metric shopping |

This is one reason clinical trials are stricter than normal observational ML studies.

---

## 11. Safety data is its own universe

During a trial, you track **adverse events**.

An adverse event is any unfavorable medical occurrence during the trial, whether or not it is
caused by the treatment.

A **serious adverse event** is a special category, such as death, life-threatening event,
hospitalization, significant disability, or congenital anomaly. These usually require urgent
reporting and medical oversight.

For an agent, safety automation should be conservative:

```text
Good:
  "This note may describe hospitalization; safety reviewer should review."

Bad:
  "This is definitely unrelated and does not need reporting."
```

The right early use is **triage and summarization**, not autonomous safety decisions.

---

## 12. Where foundation-model agents can help

At your stage, think in terms of **assistive agents**, not autonomous trial-running agents.

### Good early targets

| Agent task | Why it is good |
|---|---|
| Eligibility parsing | Trial criteria are messy text |
| Patient prescreening | High manual burden |
| Evidence extraction | Requires reading charts/notes |
| Missing-data detection | Structured, auditable |
| Protocol inconsistency checks | Natural language + rules |
| Data-query drafting | Human still approves |
| Safety triage | Can surface possible events |
| Visit-window checks | Deterministic + explainable |
| Trial document summarization | Low-risk if reviewed |

### Bad early targets

| Agent task | Why risky |
|---|---|
| Final eligibility decision | Medical/regulatory responsibility |
| Patient outreach without human approval | Ethical/privacy risk |
| Autonomous consent | Not appropriate for early system |
| Randomization outside approved system | Critical compliance risk |
| Final SAE reporting decision | Safety-critical |
| Changing protocol/SAP | Governance-heavy |
| Locking database | Regulatory-grade control needed |

The safest principle:

```text
Agents draft, flag, retrieve, summarize, and recommend.
Humans approve, decide, enroll, report, and sign off.
```

---

## 13. How to think about the data model for your proof point

For your early project, you only need a tiny subset of the full clinical-trial data model.

### Minimum useful schema

```text
Trial
  trial_id
  title
  eligibility_text

Criterion
  criterion_id
  trial_id
  type: inclusion/exclusion
  text
  normalized_form
  domain: lab/diagnosis/medication/etc.

Patient
  patient_id
  snapshot_date

PatientDocument
  doc_id
  patient_id
  date
  type
  text

Evidence
  criterion_id
  doc_id
  quote
  normalized_fact

Judgment
  patient_id
  trial_id
  criterion_id
  prediction: met/not_met/unknown
  evidence
  rationale
```

That is enough to build:

```text
trial criteria + patient documents → evidence-backed prescreening packet
```

You do **not** need to understand the entire clinical operations stack to build a convincing first
demo.

---

## 14. One concrete example

Imagine the trial has this criterion:

```text
ANC ≥ 1500/uL within 14 days before enrollment.
```

Patient document:

```text
CBC, 2026-02-20:
ANC 2.1 K/uL; platelets 210 K/uL; hemoglobin 11.2 g/dL.
```

The agent should output:

```text
Criterion:
  ANC ≥ 1500/uL within 14 days

Decision:
  Met

Evidence:
  CBC on 2026-02-20: "ANC 2.1 K/uL"

Reason:
  2.1 K/uL = 2100/uL, which is greater than 1500/uL.
```

Now imagine this criterion:

```text
No prior anti-PD-1 or anti-PD-L1 therapy.
```

Patient documents mention chemotherapy but no immunotherapy history.

The agent should output:

```text
Decision:
  Unknown

Reason:
  No conclusive prior immunotherapy history was found.

Next action:
  Human reviewer should verify prior systemic therapy.
```

That is the kind of behavior you want.

---

## 15. What you should learn first

For ML/engineering purposes, learn clinical trials in this order:

```text
1. Trial phases
2. Protocol structure
3. Eligibility criteria
4. Visits and schedule of assessments
5. Endpoints
6. Adverse events / safety
7. Randomization and blinding
8. EDC / eCRF data capture
9. Data cleaning and queries
10. CDISC SDTM / ADaM datasets
11. Statistical Analysis Plan
12. Regulatory submission / clinical study report
```

You do not need to master everything before building. For your proof point, focus on:

```text
eligibility criteria
patient records
evidence extraction
criterion-level judgment
human review workflow
```

That is the cleanest bridge between ML and clinical trials.

---

## 16. The one-sentence summary

A clinical trial is a regulated experiment that turns human participant journeys into trustworthy
evidence; your best early agentic proof point is to help humans map messy patient records against
messy eligibility criteria and produce an auditable prescreening packet.

---

## Next

Continue to [clinique-for-ml.md](clinique-for-ml.md) for how this repo maps those concepts to
code, tests, and validation harnesses.

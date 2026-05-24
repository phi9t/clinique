# RFC-0001: Estimand-spine consistency checker

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Biostatistician |
| Context of use | Advisory drift-detection across trial statistical artifacts; flags, does not fix |
| Risk tier | Low–Medium |
| Touches PHI | no |
| Touches unblinded data | no |
| Write path to system of record | none (read-only) |

## 1. Summary

A read-only engine that ingests a trial's **protocol, SAP, ADaM specs, TLF shells, and
Define-XML**, projects every relevant assertion onto the **ICH E9(R1) estimand spine**, and
reports where the chain *estimand → SAP → ADaM spec → dataset → TLF shells → Define-XML*
drifts out of agreement. It is the lead wedge: high tedium today, errors caught late and
expensively, advisory-only output, no PHI, no unblinded data, no write-path validation burden.

## 2. Motivation

The biostatistician's true bottleneck is not writing any single document faster — it is
keeping a long artifact chain logically consistent. Today inconsistencies are caught at QC,
at dry-run, or worst of all by an FDA statistical reviewer, where the cost of a fix is highest.
Typical drift classes:

- Primary endpoint timepoint differs across protocol, schedule of events, ADaM, and shells.
- An estimand declares an intercurrent-event strategy the SAP's estimator does not implement.
- The SAP's multiplicity hierarchy is not reflected in the TLF shells.
- Analysis populations (ITT/mITT/PP/Safety) are defined inconsistently across artifacts.
- Define-XML derivations disagree with the ADaM spec.

These are cross-document logical-consistency problems: high human cost, low decision authority,
machine-checkable — the ideal automation profile.

## 3. Non-goals

- Does **not** edit any artifact. Output is findings only.
- Does **not** decide the estimand or the analysis — it checks that what's written agrees with
  itself across documents.
- Does **not** run analyses or touch data (that is RFC-0005).

## 4. Guide-level design

The statistician points the tool at a versioned artifact bundle. It returns a **finding ledger**:
each finding names the rule, the estimand attribute, the artifacts in conflict, the exact source
spans, a suggested resolution, a calibrated confidence, and whether human review is required.
Findings open side-by-side with their cited spans (disconfirmation-first, per RFC-0000 §8).

## 5. Detailed design

### 5.1 Pipeline

```text
ingest → extract claims → normalize onto estimand spine → rule engine → finding ledger → review UI
            (LLM, spans)         (deterministic)         (deterministic + LLM semantic diff)
```

### 5.2 Ingestion (parsers per artifact type)

| Artifact | Parser |
|---|---|
| protocol / SAP / CSR | docx/PDF → sectioned text with page+char spans |
| ADaM spec | xlsx/define-style → structured rows |
| Define-XML | XML → typed nodes with XPath spans |
| TLF shells | docx/RTF → titles, footnotes, column structure |

### 5.3 Claim extraction (LLM, span-anchored)

The LLM extracts `Claim` objects (RFC-0000 §4), each tagged to an estimand attribute and
carrying its `source_span`. Extraction is the only LLM step that *interprets* prose; everything
downstream is deterministic over structured claims. Low-confidence extractions are routed to
human confirmation before they can raise a finding.

### 5.4 Rule engine

Two layers:

**Deterministic rules** (fast, explainable, the backbone):

| rule_id | Checks |
|---|---|
| `EST-TIMEPOINT-ALIGN` | primary endpoint timepoint identical across protocol, SoE, ADaM, shells |
| `EST-ICE-STRATEGY` | every estimand's intercurrent-event strategy has a matching SAP estimator/handling |
| `EST-SUMMARY-ESTIMATOR` | population-level summary (e.g., difference in means / hazard ratio) matches the SAP's stated estimator |
| `POP-DEF-CONSISTENT` | ITT/mITT/PP/Safety definitions agree across protocol, SAP, ADaM |
| `MULT-HIERARCHY-SHELLS` | SAP multiplicity/gatekeeping hierarchy is represented in shell set |
| `MISSING-DATA-DECLARED` | a missing-data/ICE handling is specified per estimand |
| `DEFINE-DERIV-MATCH` | Define-XML derivations equal ADaM spec derivations |
| `SHELL-BACKED` | every TLF shell has a backing derivation; every primary derivation has a shell |

**LLM semantic-diff rules** (for prose that resists exact matching): given two claims tagged to
the same attribute, classify `consistent | conflict | underspecified` with rationale and spans.
Output is always advisory and routed through review.

### 5.5 Finding schema

```json
{
  "finding_id": "uuid",
  "rule_id": "EST-TIMEPOINT-ALIGN",
  "severity": "blocker|major|minor|info",
  "estimand_attribute": "endpoint_variable",
  "artifacts_involved": ["protocol@v3", "adam_spec@v2", "shells@v1"],
  "evidence": [{"artifact": "protocol@v3", "span": "§9.2 p.41", "text": "..."}],
  "explanation": "Protocol defines primary endpoint at Week 12; ADaM AVISIT grid stops at Week 8.",
  "suggested_resolution": "Align ADaM AVISIT to Week 12 or correct protocol endpoint timepoint.",
  "confidence": 0.86,
  "needs_human_review": true
}
```

## 6. Human-in-the-loop gates

| Action | Approver |
|---|---|
| Confirm a low-confidence extracted claim | Biostatistician |
| Accept/dismiss a `blocker`/`major` finding | Lead biostatistician |
| Close the consistency review for an artifact version | Lead biostatistician |

The engine never resolves a finding itself.

## 7. Regulatory & risk posture

Read-only, no PHI, no unblinded data, no system-of-record write — it sidesteps the integration
and Part-11 write-path burden entirely. It is an advisory aid to human review, so its FDA
context-of-use is low-risk. Provenance and model governance per RFC-0000.

## 8. Validation plan

- **Gold set**: real (or realistic synthetic) protocol+SAP+ADaM+shell bundles with **seeded
  inconsistencies** across each rule class.
- **Metrics**: per-rule precision/recall on seeded defects; false-positive rate on clean bundles
  (the metric statisticians will actually judge — noise erodes trust fast).
- **Reference-standard honesty**: where LLM semantic-diff is the judge, report inter-rater
  reliability of the human labels it's compared against (RFC-0000 §9).
- **Acceptance**: deterministic rules ≥0.99 recall on seeded defects; semantic-diff findings
  held to a tuned precision floor so the worklist stays trustworthy.

## 9. Drawbacks & alternatives

- Claim extraction is the single point where prose interpretation can go wrong; mitigated by
  span-anchoring + low-confidence routing + deterministic downstream rules.
- Alternative: pure deterministic NLP (no LLM). Rejected — it cannot handle the prose variation
  in SAPs/protocols, which is exactly where drift hides.

## 10. Open questions

- Minimum viable artifact set for a useful first release — likely protocol + SAP + shells, with
  ADaM/Define-XML in a fast-follow.
- How much of the estimand spine to require vs. infer when a protocol predates E9(R1) discipline.

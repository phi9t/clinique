# RFC-0004: Submission docs & CDISC conformance triage

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Biostatistician / statistical programmer / regulatory |
| Context of use | Drafts templated submission documents and triages CDISC validator output; draft-only |
| Risk tier | Low–Medium |
| Touches PHI | no |
| Touches unblinded data | no |
| Write path to system of record | none (draft-only) |

## 1. Summary

Two adjacent capabilities sharing the RFC-0001 artifact graph: (A) **drafting** of heavily
templated, traceability-driven submission documents — Define-XML narratives, ADRG/SDRG (Analysis
& Study Data Reviewer's Guides), CSR statistical sections, and the CONSORT 2025 flow diagram —
and (B) **CDISC conformance triage**: ingesting Pinnacle 21 / CDISC validator reports and turning
cryptic findings into plain-language explanations, classifications, and suggested fixes. Both are
draft-only and low-risk, making this the natural fast-follow to RFC-0001.

## 2. Motivation

Statisticians and programmers spend large, late-stage effort hand-producing reviewer guides and
CSR sections that are mostly mechanical transcriptions of the artifact graph, and then decoding
conformance reports whose messages are notoriously terse. Both are high-tedium, low-judgment, and
already reviewed by humans — ideal for draft automation that reuses a graph we already built.

## 3. Non-goals

- Does **not** finalize or submit any document — every output is a draft for human authoring.
- Does **not** modify datasets to "fix" conformance issues — it explains and suggests.
- Does **not** invent metadata not present in the artifact graph.

## 4. Guide-level design

**(A) Drafting.** The user selects a document type; the tool assembles a draft from the artifact
graph (RFC-0001 §4) plus the applicable template, with every claim traceable to its source node.
**(B) Conformance triage.** The user uploads a validator report; the tool returns, per issue, a
plain-language explanation, a true-error / expected / waiver-candidate classification, a suggested
fix, and a link to the relevant CDISC IG / controlled-terminology rule.

## 5. Detailed design

### 5.1 Drafting engine

```text
artifact graph + document template + RAG(CDISC IG, CT, sponsor standards) → draft + traceability map
```

- **Define-XML narrative & ADRG/SDRG**: populated from `Derivation`, `AnalysisPop`, `Endpoint`,
  and `TLFShell` nodes; each drafted statement links back to its source claim span.
- **CSR statistical sections**: drafted from the actual TLF outputs and the SAP, never from
  remembered numbers — figures are inserted by reference to produced outputs (RFC-0000 §7).
- **CONSORT 2025 flow diagram**: built from disposition counts supplied as inputs; the tool lays
  out the diagram and checks the 30-item reporting checklist for missing elements.

### 5.2 Conformance triage

```json
{
  "issue_id": "SD0064",
  "raw_message": "Variable length is too long for actual data",
  "domain": "AE",
  "classification": "true_error | expected | waiver_candidate",
  "explanation": "AETERM declared length 200 but max observed is 84; FDA prefers right-sized lengths.",
  "suggested_fix": "Set AETERM length to 84 in the SDTM spec and re-derive.",
  "reference": "SDTMIG v3.x §AE; FDA Technical Conformance Guide",
  "confidence": 0.91,
  "needs_human_review": true
}
```

Classification uses deterministic rules where the validator code is unambiguous, LLM reasoning
where the message requires context; waiver candidates always require human confirmation.

## 6. Human-in-the-loop gates

| Action | Approver |
|---|---|
| Accept a drafted document section | Author (statistician / programmer / medical writer) |
| Confirm a conformance classification or waiver | Statistical programmer / regulatory |
| Release any document toward submission | Regulatory + lead biostatistician |

## 7. Regulatory & risk posture

Low–Medium: outputs feed regulated submissions but are drafts subject to full human authoring and
the standard release gate. No PHI, no unblinded data, no system-of-record writes. Traceability
maps make every drafted statement inspectable back to its graph source.

## 8. Validation plan

- **Conformance classification accuracy** vs. programmer labels on a corpus of real validator
  reports; report confusion by class (the costly error is calling a true error "expected").
- **Document completeness checks**: drafted ADRG/SDRG/CSR sections scored against required-section
  checklists; CONSORT drafts scored against the 30-item list.
- **Traceability audit**: every drafted statement must resolve to a graph source span (hard gate).
- **No-fabrication test**: assert no metadata/number appears that is absent from the graph.

## 9. Drawbacks & alternatives

- Template drift across sponsors/agencies — mitigated by templating + RAG over sponsor standards
  rather than hard-coding.
- Alternative: buy a commercial Define-XML/reviewer-guide generator. Reasonable, but it won't do
  the cross-artifact, estimand-spine-aware drafting that reusing the RFC-0001 graph enables.

## 10. Open questions

- Validator coverage: Pinnacle 21 Community/Enterprise vs. the open CDISC CORE engine — support
  which report formats first?
- How much CSR narrative is worth drafting vs. leaving to medical writers (boundary with their tooling)?

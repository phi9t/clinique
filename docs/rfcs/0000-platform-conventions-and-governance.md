# RFC-0000: Platform conventions & governance

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Biostatistician |
| Context of use | Shared substrate for all biostatistician agents; supports no decision on its own |
| Risk tier | Low (foundation) |
| Touches PHI | no |
| Touches unblinded data | no |
| Write path to system of record | none |

## 1. Summary

This RFC defines the conventions every other RFC in this suite inherits: the **artifact
graph**, the **provenance ledger**, **model & tool governance**, the **human-in-the-loop
gate pattern**, the **numeric-provenance rule**, and the **validation philosophy**. It exists
so the functional RFCs (0001–0005) do not each re-litigate governance.

## 2. Motivation

The earlier critique of the parent design identified four failure modes that recur across
every clinical-trial agent: (a) integration/validation cost hidden behind clean diagrams,
(b) a model-vendor dependency that breaks computer-system validation, (c) LLMs applied where
validation is weakest, and (d) automation bias collapsing "human-in-the-loop" into rubber-
stamping. The conventions below are the standing answers to those four.

## 3. Non-goals

- Not a system of record. The platform never becomes the authoritative EDC/SDTM/ADaM store.
- No write-back to validated systems in v1 of any capability.
- No access to treatment-assignment / unblinded data anywhere in the platform.

## 4. The artifact graph

A single normalized graph shared by RFC-0001, -0004, -0005. Nodes:

```text
Estimand        { id, objective_type, treatment, population, endpoint_variable,
                  intercurrent_events:[{event, strategy}], population_summary }
Artifact        { id, type, version, source_uri, ingested_at, checksum }
Claim           { id, artifact_id, attribute, text, source_span, extracted_by, confidence }
AnalysisPop     { id, name, definition_claims:[Claim] }      # ITT / mITT / PP / Safety
Endpoint        { id, name, timepoint, type, estimand_id }
TLFShell        { id, title, sap_section, backing_derivation_ids }
Derivation      { id, target_var, spec_claims:[Claim], dataset }
Edge            { from, to, relation: consistent|conflict|missing|derives|references }
```

`Artifact.type ∈ {protocol, sap, adam_spec, define_xml, tlf_shell, csr, sdrg, adrg,
validator_report}`. Every `Claim` carries a `source_span` (page/section/char-range or
node path for XML) so any downstream finding is clickable back to its origin.

The estimand's five attributes (ICH E9 R1) are the **spine**: claims are tagged to the
attribute they speak to, which is what makes cross-artifact drift machine-detectable.

## 5. Provenance ledger

Every agent output (finding, draft, computation, code block) is one append-only ledger record:

```json
{
  "record_id": "uuid",
  "capability": "rfc-0001|0002|0003|0004|0005",
  "produced_at": "iso-8601",
  "inputs": ["artifact_id@version", "..."],
  "model": { "id": "claude-...", "version": "pinned", "params": {"temperature": 0} },
  "tools": [{ "name": "gsDesign", "version": "3.6.x" }],
  "prompt_hash": "sha256",
  "output_ref": "uri",
  "human_review": { "required": true, "role": "biostatistician", "status": "pending|approved|rejected", "reviewer": null, "at": null }
}
```

The ledger is the audit trail (Part-11 spirit) and the training-signal source for evaluation.

## 6. Model & tool governance

The model-vendor dependency is treated as a validation hazard, not a convenience:

- **Pinned versions.** Production runs use a pinned model + pinned tool versions recorded in
  every ledger entry. `temperature=0` where the vendor honors it.
- **Revalidation is event-driven.** Any model/prompt/tool version change is a change-control
  event that triggers the relevant capability's regression suite (§8) before promotion.
- **Deprecation runbook.** Each capability declares a fallback model and a re-benchmark gate
  for the day the pinned model is sunset. Capabilities that feed regulated artifacts should
  prefer self-hostable, version-pinnable models so a vendor cannot force an unvalidated swap
  mid-trial.

## 7. The numeric-provenance rule

**No statistical or numeric value in any output may originate from LLM reasoning.** Every
number must trace to a tool return (a validated engine, a SQL query, a deterministic macro).
A `numeric-provenance` linter scans generated artifacts and rejects any figure not backed by
a tool-call record in the ledger. This is the standing answer to "LLMs can't do math."

## 8. Human-in-the-loop gate pattern & automation-bias controls

A "human gate" that shows the AI answer first and asks "approve?" is a rubber stamp. Standard
pattern for every gate:

1. **Disconfirmation-first.** The UI surfaces the *evidence against* a finding alongside the
   evidence for it; confidence is calibrated and shown.
2. **Source click-through is mandatory** before approval on High-risk findings — the reviewer
   must open at least one cited source span.
3. **Blind spot-audits.** A scheduled fraction of agent outputs is independently re-reviewed
   without the agent's answer visible, to measure real reviewer agreement vs. rubber-stamping.
4. **Named approver per action**, recorded in the ledger.

## 9. Validation philosophy

- **Reference standard is declared and its noise measured.** Gold sets state inter-rater
  reliability of their labels; headline accuracy is reported against that, never as "truth."
- **Per-capability regression suite** of known-correct cases, run on every version change.
- **Stratified error reporting** where outputs could differ by subgroup or artifact type.
- **Seeded-defect tests.** For checkers (0001) and harnesses (0005), evaluate on artifacts
  with deliberately seeded inconsistencies/bugs; report detection precision/recall.

## 10. Drawbacks & alternatives

- Building a shared artifact graph is real data engineering; the mitigation is that each
  capability needs only a thin slice (e.g., 0001 needs estimand+claim+edge; 0003 needs none).
- Alternative: per-capability silos with no shared graph — rejected because the cross-artifact
  consistency value (0001/0004/0005) only exists if they share one normalized representation.

## 11. Open questions

- Self-hosted vs. BAA-covered hosted model for capabilities that never see PHI (0001/0003/0004)
  — is hosted acceptable there, reserving self-hosted for any future PHI path?
- Graph store: property graph (Neo4j) vs. relational with a graph view — decide at 0001 impl.

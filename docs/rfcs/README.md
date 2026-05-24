# Clinique RFCs — Biostatistician Agent Suite

This directory holds the design RFCs for an agentic tooling suite built **around the
biostatistician persona** in clinical trials. The persona was chosen because its work
is artifact-heavy, traceability-driven, and already protected by a strong human-QC
culture that agents can slot into rather than fight.

## Design stance

Every RFC here obeys the same posture, established in [RFC-0000](0000-platform-conventions-and-governance.md):

- **Agents draft, triage, and check. Humans decide.** No agent takes a regulated
  action (final analysis, unblinding, submission, database lock) without a named human approver.
- **Read-only and advisory first.** v1 of each capability writes nothing back into a
  validated system of record.
- **Calculators compute; LLMs orchestrate.** No statistical number in any output may
  originate from LLM reasoning — only from a validated engine's return value.
- **Provenance is mandatory.** Every finding/output carries its source spans, model
  version, tool version, and reviewer.

## The RFCs

| # | Title | Wedge | Touches PHI? | Touches unblinded data? |
|---|---|---|---|---|
| [0000](0000-platform-conventions-and-governance.md) | Platform conventions & governance | foundation | no | no |
| [0001](0001-estimand-spine-consistency-checker.md) | Estimand-spine consistency checker | **lead wedge** | no | no |
| [0002](0002-statistical-programming-copilot.md) | Statistical programming copilot (QC-independent) | high | no | no |
| [0003](0003-sample-size-power-orchestrator.md) | Sample size & power orchestrator | high | no | no |
| [0004](0004-submission-docs-and-cdisc-conformance.md) | Submission docs & CDISC conformance triage | high | no | no |
| [0005](0005-pre-unblinding-dry-run-harness.md) | Pre-unblinding dry-run / mock-analysis harness | high | no | **no — synthetic only by construction** |

## Recommended build order

1. **RFC-0000** — shared substrate (artifact graph, provenance ledger, model governance).
2. **RFC-0001** — the lead wedge; needs no PHI, no unblinded data, no write-path validation.
3. **RFC-0004** — reuses the 0001 artifact graph; low risk; immediate reviewer-guide / conformance wins.
4. **RFC-0003** — orchestrator pattern; self-contained.
5. **RFC-0002** — programming copilot; gated by the QC-independence constraint.
6. **RFC-0005** — dry-run harness; consumes outputs of 0002 and specs from 0001.

## Status legend

`Draft` → `Proposed` → `Accepted` → `Implemented` → `Superseded`. All RFCs here are `Draft`.

## Template

New RFCs copy [`0000-template.md`](0000-template.md).

# RFC-0002: Statistical programming copilot (QC-independent)

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Biostatistician / statistical programmer |
| Context of use | Assists authoring of ADaM/TLF programs; generated code is QC'd by an independent path |
| Risk tier | Medium |
| Touches PHI | no (operates on specs + synthetic/QC data; never production patient data in v1) |
| Touches unblinded data | no |
| Write path to system of record | none (emits code into the human's working tree, not the validated store) |

## 1. Summary

A coding copilot for ADaM derivations and TLF programs in **SAS and R**, with one
non-negotiable architectural constraint: **the agent may contribute to exactly one side of a
double-programming pair for a given output, never both.** It assists production code *or*
generates independent QC/test material — and the platform enforces that boundary so the
industry's core QC mechanism (independent double programming) is never silently defeated.

## 2. Motivation

ADaM/TLF programming is high-volume, highly templated, and slow. LLMs are strong code copilots.
But the safety of a regulated table rests on **double programming**: two programmers
independently produce the same output from the SAP, and discrepancies expose bugs. If one agent
writes both the production and the QC program, the same misreading of the SAP yields the same
wrong table twice — **correlated errors** — and double programming passes a defect through. This
is the statistical analog of "validators can't validate the hard criteria." The copilot is only
safe if independence is structurally guaranteed.

## 3. Non-goals

- Does **not** produce both halves of a QC pair for the same output. Ever.
- Does **not** run the final production analysis or compute numbers itself (RFC-0000 §7).
- Does **not** write into the validated code repository; it proposes into the programmer's branch.

## 4. Guide-level design

A programmer opens a derivation/TLF task linked to a SAP section (via the RFC-0001 graph). The
copilot offers code in the project's language, grounded in the sponsor's macro library. The task
is tagged **production** or **QC**. The platform records which side the agent touched; it then
**locks the agent out of the opposite side** for that output id.

## 5. Detailed design

### 5.1 QC-independence boundary

```text
Output O (e.g., Table 14.2.1)
   ├── side: production  ── agent may assist  ─┐
   └── side: QC          ── agent LOCKED       │  (mutually exclusive per O)
                                                ▼
                          ledger: agent_contributed_side[O] = production
```

Registry rule: for each `output_id`, `agent_contributed_side ∈ {production, QC, none}` and is
write-once. A request for agent help on the locked side is refused with an explanation. The
**preferred** mode is *production-assist + human QC*; agent-assisted QC is allowed **only** when
production was fully human-written and is recorded as such.

### 5.2 Adversarial-test mode (the high-value QC contribution)

Rather than write QC code, the agent generates **independent test material** against
human-written production code: edge-case synthetic records, boundary AVISIT/ICE scenarios,
expected-property assertions ("safety population N must equal randomized minus never-treated").
This strengthens QC *without* sharing an implementation path.

### 5.3 SAS-first reality

SAS dominates FDA submissions (transport files, legacy macros); R is accepted post-pilot but
conservative sponsors stay SAS. LLM SAS competence is weaker than R/Python. Mitigations:

- **RAG over the sponsor's validated macro library** and CDISC controlled terminology; prefer
  calling existing validated macros to writing fresh logic.
- **Template-first generation** for standard ADaM structures (BDS/OCCDS) and standard TLF types.
- **Language-aware confidence**: SAS suggestions carry a stricter human-review default than R.

### 5.4 Computation boundary

Generated code orchestrates validated macros/packages; the agent never embeds hand-derived
constants or "mental-math" results. The RFC-0000 numeric-provenance linter runs on emitted code.

### 5.5 Provenance

Every emitted block is a ledger record with model+version, SAP section ref, language, side
(prod/QC/test), and reviewer — so an inspector can see exactly what the agent contributed and
which independent path QC'd it.

## 6. Human-in-the-loop gates

| Action | Approver |
|---|---|
| Accept agent production code into a branch | Statistical programmer |
| Sign off QC pass for an output | Independent QC programmer (must not be the production author) |
| Override a side-lock (exceptional) | Lead biostatistician, with recorded justification |

## 7. Regulatory & risk posture

Medium risk because output becomes regulated code. Controlled by: no write to the validated
store, mandatory independent QC, the side-lock, computation boundary, and full provenance.
v1 runs only on specs and synthetic/QC data — no production patient data — keeping PHI out.

## 8. Validation plan

- **Regression suite**: a library of standard TLFs/ADaM derivations with known-correct outputs;
  agent-assisted code must reproduce them on synthetic fixtures.
- **Independence audit**: periodic check that no output has the agent on both sides (a hard
  invariant; any violation is a defect, not a metric).
- **Defect-injection**: seed bugs into production fixtures; confirm adversarial-test mode and
  independent QC catch them.
- **Version-change trigger**: model/macro-library bumps rerun the regression suite (RFC-0000 §6).

## 9. Drawbacks & alternatives

- Could one isolated agent instance QC another agent's production code? Rejected for v1: shared
  training priors make "independence" unprovable; human QC or human-authored-production is required.
- Side-lock adds friction. Accepted — it is the whole point.

## 10. Open questions

- Where exactly does "the agent touched it" start — code completion vs. whole-program generation?
  Define a contribution threshold that triggers the side-lock.
- Long-term: is agent-assisted QC against human production ever permissible, and under what audit?

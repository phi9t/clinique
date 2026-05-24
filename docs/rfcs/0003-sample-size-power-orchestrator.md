# RFC-0003: Sample size & power orchestrator

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Biostatistician |
| Context of use | Orchestrates validated power engines and documents assumptions; never computes numbers itself |
| Risk tier | Medium |
| Touches PHI | no |
| Touches unblinded data | no |
| Write path to system of record | none |

## 1. Summary

An orchestration layer where the **LLM selects the method and assembles/documents assumptions**,
and a **validated power engine** (gsDesign, rpact, nQuery, PASS) does every calculation. No
sample-size or power number is ever produced by LLM reasoning. Output is a fully reproducible
computation record with provenance for each assumption, plus an automatic sensitivity sweep and a
cross-check against the SAP/protocol.

## 2. Motivation

Sample size is the single highest-leverage number in a trial — wrong, and the whole study is
under- or over-powered. The cited literature is explicit that LLMs are unreliable at clinical
calculations but effective as **tool-callers**. The pain that remains for the statistician is not
the arithmetic (engines do that) but: choosing the right method, sourcing defensible assumptions,
documenting their provenance, and proving the SAP's analysis matches the powering assumptions.

## 3. Non-goals

- Does **not** compute any number. All numbers come from a validated engine's return.
- Does **not** decide the design (superiority/non-inferiority/group-sequential/adaptive) — it
  proposes and the statistician decides.
- Not a replacement for the engines; it wraps them.

## 4. Guide-level design

The statistician describes the design (or it is read from the protocol/SAP via the RFC-0001
graph). The orchestrator: (1) proposes the method + engine call, (2) assembles assumptions with a
cited source for each, (3) executes the engine, (4) runs a sensitivity sweep, (5) cross-checks
against the SAP, (6) emits a reproducible record + narrative for the protocol's statistics section.

## 5. Detailed design

### 5.1 Stages

```text
design intake → method selection → assumption assembly → engine execution
            → sensitivity sweep → SAP/protocol cross-check → reproducible record + narrative
   (LLM)            (LLM)          (LLM + sources)          (validated engine)
```

### 5.2 Method selection

LLM maps `(endpoint_type, design_type, allocation_ratio, hypothesis, interim_structure)` to a
concrete engine + function call. Selection is shown with rationale and is human-confirmable.

### 5.3 Assumption assembly with provenance

Each assumption is a typed object with a source:

```json
{
  "name": "control_event_rate",
  "value": 0.32,
  "unit": "proportion",
  "source": {"artifact": "prior_trial_NCTxxxx", "span": "Table 2", "kind": "literature|protocol|assumption"},
  "rationale": "Pooled 24-month event rate from two prior phase II studies."
}
```

Assumptions marked `kind: assumption` (no external source) are flagged for explicit statistician sign-off.

### 5.4 Engine execution (the only place numbers are born)

The orchestrator builds a structured params object and calls the pinned validated engine. The
return value — N, power, boundaries, expected sample size, alpha-spending — is the *only* source
of numbers in any output (RFC-0000 §7). The engine + version is recorded.

### 5.5 Sensitivity sweep

Automatically varies key assumptions (effect size, variance, dropout, accrual) over ranges and
tabulates N/power, so the statistician sees robustness, not a single point estimate.

### 5.6 SAP/protocol cross-check

Verifies the powering assumptions and primary analysis match what the SAP actually specifies
(reuses RFC-0001 rules `EST-SUMMARY-ESTIMATOR`, `MISSING-DATA-DECLARED`). Mismatch → finding.

### 5.7 Reproducible record

```json
{
  "method": "group-sequential, O'Brien-Fleming",
  "engine": {"name": "gsDesign", "version": "3.6.x"},
  "inputs": [/* assumption objects */],
  "result": {"n_total": 642, "power": 0.90, "source": "engine_return"},
  "sensitivity": "uri-to-table",
  "narrative": "draft protocol §statistics text",
  "ledger_ref": "uuid"
}
```

## 6. Human-in-the-loop gates

| Action | Approver |
|---|---|
| Confirm method/engine selection | Biostatistician |
| Sign off `kind: assumption` (unsourced) values | Biostatistician |
| Accept final N into the protocol | Lead biostatistician |

## 7. Regulatory & risk posture

Medium risk (the number drives the trial), controlled by: validated-engine-only computation,
numeric-provenance linter, per-assumption provenance, sensitivity analysis, and SAP cross-check.
No PHI, no unblinded data. Engine versions pinned; a version bump reruns the regression cases.

## 8. Validation plan

- **Reproduction suite**: textbook and regulatory-precedent cases with known correct N/power;
  orchestrator must reproduce them exactly via the engines.
- **Numeric-provenance test**: assert zero numbers in any output lack a tool-call backing.
- **Method-selection accuracy**: vs. statistician labels on a design corpus; report disagreements.
- **Pinning/revalidation**: engine or model version change triggers full reproduction suite.

## 9. Drawbacks & alternatives

- Engine coverage gaps (exotic adaptive designs) — fall back to "method proposed, computation
  deferred to statistician's specialized tool"; never let the LLM fill the gap with reasoning.
- Alternative: pure calculator UI with no LLM. Rejected — loses method-selection, assumption
  sourcing, and the SAP cross-check, which are the actual time sinks.

## 10. Open questions

- Which engines to wrap first (gsDesign + rpact cover most group-sequential/adaptive needs)?
- For adaptive designs needing simulation, does this RFC own the simulation harness or hand off
  to RFC-0005's harness?

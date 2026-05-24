# RFC-0005: Pre-unblinding dry-run / mock-analysis harness

| Field | Value |
|---|---|
| Status | Draft |
| Author | phissenschaft@gmail.com |
| Created | 2026-05-23 |
| Persona | Biostatistician / statistical programmer |
| Context of use | Runs SAP analysis programs on synthetic data before lock to surface errors early |
| Risk tier | Medium |
| Touches PHI | **no — synthetic data only, by construction** |
| Touches unblinded data | **no — synthetic data only, by construction** |
| Write path to system of record | none |

## 1. Summary

A harness that **generates synthetic data conforming to the ADaM specs**, runs the SAP's analysis
programs (the production code from RFC-0002) against it, and surfaces programming and
specification errors **before database lock and unblinding** — when fixes are cheap. A hard
architectural wall guarantees the harness can *only* ever touch synthetic data, so it is
blinding-safe and PHI-free by construction.

## 2. Motivation

Today, many analysis-program defects and spec gaps are not found until the real dry run after
database lock, or after unblinding, where every fix is expensive and schedule-critical. Running
the analysis pipeline end-to-end on conformant mock data — across deliberately varied scenarios —
catches "the program crashes," "the shell never populates," "this derivation has no backing," and
"the missing-data strategy isn't actually implemented" while they are cheap to fix.

## 3. Non-goals

- Does **not** touch real, production, or unblinded data — ever (enforced, §5.4).
- Does **not** interpret results for efficacy — synthetic results are meaningless by design; it
  checks that the *machinery* runs and is complete, not what it concludes.
- Does **not** replace the formal post-lock dry run; it front-loads error discovery.

## 4. Guide-level design

The statistician points the harness at the ADaM specs (RFC-0001 graph), the production programs
(RFC-0002), and the shell set. It generates mock datasets under a chosen scenario, executes the
programs, and returns a report: which programs ran, which shells populated, which derivations are
unbacked, and which estimand/missing-data behaviors did or didn't materialize.

## 5. Detailed design

### 5.1 Synthetic data generator

From `Derivation`/`Endpoint`/`AnalysisPop` specs plus protocol assumptions, generate ADaM-
conformant datasets (BDS/OCCDS structures, valid CT, plausible visit grids). Generation is
parameterized by **scenario** (§5.3) and is explicitly labeled synthetic in metadata.

### 5.2 Execution harness

Runs the SAP production programs (SAS/R) on the mock data in an isolated sandbox; captures
return codes, logs, and produced outputs. Then runs structural checks:

| Check | Catches |
|---|---|
| `PROGRAM-RUNS` | crashes, missing inputs, environment gaps |
| `SHELL-POPULATES` | a TLF shell that produces no/empty output |
| `DERIVATION-BACKED` | a shell with no backing derivation, or a derivation with no shell (mirror of RFC-0001 `SHELL-BACKED`) |
| `ICE-MATERIALIZES` | estimand intercurrent-event handling that the code never actually applies |
| `MISSING-DATA-APPLIED` | the SAP's missing-data strategy not exercised by the program |
| `STRUCTURE-MATCHES-SHELL` | output columns/footnotes diverge from the approved shell |

### 5.3 Scenario library

Synthetic scenarios stress the pipeline, not the science:

- **Null** (no treatment effect), **strong effect**, **high missingness**, **ICE-heavy**
  (many intercurrent events), **boundary** (extreme visit windows, single-subject arms).
- ICE-heavy and high-missingness scenarios specifically exercise the estimand and missing-data
  machinery that RFC-0001 checks *on paper* — here we confirm the *code* honors it.

### 5.4 Blinding & PHI wall (the load-bearing guarantee)

```text
harness data source ──► [SyntheticDataProvider]  ◄── ONLY permitted provider
real/production/unblinded paths ──► HARD DENY (no code path exists)
```

- The harness depends on a single `SyntheticDataProvider` interface; no connector to EDC,
  production ADaM, or the RTSM/unblinding store is compiled into the harness at all.
- A CI gate fails the build if any real-data or treatment-assignment import appears in the
  harness module. The guarantee is structural, not procedural.

## 6. Human-in-the-loop gates

| Action | Approver |
|---|---|
| Accept the dry-run report / triage findings | Statistical programmer |
| Sign off pipeline readiness for real dry run | Lead biostatistician |

No agent action here changes a regulated artifact; the harness only reports.

## 7. Regulatory & risk posture

Medium risk because it exercises the regulated analysis pipeline, but it is blinding- and PHI-safe
by construction (§5.4), which removes the trial-integrity hazard that would otherwise dominate.
Synthetic results carry no inferential meaning and must be labeled as such everywhere.

## 8. Validation plan

- **Defect-injection**: seed known bugs into production programs and spec gaps into shells;
  measure detection rate per check class.
- **Conformance of synthetic data**: generated datasets pass the same CDISC validation as real
  ADaM (reuse RFC-0004 triage).
- **Wall test**: automated proof that no real-data/unblinding code path links into the harness
  (build-breaking invariant).
- **Scenario coverage**: every TLF shell exercised by ≥1 scenario.

## 9. Drawbacks & alternatives

- Synthetic data can be unrealistic enough to miss data-shaped bugs; mitigated by the scenario
  library and CDISC-conformant generation, but it never replaces the post-lock dry run.
- Alternative: wait for the real post-lock dry run (status quo). Rejected — that is exactly the
  expensive, schedule-critical late discovery this RFC removes.

## 10. Open questions

- How realistic should synthetic data be — pure spec-conformant, or distribution-matched to
  blinded aggregate summaries (without risking any unblinding)?
- Shared scenario engine with RFC-0003's adaptive-design simulation, or separate concerns?

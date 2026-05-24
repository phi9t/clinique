# ML onboarding primer

Start here if you have an ML or MLsys background and are new to clinical trials or this repo.

## Reading order

| Step | Doc | Who should read it |
|---|---|---|
| 1 | [Clinical trials for ML](clinical-trials-for-ml.md) | Everyone — domain mental model in ML language |
| 2 | [Clinique for ML](clinique-for-ml.md) | Everyone — repo map, commands, eval harness |
| — | [Terminology glossary](terminology-glossary.md) | **Reference** — acronyms (EDC, CDISC, ADaM, NCT, L0–L4), prescreen/EDC/CDISC wedges |
| 3 | [Trial prescreening design](../design/trial-prescreening.md) | ML researchers — active proof-point wedge (L0: ingestion, normalizers, validation gate) |
| 4 | [EDC query validation](../design/edc-query-validation.md) | MLsys — L0–L2 gate-driven validation example |
| 5 | [Biostat agent suite](../design/biostat-agent-suite.md) | MLsys — substrate, provenance gates, orchestrator pattern |

## Quick paths

**ML researcher** — eligibility criteria, labels, and the prescreening proof point:

1. [Primer §7–8: inclusion vs exclusion](clinical-trials-for-ml.md#7-eligibility-criteria-are-the-first-great-mlagent-wedge)
2. [Primer §14: ANC example](clinical-trials-for-ml.md#14-one-concrete-example)
3. [Terminology glossary → acronyms & labels](terminology-glossary.md#quick-acronym-index)
4. [Clinique for ML → run this first](clinique-for-ml.md#run-this-first-15-minutes)
5. [Trial prescreening design](../design/trial-prescreening.md)

**MLsys engineer** — pipelines, fixtures, gates, reproducibility:

1. [Clinique for ML → validation stack](clinique-for-ml.md#validation-stack-in-ml-eval-terms)
2. [Clinique for ML → three data wedges](clinique-for-ml.md#three-data-wedges-prescreen-edc-cdisc)
3. [Clinique for ML → MLsys architecture](clinique-for-ml.md#mlsys-architecture-notes)
4. [Terminology glossary → EDC §14, CDISC §15](terminology-glossary.md#14-edc-query-validation-wedge)
5. [EDC validation design](../design/edc-query-validation.md)
6. [Biostat substrate design](../design/biostat-agent-suite.md)

## Related

- [Docs index](../README.md) — all design and governance docs
- [Root README](../../README.md) — quickstart and CLI examples

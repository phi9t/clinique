# Clinique documentation

Design and governance docs for the Clinique agent suite.

## Design

| Doc | Status | Description |
|---|---|---|
| [Biostatistician agent suite](design/biostat-agent-suite.md) | `SCAFFOLD-COMPLETE` | Platform substrate + biostat capabilities (provenance, power, estimand, programming, conformance, dry-run) |
| [EDC query validation](design/edc-query-validation.md) | `LOCAL-COMPLETE` | Draft-only EDC query agent; L0–L2 synthetic validation complete |
| [Trial prescreening agent](design/trial-prescreening.md) | `L0-PUBLIC-SCAFFOLD` | Draft-only eligibility prescreening copilot; ClinicalTrials.gov ingestion + Synthea normalizer built, judge/atomizer proposed |

## EDC governance artifacts

Operational checklists and protocols used by the EDC validation CLI and tests:

- [validation-summary.md](edc-query-validation/validation-summary.md)
- [release-readiness-checklist.md](edc-query-validation/release-readiness-checklist.md)
- [annotation-manual.md](edc-query-validation/annotation-manual.md)
- [label-schema.json](edc-query-validation/label-schema.json)
- [internal-data-manifest.template.json](edc-query-validation/internal-data-manifest.template.json)
- [data-inventory.md](edc-query-validation/data-inventory.md)
- [access-boundary.md](edc-query-validation/access-boundary.md)
- [silent-prospective-protocol.md](edc-query-validation/silent-prospective-protocol.md)
- [controlled-rollout-gate.md](edc-query-validation/controlled-rollout-gate.md)

## Other

- [Gemini CLI migration guide](gcli-migration.md)
- [Superpowers implementation plans](superpowers/) — historical agent session plans (paths may reference pre-migration layout)

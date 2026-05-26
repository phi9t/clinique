# PrescreenBench Explorer Design

## Purpose

Build a PrescreenBench UI for researchers to understand the benchmark dataset, compare agent
outputs, and inspect scorer behavior case by case. The primary persona is an ML researcher
evaluating clinical-trial prescreening agents, with clinical and biostats readers treated as
first-class users who need clear field meanings, metric explanations, and primer hints.

The UI is a research workbench, not only a scorecard. It must help users move through many
patient-trial examples, understand the source trial and patient data, inspect model predictions and
evidence, and see exactly why the grader assigned each metric outcome.

## Existing Context

The repo already has:

- `explorer/`: a Vite/React static app for CDISC and Prescreen L0 data exploration.
- `explorer/public/data/prescreen/`: static JSON exports for trials, patients, schema, stats, and
  validation.
- `src/clinique/benchmarks/prescreenbench/`: PrescreenBench schema, loading, baselines, scoring, and
  report rendering.
- `benchmarks/prescreenbench/data/{synthetic,lite}/`: split artifacts.
- deterministic baseline agents: `always_unknown`, `keyword_rule`, `clinique_rule`.

The PrescreenBench Explorer should reuse this static-export architecture. React must display
exported data and annotations; Python remains the source of truth for scoring and grader logic.

## Scope

V0 includes:

- PrescreenBench as a third top-level family in the existing explorer:
  `Regulatory CDISC`, `Prescreen L0`, `PrescreenBench`.
- committed demo data for deterministic baseline runs.
- a Python export path for custom/LLM predictions and reports.
- multi-agent comparison for a selected split.
- case-first exploration with metric and agent filters.
- criterion-level gold vs prediction comparison.
- evidence quote inspection and document highlighting when offsets are available.
- inline explanations for fields, clinical/biostats concepts, labels, and metrics.
- Playwright end-to-end validation of the export-to-browser workflow.

V0 does not include:

- a backend service.
- persisted browser uploads.
- interactive EHR simulation.
- hidden split submission server.
- full patient timeline interaction beyond existing/simple document ordering.

## Architecture

PrescreenBench is added to the existing `explorer/` app as a third dataset family. It loads static
JSON from:

```text
explorer/public/data/prescreenbench/
```

The Python exporter reads split artifacts, agent prediction JSONL files, score reports, and source
trial/patient records. It writes a UI-oriented bundle that includes source records, predictions,
reports, grader annotations, field definitions, metric definitions, and primer snippets.

The static app remains GitHub Pages compatible. Demo bundles are committed. Custom LLM runs are
exported locally into the same JSON shape, so researchers can inspect local experiment outputs
without committing them.

## Exported Data Model

The default committed bundle should include:

```text
explorer/public/data/prescreenbench/index.json
explorer/public/data/prescreenbench/definitions.json
explorer/public/data/prescreenbench/synthetic.json
explorer/public/data/prescreenbench/lite.json
```

`index.json` describes available splits, agents, counts, provenance, fixture paths, and generation
metadata.

`definitions.json` contains:

- prediction label meanings.
- metric definitions.
- hard-gate definitions.
- clinical/biostats primer snippets.
- source field help text, reusing existing prescreen schema docs where possible.

Each split bundle contains:

- `split`
- `benchmark_id`
- `task_types`
- `agents`, each with agent name and `ScoreReport`
- `cases`, each with:
  - `case`: `BenchmarkCase`
  - `trial`: normalized `Trial`
  - `patient`: normalized `PatientCorpus`
  - `gold`: `GoldLabel`
  - `agent_outputs`: `SubmissionPacket` by agent
  - `grader`: per-agent, per-case grader annotations

The split bundle is shaped for direct UI consumption. The React app should not join raw JSONL rows
or reimplement scorer semantics.

## Grader Annotations

Python exports per-agent/per-case/per-criterion annotations using scorer logic or a shared helper
extracted from the scorer. React only renders these annotations.

Each criterion annotation includes:

- `criterion_id`
- criterion text when available
- `criterion_type`
- `clinical_domain`
- `is_safety_critical`
- `gold_label`
- `prediction`
- `correct`
- `evidence_present`
- `quotes_verbatim`
- `fabricated_quote_count`
- `unsupported_decision`
- `unsafe_clearance`
- `blocking_gold`
- `blocking_pred`
- `counts_toward_core_metrics`
- `counts_toward_gate_metrics`
- `schema_errors`
- `evidence_checks`

Each evidence check includes:

- `doc_id`
- `quote`
- `document_found`
- `quote_found`
- `empty_quote`
- `start_char`
- `end_char`

Offsets are computed with an exact substring search within the cited document. When the document or
quote is missing, `start_char` and `end_char` are `null` and the UI shows quote status plus the
document text that is available.

## UI Structure

The PrescreenBench view opens with aggregate analysis, then guides the user into cases.

### Benchmark Overview

The overview includes:

- split selector.
- agent checklist.
- headline metric cards:
  - score
  - criterion macro-F1
  - evidence support accuracy
  - unsafe clearance rate
  - unsupported decision count
  - fabricated quote count
  - schema valid rate
- hard-gate pass/fail summary.
- caveat that seed splits are machinery/debugging fixtures and not clinical capability claims.

Metric cards include short explanations. Clinical/biostats readers should be able to understand
what each metric means without opening source code.

### Metric Slices

Filters slice the case table, not separate pages. Initial filters:

- incorrect criterion
- unsafe clearance
- unsupported decision
- fabricated quote
- schema issue
- gold unknown
- agent predicted unknown
- inclusion
- exclusion
- safety critical
- agent

Metric slices should answer research questions such as:

- Which cases explain an agent's macro-F1 gap?
- Where did an agent abstain?
- Where did it clear an exclusion?
- Which failures are evidence failures vs classification failures?

### Case Table

Rows are patient-trial cases. Columns include:

- case id
- trial id/title
- patient id/source
- task
- gold overall label
- selected agents' overall recommendations
- worst failure badge
- criterion count
- evidence issue count

Selecting a row opens the case deep dive.

### Case Deep Dive

The deep dive is the main work surface.

It includes:

- trial summary and eligibility text.
- patient summary and documents.
- criterion comparison grid.

The criterion grid shows:

- criterion id and text.
- inclusion/exclusion.
- clinical domain.
- safety-critical flag.
- gold label.
- each agent prediction.
- correctness.
- rationale.
- evidence quote status.
- unsafe/unsupported/fabricated badges.

Clicking a cited quote selects the corresponding patient document and highlights the quote span when
offsets are available. Missing documents, missing quotes, empty quotes, and demographic exemptions
are visibly distinct states.

### Explanation Surfaces

The UI should make technical terms inspectable:

- NCT ID.
- eligibility criterion.
- inclusion/exclusion.
- `met`, `not_met`, `unknown`, `not_applicable`, `conflicting_evidence`.
- unsafe clearance.
- evidence support.
- fabricated quote.
- macro-F1.
- blocking criterion recall.
- overall recommendation.

Use compact inline help, side panels, or tooltip-style definitions. Primer text should be short and
derived from existing `docs/primer/` concepts where possible.

## Error Handling

Exporter behavior:

- missing prediction: export case with `schema_errors: ["missing prediction"]`.
- schema-invalid prediction: include schema errors and omit parsed predictions from core metric
  annotations.
- missing trial or patient corpus: include case-level export error and keep the row visible.
- invalid evidence quote: export evidence check status and let scorer-derived annotations explain
  the metric impact.
- incompatible split/prediction/report inputs: fail the CLI export with a clear error.

UI behavior:

- global load failures show a clear message with the regeneration command.
- partial case data remains inspectable.
- issue badges appear in overview, case table, and deep dive.
- document/evidence states distinguish:
  - cited document missing.
  - quote not found in cited document.
  - empty quote.
  - no evidence provided.
  - demographic exemption.

## CLI And Data Generation

Add a benchmark explorer export command:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --agents always_unknown,keyword_rule,clinique_rule \
  --out explorer/public/data/prescreenbench
```

For custom LLM runs, support explicit prediction/report inputs:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --prediction clinique_llm=path/to/predictions.jsonl \
  --report clinique_llm=path/to/report.json \
  --out .local/prescreenbench-explorer
```

`--agents` runs deterministic baselines and writes predictions/reports into the exported bundle.
`--prediction` and `--report` may be repeated for custom agents. When both deterministic and custom
agents are supplied, all agents are included in the same split bundle.

## Testing

Python tests:

- exporter writes all expected files deterministically.
- committed demo bundle matches a fresh export.
- per-case/per-criterion annotations match scorer behavior.
- quote offsets match patient document text.
- malformed predictions are exported as visible schema errors.
- missing prediction/corpus/trial paths do not crash export.
- custom prediction/report inputs fail clearly when mismatched.

Frontend tests:

- PrescreenBench appears as the third family.
- overview loads committed benchmark bundle.
- metric cards render pass/fail and score values.
- metric filters narrow the case table.
- selecting a case renders trial, patient, gold labels, agent predictions, rationale, and evidence.
- evidence quote selection highlights the correct patient document span when offsets exist.
- schema/error states render without crashing.

Playwright end-to-end tests:

- run the deterministic export command.
- start the Vite dev server.
- open the PrescreenBench family.
- select `synthetic`.
- verify aggregate cards for deterministic baselines.
- filter to unsafe-clearance cases and confirm `keyword_rule` failure is visible.
- open a case and verify trial, patient, criterion grid, prediction, rationale, evidence status, and
  document text all render.
- click a quote and verify the corresponding document/highlight behavior.

Manual verification:

- inspect one safe `clinique_rule` case.
- inspect one failing `keyword_rule` case.
- confirm clinical/biostats help text is visible where it reduces ambiguity.

## Acceptance Criteria

The feature is complete when:

- the static explorer exposes PrescreenBench as a third family.
- committed deterministic baseline bundles load without network/backend dependencies.
- custom/LLM run exports produce the same bundle shape.
- researchers can compare multiple agents on a split.
- users can filter cases by metric/failure slices.
- users can deep dive trial, patient, gold, predictions, rationale, evidence, and grader outcome.
- clinical/biostats field and metric explanations are present in the UI.
- Python, frontend build, and Playwright E2E checks pass.

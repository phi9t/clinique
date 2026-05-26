# PrescreenBench — Dataset Card (V0)

## Summary

PrescreenBench V0 ships the **benchmark machinery** (decoupled scorer, frozen submission schema,
metrics, baselines, report) with **unit-grade seed splits**. It is not yet a clinical-capability
benchmark. Read the honesty caveats before quoting any number.

- `benchmark_id`: `prescreenbench_v0`
- Splits: `synthetic` (2 cases, 6 criterion labels, `end_to_end_packet`),
  `lite` (6 cases, 6 criterion labels, `criterion_judgment`).

## Provenance

There is **no hand-entered clinical data** in the seed splits. Everything is regenerated
deterministically by [`build_seed.py`](build_seed.py) from committed, PHI-free repo fixtures:

| Artifact            | Source                                                            |
|---------------------|------------------------------------------------------------------|
| `trials.jsonl`      | `tests/fixtures/prescreen/trials.jsonl` (recorded ClinicalTrials.gov API v2 payloads) |
| `patients.jsonl`    | Synthea fixture (`tests/fixtures/prescreen/synthea/`) + PMC-Patients fixture; normalized `PatientCorpus`, snapshot baked in |
| criterion type/safety | deterministic `ReferenceAtomizer`                              |
| gold labels         | `.workstream/prescreen-copilot/l0_cases.jsonl` (already-reviewed L0 eval cases) |
| `overall_label`     | deterministic `aggregate()` of the split's gold criterion labels |

Regenerate: `uv run python benchmarks/prescreenbench/build_seed.py`.

## Honesty caveats (read before claiming anything)

- **Unit-grade only.** The generator, atomizer, and judge share an ontology, so high scores here
  prove *internal consistency and plumbing*, not clinical NLP capability. Do not report seed-split
  numbers as "prescreening performance."
- **Synthea text is templated** — it proves retrieval/aggregation mechanics, never real-text
  robustness (negation, temporal nuance, prior-therapy history).
- **Unknown-heavy gold.** 5 of 6 seed criterion labels are `unknown`. As a result `always_unknown`
  scores *high* (~0.64). This is the design's documented "conservative-unknown looks good" hazard,
  amplified by tiny data — it is the reason `unknown_actionability` must eventually be a real,
  human-rated gate. The current `unknown_actionability` term is **proxied by `unknown_recall`**,
  which *overstates* pure-abstention agents; treat it as a placeholder.
- **`blocking_criterion_recall` defaults to `0.0`** when a split has no gold-blocking criteria (as
  the seed splits do). It only becomes informative once blocking cases are added.
- **`gold_evidence` spans are empty** in V0. Evidence support is scored on *predicted* quotes vs.
  the corpus (quote fidelity), not against gold spans. Evidence-retrieval metrics (Recall@k, MRR)
  are deferred to V1.

## Scoring contract

- Criterion alignment is by `criterion_id`; a gold criterion the agent omits is scored as `unknown`.
- Quote fidelity: a predicted quote is "verbatim" iff it is a substring of its *cited* document's
  text. A cited `doc_id` absent from the corpus counts as a fabricated quote.
- Demographic exemption: a `met`/`not_met` on a `demographic` criterion with a rationale is treated
  as supported without a free-text quote — mirroring the substrate evidence gate
  (`prescreen/evidence_gate.py`), because age/sex are derived from structured demographics.
- Score weights and gate thresholds: `clinique.prescreen.metrics.SCORE_WEIGHTS` / `HARD_GATES`.
- Explorer-facing score payloads also include:
  - `patient_level_metrics` (overall recommendation summary with overall accuracy, per-class support,
    and a case-level confusion matrix).
  - `per_criterion_metrics` (per-criterion `support`, classification quality, and safety-failure
    counters).

## Roadmap

- **V1**: n2c2 judge-only track (macro-F1 over the 13 criteria; `run_n2c2_eval` already exists),
  TREC trial-retrieval track, a human-labeled 100-case Lite set, real `gold_evidence` spans.
- **V2**: human-adjudicated `Verified` split, contamination-resistant `Hidden` split with a
  submission server, and the `Interactive` (tau-bench-style) environment with simulated EHR tools.

## Licensing / PHI

All committed data is synthetic or open and PHI-free, consistent with the repo's fixture policy.
Credentialed corpora (n2c2 2018, full MIMIC-IV) are **never** committed; V1+ tracks that use them
load from the user's licensed copy at run time.

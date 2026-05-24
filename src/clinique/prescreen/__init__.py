"""Trial prescreening capability (design: docs/design/trial-prescreening.md).

Domain primer: docs/primer/clinical-trials-for-ml.md §7–8, §13–14.

L0 public-data path: ClinicalTrials.gov ingestion (single-study + search),
Synthea / PMC-Patients / MIMIC-IV demo normalizers, and a conformance gate
(``validation.py``). ``aggregator.py`` provides deterministic overall
recommendations from criterion judgments (no LLM). Atomizer, retriever, criterion
judge, and the evidence-provenance gate are specified but not yet implemented.
"""

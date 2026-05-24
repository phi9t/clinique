"""Trial prescreening capability (design: docs/design/trial-prescreening.md).

Domain primer: docs/primer/clinical-trials-for-ml.md §7–8, §13–14.

L0 public-data path only at this stage: ClinicalTrials.gov trial ingestion and a Synthea patient
normalizer, both deterministic and offline-testable. Atomizer, retriever, criterion judge, and
the evidence-provenance gate are specified in the design doc but not yet implemented.
"""

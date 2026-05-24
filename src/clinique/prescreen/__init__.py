"""Trial prescreening capability (design: docs/design/trial-prescreening.md).

Domain primer: docs/primer/clinical-trials-for-ml.md §7–8, §13–14.

L0 public-data path: ClinicalTrials.gov ingestion (single-study + search),
Synthea / PMC-Patients / MIMIC-IV demo normalizers, and a conformance gate
(``validation.py``). Copilot tools: ``atomizer``, ``retrieval``, ``judge``,
``evidence_gate``, ``orchestrator``, ``eval`` (deterministic stand-ins for CI).
Workstream tracking: ``.workstream/prescreen-copilot/``.
"""

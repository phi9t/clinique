# Prescreen Copilot — Access Boundary

## In scope (open, no credentialing)

- ClinicalTrials.gov API v2
- Synthea synthetic exports (Apache-2.0)
- PMC-Patients open HF subset
- MIMIC-IV **demo** (ODbL, no DUA)

## Out of scope (credentialed / PHI)

- n2c2 2018 Track 1 gold labels
- MIMIC-IV full + Note
- Live EHR / FHIR / OMOP connectivity
- Any PHI-bearing internal patient data

## Storage rule

Large frozen snapshots **never** enter git. They live under `~/.clinique/datasets/`.
Committed fixtures stay synthetic-shaped and minimal.

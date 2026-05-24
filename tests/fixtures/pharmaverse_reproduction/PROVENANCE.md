# Pinned Pharmaverse and R-Pilot Sources

This document describes the pinned data and code structures from the Pharmaverse and the R Consortium FDA submission pilot, which serve as the reference standard for statistical programming reproduction (RFC-0002 / RFC-0005).

## 1. R Consortium FDA Submission Pilot (Pilot 1)
- **Repository**: [RConsortium/submissions-pilot1-to-fda](https://github.com/RConsortium/submissions-pilot1-to-fda)
- **Version/Tag**: `main` (pinned to commit `3a8f5b8` or latest stable release)
- **Key Artifacts**:
  - **Define-XML**: `m5/datasets/rconsortiumpilot1/analysis/adam/datasets/define.xml`
  - **ADSL dataset**: `m5/datasets/rconsortiumpilot1/analysis/adam/datasets/adsl.xpt`
  - **ADTTE dataset**: `m5/datasets/rconsortiumpilot1/analysis/adam/datasets/adtte.xpt`

## 2. Pharmaverse ADaM admiral Templates
- **Repository**: [pharmaverse/admiral](https://github.com/pharmaverse/admiral)
- **Version**: admiral v1.0.0 or later
- **Key Templates**:
  - **ADSL generation template**: `inst/templates/ad_adsl.R`
  - **ADACTION generation template**: `inst/templates/ad_adae.R`

## 3. Local Fixtures and Reproduction Stub
- Local copies of the R Consortium pilot data (`define.xml`, `adsl.xpt`, `adtte.xpt`) are downloaded to `tests/fixtures/realdata/` and used to verify the estimand-spine consistency checker.
- A reproduction stub is implemented in `tests/test_dryrun_reproduction.py` to assert that programs running in the `DryRunHarness` can reproduce standard ADaM derivations on synthetic inputs matching the pilot's schema.

# Design Spec: Prescreen Hardening, Doc Sync, and Aggregator

**Date:** 2026-05-24  
**Status:** Implemented (2026-05-24)

## 1. Goal

Close the gaps identified in the codebase review: sync documentation with the implemented L0
prescreen stack, harden prescreen CLI error handling, add prescreen CLI tests, refactor the monolithic
CLI into a package, and implement deterministic judgment aggregation as a library (no new CLI
subcommand).

## 2. Background

The prescreen L0 path has grown beyond the original scaffold:

- **Modules:** `schemas.py`, `ingestion.py` (including CT.gov search), `normalizer.py`,
  `validation.py`, `pmc_patients.py`, `mimic_demo.py`
- **CLI:** `ingest`, `search`, `show`, `normalize-synthea`, `ingest-pmc`, `validate` (exit 7 on
  conformance failure)
- **Tests:** six `test_prescreen_*.py` modules; no prescreen CLI tests; no aggregation tests

Documentation (`README.md`, primer, `prescreen/__init__.py`) and the design doc implementation
layout still describe a narrower L0. The CLI (`src/clinique/cli.py`, ~268 lines) mixes EDC and
prescreen dispatch. Three prescreen network commands use broad `except Exception`.

Aggregation logic is specified in
[`docs/design/trial-prescreening.md`](../../design/trial-prescreening.md) but not implemented.
Per scope choice **A**, aggregation ships as **library + unit tests only** — no
`prescreen aggregate` CLI in this workstream.

## 3. Approach

**Recommended:** Single ordered workstream (Approach 1 from design review):

1. Doc sync (accurate before refactor)
2. `aggregator.py` + schema types + tests
3. Exception narrowing + prescreen CLI tests
4. CLI package split

**Out of scope:** atomizer, judge, retrieval, n2c2 ingestion, evidence gate, orchestrator, new CLI
features, retry/backoff for network commands.

## 4. Aggregator Module

### 4.1 New types in `schemas.py`

Add controlled vocabularies and a frozen dataclass:

```python
CRITERION_TYPES = frozenset({"inclusion", "exclusion"})
PREDICTIONS = frozenset({"met", "not_met", "unknown", "not_applicable", "conflicting_evidence"})
RECOMMENDATIONS = frozenset({"likely_ineligible", "needs_review", "potentially_eligible"})

@dataclass(frozen=True)
class CriterionJudgment:
    criterion_id: str
    criterion_type: str   # inclusion | exclusion
    prediction: str       # met | not_met | unknown | not_applicable | conflicting_evidence
```

Field names use `criterion_type` (not `type`) to match existing schema naming. The design doc
pseudocode uses `j.type`; implementation uses `j.criterion_type`.

### 4.2 `aggregator.py`

New module with a single public function:

```python
def aggregate(judgments: Sequence[CriterionJudgment]) -> str:
    ...
```

**Rules** (deterministic, order-independent; matches design doc):

| Priority | Condition | Result |
|---|---|---|
| 1 | Any `exclusion` + `met` | `likely_ineligible` |
| 2 | Any `inclusion` + `not_met` | `likely_ineligible` |
| 3 | Any `unknown` or `conflicting_evidence` | `needs_review` |
| 4 | Else | `potentially_eligible` |

**`not_applicable`:** Ignored for all gate checks. Does not trigger ineligible or needs_review.

**Empty input:** Return `potentially_eligible` (vacuous pass; document in module docstring).

**Validation:** Raise `ValueError` with a clear message if any judgment has an invalid
`criterion_type` or `prediction`. No silent coercion.

**No CLI exposure** in this workstream.

### 4.3 Tests: `tests/test_prescreen_aggregation.py`

Inline `CriterionJudgment` construction (no JSONL fixture required):

| Scenario | Expected |
|---|---|
| Exclusion `met` | `likely_ineligible` |
| Inclusion `not_met` | `likely_ineligible` |
| Any `unknown` | `needs_review` |
| Any `conflicting_evidence` | `needs_review` |
| Clean pass (inclusion `met`, exclusion `not_met`) | `potentially_eligible` |
| Exclusion `not_met` alone does not override failed inclusion | `likely_ineligible` |
| `not_applicable` judgments ignored | per rules above |
| Empty list | `potentially_eligible` |
| Invalid `criterion_type` or `prediction` | `ValueError` |
| Same input twice | identical output (determinism) |

## 5. Documentation Sync

### 5.1 `docs/design/trial-prescreening.md`

- Implementation layout: mark ✅ `validation.py`, `pmc_patients.py`, `mimic_demo.py`, expanded
  `ingestion.py` / `normalizer.py`; mark ✅ `aggregator.py` after implementation
- Replace CLI section with full command table (`ingest`, `search`, `show`, `normalize-synthea`,
  `ingest-pmc`, `validate`)
- Update tests list: existing six modules + `test_prescreen_aggregation.py` + `test_prescreen_cli.py`
- Status line: expanded L0 public-data path; atomizer/judge still proposed (not L1)

### 5.2 `README.md`

- Opening already says "regulated clinical-trial workflows"; ensure prescreen bullet reflects full L0
  (PMC, MIMIC, validation, search)
- Expand prescreen CLI section: `validate`, `normalize-synthea` examples using committed fixtures
  (offline paths only; network commands documented but not required for CI)

### 5.3 `docs/primer/clinique-for-ml.md`

- Extend schema table: PMC/MIMIC sources, `validation.py`, `aggregator.py`
- Add prescreen exit code 7 to CLI table
- Update "Run this first" with `prescreen validate` on committed fixtures

### 5.4 `docs/README.md`, `docs/primer/README.md`

- One-line prescreen description updates to match expanded L0

### 5.5 `src/clinique/prescreen/__init__.py`

- Module docstring lists all L0 modules and notes `aggregator.py` as deterministic (no LLM)

## 6. Exception Hardening

In prescreen network handlers (`ingest`, `search`, `ingest-pmc`), replace:

```python
except Exception as exc:
```

with:

```python
except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
```

Add `import urllib.error` where needed. Unexpected exceptions propagate for dev/test visibility.
Offline commands (`validate`, `show`, `normalize-synthea`) already use narrow handlers; leave
unchanged unless refactor moves them.

## 7. Prescreen CLI Tests

New `tests/test_prescreen_cli.py`, mirroring `tests/test_edc_cli.py` — call `main(argv=[...])`
directly:

| Test | Assert |
|---|---|
| `prescreen show` on `tests/fixtures/prescreen/trials.jsonl` | exit 0 |
| `prescreen validate --trials tests/fixtures/prescreen/trials.jsonl` | exit 0 |
| `prescreen validate` with intentionally bad corpus (inline tmp fixture) | exit 7 |
| Missing required args (e.g. `validate` with no inputs) | exit 2 |
| Unknown subcommand / missing prescreen subcommand | exit 0 (prints help banner) or exit 2 per argparse behavior — match existing EDC pattern |

Use existing fixtures under `tests/fixtures/prescreen/` where possible. Create minimal invalid
corpus inline in test (tmp_path) if no committed bad fixture exists.

## 8. CLI Package Refactor

Replace `src/clinique/cli.py` (single file) with package:

```
src/clinique/cli/
  __init__.py     # exports main(); wires parser → handlers
  parser.py       # build_parser()
  edc.py          # handle_edc(args) -> int
  prescreen.py    # handle_prescreen(args) -> int
```

- `pyproject.toml` entry point stays `clinique = "clinique.cli:main"` (package `__init__.py`
  exports `main`)
- Delete top-level `src/clinique/cli.py`
- **No behavior change** — existing `tests/test_edc_cli.py` must pass unchanged
- `tests/test_prescreen_cli.py` imports `from clinique.cli import main` (same public API)

## 9. Verification

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

All existing tests pass; new aggregation and prescreen CLI tests added. No Docker requirement for
this workstream.

## 10. Commit Strategy

Suggested commit sequence (implementation plan may refine):

1. `docs: sync prescreen L0 docs and README`
2. `feat(prescreen): deterministic judgment aggregator`
3. `fix(prescreen): narrow CLI network exception handling`
4. `test(prescreen): add CLI integration tests`
5. `refactor(cli): split into cli package`

## 11. Success Criteria

- [x] Design doc, README, primer, and `__init__.py` describe implemented L0 accurately
- [x] `aggregate()` implements design-doc rules with full test coverage
- [x] No `prescreen aggregate` CLI subcommand
- [x] Network prescreen commands catch only expected exception types
- [x] `tests/test_prescreen_cli.py` covers show, validate (0 and 7), and missing-args paths
- [x] CLI split complete; EDC CLI tests unchanged
- [x] Full pytest suite and ruff pass (236 tests; untracked `explorer_export.py` excluded)

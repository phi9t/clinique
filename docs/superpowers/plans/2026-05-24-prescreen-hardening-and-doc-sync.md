# Prescreen Hardening and Aggregator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sync prescreen documentation with implemented L0, add deterministic `aggregate()`, harden prescreen CLI exceptions, add prescreen CLI tests, and split the monolithic CLI into a package.

**Architecture:** Docs-first so references stay accurate; then library-only aggregator with TDD; then CLI hardening and tests against the existing `main(argv=...)` API; finally mechanical CLI split into `cli/parser.py`, `cli/edc.py`, `cli/prescreen.py` with no behavior change.

**Tech Stack:** Python 3.12, stdlib dataclasses/argparse/urllib, pytest, ruff.

**Spec:** [2026-05-24-prescreen-hardening-and-doc-sync-design.md](../specs/2026-05-24-prescreen-hardening-and-doc-sync-design.md)

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `docs/design/trial-prescreening.md` | Full L0 layout, CLI table, tests list |
| Modify | `README.md` | Expanded prescreen L0 + CLI examples |
| Modify | `docs/README.md` | Prescreen status blurb |
| Modify | `docs/primer/clinique-for-ml.md` | Schema table, CLI table, run-first |
| Modify | `docs/primer/README.md` | One-line prescreen update |
| Modify | `src/clinique/prescreen/__init__.py` | Module list docstring |
| Modify | `src/clinique/prescreen/schemas.py` | `CriterionJudgment`, vocab constants |
| Create | `src/clinique/prescreen/aggregator.py` | `aggregate()` |
| Create | `tests/test_prescreen_aggregation.py` | Aggregator unit tests |
| Modify | `src/clinique/cli/prescreen.py` | Narrow network exceptions (after refactor) |
| Create | `tests/test_prescreen_cli.py` | CLI integration tests |
| Create | `src/clinique/cli/__init__.py` | `main()` entry |
| Create | `src/clinique/cli/parser.py` | `build_parser()` |
| Create | `src/clinique/cli/edc.py` | EDC dispatch |
| Create | `src/clinique/cli/prescreen.py` | Prescreen dispatch |
| Delete | `src/clinique/cli.py` | Replaced by package |

---

### Task 1: Documentation sync

**Files:**
- Modify: `docs/design/trial-prescreening.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/primer/clinique-for-ml.md`
- Modify: `docs/primer/README.md`
- Modify: `src/clinique/prescreen/__init__.py`

- [ ] **Step 1: Update design doc implementation layout and CLI section**

In `docs/design/trial-prescreening.md`:

- Change `docs/README.md` index status from implied narrow scaffold to expanded L0 (keep atomizer/judge proposed).
- In **Proposed implementation layout**, mark ✅ on: `validation.py`, expanded `ingestion.py`, expanded `normalizer.py`, `pmc_patients.py`, `mimic_demo.py`; leave `aggregator.py` as ◻ until Task 2 completes, then flip to ✅.
- Replace the two-line CLI note with:

```markdown
| Command | Purpose | Exit codes |
|---|---|---|
| `prescreen ingest` | Record NCT ids from ClinicalTrials.gov | 0 success, 2 fetch/parse failure |
| `prescreen search` | Record CT.gov search results | 0 success, 2 fetch/parse failure |
| `prescreen show` | Offline trial summary from JSONL | 0 success, 2 load failure |
| `prescreen normalize-synthea` | Synthea CSV dir → PatientCorpus JSONL | 0 success, 2 I/O or parse failure |
| `prescreen ingest-pmc` | Record PMC-Patients sample | 0 success, 2 fetch/parse failure |
| `prescreen validate` | L0 conformance report | 0 clean, 2 load failure, 7 conformance errors |
```

- Update tests list to include all six existing `test_prescreen_*.py` files plus placeholders for `test_prescreen_aggregation.py` and `test_prescreen_cli.py`.

- [ ] **Step 2: Update README prescreen section**

In `README.md`:

- Line 16: change prescreen parenthetical to mention CT.gov search, Synthea/PMC/MIMIC normalizers, and L0 validation gate.
- Lines 46–47: expand "Trial prescreening (L0)" bullet to list ingestion, search, three patient sources, validation gate.
- After the existing `prescreen ingest` example, add:

```bash
# Offline conformance check (exit 7 when records fail vocab / leakage rules)
uv run clinique prescreen validate \
  --trials tests/fixtures/prescreen/trials.jsonl

# Synthea CSV → PatientCorpus JSONL (offline; requires a Synthea export directory)
uv run clinique prescreen normalize-synthea \
  --csv-dir tests/fixtures/prescreen/synthea \
  --snapshot 2026-03-01 \
  --out /tmp/patients.jsonl
```

- [ ] **Step 3: Update primer and docs index**

In `docs/README.md` line 19, change prescreen description to mention search, PMC/MIMIC, validation gate, and aggregator (library).

In `docs/primer/clinique-for-ml.md`:

- Add rows to **Minimum schema → code mapping** for `validation.py`, `pmc_patients.py`, `mimic_demo.py`, and `aggregator.py` (CriterionJudgment + aggregate).
- Extend **CLI as batch jobs** table with `prescreen search`, `normalize-synthea`, `ingest-pmc`, `validate` (exit 7).
- In **Run this first**, add after `prescreen show`:

```bash
uv run clinique prescreen validate --trials tests/fixtures/prescreen/trials.jsonl
```

In `docs/primer/README.md`, update any one-line prescreen summary to match expanded L0.

- [ ] **Step 4: Update prescreen package docstring**

Replace `src/clinique/prescreen/__init__.py` module docstring with:

```python
"""Trial prescreening capability (design: docs/design/trial-prescreening.md).

Domain primer: docs/primer/clinical-trials-for-ml.md §7–8, §13–14.

L0 public-data path: ClinicalTrials.gov ingestion (single-study + search),
Synthea / PMC-Patients / MIMIC-IV demo normalizers, and a conformance gate
(``validation.py``). ``aggregator.py`` provides deterministic overall
recommendations from criterion judgments (no LLM). Atomizer, retriever, criterion
judge, and the evidence-provenance gate are specified but not yet implemented.
"""
```

- [ ] **Step 5: Commit**

```bash
git add docs/design/trial-prescreening.md README.md docs/README.md \
  docs/primer/clinique-for-ml.md docs/primer/README.md \
  src/clinique/prescreen/__init__.py
git commit -m "$(cat <<'EOF'
docs: sync prescreen L0 docs with implemented modules and CLI

EOF
)"
```

---

### Task 2: Aggregator schemas and tests (TDD)

**Files:**
- Modify: `src/clinique/prescreen/schemas.py`
- Create: `tests/test_prescreen_aggregation.py`
- Create: `src/clinique/prescreen/aggregator.py`

- [ ] **Step 1: Add schema types**

Append to `src/clinique/prescreen/schemas.py` after existing vocab constants:

```python
CRITERION_TYPES = frozenset({"inclusion", "exclusion"})
PREDICTIONS = frozenset(
    {"met", "not_met", "unknown", "not_applicable", "conflicting_evidence"}
)
RECOMMENDATIONS = frozenset({"likely_ineligible", "needs_review", "potentially_eligible"})


@dataclass(frozen=True)
class CriterionJudgment:
    criterion_id: str
    criterion_type: str
    prediction: str
```

- [ ] **Step 2: Write failing aggregation tests**

Create `tests/test_prescreen_aggregation.py`:

```python
from __future__ import annotations

import pytest

from clinique.prescreen.aggregator import aggregate
from clinique.prescreen.schemas import CriterionJudgment


def _j(criterion_id: str, criterion_type: str, prediction: str) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_id=criterion_id,
        criterion_type=criterion_type,
        prediction=prediction,
    )


def test_exclusion_met_is_likely_ineligible():
    assert aggregate([_j("E-1", "exclusion", "met")]) == "likely_ineligible"


def test_inclusion_not_met_is_likely_ineligible():
    assert aggregate([_j("I-1", "inclusion", "not_met")]) == "likely_ineligible"


def test_unknown_triggers_needs_review():
    assert aggregate([_j("I-1", "inclusion", "unknown")]) == "needs_review"


def test_conflicting_evidence_triggers_needs_review():
    assert aggregate([_j("I-1", "inclusion", "conflicting_evidence")]) == "needs_review"


def test_clean_pass_is_potentially_eligible():
    judgments = [
        _j("I-1", "inclusion", "met"),
        _j("E-1", "exclusion", "not_met"),
    ]
    assert aggregate(judgments) == "potentially_eligible"


def test_exclusion_not_met_does_not_override_failed_inclusion():
    judgments = [
        _j("I-1", "inclusion", "not_met"),
        _j("E-1", "exclusion", "not_met"),
    ]
    assert aggregate(judgments) == "likely_ineligible"


def test_not_applicable_is_ignored():
    judgments = [
        _j("I-1", "inclusion", "met"),
        _j("N-1", "inclusion", "not_applicable"),
    ]
    assert aggregate(judgments) == "potentially_eligible"


def test_empty_judgments_is_potentially_eligible():
    assert aggregate([]) == "potentially_eligible"


def test_invalid_criterion_type_raises():
    with pytest.raises(ValueError, match="criterion_type"):
        aggregate([_j("X-1", "maybe", "met")])


def test_invalid_prediction_raises():
    with pytest.raises(ValueError, match="prediction"):
        aggregate([_j("I-1", "inclusion", "maybe")])


def test_aggregate_is_deterministic():
    judgments = [_j("I-1", "inclusion", "met"), _j("E-1", "exclusion", "unknown")]
    assert aggregate(judgments) == aggregate(list(judgments))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_prescreen_aggregation.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'clinique.prescreen.aggregator'`

- [ ] **Step 4: Implement aggregator**

Create `src/clinique/prescreen/aggregator.py`:

```python
"""Deterministic overall recommendation from criterion-level judgments."""

from __future__ import annotations

from collections.abc import Sequence

from clinique.prescreen.schemas import (
    CRITERION_TYPES,
    PREDICTIONS,
    CriterionJudgment,
)


def _validate(judgment: CriterionJudgment) -> None:
    if judgment.criterion_type not in CRITERION_TYPES:
        raise ValueError(f"invalid criterion_type: {judgment.criterion_type!r}")
    if judgment.prediction not in PREDICTIONS:
        raise ValueError(f"invalid prediction: {judgment.prediction!r}")


def aggregate(judgments: Sequence[CriterionJudgment]) -> str:
    """Return likely_ineligible, needs_review, or potentially_eligible.

    ``not_applicable`` judgments are ignored. An empty sequence returns
    ``potentially_eligible`` (vacuous pass).
    """
    for judgment in judgments:
        _validate(judgment)

    applicable = [j for j in judgments if j.prediction != "not_applicable"]

    if any(j.criterion_type == "exclusion" and j.prediction == "met" for j in applicable):
        return "likely_ineligible"
    if any(j.criterion_type == "inclusion" and j.prediction == "not_met" for j in applicable):
        return "likely_ineligible"
    if any(j.prediction in {"unknown", "conflicting_evidence"} for j in applicable):
        return "needs_review"
    return "potentially_eligible"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_prescreen_aggregation.py -v`

Expected: all PASS

- [ ] **Step 6: Mark aggregator ✅ in design doc and commit**

In `docs/design/trial-prescreening.md`, change `aggregator.py ◻` to `aggregator.py ✅`.

```bash
git add src/clinique/prescreen/schemas.py src/clinique/prescreen/aggregator.py \
  tests/test_prescreen_aggregation.py docs/design/trial-prescreening.md
git commit -m "$(cat <<'EOF'
feat(prescreen): deterministic judgment aggregator

EOF
)"
```

---

### Task 3: Narrow prescreen network exception handling

**Files:**
- Modify: `src/clinique/cli.py` (relocated to `prescreen.py` in Task 5; do this before or during Task 5)

- [ ] **Step 1: Replace broad except on network commands**

In the prescreen ingest/search/ingest-pmc handlers, add `import urllib.error` at module top and change each block from `except Exception` to:

```python
except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
```

Leave comments explaining these are expected fetch/parse failures; do not catch `Exception`.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -q`

Expected: all PASS (no behavior change on happy paths)

- [ ] **Step 3: Commit**

```bash
git add src/clinique/cli.py
git commit -m "$(cat <<'EOF'
fix(prescreen): narrow CLI network exception handling

EOF
)"
```

---

### Task 4: Prescreen CLI tests

**Files:**
- Create: `tests/test_prescreen_cli.py`

- [ ] **Step 1: Write prescreen CLI tests**

Create `tests/test_prescreen_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from clinique.cli import main

TRIALS = Path("tests/fixtures/prescreen/trials.jsonl")


def test_prescreen_show_exits_zero_on_committed_fixture(capsys):
    exit_code = main(
        ["prescreen", "show", "--fixtures", str(TRIALS)],
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NCT" in captured.out


def test_prescreen_validate_clean_trials_exits_zero(capsys):
    exit_code = main(
        ["prescreen", "validate", "--trials", str(TRIALS)],
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "errors" in captured.err


def test_prescreen_validate_bad_trial_exits_seven(tmp_path, capsys):
    bad = tmp_path / "bad_trials.jsonl"
    payload = {
        "trial_id": "NCT00000001",
        "source": "clinicaltrials_gov",
        "title": "t",
        "conditions": [],
        "phase": "PHASE9",
        "recruitment_status": "RECRUITING",
        "eligibility_text": "x",
        "sex": "UNISEX",
        "accepts_healthy_volunteers": False,
        "minimum_age": {"raw": "18 Years", "years": 18.0},
        "maximum_age": {"raw": None, "years": None},
        "std_ages": ["ADULT"],
        "sponsor": "s",
    }
    bad.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    exit_code = main(
        ["prescreen", "validate", "--trials", str(bad)],
    )
    capsys.readouterr()
    assert exit_code == 7


def test_prescreen_validate_without_inputs_exits_two(capsys):
    exit_code = main(["prescreen", "validate"])
    capsys.readouterr()
    assert exit_code == 2
```

- [ ] **Step 2: Run prescreen CLI tests**

Run: `uv run pytest tests/test_prescreen_cli.py -v`

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_prescreen_cli.py
git commit -m "$(cat <<'EOF'
test(prescreen): add CLI integration tests for show and validate

EOF
)"
```

---

### Task 5: CLI package refactor

**Files:**
- Create: `src/clinique/cli/__init__.py`
- Create: `src/clinique/cli/parser.py`
- Create: `src/clinique/cli/edc.py`
- Create: `src/clinique/cli/prescreen.py`
- Delete: `src/clinique/cli.py`

- [ ] **Step 1: Create parser module**

Move `_build_parser()` body from `src/clinique/cli.py` into `src/clinique/cli/parser.py` as `build_parser()` (drop leading underscore; export publicly within package).

- [ ] **Step 2: Create EDC handler module**

Create `src/clinique/cli/edc.py` with `handle_edc(args) -> int | None` containing all `args.command == "edc-query"` branches from current `main()`. Return `None` when the command is not an EDC subcommand.

- [ ] **Step 3: Create prescreen handler module**

Create `src/clinique/cli/prescreen.py` with `handle_prescreen(args) -> int | None` containing all prescreen branches (including narrowed exceptions from Task 3). Return `None` when not a prescreen subcommand.

- [ ] **Step 4: Create package entry point**

Create `src/clinique/cli/__init__.py`:

```python
"""CLI entry point."""

from __future__ import annotations

import sys

from clinique.cli.edc import handle_edc
from clinique.cli.parser import build_parser
from clinique.cli.prescreen import handle_prescreen


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    for handler in (handle_edc, handle_prescreen):
        code = handler(args)
        if code is not None:
            return code
    print("clinique — biostatistician agent suite.")
    print("Design: docs/design/  |  Index: docs/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Delete old cli.py**

Remove `src/clinique/cli.py` after confirming `pyproject.toml` still has `clinique = "clinique.cli:main"`.

- [ ] **Step 6: Run full verification**

```bash
uv run ruff check src tests
uv run ruff format src tests
uv run pytest
```

Expected: ruff clean; all tests PASS including `tests/test_edc_cli.py` and `tests/test_prescreen_cli.py`.

- [ ] **Step 7: Commit**

```bash
git add src/clinique/cli/ src/clinique/cli.py
git commit -m "$(cat <<'EOF'
refactor(cli): split monolithic cli.py into cli package

EOF
)"
```

Note: `git add src/clinique/cli.py` stages the deletion when the file is removed.

---

### Task 6: Final verification and spec checklist

- [ ] **Step 1: Run full gate commands**

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest
```

Expected: exit 0; test count increases by aggregation + CLI tests.

- [ ] **Step 2: Walk spec success criteria**

Confirm each item in spec §11 is satisfied; update spec status to `Implemented` when done.

- [ ] **Step 3: Commit spec and plan (if not already committed)**

```bash
git add docs/superpowers/specs/2026-05-24-prescreen-hardening-and-doc-sync-design.md \
  docs/superpowers/plans/2026-05-24-prescreen-hardening-and-doc-sync.md
git commit -m "$(cat <<'EOF'
docs: add prescreen hardening spec and implementation plan

EOF
)"
```

---

## Spec Coverage Checklist

| Spec § | Task |
|---|---|
| §4 Aggregator | Task 2 |
| §5 Documentation | Task 1 (+ aggregator ✅ in Task 2) |
| §6 Exception hardening | Task 3 |
| §7 Prescreen CLI tests | Task 4 |
| §8 CLI refactor | Task 5 |
| §9 Verification | Task 6 |

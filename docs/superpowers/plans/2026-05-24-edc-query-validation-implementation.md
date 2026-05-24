# EDC Query Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `.workstreams/edc-query-validation` workstream end to end on PHI-free synthetic data, with careful validation of contracts, deterministic behavior, replay leakage controls, metrics, reports, and governance gates.

**Architecture:** Add a focused `clinique.edc` package with small modules for typed records, JSON fixture loading, timestamp-gated evidence selection, duplicate detection, candidate-query generation, benchmarking, replay, metrics, and report writing. Keep all APIs read-only; generated outputs are validation reports and governance documents, not EDC write-backs.

**Tech Stack:** Python 3.12, stdlib dataclasses/json/datetime/pathlib, pytest, Ruff, existing `clinique.substrate.provenance` concepts where useful.

---

## Completion summary

| Task | Scope | Status |
|------|-------|--------|
| Tasks 1–6: Synthetic EDC validation stack | clinique | Done |
| Internal EDC exports + prospective runs | operational (external) | Blocked |

**Status: Closed (local synthetic phase)** — verified 2026-05-24. `goal_complete` correctly remains
false until internal/prospective checklist items in
`.workstreams/edc-query-validation/release-readiness-checklist.md` are satisfied with real evidence.

## Verification record (2026-05-24)

| Check | Command | Expected |
|-------|---------|----------|
| Lint | `uv run ruff check src tests` | exit 0 |
| Tests | `uv run pytest` | all pass |
| L0–L2 reports | `uv run clinique edc-query validate …` | `local_synthetic_validation_complete: true` |
| Bundled verifier | `uv run clinique edc-query verify-workstream …` | exit nonzero; `goal_complete: false` with documented local gate failures |

---

## File Map

- Create `src/clinique/edc/__init__.py`: public exports.
- Create `src/clinique/edc/records.py`: immutable dataclasses and JSON conversion helpers.
- Create `src/clinique/edc/fixtures.py`: read-only fixture loading and validation.
- Create `src/clinique/edc/replay.py`: timestamp-gated snapshot/rule selection.
- Create `src/clinique/edc/detection.py`: deterministic candidate-query generator and duplicate detection.
- Create `src/clinique/edc/metrics.py`: confusion counts and workflow metrics.
- Create `src/clinique/edc/reports.py`: JSON report assembly and writing.
- Create `tests/fixtures/edc_query/*.json`: synthetic PHI-free fixture set.
- Create `tests/fixtures/edc_query/PROVENANCE.md`: fixture provenance.
- Create `tests/test_edc_fixtures.py`, `tests/test_edc_replay.py`, `tests/test_edc_detection.py`, `tests/test_edc_metrics_reports.py`.
- Create `.workstreams/edc-query-validation/{data-inventory.md,access-boundary.md,label-schema.json,annotation-manual.md,silent-prospective-protocol.md,controlled-rollout-gate.md,validation-summary.md,release-readiness-checklist.md}`.
- Modify `.workstreams/edc-query-validation/tracker.org`: mark completed synthetic/offline milestones with evidence.

## Task 1: Fixture Contract and Loader

**Files:**
- Create: `tests/fixtures/edc_query/snapshots.json`
- Create: `tests/fixtures/edc_query/rules.json`
- Create: `tests/fixtures/edc_query/query_logs.json`
- Create: `tests/fixtures/edc_query/labels.json`
- Create: `tests/fixtures/edc_query/PROVENANCE.md`
- Create: `tests/test_edc_fixtures.py`
- Create: `src/clinique/edc/__init__.py`
- Create: `src/clinique/edc/records.py`
- Create: `src/clinique/edc/fixtures.py`

- [x] **Step 1: Write failing fixture loader tests**

```python
from pathlib import Path

from clinique.edc.fixtures import load_fixture_bundle


FIXTURES = Path("tests/fixtures/edc_query")


def test_load_fixture_bundle_has_timestamped_snapshots_and_labels():
    bundle = load_fixture_bundle(FIXTURES)

    assert [snapshot.snapshot_id for snapshot in bundle.snapshots] == ["snap-2026-03-01", "snap-2026-03-08"]
    assert {label.query_category for label in bundle.labels} >= {"missing", "inconsistent", "impossible", "duplicate"}
    assert all(not snapshot.contains_phi for snapshot in bundle.snapshots)


def test_fixture_bundle_rejects_unblinded_or_phi_markers(tmp_path):
    fixture_dir = tmp_path / "bad"
    fixture_dir.mkdir()
    (fixture_dir / "snapshots.json").write_text(
        '[{"snapshot_id":"bad","snapshot_at":"2026-03-01T00:00:00Z","contains_phi":true,'
        '"contains_unblinded":false,"records":[]}]'
    )
    (fixture_dir / "rules.json").write_text("[]")
    (fixture_dir / "query_logs.json").write_text("[]")
    (fixture_dir / "labels.json").write_text("[]")

    try:
        load_fixture_bundle(fixture_dir)
    except ValueError as exc:
        assert "PHI" in str(exc)
    else:
        raise AssertionError("expected PHI fixture rejection")
```

- [x] **Step 2: Run RED**

Run: `uv run pytest tests/test_edc_fixtures.py -q`

Expected: FAIL because `clinique.edc` does not exist.

- [x] **Step 3: Add synthetic fixture JSON and provenance**

Use two snapshots, active/stale rules, historical queries, and labels for missing, inconsistent,
impossible, duplicate, waived/no-query, and negative cases. Use synthetic IDs such as `SUBJ-001`;
do not include names, dates of birth, free-text clinical narratives, or treatment assignments.

- [x] **Step 4: Implement immutable records and loader**

Implement frozen dataclasses for `EdcRecord`, `EdcSnapshot`, `EditCheckRule`, `QueryLog`,
`QueryLabel`, and `FixtureBundle`. Parse ISO timestamps into timezone-aware UTC datetimes.
Reject any snapshot marked `contains_phi` or `contains_unblinded`.

- [x] **Step 5: Run GREEN**

Run: `uv run pytest tests/test_edc_fixtures.py -q`

Expected: PASS.

## Task 2: Timestamp-Gated Replay and No-Write Boundary

**Files:**
- Create: `tests/test_edc_replay.py`
- Create: `src/clinique/edc/replay.py`

- [x] **Step 1: Write failing replay tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.replay import evidence_at


def test_evidence_at_excludes_future_snapshots_and_rules():
    bundle = load_fixture_bundle(Path("tests/fixtures/edc_query"))
    evidence = evidence_at(bundle, datetime(2026, 3, 2, tzinfo=timezone.utc))

    assert evidence.snapshot.snapshot_id == "snap-2026-03-01"
    assert {rule.rule_id for rule in evidence.active_rules} == {"RULE-MISSING-AE", "RULE-CONMED-AE-DATE"}
    assert "snap-2026-03-08" not in [source.source_id for source in evidence.sources]


def test_evidence_at_refuses_dates_before_first_snapshot():
    bundle = load_fixture_bundle(Path("tests/fixtures/edc_query"))

    try:
        evidence_at(bundle, datetime(2026, 2, 1, tzinfo=timezone.utc))
    except ValueError as exc:
        assert "No snapshot" in str(exc)
    else:
        raise AssertionError("expected missing snapshot failure")
```

- [x] **Step 2: Run RED**

Run: `uv run pytest tests/test_edc_replay.py -q`

Expected: FAIL because `evidence_at` is missing.

- [x] **Step 3: Implement timestamp-gated evidence**

Select the latest snapshot at or before the replay timestamp and active rules with effective
dates at or before the timestamp and no retired date before the timestamp. Return structured
source references. Do not expose any write/update/delete method.

- [x] **Step 4: Run GREEN**

Run: `uv run pytest tests/test_edc_replay.py -q`

Expected: PASS.

## Task 3: Deterministic Candidate Query Detection

**Files:**
- Create: `tests/test_edc_detection.py`
- Create: `src/clinique/edc/detection.py`

- [x] **Step 1: Write failing detection tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.replay import evidence_at


def test_detect_candidate_queries_generates_expected_categories():
    bundle = load_fixture_bundle(Path("tests/fixtures/edc_query"))
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
    by_key = {(c.subject_id, c.form, c.field): c for c in candidates}

    assert by_key[("SUBJ-001", "AE", "term")].query_category == "missing"
    assert by_key[("SUBJ-001", "ConMeds", "start_date")].query_category == "inconsistent"
    assert by_key[("SUBJ-002", "Vitals", "visit_date")].query_category == "impossible"
    assert by_key[("SUBJ-003", "Labs", "hemoglobin")].is_duplicate is True


def test_candidate_queries_are_draft_only_and_evidence_backed():
    bundle = load_fixture_bundle(Path("tests/fixtures/edc_query"))
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    assert all(candidate.draft_only for candidate in candidates)
    assert all(candidate.evidence for candidate in candidates)
```

- [x] **Step 2: Run RED**

Run: `uv run pytest tests/test_edc_detection.py -q`

Expected: FAIL because detection is missing.

- [x] **Step 3: Implement minimal deterministic rules**

Support rule kinds `required_field`, `date_order`, `future_date`, and `duplicate_existing_query`.
Generate `CandidateQuery` records with category, text, evidence refs, duplicate flag, and
`draft_only=True`.

- [x] **Step 4: Run GREEN**

Run: `uv run pytest tests/test_edc_detection.py -q`

Expected: PASS.

## Task 4: Metrics and Reports

**Files:**
- Create: `tests/test_edc_metrics_reports.py`
- Create: `src/clinique/edc/metrics.py`
- Create: `src/clinique/edc/reports.py`

- [x] **Step 1: Write failing metrics/report tests**

```python
from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.metrics import evaluate_candidates
from clinique.edc.replay import evidence_at
from clinique.edc.reports import build_offline_report, build_retrospective_report


def test_evaluate_candidates_reports_task_and_workflow_metrics():
    bundle = load_fixture_bundle(Path("tests/fixtures/edc_query"))
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))
    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    metrics = evaluate_candidates(candidates, bundle.labels, replayed_at=evidence.replayed_at)

    assert metrics.true_discrepancies_detected >= 3
    assert metrics.false_query_rate == 0
    assert metrics.duplicate_query_rate > 0
    assert metrics.median_days_earlier >= 0


def test_reports_are_json_serializable_and_include_ship_gates(tmp_path):
    bundle = load_fixture_bundle(Path("tests/fixtures/edc_query"))
    offline = build_offline_report(bundle, replayed_at=datetime(2026, 3, 8, tzinfo=timezone.utc))
    replay = build_retrospective_report(bundle)

    offline_path = tmp_path / "offline.json"
    replay_path = tmp_path / "replay.json"
    offline.write_json(offline_path)
    replay.write_json(replay_path)

    assert '"no_write_back": true' in offline_path.read_text()
    assert '"leakage_checks_passed": true' in replay_path.read_text()
```

- [x] **Step 2: Run RED**

Run: `uv run pytest tests/test_edc_metrics_reports.py -q`

Expected: FAIL because metrics/reports are missing.

- [x] **Step 3: Implement evaluation and reports**

Match candidates to labels by subject/form/field/category. Compute true detections, false query
rate, duplicate query rate, category accuracy, evidence support rate, median days earlier, and
ship-gate booleans. Reports must serialize to deterministic JSON with inputs, metrics, gates,
and provenance-like source summaries.

- [x] **Step 4: Run GREEN and full tests**

Run: `uv run pytest tests/test_edc_metrics_reports.py -q`

Expected: PASS.

Run: `uv run pytest`

Expected: PASS.

## Task 5: Governance Artifacts and Tracker Evidence

**Files:**
- Create: `.workstreams/edc-query-validation/data-inventory.md`
- Create: `.workstreams/edc-query-validation/access-boundary.md`
- Create: `.workstreams/edc-query-validation/label-schema.json`
- Create: `.workstreams/edc-query-validation/annotation-manual.md`
- Create: `.workstreams/edc-query-validation/silent-prospective-protocol.md`
- Create: `.workstreams/edc-query-validation/controlled-rollout-gate.md`
- Create: `.workstreams/edc-query-validation/validation-summary.md`
- Create: `.workstreams/edc-query-validation/release-readiness-checklist.md`
- Modify: `.workstreams/edc-query-validation/tracker.org`

- [x] **Step 1: Create governed planning artifacts**

Write the data inventory and access boundary for synthetic/local validation, label schema and
annotation manual, silent prospective protocol, controlled rollout gate, validation summary, and
release-readiness checklist. Distinguish completed synthetic validation from future internal data
and prospective phases.

- [x] **Step 2: Update tracker state with evidence**

Mark milestones 1-4 complete for the synthetic implementation once tests and generated reports
prove them. Leave milestones requiring internal data or prospective deployment as blocked or
next, with explicit blockers and evidence requirements. Do not claim internal-data validation,
silent prospective completion, or controlled rollout completion without those artifacts.

- [x] **Step 3: Verify docs**

Run: `rg -n "TBD|PLACEHOLDER|FIXME" .workstreams/edc-query-validation docs/superpowers/plans/2026-05-24-edc-query-validation-implementation.md`

Expected: no matches except intentional TODO workflow state names in org headings/properties.

## Task 6: Final Verification and Audit

**Files:**
- Inspect: `.workstreams/edc-query-validation/tracker.org`
- Inspect: `.workstreams/edc-query-validation/design.md`
- Inspect: generated reports
- Inspect: tests and source files

- [x] **Step 1: Run complete verification**

Run:

```bash
uv run ruff check src tests
uv run pytest
git diff --check
```

Expected: Ruff exits 0, pytest exits 0, diff check exits 0.

- [x] **Step 2: Requirement-by-requirement audit**

Audit every global acceptance criterion and each milestone acceptance criterion in
`.workstreams/edc-query-validation/tracker.org`. Record whether evidence proves completion,
shows incomplete work, or is blocked by missing internal/prospective data. Do not mark the whole
goal complete unless every workstream requirement is implemented and verified or explicitly
outside achievable local scope with user-approved acceptance.

- [x] **Step 3: Commit aligned changes**

Commit implementation and documentation in coherent chunks. Do not include unrelated uncommitted
files unless they are part of this workstream.


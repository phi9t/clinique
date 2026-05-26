# PrescreenBench Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static PrescreenBench Explorer that lets ML researchers and clinical/biostats readers compare agents, inspect patient-trial cases, understand source fields, and trace metric outcomes to evidence.

**Architecture:** Python exports a UI-oriented static JSON bundle from PrescreenBench split artifacts, predictions, reports, and scorer-derived annotations. The existing Vite/React `explorer/` app loads that bundle as a third top-level family and renders overview metrics, metric slices, a case table, and a case deep dive. Playwright validates the full export-to-browser path.

**Tech Stack:** Python 3.12 stdlib + existing `clinique` modules, pytest, Vite, React 19, TypeScript, lucide-react, Playwright.

---

## Current Worktree Note

The repo currently has uncommitted PrescreenBench implementation files and docs. Do not revert or
discard them. The plan below assumes those files remain present:

- `src/clinique/benchmarks/prescreenbench/*`
- `src/clinique/cli/benchmark.py`
- `tests/test_prescreenbench_*.py`
- `benchmarks/prescreenbench/*`

Before executing tasks, run:

```bash
git status --short
```

Expected: dirty worktree with the above benchmark files. Work with those changes.

---

## File Structure

Python benchmark/export layer:

- Create `src/clinique/benchmarks/prescreenbench/explorer_export.py`
  - Builds `index.json`, `definitions.json`, and one split bundle per split.
  - Runs deterministic baselines or loads custom predictions/reports.
  - Computes per-case/per-criterion grader annotations and evidence offsets.
- Modify `src/clinique/benchmarks/prescreenbench/score.py`
  - Extract a reusable annotation helper so exporter and scorer share evidence/gate semantics.
- Modify `src/clinique/cli/benchmark.py`
  - Add `export-explorer` handler.
- Modify `src/clinique/cli/parser.py`
  - Add parser flags for `benchmark prescreen export-explorer`.
- Create `tests/test_prescreenbench_explorer_export.py`
  - Exporter determinism, annotation correctness, quote offsets, malformed input behavior.
- Modify `tests/test_prescreenbench_cli.py`
  - CLI coverage for export command.

Committed static data:

- Create `explorer/public/data/prescreenbench/index.json`
- Create `explorer/public/data/prescreenbench/definitions.json`
- Create `explorer/public/data/prescreenbench/synthetic.json`
- Create `explorer/public/data/prescreenbench/lite.json`

Frontend:

- Modify `explorer/src/App.tsx`
  - Add `PrescreenBench` as third family.
- Create `explorer/src/prescreenbench/types.ts`
  - TypeScript interfaces and JSON fetch helpers.
- Create `explorer/src/prescreenbench/PrescreenBenchExplorer.tsx`
  - Top-level orchestration, state, loading, filters.
- Create `explorer/src/prescreenbench/Overview.tsx`
  - Split/agent selection and metric cards.
- Create `explorer/src/prescreenbench/CaseTable.tsx`
  - Filtered case list.
- Create `explorer/src/prescreenbench/CaseDeepDive.tsx`
  - Trial/patient panels, criterion comparison grid, evidence document highlight.
- Create `explorer/src/prescreenbench/HelpText.tsx`
  - Compact definitions and primer text rendering.
- Modify `explorer/src/index.css`
  - Add focused PrescreenBench dashboard styles using the existing design tokens.

Frontend/E2E validation:

- Modify `explorer/package.json`
  - Add Playwright scripts and dependency.
- Create `explorer/playwright.config.ts`
- Create `explorer/tests/prescreenbench.spec.ts`

---

### Task 1: Shared Grader Annotation Helper

**Files:**
- Modify: `src/clinique/benchmarks/prescreenbench/score.py`
- Test: `tests/test_prescreenbench_score.py`

- [ ] **Step 1: Write failing tests for criterion annotations**

Add this import to `tests/test_prescreenbench_score.py`:

```python
from clinique.benchmarks.prescreenbench.score import annotate_case
```

Add this test:

```python
def test_annotate_case_reports_core_and_gate_outcomes(synthetic):
    case = synthetic.cases[0]
    rows, _ = run(synthetic, "keyword_rule")
    raw = {r["case_id"]: r for r in rows}[case.case_id]

    annotation = annotate_case(
        case=case,
        gold=synthetic.gold[case.case_id],
        corpus=synthetic.corpora_by_id[case.patient_id],
        raw_prediction=raw,
    )

    assert annotation["case_errors"] == []
    assert annotation["schema_errors"] == []
    assert annotation["overall_prediction"] == raw["overall_recommendation"]
    assert isinstance(annotation["overall_correct"], bool)
    assert annotation["criteria"]
    first = annotation["criteria"][0]
    assert first.keys() >= {
        "criterion_id",
        "gold_label",
        "prediction",
        "correct",
        "evidence_present",
        "quotes_verbatim",
        "fabricated_quote_count",
        "unsupported_decision",
        "unsafe_clearance",
        "blocking_gold",
        "blocking_pred",
        "counts_toward_core_metrics",
        "counts_toward_gate_metrics",
        "evidence_checks",
    }
    assert any(c["counts_toward_core_metrics"] for c in annotation["criteria"])
    assert any(c["counts_toward_gate_metrics"] for c in annotation["criteria"])
```

Add this quote-offset test:

```python
def test_annotate_case_computes_evidence_quote_offsets(synthetic):
    case = synthetic.cases[0]
    rows, _ = run(synthetic, "clinique_rule")
    raw = {r["case_id"]: r for r in rows}[case.case_id]

    annotation = annotate_case(
        case=case,
        gold=synthetic.gold[case.case_id],
        corpus=synthetic.corpora_by_id[case.patient_id],
        raw_prediction=raw,
    )

    checks = [
        check
        for criterion in annotation["criteria"]
        for check in criterion["evidence_checks"]
        if check["quote_found"]
    ]
    assert checks
    check = checks[0]
    doc = next(
        d
        for d in synthetic.corpora_by_id[case.patient_id].documents
        if d.doc_id == check["doc_id"]
    )
    assert doc.text[check["start_char"] : check["end_char"]] == check["quote"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_prescreenbench_score.py::test_annotate_case_reports_core_and_gate_outcomes tests/test_prescreenbench_score.py::test_annotate_case_computes_evidence_quote_offsets -q
```

Expected: FAIL with `ImportError` or missing `annotate_case`.

- [ ] **Step 3: Implement annotation helper**

In `src/clinique/benchmarks/prescreenbench/score.py`, add these helpers above `score()`:

```python
def _evidence_checks(pred: PredCriterion | None, corpus: PatientCorpus | None) -> list[dict[str, Any]]:
    if pred is None:
        return []
    docs = {d.doc_id: d.text for d in corpus.documents} if corpus is not None else {}
    checks: list[dict[str, Any]] = []
    for ev in pred.evidence:
        doc_text = docs.get(ev.doc_id) if isinstance(ev.doc_id, str) else None
        quote = ev.quote if isinstance(ev.quote, str) else ""
        start = doc_text.find(quote) if doc_text is not None and quote else -1
        checks.append(
            {
                "doc_id": ev.doc_id,
                "quote": ev.quote,
                "document_found": doc_text is not None,
                "quote_found": start >= 0,
                "empty_quote": isinstance(ev.quote, str) and not ev.quote.strip(),
                "start_char": start if start >= 0 else None,
                "end_char": start + len(quote) if start >= 0 else None,
            }
        )
    return checks


def _criterion_annotation(
    *,
    outcome: M.CriterionOutcome,
    pred: PredCriterion | None,
    corpus: PatientCorpus | None,
    criterion_text: str,
    clinical_domain: str,
    counts_toward_core_metrics: bool,
    counts_toward_gate_metrics: bool,
    schema_errors: list[str],
) -> dict[str, Any]:
    return {
        "criterion_id": outcome.criterion_id,
        "criterion_text": criterion_text,
        "criterion_type": outcome.criterion_type,
        "clinical_domain": clinical_domain,
        "is_safety_critical": outcome.is_safety_critical,
        "gold_label": outcome.gold,
        "prediction": outcome.pred,
        "correct": M.is_correct(outcome),
        "evidence_present": outcome.evidence_present,
        "quotes_verbatim": outcome.quotes_verbatim,
        "fabricated_quote_count": outcome.fabricated_quote_count,
        "unsupported_decision": M.requires_evidence(outcome.pred)
        and not M.evidence_supported(outcome),
        "unsafe_clearance": M.is_unsafe_clearance(outcome),
        "blocking_gold": M.is_blocking(outcome.gold, outcome.criterion_type),
        "blocking_pred": M.is_blocking(outcome.pred, outcome.criterion_type),
        "counts_toward_core_metrics": counts_toward_core_metrics,
        "counts_toward_gate_metrics": counts_toward_gate_metrics,
        "schema_errors": schema_errors,
        "rationale": pred.rationale if pred is not None else "",
        "evidence_checks": _evidence_checks(pred, corpus),
    }
```

Add `annotate_case(...)` using the same control flow as `score()` for one case:

```python
def annotate_case(
    *,
    case,
    gold,
    corpus: PatientCorpus | None,
    raw_prediction: dict[str, Any] | None,
) -> dict[str, Any]:
    case_errors: list[str] = []
    if corpus is None:
        case_errors.append(f"{case.case_id}: missing corpus for patient {case.patient_id}")
    if raw_prediction is not None and raw_prediction.get("case_id") != case.case_id:
        case_errors.append(f"{case.case_id}: case_id mismatch: {raw_prediction.get('case_id')!r}")
        raw_prediction = None

    schema_errors = (
        validate_submission(raw_prediction) if raw_prediction is not None else ["missing prediction"]
    )
    pred_by_id: dict[str, PredCriterion] = {}
    predicted: tuple[PredCriterion, ...] = ()
    overall_pred: str | None = None
    if raw_prediction is not None and not schema_errors:
        try:
            sub = SubmissionPacket.from_dict(raw_prediction)
            pred_by_id = {c.criterion_id: c for c in sub.criteria}
            predicted = sub.criteria
            overall_pred = sub.overall_recommendation
        except (KeyError, TypeError, ValueError):
            schema_errors = ["unparseable submission"]

    annotations: list[dict[str, Any]] = []
    gold_ids = {g.criterion_id for g in gold.criterion_labels}
    for gold_crit in gold.criterion_labels:
        pred = pred_by_id.get(gold_crit.criterion_id) if not schema_errors else None
        pred_label = pred.prediction if pred is not None else "unknown"
        present, verbatim, fabricated = _evidence_flags(pred, corpus)
        if schema_errors:
            present, verbatim, fabricated = False, True, 0
        if (
            pred is not None
            and gold_crit.clinical_domain == "demographic"
            and pred.rationale
            and M.requires_evidence(pred_label)
        ):
            present, verbatim, fabricated = True, True, 0
        outcome = M.CriterionOutcome(
            criterion_id=gold_crit.criterion_id,
            criterion_type=gold_crit.criterion_type,
            gold=gold_crit.label,
            pred=pred_label,
            is_safety_critical=gold_crit.is_safety_critical,
            evidence_present=present,
            quotes_verbatim=verbatim,
            fabricated_quote_count=fabricated,
        )
        annotations.append(
            _criterion_annotation(
                outcome=outcome,
                pred=pred,
                corpus=corpus,
                criterion_text=pred.raw_text if pred is not None else "",
                clinical_domain=gold_crit.clinical_domain,
                counts_toward_core_metrics=True,
                counts_toward_gate_metrics=True,
                schema_errors=schema_errors,
            )
        )

    if not schema_errors and case.task == "end_to_end_packet":
        for crit in predicted:
            if crit.criterion_id in gold_ids:
                continue
            present, verbatim, fabricated = _evidence_flags(crit, corpus)
            if not crit.evidence:
                present, verbatim = True, True
            outcome = M.CriterionOutcome(
                criterion_id=crit.criterion_id,
                criterion_type=crit.criterion_type,
                gold="met" if crit.criterion_type == "exclusion" else "not_met",
                pred=crit.prediction,
                is_safety_critical=False,
                evidence_present=present,
                quotes_verbatim=verbatim,
                fabricated_quote_count=fabricated,
            )
            annotations.append(
                _criterion_annotation(
                    outcome=outcome,
                    pred=crit,
                    corpus=corpus,
                    criterion_text=crit.raw_text,
                    clinical_domain=crit.clinical_domain,
                    counts_toward_core_metrics=False,
                    counts_toward_gate_metrics=True,
                    schema_errors=[],
                )
            )

    return {
        "case_id": case.case_id,
        "case_errors": case_errors,
        "schema_errors": schema_errors,
        "overall_prediction": overall_pred,
        "overall_correct": overall_pred == gold.overall_label
        if case.task != "criterion_judgment" and not schema_errors
        else None,
        "criteria": annotations,
    }
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_prescreenbench_score.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clinique/benchmarks/prescreenbench/score.py tests/test_prescreenbench_score.py
git commit -m "feat(prescreenbench): expose case grader annotations"
```

---

### Task 2: Python Explorer Export Module

**Files:**
- Create: `src/clinique/benchmarks/prescreenbench/explorer_export.py`
- Create: `tests/test_prescreenbench_explorer_export.py`

- [ ] **Step 1: Write failing exporter tests**

Create `tests/test_prescreenbench_explorer_export.py`:

```python
"""Tests for PrescreenBench static explorer export."""

from __future__ import annotations

import json

from clinique.benchmarks.prescreenbench.explorer_export import (
    DEFAULT_DEMO_AGENTS,
    build_definitions,
    build_split_bundle,
    export_explorer,
)
from clinique.benchmarks.prescreenbench.load import load_split


EXPECTED_FILES = {
    "index.json",
    "definitions.json",
    "synthetic.json",
    "lite.json",
}


def test_definitions_include_metric_and_label_help():
    definitions = build_definitions()
    assert definitions["labels"]["unknown"]["plain"]
    assert definitions["metrics"]["unsafe_clearance_rate"]["plain"]
    assert definitions["primer"]["eligibility_criteria"]


def test_build_split_bundle_contains_cases_agents_and_annotations():
    split = load_split("synthetic")
    bundle = build_split_bundle(split, agents=DEFAULT_DEMO_AGENTS)
    assert bundle["split"] == "synthetic"
    assert {a["agent"] for a in bundle["agents"]} == set(DEFAULT_DEMO_AGENTS)
    assert bundle["cases"]
    first = bundle["cases"][0]
    assert first.keys() >= {"case", "trial", "patient", "gold", "agent_outputs", "grader"}
    for agent in DEFAULT_DEMO_AGENTS:
        assert agent in first["agent_outputs"]
        assert agent in first["grader"]
        assert first["grader"][agent]["criteria"]


def test_export_writes_expected_files(tmp_path):
    written = export_explorer(tmp_path, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    assert set(written) == EXPECTED_FILES
    for name in EXPECTED_FILES:
        assert (tmp_path / name).is_file()


def test_export_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    export_explorer(a, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    export_explorer(b, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    for name in EXPECTED_FILES:
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_exported_quote_offsets_match_documents(tmp_path):
    export_explorer(tmp_path, splits=("synthetic",), agents=("clinique_rule",))
    bundle = json.loads((tmp_path / "synthetic.json").read_text())
    checks = [
        check
        for case in bundle["cases"]
        for criterion in case["grader"]["clinique_rule"]["criteria"]
        for check in criterion["evidence_checks"]
        if check["quote_found"]
    ]
    assert checks
    check = checks[0]
    docs = {
        doc["doc_id"]: doc["text"]
        for case in bundle["cases"]
        for doc in case["patient"]["documents"]
    }
    assert docs[check["doc_id"]][check["start_char"] : check["end_char"]] == check["quote"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_prescreenbench_explorer_export.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement exporter module**

Create `src/clinique/benchmarks/prescreenbench/explorer_export.py`:

```python
"""Static JSON export for the PrescreenBench Explorer UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinique.prescreen import metrics as M
from clinique.prescreen.explorer_export import FIELD_DOCS, find_repo_root
from clinique.prescreen.schemas import PREDICTIONS, RECOMMENDATIONS

from . import BENCHMARK_ID, SPLITS
from .load import SplitData, load_split
from .report import to_json
from .score import annotate_case, load_predictions, run, score

DEFAULT_DEMO_AGENTS = ("always_unknown", "keyword_rule", "clinique_rule")


def default_out_dir() -> Path:
    return find_repo_root() / "explorer/public/data/prescreenbench"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_definitions() -> dict[str, Any]:
    return {
        "labels": {
            "met": {"plain": "The patient satisfies this criterion."},
            "not_met": {"plain": "The patient does not satisfy this criterion."},
            "unknown": {
                "plain": "Available records do not support a definite call; this is the safe default."
            },
            "not_applicable": {"plain": "The criterion does not apply to this patient/case."},
            "conflicting_evidence": {
                "plain": "The record contains evidence pointing in incompatible directions."
            },
        },
        "recommendations": {
            "potentially_eligible": {"plain": "No known blocking criterion was found."},
            "needs_review": {"plain": "Human review is needed before any screening decision."},
            "likely_ineligible": {"plain": "At least one blocking criterion appears present."},
        },
        "metrics": {
            "score": {"plain": "Weighted summary score after hard-gate penalties."},
            "criterion_macro_f1": {"plain": "Unweighted mean F1 across labels present in gold or prediction."},
            "evidence_support_accuracy": {
                "plain": "Among met/not_met predictions, the fraction backed by present verbatim evidence."
            },
            "unsafe_clearance_rate": {
                "plain": "Rate of clearing a possibly disqualifying criterion."
            },
            "unsupported_decision_count": {
                "plain": "Number of definite met/not_met predictions without required evidence."
            },
            "fabricated_quote_count": {
                "plain": "Number of cited quotes not found verbatim in the cited document."
            },
            "schema_valid_rate": {"plain": "Fraction of submitted case packets passing schema validation."},
            "blocking_criterion_recall": {
                "plain": "Fraction of gold blocking criteria predicted as blocking."
            },
        },
        "hard_gates": M.HARD_GATES,
        "primer": {
            "eligibility_criteria": (
                "Clinical-trial criteria are split into inclusion requirements and exclusion "
                "disqualifiers. Prescreening produces a review packet, not an enrollment decision."
            ),
            "evidence_grounding": (
                "Definite calls must cite patient evidence. Unknown is preferable to unsupported clearance."
            ),
            "biostats_reading": (
                "Macro-F1 treats each prediction label evenly, while safety gates prevent averaging away "
                "clinically risky errors."
            ),
        },
        "field_docs": FIELD_DOCS,
        "prediction_vocab": sorted(PREDICTIONS),
        "recommendation_vocab": sorted(RECOMMENDATIONS),
    }


def _agent_rows(split: SplitData, agent: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows, errors = run(split, agent)
    predictions = {row["case_id"]: row for row in rows}
    report = score(split, predictions)
    payload = to_json(report, agent=agent)
    if errors:
        payload["run_errors"] = errors
    return predictions, payload


def build_split_bundle(
    split: SplitData,
    *,
    agents: tuple[str, ...] = DEFAULT_DEMO_AGENTS,
    custom_predictions: dict[str, dict[str, dict[str, Any]]] | None = None,
    custom_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    predictions_by_agent: dict[str, dict[str, dict[str, Any]]] = {}
    reports_by_agent: dict[str, dict[str, Any]] = {}

    for agent in agents:
        predictions, report = _agent_rows(split, agent)
        predictions_by_agent[agent] = predictions
        reports_by_agent[agent] = report

    for agent, predictions in (custom_predictions or {}).items():
        predictions_by_agent[agent] = predictions
        report = custom_reports.get(agent) if custom_reports else None
        reports_by_agent[agent] = report or to_json(score(split, predictions), agent=agent)

    case_payloads: list[dict[str, Any]] = []
    for case in split.cases:
        gold = split.gold.get(case.case_id)
        trial = split.trials_by_id.get(case.trial_id)
        patient = split.corpora_by_id.get(case.patient_id)
        if gold is None:
            continue
        graders = {
            agent: annotate_case(
                case=case,
                gold=gold,
                corpus=patient,
                raw_prediction=predictions.get(case.case_id),
            )
            for agent, predictions in predictions_by_agent.items()
        }
        case_payloads.append(
            {
                "case": case.to_dict(),
                "trial": trial.to_dict() if trial is not None else None,
                "patient": patient.to_dict() if patient is not None else None,
                "gold": gold.to_dict(),
                "agent_outputs": {
                    agent: predictions.get(case.case_id)
                    for agent, predictions in predictions_by_agent.items()
                },
                "grader": graders,
            }
        )

    return {
        "split": split.split,
        "benchmark_id": BENCHMARK_ID,
        "task_types": sorted({case.task for case in split.cases}),
        "agents": [
            {"agent": agent, "report": reports_by_agent[agent]}
            for agent in sorted(predictions_by_agent)
        ],
        "cases": case_payloads,
    }


def export_explorer(
    out_dir: str | Path | None = None,
    *,
    splits: tuple[str, ...] = SPLITS,
    agents: tuple[str, ...] = DEFAULT_DEMO_AGENTS,
    custom_prediction_paths: dict[str, Path] | None = None,
    custom_report_paths: dict[str, Path] | None = None,
    base: str | Path | None = None,
) -> list[str]:
    out = Path(out_dir) if out_dir is not None else default_out_dir()
    written: list[str] = []
    index: list[dict[str, Any]] = []
    _write_json(out / "definitions.json", build_definitions())
    written.append("definitions.json")

    custom_predictions = {
        agent: load_predictions(path)
        for agent, path in (custom_prediction_paths or {}).items()
    }
    custom_reports = {
        agent: json.loads(Path(path).read_text(encoding="utf-8"))
        for agent, path in (custom_report_paths or {}).items()
    }

    for split_name in splits:
        split = load_split(split_name, base=base)
        bundle = build_split_bundle(
            split,
            agents=agents,
            custom_predictions=custom_predictions,
            custom_reports=custom_reports,
        )
        filename = f"{split_name}.json"
        _write_json(out / filename, bundle)
        written.append(filename)
        index.append(
            {
                "split": split_name,
                "benchmark_id": BENCHMARK_ID,
                "case_count": len(bundle["cases"]),
                "agents": [agent["agent"] for agent in bundle["agents"]],
                "task_types": bundle["task_types"],
            }
        )

    _write_json(out / "index.json", index)
    written.append("index.json")
    return sorted(written)
```

- [ ] **Step 4: Run exporter tests**

Run:

```bash
uv run pytest tests/test_prescreenbench_explorer_export.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clinique/benchmarks/prescreenbench/explorer_export.py tests/test_prescreenbench_explorer_export.py
git commit -m "feat(prescreenbench): export explorer bundles"
```

---

### Task 3: Export CLI

**Files:**
- Modify: `src/clinique/cli/parser.py`
- Modify: `src/clinique/cli/benchmark.py`
- Modify: `tests/test_prescreenbench_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_prescreenbench_cli.py`:

```python
def test_export_explorer_writes_static_bundle(tmp_path):
    out = tmp_path / "prescreenbench"
    rc = main(
        [
            "benchmark",
            "prescreen",
            "export-explorer",
            "--split",
            "synthetic",
            "--agents",
            "always_unknown,keyword_rule,clinique_rule",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert (out / "index.json").is_file()
    assert (out / "definitions.json").is_file()
    assert (out / "synthetic.json").is_file()


def test_export_explorer_accepts_custom_prediction(tmp_path):
    pred = tmp_path / "pred.jsonl"
    out = tmp_path / "bundle"
    assert (
        main(
            [
                "benchmark",
                "prescreen",
                "run",
                "--split",
                "synthetic",
                "--agent",
                "clinique_rule",
                "--out",
                str(pred),
            ]
        )
        == 0
    )
    rc = main(
        [
            "benchmark",
            "prescreen",
            "export-explorer",
            "--split",
            "synthetic",
            "--agents",
            "",
            "--prediction",
            f"custom={pred}",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    payload = json.loads((out / "synthetic.json").read_text())
    assert [agent["agent"] for agent in payload["agents"]] == ["custom"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_prescreenbench_cli.py::test_export_explorer_writes_static_bundle tests/test_prescreenbench_cli.py::test_export_explorer_accepts_custom_prediction -q
```

Expected: FAIL because `export-explorer` parser command does not exist.

- [ ] **Step 3: Add parser command**

In `src/clinique/cli/parser.py`, inside `_add_benchmark_parser`, after the `score` parser:

```python
    export = pb_sub.add_parser("export-explorer", help="export PrescreenBench explorer JSON")
    export.add_argument("--split", action="append", help="split to export; repeatable")
    export.add_argument(
        "--agents",
        default="always_unknown,keyword_rule,clinique_rule",
        help="comma-separated deterministic baselines to run",
    )
    export.add_argument(
        "--prediction",
        action="append",
        default=[],
        help="custom prediction as agent=path; repeatable",
    )
    export.add_argument(
        "--report",
        action="append",
        default=[],
        help="optional custom report as agent=path; repeatable",
    )
    export.add_argument("--out", help="output directory")
    export.add_argument("--data-dir", help="override split base dir")
```

- [ ] **Step 4: Add CLI handler**

In `src/clinique/cli/benchmark.py`, update `handle_benchmark`:

```python
    if args.prescreenbench_command == "export-explorer":
        return _export_explorer(args)
```

Add helpers:

```python
def _parse_mapping(items: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"expected agent=path, got {item!r}")
        agent, path = item.split("=", 1)
        if not agent or not path:
            raise ValueError(f"expected agent=path, got {item!r}")
        parsed[agent.replace("-", "_")] = Path(path)
    return parsed


def _export_explorer(args: argparse.Namespace) -> int:
    from clinique.benchmarks.prescreenbench import SPLITS
    from clinique.benchmarks.prescreenbench.explorer_export import (
        DEFAULT_DEMO_AGENTS,
        export_explorer,
    )

    try:
        agents = tuple(
            a.strip().replace("-", "_")
            for a in (args.agents or "").split(",")
            if a.strip()
        )
        splits = tuple(args.split or SPLITS)
        prediction_paths = _parse_mapping(args.prediction)
        report_paths = _parse_mapping(args.report)
        written = export_explorer(
            args.out,
            splits=splits,
            agents=agents or (),
            custom_prediction_paths=prediction_paths,
            custom_report_paths=report_paths,
            base=args.data_dir,
        )
    except (OSError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"benchmark prescreen export-explorer failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"wrote PrescreenBench explorer bundle ({len(written)} files) to {args.out or 'default'}",
        file=sys.stderr,
    )
    return 0
```

If ruff reports `DEFAULT_DEMO_AGENTS` as unused, remove that import.

- [ ] **Step 5: Run CLI tests**

Run:

```bash
uv run pytest tests/test_prescreenbench_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/clinique/cli/parser.py src/clinique/cli/benchmark.py tests/test_prescreenbench_cli.py
git commit -m "feat(prescreenbench): add explorer export CLI"
```

---

### Task 4: Commit Demo Explorer Data

**Files:**
- Create: `explorer/public/data/prescreenbench/index.json`
- Create: `explorer/public/data/prescreenbench/definitions.json`
- Create: `explorer/public/data/prescreenbench/synthetic.json`
- Create: `explorer/public/data/prescreenbench/lite.json`
- Modify: `tests/test_prescreenbench_explorer_export.py`

- [ ] **Step 1: Add committed snapshot test**

Add to `tests/test_prescreenbench_explorer_export.py`:

```python
from clinique.benchmarks.prescreenbench.explorer_export import default_out_dir


def test_committed_prescreenbench_explorer_snapshot_matches_export(tmp_path):
    export_explorer(tmp_path, splits=("synthetic", "lite"), agents=DEFAULT_DEMO_AGENTS)
    committed = default_out_dir()
    for name in EXPECTED_FILES:
        assert (tmp_path / name).read_bytes() == (committed / name).read_bytes(), name
```

- [ ] **Step 2: Run export command**

Run:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --split lite \
  --agents always_unknown,keyword_rule,clinique_rule \
  --out explorer/public/data/prescreenbench
```

Expected: files written under `explorer/public/data/prescreenbench`.

- [ ] **Step 3: Run snapshot tests**

Run:

```bash
uv run pytest tests/test_prescreenbench_explorer_export.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add explorer/public/data/prescreenbench tests/test_prescreenbench_explorer_export.py
git commit -m "data(prescreenbench): add explorer demo bundles"
```

---

### Task 5: Frontend Types And App Family Switch

**Files:**
- Create: `explorer/src/prescreenbench/types.ts`
- Modify: `explorer/src/App.tsx`

- [ ] **Step 1: Add TypeScript types**

Create `explorer/src/prescreenbench/types.ts`:

```ts
import { dataUrl } from '../lib/assets'

export interface ScoreReport {
  split: string
  benchmark_id: string
  cases: number
  criterion_total: number
  schema_valid_rate: number
  criterion_accuracy: number
  criterion_macro_f1: number
  evidence_support_accuracy: number
  blocking_criterion_recall: number
  overall_recommendation_accuracy: number
  unknown_precision: number
  unknown_recall: number
  unsafe_clearance_rate: number
  unsafe_clearance_count: number
  unsupported_decision_count: number
  fabricated_quote_count: number
  score: number
  hard_gate_breaches: string[]
  passed_hard_gates: boolean
  per_class_f1: Record<string, { precision: number; recall: number; f1: number; support: number }>
  errors: string[]
  agent?: string
}

export interface BenchmarkIndexEntry {
  split: string
  benchmark_id: string
  case_count: number
  agents: string[]
  task_types: string[]
}

export interface DefinitionsPayload {
  labels: Record<string, { plain: string }>
  recommendations: Record<string, { plain: string }>
  metrics: Record<string, { plain: string }>
  hard_gates: Record<string, number>
  primer: Record<string, string>
  field_docs: Record<string, Record<string, { type: string; description: string; vocab?: string[] }>>
  prediction_vocab: string[]
  recommendation_vocab: string[]
}

export interface EvidenceCheck {
  doc_id: string
  quote: string
  document_found: boolean
  quote_found: boolean
  empty_quote: boolean
  start_char: number | null
  end_char: number | null
}

export interface CriterionAnnotation {
  criterion_id: string
  criterion_text: string
  criterion_type: 'inclusion' | 'exclusion'
  clinical_domain: string
  is_safety_critical: boolean
  gold_label: string
  prediction: string
  correct: boolean
  evidence_present: boolean
  quotes_verbatim: boolean
  fabricated_quote_count: number
  unsupported_decision: boolean
  unsafe_clearance: boolean
  blocking_gold: boolean
  blocking_pred: boolean
  counts_toward_core_metrics: boolean
  counts_toward_gate_metrics: boolean
  schema_errors: string[]
  rationale: string
  evidence_checks: EvidenceCheck[]
}

export interface CaseGrader {
  case_id: string
  case_errors: string[]
  schema_errors: string[]
  overall_prediction: string | null
  overall_correct: boolean | null
  criteria: CriterionAnnotation[]
}

export interface BenchmarkAgent {
  agent: string
  report: ScoreReport
}

export interface BenchmarkCase {
  case_id: string
  trial_id: string
  patient_id: string
  patient_source: string
  snapshot_date: string | null
  task: string
}

export interface TrialRecord {
  trial_id: string
  title: string
  conditions: string[]
  phase: string | null
  recruitment_status: string | null
  eligibility_text: string
  sex: string | null
  minimum_age: { raw: string | null; years: number | null }
  maximum_age: { raw: string | null; years: number | null }
  sponsor: string | null
}

export interface PatientDocument {
  doc_id: string
  patient_id: string
  date: string | null
  source_type: string
  text: string
  structured: Record<string, unknown>
}

export interface PatientRecord {
  patient_id: string
  snapshot_date: string | null
  source: string
  demographics: Record<string, unknown>
  documents: PatientDocument[]
}

export interface GoldLabel {
  case_id: string
  overall_label: string
  criterion_labels: Array<{
    criterion_id: string
    label: string
    criterion_type: string
    clinical_domain: string
    is_safety_critical: boolean
  }>
}

export interface ExplorerCase {
  case: BenchmarkCase
  trial: TrialRecord | null
  patient: PatientRecord | null
  gold: GoldLabel
  agent_outputs: Record<string, unknown>
  grader: Record<string, CaseGrader>
}

export interface SplitBundle {
  split: string
  benchmark_id: string
  task_types: string[]
  agents: BenchmarkAgent[]
  cases: ExplorerCase[]
}

export const BENCHMARK_BASE = dataUrl('data/prescreenbench')

export async function fetchBenchmarkJson<T>(filename: string): Promise<T> {
  const res = await fetch(`${BENCHMARK_BASE}/${filename}?t=${Date.now()}`)
  if (!res.ok) {
    throw new Error(`Failed to load ${filename} (HTTP ${res.status})`)
  }
  return res.json() as Promise<T>
}

export function formatMetric(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3)
}
```

- [ ] **Step 2: Wire third app family**

Modify `explorer/src/App.tsx`:

```ts
import PrescreenBenchExplorer from './prescreenbench/PrescreenBenchExplorer'

export type DatasetFamily = 'cdisc' | 'prescreen' | 'prescreenbench'
```

Update the paragraph:

```tsx
{family === 'cdisc'
  ? 'FDA-pilot CDISC ADaM datasets & metadata validation dashboard'
  : family === 'prescreen'
    ? 'Prescreen L0 public data — schema, distributions, drill-down & conformance'
    : 'PrescreenBench — agent comparison, evidence grounding, and grader analysis'}
```

Add a third switch button:

```tsx
<button
  type="button"
  className={`family-switch-btn ${family === 'prescreenbench' ? 'active' : ''}`}
  aria-pressed={family === 'prescreenbench'}
  onClick={() => setFamily('prescreenbench')}
>
  PrescreenBench
</button>
```

Update main content:

```tsx
{family === 'cdisc' ? (
  <CdiscExplorer />
) : family === 'prescreen' ? (
  <PrescreenExplorer />
) : (
  <PrescreenBenchExplorer />
)}
```

- [ ] **Step 3: Add temporary stub component**

Create `explorer/src/prescreenbench/PrescreenBenchExplorer.tsx`:

```tsx
export default function PrescreenBenchExplorer() {
  return (
    <section className="card-view prescreenbench-shell" aria-label="PrescreenBench Explorer">
      <h2>PrescreenBench</h2>
      <p>Agent comparison and evidence-grounded grader analysis.</p>
    </section>
  )
}
```

- [ ] **Step 4: Build frontend**

Run:

```bash
cd explorer && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add explorer/src/App.tsx explorer/src/prescreenbench/types.ts explorer/src/prescreenbench/PrescreenBenchExplorer.tsx
git commit -m "feat(explorer): add PrescreenBench family"
```

---

### Task 6: PrescreenBench Overview And Filters

**Files:**
- Modify: `explorer/src/prescreenbench/PrescreenBenchExplorer.tsx`
- Create: `explorer/src/prescreenbench/Overview.tsx`
- Create: `explorer/src/prescreenbench/HelpText.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Create help component**

Create `explorer/src/prescreenbench/HelpText.tsx`:

```tsx
import type { DefinitionsPayload } from './types'

export function HelpText({
  title,
  text,
}: {
  title: string
  text: string
}) {
  return (
    <span className="pb-help" title={`${title}: ${text}`} aria-label={`${title}: ${text}`}>
      ?
    </span>
  )
}

export function MetricHelp({
  definitions,
  metric,
}: {
  definitions: DefinitionsPayload
  metric: string
}) {
  const text = definitions.metrics[metric]?.plain ?? metric
  return <HelpText title={metric} text={text} />
}
```

- [ ] **Step 2: Create overview component**

Create `explorer/src/prescreenbench/Overview.tsx`:

```tsx
import { CheckCircle2, ShieldAlert } from 'lucide-react'
import { formatMetric } from './types'
import type { DefinitionsPayload, SplitBundle } from './types'
import { MetricHelp } from './HelpText'

const METRICS = [
  'score',
  'criterion_macro_f1',
  'evidence_support_accuracy',
  'unsafe_clearance_rate',
  'unsupported_decision_count',
  'fabricated_quote_count',
  'schema_valid_rate',
] as const

export default function Overview({
  bundle,
  definitions,
  selectedAgents,
  onToggleAgent,
}: {
  bundle: SplitBundle
  definitions: DefinitionsPayload
  selectedAgents: string[]
  onToggleAgent: (agent: string) => void
}) {
  return (
    <div className="pb-overview">
      <div className="pb-agent-row" aria-label="Agent filters">
        {bundle.agents.map(({ agent, report }) => (
          <label key={agent} className="pb-agent-toggle">
            <input
              type="checkbox"
              checked={selectedAgents.includes(agent)}
              onChange={() => onToggleAgent(agent)}
            />
            <span>{agent}</span>
            {report.passed_hard_gates ? (
              <CheckCircle2 size={14} className="text-success" aria-hidden="true" />
            ) : (
              <ShieldAlert size={14} className="text-danger" aria-hidden="true" />
            )}
          </label>
        ))}
      </div>

      <div className="pb-metric-grid">
        {bundle.agents
          .filter(({ agent }) => selectedAgents.includes(agent))
          .map(({ agent, report }) => (
            <article key={agent} className="pb-agent-card">
              <h3>{agent}</h3>
              <div className={report.passed_hard_gates ? 'pb-gate-pass' : 'pb-gate-fail'}>
                {report.passed_hard_gates ? 'Gates pass' : `Gates fail: ${report.hard_gate_breaches.join(', ')}`}
              </div>
              <dl className="pb-metrics">
                {METRICS.map((metric) => (
                  <div key={metric}>
                    <dt>
                      {metric}
                      <MetricHelp definitions={definitions} metric={metric} />
                    </dt>
                    <dd>{formatMetric(Number(report[metric]))}</dd>
                  </div>
                ))}
              </dl>
            </article>
          ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Load bundle and definitions**

Replace the stub in `PrescreenBenchExplorer.tsx` with:

```tsx
import { useEffect, useMemo, useState } from 'react'
import Overview from './Overview'
import type { BenchmarkIndexEntry, DefinitionsPayload, SplitBundle } from './types'
import { fetchBenchmarkJson } from './types'

export default function PrescreenBenchExplorer() {
  const [index, setIndex] = useState<BenchmarkIndexEntry[]>([])
  const [definitions, setDefinitions] = useState<DefinitionsPayload | null>(null)
  const [bundle, setBundle] = useState<SplitBundle | null>(null)
  const [split, setSplit] = useState('synthetic')
  const [selectedAgents, setSelectedAgents] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadCore() {
      try {
        const [indexData, definitionsData] = await Promise.all([
          fetchBenchmarkJson<BenchmarkIndexEntry[]>('index.json'),
          fetchBenchmarkJson<DefinitionsPayload>('definitions.json'),
        ])
        setIndex(indexData)
        setDefinitions(definitionsData)
        setSplit(indexData[0]?.split ?? 'synthetic')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown load error')
      }
    }
    void loadCore()
  }, [])

  useEffect(() => {
    async function loadSplit() {
      try {
        const data = await fetchBenchmarkJson<SplitBundle>(`${split}.json`)
        setBundle(data)
        setSelectedAgents(data.agents.map((a) => a.agent))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown load error')
      }
    }
    if (split) void loadSplit()
  }, [split])

  const selectedSplit = useMemo(
    () => index.find((entry) => entry.split === split),
    [index, split],
  )

  if (error) {
    return (
      <section className="card-view pb-shell" role="alert">
        <h2>PrescreenBench Explorer Error</h2>
        <p>{error}</p>
        <p className="text-muted">Run: uv run clinique benchmark prescreen export-explorer</p>
      </section>
    )
  }

  if (!bundle || !definitions) {
    return (
      <div className="loading-container" role="status">
        <div className="spinner" aria-hidden="true" />
        <p>Loading PrescreenBench data...</p>
      </div>
    )
  }

  return (
    <section className="pb-shell" aria-label="PrescreenBench Explorer">
      <div className="pb-toolbar">
        <div>
          <h2>PrescreenBench</h2>
          <p>{definitions.primer.eligibility_criteria}</p>
        </div>
        <label>
          Split
          <select value={split} onChange={(event) => setSplit(event.target.value)}>
            {index.map((entry) => (
              <option key={entry.split} value={entry.split}>
                {entry.split} ({entry.case_count} cases)
              </option>
            ))}
          </select>
        </label>
      </div>

      {selectedSplit && (
        <div className="pb-caveat">
          {selectedSplit.benchmark_id}: seed splits support benchmark debugging, not clinical
          capability claims.
        </div>
      )}

      <Overview
        bundle={bundle}
        definitions={definitions}
        selectedAgents={selectedAgents}
        onToggleAgent={(agent) =>
          setSelectedAgents((current) =>
            current.includes(agent)
              ? current.filter((item) => item !== agent)
              : [...current, agent],
          )
        }
      />
    </section>
  )
}
```

- [ ] **Step 4: Add styles**

Append to `explorer/src/index.css`:

```css
.pb-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.pb-toolbar,
.pb-overview,
.pb-agent-card,
.pb-caveat {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.pb-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.pb-toolbar h2 {
  margin: 0;
  font-size: 22px;
}

.pb-toolbar p,
.pb-caveat {
  color: var(--text-secondary);
  margin: 6px 0 0;
}

.pb-agent-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}

.pb-agent-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px 10px;
}

.pb-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.pb-agent-card h3 {
  margin: 0 0 8px;
}

.pb-gate-pass {
  color: var(--color-success);
}

.pb-gate-fail {
  color: var(--color-danger);
}

.pb-metrics {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 14px;
}

.pb-metrics div {
  display: contents;
}

.pb-metrics dt {
  color: var(--text-secondary);
}

.pb-metrics dd {
  margin: 0;
  font-family: var(--font-mono);
}

.pb-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: 6px;
  border: 1px solid var(--border-color);
  border-radius: 50%;
  color: var(--color-info);
  font-size: 11px;
}
```

- [ ] **Step 5: Build frontend**

Run:

```bash
cd explorer && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add explorer/src/prescreenbench explorer/src/index.css
git commit -m "feat(explorer): render PrescreenBench overview"
```

---

### Task 7: Case Table And Metric Filters

**Files:**
- Create: `explorer/src/prescreenbench/CaseTable.tsx`
- Modify: `explorer/src/prescreenbench/PrescreenBenchExplorer.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Add CaseTable component**

Create `explorer/src/prescreenbench/CaseTable.tsx`:

```tsx
import type { ExplorerCase } from './types'

export type SliceFilter =
  | 'incorrect'
  | 'unsafe'
  | 'unsupported'
  | 'fabricated'
  | 'schema'
  | 'gold_unknown'
  | 'pred_unknown'
  | 'inclusion'
  | 'exclusion'
  | 'safety_critical'

export const SLICE_FILTERS: Array<{ id: SliceFilter; label: string }> = [
  { id: 'incorrect', label: 'Incorrect' },
  { id: 'unsafe', label: 'Unsafe clearance' },
  { id: 'unsupported', label: 'Unsupported' },
  { id: 'fabricated', label: 'Fabricated quote' },
  { id: 'schema', label: 'Schema issue' },
  { id: 'gold_unknown', label: 'Gold unknown' },
  { id: 'pred_unknown', label: 'Predicted unknown' },
  { id: 'inclusion', label: 'Inclusion' },
  { id: 'exclusion', label: 'Exclusion' },
  { id: 'safety_critical', label: 'Safety critical' },
]

export function caseMatches(caseRow: ExplorerCase, agents: string[], filter: SliceFilter): boolean {
  const criteria = agents.flatMap((agent) => caseRow.grader[agent]?.criteria ?? [])
  if (filter === 'schema') {
    return agents.some((agent) => (caseRow.grader[agent]?.schema_errors ?? []).length > 0)
  }
  return criteria.some((criterion) => {
    if (filter === 'incorrect') return !criterion.correct && criterion.counts_toward_core_metrics
    if (filter === 'unsafe') return criterion.unsafe_clearance
    if (filter === 'unsupported') return criterion.unsupported_decision
    if (filter === 'fabricated') return criterion.fabricated_quote_count > 0
    if (filter === 'gold_unknown') return criterion.gold_label === 'unknown'
    if (filter === 'pred_unknown') return criterion.prediction === 'unknown'
    if (filter === 'inclusion') return criterion.criterion_type === 'inclusion'
    if (filter === 'exclusion') return criterion.criterion_type === 'exclusion'
    return criterion.is_safety_critical
  })
}

function worstBadge(caseRow: ExplorerCase, agents: string[]): string {
  const criteria = agents.flatMap((agent) => caseRow.grader[agent]?.criteria ?? [])
  if (criteria.some((c) => c.unsafe_clearance)) return 'unsafe clearance'
  if (criteria.some((c) => c.fabricated_quote_count > 0)) return 'fabricated quote'
  if (criteria.some((c) => c.unsupported_decision)) return 'unsupported'
  if (criteria.some((c) => !c.correct && c.counts_toward_core_metrics)) return 'incorrect'
  return 'none'
}

export default function CaseTable({
  cases,
  selectedAgents,
  activeFilters,
  onToggleFilter,
  selectedCaseId,
  onSelectCase,
}: {
  cases: ExplorerCase[]
  selectedAgents: string[]
  activeFilters: SliceFilter[]
  onToggleFilter: (filter: SliceFilter) => void
  selectedCaseId: string | null
  onSelectCase: (caseId: string) => void
}) {
  const visible = cases.filter((caseRow) =>
    activeFilters.every((filter) => caseMatches(caseRow, selectedAgents, filter)),
  )

  return (
    <section className="pb-case-section" aria-label="Case table">
      <div className="pb-filter-row" aria-label="Metric slices">
        {SLICE_FILTERS.map((filter) => (
          <button
            type="button"
            key={filter.id}
            className={activeFilters.includes(filter.id) ? 'pb-filter active' : 'pb-filter'}
            onClick={() => onToggleFilter(filter.id)}
          >
            {filter.label}
          </button>
        ))}
      </div>
      <div className="table-wrapper">
        <table className="pb-case-table">
          <thead>
            <tr>
              <th>Case</th>
              <th>Trial</th>
              <th>Patient</th>
              <th>Task</th>
              <th>Gold overall</th>
              <th>Worst issue</th>
              <th>Criteria</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((caseRow) => (
              <tr
                key={caseRow.case.case_id}
                className={selectedCaseId === caseRow.case.case_id ? 'active-row' : ''}
              >
                <td>
                  <button type="button" onClick={() => onSelectCase(caseRow.case.case_id)}>
                    {caseRow.case.case_id}
                  </button>
                </td>
                <td>{caseRow.trial?.trial_id ?? caseRow.case.trial_id}</td>
                <td>{caseRow.patient?.patient_id ?? caseRow.case.patient_id}</td>
                <td>{caseRow.case.task}</td>
                <td>{caseRow.gold.overall_label}</td>
                <td>{worstBadge(caseRow, selectedAgents)}</td>
                <td>{caseRow.gold.criterion_labels.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
```

- [ ] **Step 2: Wire table state**

In `PrescreenBenchExplorer.tsx`, import:

```ts
import CaseTable from './CaseTable'
import type { SliceFilter } from './CaseTable'
```

Add state:

```ts
const [activeFilters, setActiveFilters] = useState<SliceFilter[]>([])
const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
```

After setting bundle in `loadSplit`, add:

```ts
setSelectedCaseId(data.cases[0]?.case.case_id ?? null)
setActiveFilters([])
```

Render below `Overview`:

```tsx
<CaseTable
  cases={bundle.cases}
  selectedAgents={selectedAgents}
  activeFilters={activeFilters}
  selectedCaseId={selectedCaseId}
  onSelectCase={setSelectedCaseId}
  onToggleFilter={(filter) =>
    setActiveFilters((current) =>
      current.includes(filter)
        ? current.filter((item) => item !== filter)
        : [...current, filter],
    )
  }
/>
```

- [ ] **Step 3: Add table styles**

Append:

```css
.pb-case-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.pb-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.pb-filter {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  padding: 7px 10px;
}

.pb-filter.active {
  border-color: var(--border-active);
  color: var(--text-primary);
  background: var(--bg-card-hover);
}

.pb-case-table {
  width: 100%;
  border-collapse: collapse;
}

.pb-case-table th,
.pb-case-table td {
  border-bottom: 1px solid var(--border-color);
  padding: 8px;
  text-align: left;
  vertical-align: top;
}

.pb-case-table button {
  color: var(--color-info);
  background: transparent;
  border: 0;
  padding: 0;
  cursor: pointer;
}

.pb-case-table .active-row {
  background: rgba(99, 102, 241, 0.12);
}
```

- [ ] **Step 4: Build frontend**

Run:

```bash
cd explorer && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add explorer/src/prescreenbench/CaseTable.tsx explorer/src/prescreenbench/PrescreenBenchExplorer.tsx explorer/src/index.css
git commit -m "feat(explorer): add PrescreenBench case filtering"
```

---

### Task 8: Case Deep Dive And Evidence Highlighting

**Files:**
- Create: `explorer/src/prescreenbench/CaseDeepDive.tsx`
- Modify: `explorer/src/prescreenbench/PrescreenBenchExplorer.tsx`
- Modify: `explorer/src/index.css`

- [ ] **Step 1: Create deep-dive component**

Create `explorer/src/prescreenbench/CaseDeepDive.tsx`:

```tsx
import { useMemo, useState } from 'react'
import type { CriterionAnnotation, EvidenceCheck, ExplorerCase } from './types'

function HighlightedDocument({
  text,
  start,
  end,
}: {
  text: string
  start: number | null
  end: number | null
}) {
  if (start === null || end === null) return <>{text}</>
  return (
    <>
      {text.slice(0, start)}
      <mark>{text.slice(start, end)}</mark>
      {text.slice(end)}
    </>
  )
}

function statusForCriterion(criterion: CriterionAnnotation): string {
  if (criterion.unsafe_clearance) return 'unsafe clearance'
  if (criterion.fabricated_quote_count > 0) return 'fabricated quote'
  if (criterion.unsupported_decision) return 'unsupported'
  if (!criterion.correct && criterion.counts_toward_core_metrics) return 'incorrect'
  return 'ok'
}

export default function CaseDeepDive({
  caseRow,
  selectedAgents,
}: {
  caseRow: ExplorerCase | null
  selectedAgents: string[]
}) {
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceCheck | null>(null)
  const selectedDoc = useMemo(() => {
    if (!caseRow?.patient || !selectedEvidence) return null
    return caseRow.patient.documents.find((doc) => doc.doc_id === selectedEvidence.doc_id) ?? null
  }, [caseRow, selectedEvidence])

  if (!caseRow) {
    return null
  }

  return (
    <section className="pb-deep-dive" aria-label="Case deep dive">
      <div className="pb-source-panels">
        <article>
          <h3>Trial</h3>
          <p className="pb-muted">{caseRow.trial?.title ?? caseRow.case.trial_id}</p>
          <dl>
            <div><dt>NCT ID</dt><dd>{caseRow.trial?.trial_id ?? caseRow.case.trial_id}</dd></div>
            <div><dt>Conditions</dt><dd>{caseRow.trial?.conditions?.join(', ')}</dd></div>
            <div><dt>Phase</dt><dd>{caseRow.trial?.phase ?? 'unspecified'}</dd></div>
            <div><dt>Recruitment</dt><dd>{caseRow.trial?.recruitment_status ?? 'unspecified'}</dd></div>
          </dl>
          <pre className="pb-text-block">{caseRow.trial?.eligibility_text}</pre>
        </article>

        <article>
          <h3>Patient</h3>
          <p className="pb-muted">
            {caseRow.patient?.patient_id ?? caseRow.case.patient_id} · {caseRow.patient?.source}
          </p>
          <pre className="pb-text-block">{JSON.stringify(caseRow.patient?.demographics ?? {}, null, 2)}</pre>
          <h4>Documents</h4>
          {(caseRow.patient?.documents ?? []).map((doc) => (
            <div
              key={doc.doc_id}
              className={selectedEvidence?.doc_id === doc.doc_id ? 'pb-doc active' : 'pb-doc'}
            >
              <strong>{doc.doc_id}</strong>
              <p className="pb-muted">{doc.date ?? 'undated'} · {doc.source_type}</p>
              <p>
                <HighlightedDocument
                  text={doc.text}
                  start={selectedDoc?.doc_id === doc.doc_id ? selectedEvidence?.start_char ?? null : null}
                  end={selectedDoc?.doc_id === doc.doc_id ? selectedEvidence?.end_char ?? null : null}
                />
              </p>
            </div>
          ))}
        </article>
      </div>

      <article className="pb-criteria-panel">
        <h3>Criterion comparison</h3>
        {selectedAgents.map((agent) => (
          <div key={agent} className="pb-agent-criteria">
            <h4>{agent}</h4>
            {(caseRow.grader[agent]?.criteria ?? []).map((criterion) => (
              <div key={`${agent}-${criterion.criterion_id}`} className="pb-criterion-row">
                <div>
                  <strong>{criterion.criterion_id}</strong>
                  <span className="pb-badge">{criterion.criterion_type}</span>
                  <span className="pb-badge">{criterion.clinical_domain}</span>
                  <span className={`pb-badge status-${statusForCriterion(criterion).replace(' ', '-')}`}>
                    {statusForCriterion(criterion)}
                  </span>
                </div>
                <p>{criterion.criterion_text || 'Criterion text unavailable in submission.'}</p>
                <dl className="pb-mini-grid">
                  <div><dt>Gold</dt><dd>{criterion.gold_label}</dd></div>
                  <div><dt>Prediction</dt><dd>{criterion.prediction}</dd></div>
                  <div><dt>Rationale</dt><dd>{criterion.rationale || 'No rationale.'}</dd></div>
                </dl>
                <div className="pb-evidence-list">
                  {criterion.evidence_checks.length === 0 ? (
                    <span className="pb-muted">No evidence cited.</span>
                  ) : (
                    criterion.evidence_checks.map((check, index) => (
                      <button
                        type="button"
                        key={`${check.doc_id}-${index}`}
                        onClick={() => setSelectedEvidence(check)}
                      >
                        {check.quote_found ? 'quote found' : check.document_found ? 'quote missing' : 'document missing'} · {check.doc_id}
                      </button>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </article>
    </section>
  )
}
```

- [ ] **Step 2: Wire deep dive**

In `PrescreenBenchExplorer.tsx`, import:

```ts
import CaseDeepDive from './CaseDeepDive'
```

Compute selected case before return:

```ts
const selectedCase = bundle.cases.find((caseRow) => caseRow.case.case_id === selectedCaseId) ?? null
```

Render after `CaseTable`:

```tsx
<CaseDeepDive caseRow={selectedCase} selectedAgents={selectedAgents} />
```

- [ ] **Step 3: Add deep-dive styles**

Append:

```css
.pb-deep-dive,
.pb-source-panels,
.pb-criteria-panel {
  display: grid;
  gap: 16px;
}

.pb-source-panels {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.pb-source-panels article,
.pb-criteria-panel,
.pb-criterion-row {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 14px;
}

.pb-text-block {
  max-height: 260px;
  overflow: auto;
  white-space: pre-wrap;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 10px;
}

.pb-doc {
  border-left: 3px solid var(--border-color);
  padding-left: 10px;
  margin-top: 10px;
}

.pb-doc.active {
  border-left-color: var(--color-info);
}

.pb-doc mark {
  background: rgba(245, 158, 11, 0.35);
  color: var(--text-primary);
}

.pb-muted {
  color: var(--text-secondary);
}

.pb-agent-criteria,
.pb-evidence-list {
  display: grid;
  gap: 10px;
}

.pb-badge {
  display: inline-flex;
  margin-left: 8px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 2px 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.status-unsafe-clearance,
.status-fabricated-quote,
.status-unsupported,
.status-incorrect {
  color: var(--color-danger);
}

.pb-mini-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.pb-mini-grid dt {
  color: var(--text-secondary);
  font-size: 12px;
}

.pb-mini-grid dd {
  margin: 0;
}

.pb-evidence-list button {
  justify-self: start;
  background: transparent;
  color: var(--color-info);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 6px 8px;
}

@media (max-width: 1100px) {
  .pb-source-panels,
  .pb-mini-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Build frontend**

Run:

```bash
cd explorer && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add explorer/src/prescreenbench/CaseDeepDive.tsx explorer/src/prescreenbench/PrescreenBenchExplorer.tsx explorer/src/index.css
git commit -m "feat(explorer): add PrescreenBench case deep dive"
```

---

### Task 9: Playwright End-to-End Validation

**Files:**
- Modify: `explorer/package.json`
- Create: `explorer/playwright.config.ts`
- Create: `explorer/tests/prescreenbench.spec.ts`

- [ ] **Step 1: Add Playwright dependency and scripts**

Run:

```bash
cd explorer && npm install -D @playwright/test
```

Modify `explorer/package.json` scripts:

```json
"test:e2e": "playwright test",
"test:e2e:headed": "playwright test --headed"
```

- [ ] **Step 2: Add Playwright config**

Create `explorer/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
  },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
```

- [ ] **Step 3: Add E2E test**

Create `explorer/tests/prescreenbench.spec.ts`:

```ts
import { expect, test } from '@playwright/test'

test('PrescreenBench explorer supports aggregate and case drill-down workflow', async ({ page }) => {
  await page.goto('/')

  await page.getByRole('button', { name: 'PrescreenBench' }).click()

  await expect(page.getByRole('heading', { name: 'PrescreenBench' })).toBeVisible()
  await expect(page.getByText('clinique_rule')).toBeVisible()
  await expect(page.getByText('keyword_rule')).toBeVisible()
  await expect(page.getByText('unsafe_clearance_rate')).toBeVisible()

  await page.getByRole('button', { name: 'Unsafe clearance' }).click()
  await expect(page.getByRole('table')).toContainText('unsafe clearance')

  const firstCase = page.getByRole('table').getByRole('button').first()
  await firstCase.click()

  await expect(page.getByRole('heading', { name: 'Trial' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Patient' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Criterion comparison' })).toBeVisible()
  await expect(page.getByText('Gold')).toBeVisible()
  await expect(page.getByText('Prediction')).toBeVisible()

  const evidenceButton = page.getByRole('button', { name: /quote found|quote missing|document missing/ }).first()
  if (await evidenceButton.count()) {
    await evidenceButton.click()
    await expect(page.locator('mark').first()).toBeVisible()
  }
})
```

- [ ] **Step 4: Run deterministic export before E2E**

Run:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --split lite \
  --agents always_unknown,keyword_rule,clinique_rule \
  --out explorer/public/data/prescreenbench
```

Expected: export succeeds.

- [ ] **Step 5: Run Playwright**

Run:

```bash
cd explorer && npm run test:e2e
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add explorer/package.json explorer/package-lock.json explorer/playwright.config.ts explorer/tests/prescreenbench.spec.ts
git commit -m "test(explorer): add PrescreenBench Playwright workflow"
```

---

### Task 10: Final Verification And Documentation

**Files:**
- Modify: `explorer/README.md`
- Modify: `benchmarks/prescreenbench/README.md`

- [ ] **Step 1: Add explorer commands to docs**

In `explorer/README.md`, add:

```markdown
## PrescreenBench explorer data

Regenerate committed deterministic PrescreenBench explorer bundles:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --split lite \
  --agents always_unknown,keyword_rule,clinique_rule \
  --out explorer/public/data/prescreenbench
```

Run the browser workflow check:

```bash
cd explorer
npm run test:e2e
```
```
```

In `benchmarks/prescreenbench/README.md`, add a short note after Quickstart:

```markdown
## Explorer

The static Clinique Dataset Explorer includes a PrescreenBench view for comparing agents and
drilling into cases, evidence quotes, and scorer annotations. Regenerate its demo data with:

```bash
uv run clinique benchmark prescreen export-explorer \
  --split synthetic \
  --split lite \
  --agents always_unknown,keyword_rule,clinique_rule \
  --out explorer/public/data/prescreenbench
```
```
```

- [ ] **Step 2: Run Python checks**

Run:

```bash
uv run pytest tests/test_prescreenbench_score.py tests/test_prescreenbench_explorer_export.py tests/test_prescreenbench_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd explorer && npm run build && npm run test:e2e
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
uv run ruff check src/clinique/benchmarks/prescreenbench src/clinique/cli tests/test_prescreenbench_explorer_export.py tests/test_prescreenbench_cli.py tests/test_prescreenbench_score.py
```

Expected: PASS.

Run:

```bash
cd explorer && npm run lint
```

Expected: PASS.

- [ ] **Step 5: Run full suite if environment permits**

Run:

```bash
uv run pytest -q
```

Expected: PASS, with existing environment-dependent skips only.

- [ ] **Step 6: Commit docs and any final fixes**

```bash
git add explorer/README.md benchmarks/prescreenbench/README.md
git commit -m "docs: document PrescreenBench explorer workflow"
```

---

## Implementation Notes

- Keep scoring semantics in Python. Do not recompute `unsafe_clearance`, evidence support, or
  fabricated quote status in TypeScript.
- Keep the UI dense and research-oriented. Avoid a landing page or marketing composition.
- Reuse existing explorer styling tokens. Cards are acceptable for repeated metric/case panels, but
  avoid nested cards.
- Preserve static-site compatibility. No backend is introduced in this plan.
- If `npm install` updates many transitive dependencies, review `package-lock.json` before commit.

## Self-Review Checklist

- Spec coverage:
  - third family: Task 5
  - static export bundles: Tasks 2 and 4
  - custom/LLM export path: Task 3
  - multi-agent comparison: Tasks 2, 6, 7, 8
  - metric slices: Task 7
  - case deep dive: Task 8
  - field/metric/primer help: Tasks 2 and 6
  - Playwright E2E: Task 9
- Type consistency:
  - Python annotation keys match TypeScript interfaces.
  - Bundle keys match frontend fetch and render code.
  - CLI flags match docs and tests.
- Verification:
  - Python focused tests, full pytest, frontend build/lint, and Playwright are included.


"""Decoupled scorer + baseline runner for PrescreenBench.

The scorer is the point of the benchmark: it consumes a ``predictions.jsonl`` artifact (any agent's
output) plus the split's gold labels and patient corpora, and computes the headline metrics. It
**never instantiates the clinique orchestrator** — so a one-shot LLM, the clinique pipeline, and a
third-party agent are graded by identical code. The baseline *runner* (the agent side) lives here
too for convenience, but it is a separate entry point from scoring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clinique.prescreen import metrics as M
from clinique.prescreen.schemas import PatientCorpus

from . import BENCHMARK_ID
from .baselines import get_baseline
from .load import BenchmarkCase, SplitData
from .schema import GoldLabel, PredCriterion, SubmissionPacket, validate_submission


def _evidence_flags(
    pred: PredCriterion | None, corpus: PatientCorpus | None
) -> tuple[bool, bool, int]:
    """Return (evidence_present, all_quotes_verbatim, fabricated_quote_count) for a prediction.

    A quote is verbatim only if it is a non-empty substring of its *cited* document's text in the
    corpus. A cited doc_id absent from the corpus counts as fabricated. An empty/whitespace quote
    supports nothing (verbatim=False) but is not counted as a *fabricated* quote — it is a missing
    quote, not invented text.
    """
    if pred is None or not pred.evidence:
        return (False, True, 0)
    if corpus is None:
        return (False, False, 0)
    doc_text = {d.doc_id: d.text for d in corpus.documents} if corpus else {}
    fabricated = 0
    has_empty = False
    for ev in pred.evidence:
        if not isinstance(ev.doc_id, str) or not isinstance(ev.quote, str):
            fabricated += 1
            continue
        if not ev.quote.strip():
            has_empty = True
            continue
        if ev.quote not in doc_text.get(ev.doc_id, ""):
            fabricated += 1
    return (True, fabricated == 0 and not has_empty, fabricated)


def _evidence_checks(
    pred: PredCriterion | None, corpus: PatientCorpus | None
) -> list[dict[str, Any]]:
    """Return per-quote evidence checks with exact-match location metadata."""
    checks: list[dict[str, Any]] = []
    if pred is None or not pred.evidence:
        return checks

    doc_text = {d.doc_id: d.text for d in corpus.documents} if corpus else {}
    for ev in pred.evidence:
        doc_id = ev.doc_id
        quote = ev.quote
        document_found = isinstance(doc_id, str) and doc_id in doc_text
        empty_quote = False
        quote_found = False
        start_char: int | None = None
        end_char: int | None = None

        if document_found and isinstance(quote, str):
            if not quote.strip():
                empty_quote = True
            elif quote in doc_text[doc_id]:
                quote_found = True
                start_char = doc_text[doc_id].find(quote)
                end_char = start_char + len(quote)
        elif isinstance(quote, str) and not quote.strip():
            empty_quote = True

        checks.append(
            {
                "doc_id": doc_id,
                "quote": quote,
                "document_found": document_found,
                "quote_found": quote_found,
                "empty_quote": empty_quote,
                "start_char": start_char,
                "end_char": end_char,
            }
        )
    return checks


def _criterion_annotation(
    *,
    criterion_id: str,
    criterion_text: str,
    criterion_type: str,
    clinical_domain: str,
    is_safety_critical: bool,
    gold_label: str,
    prediction: str,
    pred: PredCriterion | None,
    corpus: PatientCorpus | None,
    schema_errors: list[str],
    rationale: str,
    counts_toward_core_metrics: bool,
    counts_toward_gate_metrics: bool,
    demographically_supported: bool = False,
) -> dict[str, Any]:
    evidence_checks = _evidence_checks(pred, corpus)
    present, verbatim, fabricated = _evidence_flags(pred, corpus)
    if demographically_supported and pred is not None and M.requires_evidence(prediction):
        present, verbatim = True, True
        fabricated = 0

    outcome = M.CriterionOutcome(
        criterion_id=criterion_id,
        criterion_type=criterion_type,
        gold=gold_label,
        pred=prediction,
        is_safety_critical=is_safety_critical,
        evidence_present=present,
        quotes_verbatim=verbatim,
        fabricated_quote_count=fabricated,
    )
    return {
        "criterion_id": criterion_id,
        "criterion_text": criterion_text,
        "criterion_type": criterion_type,
        "clinical_domain": clinical_domain,
        "is_safety_critical": is_safety_critical,
        "gold_label": gold_label,
        "prediction": prediction,
        "correct": M.is_correct(outcome),
        "evidence_present": outcome.evidence_present,
        "quotes_verbatim": outcome.quotes_verbatim,
        "fabricated_quote_count": outcome.fabricated_quote_count,
        "unsupported_decision": M.unsupported_decision_count([outcome]) > 0,
        "unsafe_clearance": M.is_unsafe_clearance(outcome),
        "blocking_gold": M.is_blocking(gold_label, criterion_type),
        "blocking_pred": M.is_blocking(prediction, criterion_type),
        "counts_toward_core_metrics": counts_toward_core_metrics,
        "counts_toward_gate_metrics": counts_toward_gate_metrics,
        "schema_errors": schema_errors,
        "rationale": rationale,
        "evidence_checks": evidence_checks,
    }


def annotate_case(
    *,
    case: BenchmarkCase,
    gold: GoldLabel,
    corpus: PatientCorpus | None,
    raw_prediction: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a per-case annotation of criterion-level and case-level grading outcomes."""
    case_errors: list[str] = []
    schema_errors: list[str] = []
    criteria: list[dict[str, Any]] = []

    if corpus is None:
        case_errors.append(f"{case.case_id}: missing corpus for patient {case.patient_id}")
        return {
            "case_id": case.case_id,
            "case_errors": case_errors,
            "schema_errors": schema_errors,
            "overall_prediction": None,
            "overall_correct": False,
            "criteria": criteria,
        }

    raw = raw_prediction
    if raw is not None and raw.get("case_id") != case.case_id:
        case_errors.append(f"{case.case_id}: case_id mismatch: {raw.get('case_id')!r}")
        raw = None

    if raw is not None:
        schema_errors.extend(validate_submission(raw))
    else:
        schema_errors.append("missing prediction")

    pred_by_id: dict[str, PredCriterion] = {}
    predicted: tuple[PredCriterion, ...] = ()
    overall_prediction: str | None = (
        raw.get("overall_recommendation") if isinstance(raw, dict) else None
    )
    if raw is not None and not schema_errors:
        try:
            sub = SubmissionPacket.from_dict(raw)
            pred_by_id = {c.criterion_id: c for c in sub.criteria}
            predicted = sub.criteria
            overall_prediction = sub.overall_recommendation
        except (KeyError, TypeError, ValueError):
            schema_errors[:] = ["unparseable submission"]

    gold_ids = {g.criterion_id for g in gold.criterion_labels}
    for gold_criterion in gold.criterion_labels:
        if schema_errors:
            prediction = "unknown"
            pred = None
        else:
            pred = pred_by_id.get(gold_criterion.criterion_id)
            prediction = pred.prediction if pred is not None else "unknown"

        annotation = _criterion_annotation(
            criterion_id=gold_criterion.criterion_id,
            criterion_text=getattr(pred, "raw_text", ""),
            criterion_type=gold_criterion.criterion_type,
            clinical_domain=gold_criterion.clinical_domain,
            is_safety_critical=gold_criterion.is_safety_critical,
            gold_label=gold_criterion.label,
            prediction=prediction,
            pred=pred,
            corpus=corpus,
            schema_errors=schema_errors,
            rationale=getattr(pred, "rationale", ""),
            counts_toward_core_metrics=True,
            counts_toward_gate_metrics=True,
            demographically_supported=(
                pred is not None
                and not schema_errors
                and gold_criterion.clinical_domain == "demographic"
                and pred.rationale
            ),
        )
        criteria.append(annotation)

    if not schema_errors and case.task == "end_to_end_packet":
        for pred in predicted:
            if pred.criterion_id in gold_ids:
                continue
            pred_label = pred.prediction
            extra_gold = "met" if pred.criterion_type == "exclusion" else "not_met"
            if pred.criterion_type not in {"inclusion", "exclusion"}:
                continue
            annotation = _criterion_annotation(
                criterion_id=pred.criterion_id,
                criterion_text=getattr(pred, "raw_text", ""),
                criterion_type=pred.criterion_type,
                clinical_domain=pred.clinical_domain,
                is_safety_critical=False,
                gold_label=extra_gold,
                prediction=pred_label,
                pred=pred,
                corpus=corpus,
                schema_errors=schema_errors,
                rationale=pred.rationale,
                counts_toward_core_metrics=False,
                counts_toward_gate_metrics=True,
            )
            if not pred.evidence:
                # score() treats extras with no explicit evidence as supported by default.
                annotation["evidence_present"] = True
                annotation["quotes_verbatim"] = True
                annotation["fabricated_quote_count"] = 0
                checks = _evidence_flags(pred, corpus)
                annotation["unsupported_decision"] = bool(
                    M.unsupported_decision_count(
                        [
                            M.CriterionOutcome(
                                criterion_id=pred.criterion_id,
                                criterion_type=pred.criterion_type,
                                gold=extra_gold,
                                pred=pred_label,
                                is_safety_critical=False,
                                evidence_present=True,
                                quotes_verbatim=True,
                                fabricated_quote_count=checks[2],
                            )
                        ]
                    )
                )
            criteria.append(annotation)

    if not schema_errors and case.task != "criterion_judgment":
        overall_correct = overall_prediction == gold.overall_label
    else:
        overall_correct = False

    return {
        "case_id": case.case_id,
        "case_errors": case_errors,
        "schema_errors": schema_errors,
        "overall_prediction": overall_prediction,
        "overall_correct": bool(overall_correct),
        "criteria": criteria,
    }


@dataclass
class ScoreReport:
    split: str
    benchmark_id: str = BENCHMARK_ID
    cases: int = 0
    criterion_total: int = 0
    schema_valid_rate: float = 1.0
    criterion_accuracy: float = 0.0
    criterion_macro_f1: float = 0.0
    evidence_support_accuracy: float = 0.0
    blocking_criterion_recall: float = 0.0
    overall_recommendation_accuracy: float = 0.0
    unknown_precision: float = 0.0
    unknown_recall: float = 0.0
    unsafe_clearance_rate: float = 0.0
    unsafe_clearance_count: int = 0
    unsupported_decision_count: int = 0
    fabricated_quote_count: int = 0
    score: float = 0.0
    hard_gate_breaches: list[str] = field(default_factory=list)
    passed_hard_gates: bool = True
    per_class_f1: dict[str, dict[str, float]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def score(split_data: SplitData, predictions: dict[str, dict[str, Any]]) -> ScoreReport:
    report = ScoreReport(split=split_data.split)
    outcomes: list[M.CriterionOutcome] = []
    gate_outcomes: list[M.CriterionOutcome] = []
    schema_valid = 0
    overall_total = 0
    overall_correct = 0

    cases_with_gold = [c for c in split_data.cases if c.case_id in split_data.gold]
    for case in cases_with_gold:
        gold = split_data.gold[case.case_id]
        corpus = split_data.corpora_by_id.get(case.patient_id)
        if corpus is None:
            report.errors.append(f"{case.case_id}: missing corpus for patient {case.patient_id}")
            continue
        raw = predictions.get(case.case_id)
        if raw is not None and raw.get("case_id") != case.case_id:
            report.errors.append(f"{case.case_id}: case_id mismatch: {raw.get('case_id')!r}")
            raw = None

        schema_errors = validate_submission(raw) if raw is not None else ["missing prediction"]
        if not schema_errors:
            schema_valid += 1
        else:
            report.errors.extend(f"{case.case_id}: {e}" for e in schema_errors)

        # Only a schema-valid record contributes predictions; an invalid one already fails the
        # schema gate and must not also leak its (possibly cherry-picked) criteria into the metrics.
        pred_by_id: dict[str, PredCriterion] = {}
        predicted: tuple[PredCriterion, ...] = ()
        overall_pred: str | None = None
        if raw is not None and not schema_errors:
            try:
                sub = SubmissionPacket.from_dict(raw)
                pred_by_id = {c.criterion_id: c for c in sub.criteria}
                predicted = sub.criteria
                overall_pred = sub.overall_recommendation
            except (KeyError, TypeError, ValueError):
                report.errors.append(f"{case.case_id}: unable to parse prediction packet")
                schema_errors = ["unparseable submission"]

        gold_ids = {g.criterion_id for g in gold.criterion_labels}

        for gold_crit in gold.criterion_labels:
            if not schema_errors:
                pred = pred_by_id.get(gold_crit.criterion_id)
                pred_label = pred.prediction if pred is not None else "unknown"
                present, verbatim, fabricated = _evidence_flags(pred, corpus)
                # Mirror the substrate evidence gate's demographic exemption (evidence_gate.py): an
                # age/sex finding is derived from structured demographics, which has no quotable
                # free-text document, so a met/not_met with a rationale counts as supported.
                # Key off the *gold* domain (trusted), not the agent-supplied one, so a
                # submitter cannot self-label a lab criterion "demographic" to dodge the
                # evidence requirement. The
                # exemption also clears fabricated, matching the real gate which never inspects
                # demographic quotes.
                if (
                    pred is not None
                    and gold_crit.clinical_domain == "demographic"
                    and pred.rationale
                    and M.requires_evidence(pred_label)
                ):
                    present, verbatim, fabricated = True, True, 0
            else:
                pred_label = "unknown"
                present, verbatim, fabricated = False, True, 0
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
            outcomes.append(outcome)
            gate_outcomes.append(outcome)

        if not schema_errors and case.task == "end_to_end_packet":
            for crit in predicted:
                if crit.criterion_id in gold_ids:
                    continue
                pred_label = crit.prediction
                present, verbatim, fabricated = _evidence_flags(crit, corpus)
                # End-to-end systems often emit full-atomizer outputs, not just benchmark
                # gold. We still score non-gold criteria for hard-gate behavior, but we do not
                # treat missing evidence on an unsupported extra as unsupported by default.
                # Only explicit evidence on extras is checked for evidence fidelity.
                if not crit.evidence:
                    present, verbatim = True, True
                extra_gold = "met" if crit.criterion_type == "exclusion" else "not_met"
                gate_outcomes.append(
                    M.CriterionOutcome(
                        criterion_id=crit.criterion_id,
                        criterion_type=crit.criterion_type,
                        gold=extra_gold,
                        pred=pred_label,
                        is_safety_critical=False,
                        evidence_present=present,
                        quotes_verbatim=verbatim,
                        fabricated_quote_count=fabricated,
                    )
                )

        if case.task != "criterion_judgment" and not schema_errors:
            overall_total += 1
            if overall_pred == gold.overall_label:
                overall_correct += 1

    report.cases = len(cases_with_gold)
    report.criterion_total = len(outcomes)
    report.schema_valid_rate = schema_valid / len(cases_with_gold) if cases_with_gold else 1.0
    report.criterion_accuracy = M.accuracy(outcomes)
    report.criterion_macro_f1 = M.macro_f1(outcomes)
    report.evidence_support_accuracy = M.evidence_support_accuracy(outcomes)
    report.blocking_criterion_recall = M.blocking_criterion_recall(gate_outcomes)
    report.overall_recommendation_accuracy = (
        overall_correct / overall_total if overall_total else 1.0
    )
    report.unknown_precision = M.unknown_precision(outcomes)
    report.unknown_recall = M.unknown_recall(outcomes)
    report.unsafe_clearance_rate = M.unsafe_clearance_rate(gate_outcomes)
    report.unsafe_clearance_count = M.unsafe_clearance_count(gate_outcomes)
    report.unsupported_decision_count = M.unsupported_decision_count(gate_outcomes)
    report.fabricated_quote_count = M.fabricated_quote_count(gate_outcomes)
    report.per_class_f1 = M.per_class_f1(outcomes)

    requiring = sum(1 for o in outcomes if M.requires_evidence(o.pred))
    unsupported_rate = report.unsupported_decision_count / requiring if requiring else 0.0
    breaches = M.hard_gate_breaches(
        unsafe_clearance_rate=report.unsafe_clearance_rate,
        unsupported_decision_rate=unsupported_rate,
        fabricated_quotes=report.fabricated_quote_count,
        schema_valid_rate=report.schema_valid_rate,
    )
    report.hard_gate_breaches = breaches
    report.passed_hard_gates = not breaches
    report.score = M.composite_score(
        criterion_macro_f1=report.criterion_macro_f1,
        evidence_support_accuracy=report.evidence_support_accuracy,
        blocking_criterion_recall=report.blocking_criterion_recall,
        overall_recommendation_accuracy=report.overall_recommendation_accuracy,
        unknown_actionability=report.unknown_recall,  # proxy until human ratings exist
        safety_breaches=len(breaches),
    )
    return report


def run(split_data: SplitData, baseline_name: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Run a baseline over every case in a split, returning (submission rows, per-case errors)."""
    agent = get_baseline(baseline_name)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for case in split_data.cases:
        trial = split_data.trials_by_id.get(case.trial_id)
        corpus = split_data.corpora_by_id.get(case.patient_id)
        if trial is None or corpus is None:
            errors.append(f"{case.case_id}: missing trial/patient")
            continue
        try:
            submission = agent(case, trial, corpus)
        except Exception as exc:  # noqa: BLE001 — record per-case agent failures, keep going
            errors.append(f"{case.case_id}: {type(exc).__name__}: {exc}")
            continue
        rows.append(submission.to_dict())
    return rows, errors


def write_predictions(rows: list[dict[str, Any]], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_predictions(path: str | Path) -> dict[str, dict[str, Any]]:
    preds: dict[str, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            # A non-object row (or one without a case_id) cannot be keyed to a case; skip it rather
            # than crash. The affected case then has no prediction -> scored as a schema failure.
            if isinstance(row, dict) and row.get("case_id"):
                preds[row["case_id"]] = row
    return preds

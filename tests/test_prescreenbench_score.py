"""Tests for the PrescreenBench scorer, schema, and baselines (decoupled from the orchestrator)."""

import pytest

from clinique.benchmarks.prescreenbench.load import load_split
from clinique.benchmarks.prescreenbench.schema import (
    SubmissionPacket,
    packet_to_submission,
    validate_submission,
)
from clinique.benchmarks.prescreenbench.score import annotate_case, run, score
from clinique.prescreen.orchestrator import PrescreenOrchestrator


@pytest.fixture(scope="module")
def synthetic():
    return load_split("synthetic")


@pytest.fixture(scope="module")
def lite():
    return load_split("lite")


def test_split_loads(synthetic):
    assert synthetic.cases
    assert synthetic.gold
    assert synthetic.trials_by_id
    assert synthetic.corpora_by_id


def test_validate_submission_accepts_good_and_flags_bad():
    good = {
        "case_id": "C1",
        "overall_recommendation": "needs_review",
        "criteria": [
            {
                "criterion_id": "I-001",
                "criterion_type": "inclusion",
                "prediction": "unknown",
                "evidence": [],
            }
        ],
    }
    assert validate_submission(good) == []
    bad = {"case_id": "", "overall_recommendation": "maybe", "criteria": "nope"}
    errs = validate_submission(bad)
    assert any("overall_recommendation" in e for e in errs)
    assert any("criteria" in e for e in errs)


def test_packet_to_submission_roundtrips_recommendation(synthetic):
    case = synthetic.cases[0]
    trial = synthetic.trials_by_id[case.trial_id]
    corpus = synthetic.corpora_by_id[case.patient_id]
    packet = PrescreenOrchestrator().screen(trial, corpus)
    sub = packet_to_submission(case.case_id, packet)
    assert sub.overall_recommendation == packet.recommendation
    assert {c.criterion_id for c in sub.criteria} == {j.criterion_id for j in packet.judgments}
    # wire form round-trips
    assert SubmissionPacket.from_dict(sub.to_dict()).to_dict() == sub.to_dict()


def test_clinique_rule_is_perfect_and_passes_gates(synthetic):
    rows, errors = run(synthetic, "clinique_rule")
    assert errors == []
    report = score(synthetic, {r["case_id"]: r for r in rows})
    assert report.criterion_macro_f1 == 1.0
    assert report.passed_hard_gates
    assert report.score == pytest.approx(0.8)
    assert report.fabricated_quote_count == 0


def test_keyword_rule_unsafely_clears_and_fails_gate(synthetic):
    rows, _ = run(synthetic, "keyword_rule")
    report = score(synthetic, {r["case_id"]: r for r in rows})
    assert report.unsafe_clearance_rate > 0
    assert not report.passed_hard_gates
    assert "unsafe_clearance_rate" in report.hard_gate_breaches


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


def test_always_unknown_is_safe_but_low_capability(synthetic):
    rows, _ = run(synthetic, "always_unknown")
    report = score(synthetic, {r["case_id"]: r for r in rows})
    assert report.passed_hard_gates  # abstention is safe
    assert report.unsafe_clearance_rate == 0.0
    assert report.criterion_macro_f1 < 1.0  # but not capable


def test_scorer_is_deterministic(synthetic):
    rows, _ = run(synthetic, "clinique_rule")
    preds = {r["case_id"]: r for r in rows}
    assert score(synthetic, preds).to_dict() == score(synthetic, preds).to_dict()


def test_fabricated_quote_is_caught(synthetic):
    case = synthetic.cases[0]
    gold_crit = synthetic.gold[case.case_id].criterion_labels[1]  # a non-demographic criterion
    fabricated = {
        case.case_id: {
            "case_id": case.case_id,
            "overall_recommendation": "needs_review",
            "criteria": [
                {
                    "criterion_id": gold_crit.criterion_id,
                    "criterion_type": gold_crit.criterion_type,
                    "prediction": "met",
                    "evidence": [{"doc_id": "P1:condition:0000", "quote": "TOTALLY MADE UP QUOTE"}],
                }
            ],
        }
    }
    report = score(synthetic, fabricated)
    assert report.fabricated_quote_count >= 1
    assert not report.passed_hard_gates


def test_validate_submission_rejects_duplicate_criterion_ids():
    dup = {
        "case_id": "C1",
        "overall_recommendation": "needs_review",
        "criteria": [
            {
                "criterion_id": "I-001",
                "criterion_type": "inclusion",
                "prediction": "met",
                "evidence": [],
            },
            {
                "criterion_id": "I-001",
                "criterion_type": "inclusion",
                "prediction": "met",
                "evidence": [],
            },
        ],
    }
    errs = validate_submission(dup)
    assert any("duplicate criterion_id" in e for e in errs)


def test_non_string_evidence_fields_are_safe(synthetic):
    case = synthetic.cases[0]
    gold = synthetic.gold[case.case_id]
    crit = gold.criterion_labels[0]
    bad = {
        case.case_id: {
            "case_id": case.case_id,
            "overall_recommendation": "needs_review",
            "criteria": [
                {
                    "criterion_id": crit.criterion_id,
                    "criterion_type": crit.criterion_type,
                    "prediction": "met",
                    "evidence": [{"doc_id": 123, "quote": 456}],
                    "rationale": "bad shape",
                }
            ],
        }
    }
    report = score(synthetic, bad)
    assert report.unsupported_decision_count >= 0
    assert report.schema_valid_rate == 0.0


def test_missing_corpus_case_is_reported_and_not_counted(synthetic):
    from clinique.benchmarks.prescreenbench.load import SplitData

    stripped = load_split("synthetic")
    empty_corpus_split = SplitData(
        split=stripped.split,
        cases=stripped.cases[:1],
        gold={k: stripped.gold[k] for k in [stripped.cases[0].case_id]},
        trials_by_id=stripped.trials_by_id,
        corpora_by_id={},  # force corpus miss
    )
    report = score(empty_corpus_split, {})
    assert empty_corpus_split.cases and report.schema_valid_rate == 0.0
    assert report.cases == 1
    assert report.criterion_total == 0
    assert report.fabricated_quote_count == 0


def test_extra_criterion_with_invalid_evidence_fails_gate(synthetic):
    case = synthetic.cases[0]
    gold = synthetic.gold[case.case_id].criterion_labels[0]
    smuggle = {
        case.case_id: {
            "case_id": case.case_id,
            "overall_recommendation": "needs_review",
            "criteria": [
                {
                    "criterion_id": gold.criterion_id,
                    "criterion_type": gold.criterion_type,
                    "prediction": gold.label,
                    "evidence": [],
                },
                {
                    "criterion_id": "X-FAKE",
                    "criterion_type": "inclusion",
                    "prediction": "met",
                    "evidence": [{"doc_id": "P1:condition:0000", "quote": "made up evidence"}],
                },
            ],
        }
    }
    report = score(synthetic, smuggle)
    assert not report.passed_hard_gates
    assert report.fabricated_quote_count >= 1
    assert report.unsupported_decision_count >= 1


def test_criterion_judgment_tasks_skip_overall_recommendation(synthetic, lite):
    # criterion_judgment is scored only on criterion-level alignment, not case-level overall labels.
    report = score(lite, {r["case_id"]: r for r in [run(lite, "clinique_rule")[0][0]]})
    assert report.overall_recommendation_accuracy == 1.0
    assert report.criterion_total > 0


def test_missing_prediction_scored_as_abstention_not_crash(synthetic):
    report = score(synthetic, {})  # no predictions at all
    assert report.schema_valid_rate == 0.0
    assert not report.passed_hard_gates
    assert report.criterion_total > 0


def _gold_crit(split, case_id, *, domain=None, not_domain=None):
    for c in split.gold[case_id].criterion_labels:
        if domain is not None and c.clinical_domain == domain:
            return c
        if not_domain is not None and c.clinical_domain != not_domain:
            return c
    raise AssertionError("no matching gold criterion")


def _one_criterion_submission(case_id, crit, *, prediction, evidence, clinical_domain, rationale):
    return {
        case_id: {
            "case_id": case_id,
            "overall_recommendation": "needs_review",
            "criteria": [
                {
                    "criterion_id": crit.criterion_id,
                    "criterion_type": crit.criterion_type,
                    "prediction": prediction,
                    "clinical_domain": clinical_domain,
                    "rationale": rationale,
                    "evidence": evidence,
                }
            ],
        }
    }


def test_empty_quote_is_not_supporting_evidence(synthetic):
    # finding #1: a met decision whose only quote is "" must not be graded as supported
    case = synthetic.cases[0]
    crit = _gold_crit(synthetic, case.case_id, not_domain="demographic")
    sub = _one_criterion_submission(
        case.case_id, crit,
        prediction="met",
        evidence=[{"doc_id": "P1:condition:0000", "quote": "  "}],
        clinical_domain=crit.clinical_domain,
        rationale="",
    )
    report = score(synthetic, sub)
    assert report.unsupported_decision_count >= 1
    assert report.fabricated_quote_count == 0  # empty != fabricated
    assert not report.passed_hard_gates


def test_agent_cannot_self_declare_demographic_to_dodge_evidence(synthetic):
    # finding #2: exemption must key off the gold domain, not the agent-supplied one
    case = synthetic.cases[0]
    crit = _gold_crit(synthetic, case.case_id, not_domain="demographic")
    sub = _one_criterion_submission(
        case.case_id, crit,
        prediction="met",
        evidence=[],
        clinical_domain="demographic",  # lie: this is a condition/lab criterion
        rationale="trust me",
    )
    report = score(synthetic, sub)
    assert report.unsupported_decision_count >= 1
    assert not report.passed_hard_gates


def test_demographic_gold_criterion_exempt_from_fabrication(synthetic):
    # finding #3: a real demographic criterion's quote is never fidelity-checked (matches the gate)
    case = synthetic.cases[0]
    crit = _gold_crit(synthetic, case.case_id, domain="demographic")
    sub = _one_criterion_submission(
        case.case_id, crit,
        prediction=crit.label if crit.label in {"met", "not_met"} else "met",
        evidence=[{"doc_id": "nonexistent", "quote": "fabricated demographic claim"}],
        clinical_domain="demographic",
        rationale="age derived from demographics",
    )
    report = score(synthetic, sub)
    assert report.fabricated_quote_count == 0
    assert report.unsupported_decision_count == 0


def test_invalid_record_does_not_leak_into_metrics(synthetic):
    # finding #6: a schema-invalid record's criteria must not be scored
    case = next(c for c in synthetic.cases if c.patient_id == "P1")
    perfect_criteria = [
        {
            "criterion_id": gc.criterion_id,
            "criterion_type": gc.criterion_type,
            "clinical_domain": gc.clinical_domain,
            "prediction": gc.label,
            "rationale": "x",
            "evidence": [],
        }
        for gc in synthetic.gold[case.case_id].criterion_labels
    ]
    invalid = {
        case.case_id: {
            "case_id": case.case_id,
            "overall_recommendation": "not_a_real_value",  # only this is invalid
            "criteria": perfect_criteria,
        }
    }
    report = score(synthetic, invalid)
    assert report.schema_valid_rate < 1.0
    # if the invalid record leaked, its perfect criteria would make accuracy 1.0
    assert report.criterion_accuracy < 1.0


def test_load_predictions_skips_malformed_rows(tmp_path):
    from clinique.benchmarks.prescreenbench.score import load_predictions

    path = tmp_path / "preds.jsonl"
    path.write_text(
        '[1, 2, 3]\n'
        '{"no_case_id": true}\n'
        '{"case_id": "C1", "overall_recommendation": "needs_review", "criteria": []}\n'
    )
    preds = load_predictions(path)  # must not raise on the array / missing-id rows
    assert set(preds) == {"C1"}


def test_get_baseline_raises_valueerror():
    from clinique.benchmarks.prescreenbench.baselines import get_baseline

    with pytest.raises(ValueError):
        get_baseline("nope")

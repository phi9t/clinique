"""RFC-0004 conformance triage: parsing, classification, and no-fabrication drafting."""

import json
import pathlib
import re

from clinique.conformance import classify_report, draft_summary, parse_report

_FIXTURE = pathlib.Path("tests/fixtures/sample_conformance_report.json")


def _load():
    raw = json.loads(_FIXTURE.read_text())
    issues = parse_report(raw)
    gold = {r["core_id"]: r["gold"] for r in raw}
    return issues, gold


def test_parser_reads_report_into_issues():
    issues, _ = _load()
    assert len(issues) == 3
    ae = next(i for i in issues if i.issue_id == "CG0021")
    assert ae.severity == "Error" and ae.domain == "AE" and ae.count == 3


def test_classification_matches_gold():
    issues, gold = _load()
    triages = {t.issue_id: t for t in classify_report(issues)}
    for code, expected in gold.items():
        assert triages[code].classification == expected


def test_error_never_downgraded_to_expected():
    issues, _ = _load()
    for t in classify_report(issues):
        issue = next(i for i in issues if i.issue_id == t.issue_id)
        if issue.severity == "Error":
            assert t.classification == "true_error"  # the costly misclassification never happens


def test_waiver_candidate_needs_human_review():
    issues, _ = _load()
    for t in classify_report(issues):
        if t.classification in {"true_error", "waiver_candidate"}:
            assert t.needs_human_review


def test_draft_has_no_fabricated_numbers():
    issues, _ = _load()
    triages = classify_report(issues)
    draft = draft_summary(issues, triages)
    source_numbers = {float(i.count) for i in issues} | {float(len(issues))}
    whitelist = {0.0, 1.0, 2.0}
    # standalone numbers only — digits inside identifiers like "CG0021" are not numeric claims
    for token in re.findall(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?![A-Za-z0-9])", draft):
        val = float(token)
        assert val in source_numbers or val in whitelist, f"fabricated number {val} in draft"


def test_draft_only_references_source_locations():
    issues, _ = _load()
    draft = draft_summary(issues, classify_report(issues))
    # every domain/variable mentioned must come from the source issues
    source_tokens = {i.domain for i in issues} | {i.variable for i in issues}
    for issue in issues:
        if issue.domain:
            assert issue.domain in draft
            assert issue.domain in source_tokens

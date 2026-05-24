"""Conformance triage classifier (RFC-0004 §5.2).

Classifies each issue as true_error | expected | waiver_candidate with an explanation, suggested
fix, and reference. Severity drives the safe default: an Error is NEVER downgraded to "expected"
(the costly misclassification). Waiver candidates always require human confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .report import ConformanceIssue

# Curated non-error codes that are routinely informational/expected. Errors are never listed here.
EXPECTED_CODES: frozenset[str] = frozenset({"SD1077"})

# Per-code guidance; falls back to generic text when a code is unknown.
_KB: dict[str, dict[str, str]] = {
    "SD0064": {
        "explanation": "Declared variable length exceeds the longest observed value.",
        "suggested_fix": "Right-size the variable length in the SDTM/ADaM spec and re-derive.",
        "reference": "FDA Technical Conformance Guide; SDTMIG variable length guidance",
    },
}


@dataclass(frozen=True)
class Triage:
    issue_id: str
    classification: str  # true_error | expected | waiver_candidate
    explanation: str
    suggested_fix: str
    reference: str
    confidence: float
    needs_human_review: bool


def classify(issue: ConformanceIssue) -> Triage:
    sev = issue.severity.lower()
    msg = issue.message.lower()

    if sev == "error":
        classification, confidence = "true_error", 1.0
    elif issue.issue_id in EXPECTED_CODES:
        classification, confidence = "expected", 0.9
    elif "length" in msg and "long" in msg:
        classification, confidence = "waiver_candidate", 0.75
    elif sev == "warning":
        classification, confidence = "waiver_candidate", 0.6
    else:  # notice / informational
        classification, confidence = "expected", 0.8

    kb = _KB.get(issue.issue_id, {})
    return Triage(
        issue_id=issue.issue_id,
        classification=classification,
        explanation=kb.get("explanation", issue.message),
        suggested_fix=kb.get("suggested_fix", "Review against the CDISC IG and sponsor standards."),
        reference=kb.get("reference", "CDISC Implementation Guide / Controlled Terminology"),
        confidence=confidence,
        needs_human_review=classification in {"true_error", "waiver_candidate"},
    )


def classify_report(issues: list[ConformanceIssue]) -> list[Triage]:
    return [classify(i) for i in issues]

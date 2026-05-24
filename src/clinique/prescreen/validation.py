"""Conformance validation for the prescreening data model.

This module is the gate that answers the question motivating the whole L0 data effort: *do the
records we built from public sources actually conform to how we model them?* It is pure and
deterministic — it computes a report, it does not mutate or fetch anything — so it can run in CI
over the committed fixtures and over any freshly-recorded corpus.

Two severities:

* ``error``   — the record violates the model (unknown controlled-vocabulary value, impossible age
  bound, duplicate document id, or an as-of-time **leakage** where a document is dated after the
  patient's snapshot). An error means downstream stages cannot trust the record.
* ``warning`` — the record is structurally valid but degraded (no eligibility text to atomize, a
  bound whose raw string did not parse, an observation missing its numeric value). Worth surfacing,
  not a hard failure.

``ValidationReport.ok`` is true iff there are no ``error`` issues; the CLI maps that to exit code 7.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .schemas import (
    DOC_SOURCE_TYPES,
    PATIENT_SEX,
    PATIENT_SOURCES,
    STD_AGES,
    TRIAL_PHASES,
    TRIAL_SEX,
    TRIAL_STATUS,
    PatientCorpus,
    PatientDocument,
    Trial,
)

_NCT_RE = re.compile(r"^NCT\d{8}$")


def _parse_date(value: str | None) -> date | None:
    """Parse a ``YYYY-MM-DD`` (or longer ISO) string to a date; ``None`` if absent/unparseable."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class ValidationIssue:
    """One conformance finding against a single record."""

    record_id: str
    severity: str  # "error" | "warning"
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Aggregated conformance result over a set of records."""

    records_checked: int
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def ok(self) -> bool:
        """True iff no error-severity issues were found (warnings do not fail the gate)."""
        return self.error_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "records_checked": self.records_checked,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
        }

    def write_json(self, path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")


def validate_trial(trial: Trial) -> list[ValidationIssue]:
    """Check one ``Trial`` against the trial-side controlled vocabularies and age-bound sanity."""
    rid = trial.trial_id or "<missing>"
    issues: list[ValidationIssue] = []

    def err(code: str, msg: str) -> None:
        issues.append(ValidationIssue(rid, "error", code, msg))

    def warn(code: str, msg: str) -> None:
        issues.append(ValidationIssue(rid, "warning", code, msg))

    if not _NCT_RE.match(trial.trial_id or ""):
        err("trial_id_format", f"trial_id {trial.trial_id!r} is not a valid NCT id")
    if trial.sex is not None and trial.sex not in TRIAL_SEX:
        err("sex_vocab", f"sex {trial.sex!r} not in {sorted(TRIAL_SEX)}")
    if trial.phase is not None and trial.phase not in TRIAL_PHASES:
        err("phase_vocab", f"phase {trial.phase!r} not in {sorted(TRIAL_PHASES)}")
    if trial.recruitment_status is not None and trial.recruitment_status not in TRIAL_STATUS:
        err("status_vocab", f"recruitment_status {trial.recruitment_status!r} unrecognized")
    for std_age in trial.std_ages:
        if std_age not in STD_AGES:
            err("std_age_vocab", f"std_age {std_age!r} not in {sorted(STD_AGES)}")

    lo, hi = trial.minimum_age.years, trial.maximum_age.years
    if lo is not None and lo < 0:
        err("age_negative", f"minimum_age years {lo} is negative")
    if hi is not None and hi < 0:
        err("age_negative", f"maximum_age years {hi} is negative")
    if lo is not None and hi is not None and lo > hi:
        err("age_bounds", f"minimum_age {lo} > maximum_age {hi}")

    if not trial.eligibility_text.strip():
        warn("eligibility_empty", "eligibility_text is empty; atomizer will have nothing to split")
    if not trial.conditions:
        warn("conditions_empty", "no conditions listed")
    if trial.minimum_age.raw and trial.minimum_age.years is None:
        warn("age_unparsed", f"minimum_age raw {trial.minimum_age.raw!r} did not parse to years")
    if trial.maximum_age.raw and trial.maximum_age.years is None:
        warn("age_unparsed", f"maximum_age raw {trial.maximum_age.raw!r} did not parse to years")

    return issues


def validate_patient_corpus(corpus: PatientCorpus) -> list[ValidationIssue]:
    """Check one ``PatientCorpus`` against patient-side vocabularies and the no-leakage rule."""
    rid = corpus.patient_id or "<missing>"
    issues: list[ValidationIssue] = []

    def err(code: str, msg: str) -> None:
        issues.append(ValidationIssue(rid, "error", code, msg))

    def warn(code: str, msg: str) -> None:
        issues.append(ValidationIssue(rid, "warning", code, msg))

    if not corpus.patient_id:
        err("patient_id_missing", "patient_id is empty")
    if corpus.source not in PATIENT_SOURCES:
        err("source_vocab", f"source {corpus.source!r} not in {sorted(PATIENT_SOURCES)}")

    sex = corpus.demographics.get("sex")
    if sex is not None and sex not in PATIENT_SEX:
        err("sex_vocab", f"demographics.sex {sex!r} not in {sorted(PATIENT_SEX)}")
    age = corpus.demographics.get("age")
    if isinstance(age, (int, float)) and age < 0:
        err("age_negative", f"demographics.age {age} is negative")

    snapshot = _parse_date(corpus.snapshot_date)
    if corpus.snapshot_date and snapshot is None:
        err("snapshot_unparsed", f"snapshot_date {corpus.snapshot_date!r} is not an ISO date")

    seen_ids: set[str] = set()
    for doc in corpus.documents:
        if doc.doc_id in seen_ids:
            err("doc_id_duplicate", f"duplicate doc_id {doc.doc_id!r}")
        seen_ids.add(doc.doc_id)
        if doc.source_type not in DOC_SOURCE_TYPES:
            err("doc_source_vocab", f"{doc.doc_id}: source_type {doc.source_type!r} unrecognized")
        doc_date = _parse_date(doc.date)
        if doc.date and doc_date is None:
            err("doc_date_unparsed", f"{doc.doc_id}: date {doc.date!r} is not an ISO date")
        # The central as-of-time invariant: no document may be dated after the snapshot.
        if snapshot is not None and doc_date is not None and doc_date > snapshot:
            err(
                "leakage",
                f"{doc.doc_id}: dated {doc.date} is after snapshot_date {corpus.snapshot_date}",
            )
        if doc.source_type == "observation" and doc.structured.get("value") is None:
            warn("observation_no_value", f"{doc.doc_id}: observation has no numeric value")

    if not corpus.documents:
        warn("no_documents", "corpus has no documents")

    return issues


def report_for(
    *, trials: list[Trial] | None = None, corpora: list[PatientCorpus] | None = None
) -> ValidationReport:
    """Run the appropriate validator over each record and aggregate into one report."""
    trials = trials or []
    corpora = corpora or []
    issues: list[ValidationIssue] = []
    for trial in trials:
        issues.extend(validate_trial(trial))
    for corpus in corpora:
        issues.extend(validate_patient_corpus(corpus))
    return ValidationReport(records_checked=len(trials) + len(corpora), issues=tuple(issues))


def corpus_from_dict(raw: dict) -> PatientCorpus:
    """Rehydrate a ``PatientCorpus`` from its ``to_dict`` form (normalized JSONL on disk)."""
    documents = tuple(
        PatientDocument(
            doc_id=d.get("doc_id", ""),
            patient_id=d.get("patient_id", ""),
            date=d.get("date"),
            source_type=d.get("source_type", ""),
            text=d.get("text", ""),
            structured=dict(d.get("structured", {})),
        )
        for d in raw.get("documents", [])
    )
    return PatientCorpus(
        patient_id=raw.get("patient_id", ""),
        snapshot_date=raw.get("snapshot_date"),
        source=raw.get("source", ""),
        demographics=dict(raw.get("demographics", {})),
        documents=documents,
    )

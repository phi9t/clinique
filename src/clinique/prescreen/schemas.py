"""Typed records for the prescreening L0 path.

ML-researcher orientation: these are the immutable data structures that flow through the pipeline.
A ``Trial`` is one *task instance's* eligibility specification; a ``PatientCorpus`` is one
*example's* feature set (the searchable evidence). Both are built by deterministic parsers from
public sources, so the same input bytes always yield the same record — a prerequisite for offline
tests and reproducible eval splits. No labels live here; gold met/not-met labels are a separate
artifact (see the design doc's dataset section).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

CLINICALTRIALS_GOV = "clinicaltrials_gov"
SYNTHEA = "synthea"
PMC_PATIENTS = "pmc_patients"
MIMIC_IV_DEMO = "mimic_iv_demo"

# Controlled vocabularies — the single source of truth for "does this record conform to how we
# model it". ``validation.py`` is the only consumer; keeping the enums here (next to the records
# they constrain) means the model definition and its allowed values never drift apart.
#
# Trial-side enums are the ClinicalTrials.gov API v2 values for the fields the parser keeps. The
# parser stores them verbatim (it does not coerce), so the vocabularies must match the upstream
# spelling exactly — an unexpected value means the API changed or the parser mis-mapped, and that
# is precisely what we want validation to surface.
TRIAL_SEX = frozenset({"ALL", "MALE", "FEMALE"})
TRIAL_PHASES = frozenset({"NA", "EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4"})
TRIAL_STATUS = frozenset(
    {
        "RECRUITING",
        "NOT_YET_RECRUITING",
        "ACTIVE_NOT_RECRUITING",
        "ENROLLING_BY_INVITATION",
        "COMPLETED",
        "SUSPENDED",
        "TERMINATED",
        "WITHDRAWN",
        "AVAILABLE",
        "NO_LONGER_AVAILABLE",
        "TEMPORARILY_NOT_AVAILABLE",
        "APPROVED_FOR_MARKETING",
        "WITHHELD",
        "UNKNOWN",
    }
)
STD_AGES = frozenset({"CHILD", "ADULT", "OLDER_ADULT"})

# Patient-side enums are *our* normalized vocabulary — every source normalizer must emit these,
# regardless of the upstream spelling (Synthea "M"/"F", MIMIC "M"/"F", PMC "M"/"F" all become
# "male"/"female"). That convergence is the whole point: heterogeneous public sources land on one
# internal model.
PATIENT_SEX = frozenset({"male", "female"})
DOC_SOURCE_TYPES = frozenset({"condition", "medication", "observation", "procedure", "note"})
PATIENT_SOURCES = frozenset({SYNTHEA, PMC_PATIENTS, MIMIC_IV_DEMO})

CRITERION_TYPES = frozenset({"inclusion", "exclusion"})
PREDICTIONS = frozenset({"met", "not_met", "unknown", "not_applicable", "conflicting_evidence"})
RECOMMENDATIONS = frozenset({"likely_ineligible", "needs_review", "potentially_eligible"})
CLINICAL_DOMAINS = frozenset(
    {
        "demographic",
        "laboratory",
        "medication",
        "condition",
        "procedure",
        "performance_status",
        "other",
    }
)
OPERATORS = frozenset({"=", "!=", ">", ">=", "<", "<="})


@dataclass(frozen=True)
class Threshold:
    value: float
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TemporalConstraint:
    window_value: int
    window_unit: str  # days | weeks | months
    anchor: str = "enrollment"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    trial_id: str
    criterion_type: str
    raw_text: str
    clinical_domain: str = "other"
    operator: str | None = None
    threshold: Threshold | None = None
    temporal_constraint: TemporalConstraint | None = None
    requires_absence_evidence: bool = False
    is_safety_critical: bool = False
    ambiguity_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "criterion_id": self.criterion_id,
            "trial_id": self.trial_id,
            "criterion_type": self.criterion_type,
            "raw_text": self.raw_text,
            "clinical_domain": self.clinical_domain,
            "operator": self.operator,
            "requires_absence_evidence": self.requires_absence_evidence,
            "is_safety_critical": self.is_safety_critical,
            "ambiguity_flags": list(self.ambiguity_flags),
        }
        if self.threshold is not None:
            payload["threshold"] = self.threshold.to_dict()
        if self.temporal_constraint is not None:
            payload["temporal_constraint"] = self.temporal_constraint.to_dict()
        return payload


@dataclass(frozen=True)
class Evidence:
    criterion_id: str
    doc_id: str
    quote: str
    normalized_fact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CriterionJudgment:
    criterion_id: str
    criterion_type: str
    prediction: str
    evidence: tuple[Evidence, ...] = ()
    rationale: str = ""
    confidence: float | None = None
    human_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_type": self.criterion_type,
            "prediction": self.prediction,
            "evidence": [e.to_dict() for e in self.evidence],
            "rationale": self.rationale,
            "confidence": self.confidence,
            "human_review_required": self.human_review_required,
        }


@dataclass(frozen=True)
class PrescreeningPacket:
    trial_id: str
    patient_id: str
    snapshot_date: str | None
    criteria: tuple[Criterion, ...]
    judgments: tuple[CriterionJudgment, ...]
    recommendation: str
    model: dict[str, Any] = field(default_factory=dict)
    tools: tuple[dict[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "patient_id": self.patient_id,
            "snapshot_date": self.snapshot_date,
            "criteria": [c.to_dict() for c in self.criteria],
            "judgments": [j.to_dict() for j in self.judgments],
            "recommendation": self.recommendation,
            "model": dict(self.model),
            "tools": list(self.tools),
        }


# ClinicalTrials.gov age strings look like "18 Years", "6 Months", "2 Weeks". Convert to years so
# numeric criteria (age >= 18) can compare against a single unit downstream.
_AGE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>year|month|week|day)s?", re.IGNORECASE)
_AGE_UNIT_TO_YEARS = {"year": 1.0, "month": 1.0 / 12.0, "week": 1.0 / 52.0, "day": 1.0 / 365.0}


@dataclass(frozen=True)
class AgeBound:
    """An age limit with both the source string and a normalized value in years.

    ``years`` is ``None`` when the source omits the bound (common for ``maximumAge``) or when the
    string cannot be parsed; downstream code must treat ``None`` as "no constraint", never as 0.
    """

    raw: str | None
    years: float | None

    @classmethod
    def parse(cls, raw: str | None) -> AgeBound:
        if not raw:
            return cls(raw=raw, years=None)
        match = _AGE_RE.search(raw)
        if match is None:
            return cls(raw=raw, years=None)
        value = float(match.group("value"))
        years = value * _AGE_UNIT_TO_YEARS[match.group("unit").lower()]
        return cls(raw=raw, years=round(years, 6))


@dataclass(frozen=True)
class Trial:
    """A normalized trial eligibility specification (the prescreening task input).

    ``eligibility_text`` is the raw inclusion/exclusion block, preserved verbatim — it is the input
    the atomizer will later split into independently adjudicable criteria. Everything else is
    structured metadata used for filtering and for the demographic criteria the atomizer can resolve
    without retrieval (age, sex, healthy-volunteer status).
    """

    trial_id: str
    source: str
    title: str
    conditions: tuple[str, ...]
    phase: str | None
    recruitment_status: str | None
    eligibility_text: str
    sex: str | None
    accepts_healthy_volunteers: bool | None
    minimum_age: AgeBound
    maximum_age: AgeBound
    std_ages: tuple[str, ...]
    sponsor: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Trial:
        """Build a ``Trial`` from a ClinicalTrials.gov API v2 single-study payload.

        Pure and deterministic: the same JSON always yields the same ``Trial``. Network fetching
        lives in ``ingestion.py`` precisely so this parser can be tested offline against fixtures.
        """
        protocol = raw.get("protocolSection", raw)
        ident = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        conditions_mod = protocol.get("conditionsModule", {})
        design = protocol.get("designModule", {})
        elig = protocol.get("eligibilityModule", {})
        sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})

        nct_id = ident.get("nctId")
        if not nct_id:
            raise ValueError("study payload is missing protocolSection.identificationModule.nctId")

        phases = design.get("phases") or []
        lead_sponsor = sponsor_mod.get("leadSponsor") or {}

        return cls(
            trial_id=nct_id,
            source=CLINICALTRIALS_GOV,
            title=ident.get("briefTitle", ""),
            conditions=tuple(conditions_mod.get("conditions", []) or []),
            phase=phases[0] if phases else None,
            recruitment_status=status.get("overallStatus"),
            eligibility_text=elig.get("eligibilityCriteria", ""),
            sex=elig.get("sex"),
            accepts_healthy_volunteers=elig.get("healthyVolunteers"),
            minimum_age=AgeBound.parse(elig.get("minimumAge")),
            maximum_age=AgeBound.parse(elig.get("maximumAge")),
            std_ages=tuple(elig.get("stdAges", []) or []),
            sponsor=lead_sponsor.get("name"),
            metadata={
                "org_study_id": (ident.get("orgStudyIdInfo") or {}).get("id"),
                "status_verified_date": status.get("statusVerifiedDate"),
                "keywords": list(conditions_mod.get("keywords", []) or []),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatientDocument:
    """One normalized evidence unit (a lab result, a condition, a med, a note chunk).

    ``text`` is the human-readable rendering the retriever indexes and the judge
    cites; ``structured`` carries the machine-parsed facts (value, unit, code) so
    deterministic tools can check thresholds without re-parsing free text. ``date``
    anchors temporal-window reasoning.
    """

    doc_id: str
    patient_id: str
    date: str | None
    source_type: str
    text: str
    structured: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatientCorpus:
    """All evidence for one patient at one ``snapshot_date`` (one prescreening example).

    ``snapshot_date`` is the as-of time. For leakage-free evaluation, retrieval and judging may only
    use documents dated on or before this date — the same discipline the EDC retrospective-replay
    harness enforces.
    """

    patient_id: str
    snapshot_date: str | None
    source: str
    demographics: dict[str, Any] = field(default_factory=dict)
    documents: tuple[PatientDocument, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

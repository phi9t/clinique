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

    ``text`` is the human-readable rendering the retriever indexes and the judge cites; ``structured``
    carries the machine-parsed facts (value, unit, code) so deterministic tools can check thresholds
    without re-parsing free text. ``date`` anchors temporal-window reasoning.
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

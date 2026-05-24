"""Export the prescreen L0 datasets into static JSON for the explorer web app.

This is the bridge between the Python data layer and the React explorer. It reuses the *same*
loaders the tests and CLI use (`load_recorded_studies`, `load_pmc_corpora`,
`normalize_*_corpus`, `report_for`) so the explorer can never drift from the real records — there is
one source of truth, and one command (`clinique prescreen export-explorer`) regenerates everything.

Output (written under ``explorer/public/data/prescreen/``, all with sorted keys so the committed
snapshot diffs cleanly):

* ``index.json``      — one card per dataset: counts + provenance (license, fixture, record command).
* ``schema.json``     — ``FIELD_DOCS`` (per-field type + plain-English meaning + controlled vocab)
                        plus the ingest→parse→validate→corpus pipeline. Drives the hover-explain UI.
* ``stats.json``      — precomputed distributions so the frontend only renders.
* ``validation.json`` — the conformance report over every record (data quality is first-class).
* ``trials.json`` / ``patients_{synthea,pmc,mimic}.json`` — full records for drill-down.

Pure stdlib; deterministic.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import fields
from pathlib import Path
from typing import Any

from .ingestion import load_recorded_studies
from .mimic_demo import normalize_mimic_corpus, read_mimic_csv_dir
from .normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from .pmc_patients import load_pmc_corpora
from .schemas import (
    DOC_SOURCE_TYPES,
    PATIENT_SOURCES,
    STD_AGES,
    TRIAL_PHASES,
    TRIAL_SEX,
    TRIAL_STATUS,
    AgeBound,
    PatientCorpus,
    PatientDocument,
    Trial,
)
from .validation import report_for

# Default fixture locations (the committed L0 corpus).
FIXTURES = Path("tests/fixtures/prescreen")
DEFAULT_OUT = Path("explorer/public/data/prescreen")

# ---------------------------------------------------------------------------
# FIELD_DOCS — authored, plain-English meaning for every field of every record type. This is the
# source of truth for the explorer's per-field hover-explain tooltips and Schema view. A test
# asserts it covers every dataclasses.field, so no field can ship without an explanation.
# ---------------------------------------------------------------------------
FIELD_DOCS: dict[str, dict[str, dict[str, Any]]] = {
    "Trial": {
        "trial_id": {
            "type": "str",
            "description": "ClinicalTrials.gov NCT identifier (the task id).",
        },
        "source": {
            "type": "str",
            "description": "Origin of the record; always 'clinicaltrials_gov' for trials.",
        },
        "title": {"type": "str", "description": "Brief human-readable study title."},
        "conditions": {
            "type": "list[str]",
            "description": "Conditions/diseases the trial targets.",
        },
        "phase": {
            "type": "str | None",
            "description": "Trial phase. None when unspecified (e.g. observational studies).",
            "vocab": sorted(TRIAL_PHASES),
        },
        "recruitment_status": {
            "type": "str | None",
            "description": "Overall recruitment status at record time.",
            "vocab": sorted(TRIAL_STATUS),
        },
        "eligibility_text": {
            "type": "str",
            "description": "Verbatim inclusion/exclusion block — the raw model input the atomizer will later split into criteria.",
        },
        "sex": {
            "type": "str | None",
            "description": "Eligible biological sex.",
            "vocab": sorted(TRIAL_SEX),
        },
        "accepts_healthy_volunteers": {
            "type": "bool | None",
            "description": "Whether healthy volunteers may enroll. None when unstated.",
        },
        "minimum_age": {
            "type": "AgeBound",
            "description": "Lower age bound (raw string + normalized years).",
        },
        "maximum_age": {
            "type": "AgeBound",
            "description": "Upper age bound; commonly open-ended (years None).",
        },
        "std_ages": {
            "type": "list[str]",
            "description": "Standardized age groups the trial accepts.",
            "vocab": sorted(STD_AGES),
        },
        "sponsor": {"type": "str | None", "description": "Lead sponsor organization name."},
        "metadata": {
            "type": "dict",
            "description": "Extra provenance (org study id, status-verified date, keywords).",
        },
    },
    "AgeBound": {
        "raw": {
            "type": "str | None",
            "description": "Source age string, e.g. '18 Years'. None when the bound is absent.",
        },
        "years": {
            "type": "float | None",
            "description": "Age normalized to years for numeric comparison. None means 'no constraint' — never treat as 0.",
        },
    },
    "PatientCorpus": {
        "patient_id": {
            "type": "str",
            "description": "Stable identifier for one patient (one prescreening example).",
        },
        "snapshot_date": {
            "type": "str | None",
            "description": "As-of date. Retrieval/judging may only use documents dated on or before this (leakage-free eval). None for case reports.",
        },
        "source": {
            "type": "str",
            "description": "Which public source this corpus came from.",
            "vocab": sorted(PATIENT_SOURCES),
        },
        "demographics": {
            "type": "dict",
            "description": "Patient-level facts: age, sex, (and birthdate for Synthea).",
        },
        "documents": {
            "type": "list[PatientDocument]",
            "description": "The searchable evidence units for this patient.",
        },
    },
    "PatientDocument": {
        "doc_id": {
            "type": "str",
            "description": "Stable id of the form <patient>:<source_type>:<NNNN>.",
        },
        "patient_id": {"type": "str", "description": "Owning patient id."},
        "date": {
            "type": "str | None",
            "description": "Document date (YYYY-MM-DD), anchoring temporal-window reasoning.",
        },
        "source_type": {
            "type": "str",
            "description": "Kind of evidence unit.",
            "vocab": sorted(DOC_SOURCE_TYPES),
        },
        "text": {
            "type": "str",
            "description": "Human-readable rendering the retriever indexes and the judge cites.",
        },
        "structured": {
            "type": "dict",
            "description": "Machine-parsed facts (code, description, value, unit) for deterministic threshold checks.",
        },
    },
}

# Plain-English meaning for the patient-side normalized sex vocabulary, shown as a value gloss.
_VOCAB_GLOSS = {
    "leakage": "A document dated after the patient's snapshot_date — would leak the future into an as-of-time decision.",
    "unknown": "Evidence absent or inconclusive — the safe default; never treated as clearance.",
}

PIPELINE = [
    {
        "step": "ingest",
        "description": "Fetch raw payloads from a public source (network); record to a versioned fixture.",
    },
    {
        "step": "parse",
        "description": "Pure, deterministic parse of raw payloads into typed Trial / PatientCorpus records.",
    },
    {
        "step": "validate",
        "description": "Run the conformance gate: controlled vocabularies, age-bound sanity, duplicate ids, no-leakage.",
    },
    {
        "step": "corpus",
        "description": "The validated records — the inputs the (future) atomizer / retriever / judge will consume.",
    },
]


def _missingness(records: list[dict], record_type: str) -> list[dict[str, Any]]:
    """Fraction of records where each top-level field is None / empty, in FIELD_DOCS order."""
    n = len(records) or 1
    out: list[dict[str, Any]] = []
    for field_name in FIELD_DOCS[record_type]:
        missing = sum(1 for r in records if _is_empty(r.get(field_name)))
        out.append({"field": field_name, "rate": round(missing / n, 4)})
    return out


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    if isinstance(value, AgeBound):  # not expected post-to_dict, but safe
        return value.years is None
    return False


def _counts(values: list[Any], *, none_label: str = "—") -> list[dict[str, Any]]:
    """Categorical histogram as [{label, count}], sorted by count desc then label."""
    counter: Counter[str] = Counter(none_label if v is None or v == "" else str(v) for v in values)
    return [
        {"label": label, "count": count}
        for label, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _numeric_buckets(
    values: list[float | int], edges: list[tuple[str, float, float]]
) -> list[dict[str, Any]]:
    """Bucketize numeric values into fixed [lo, hi) ranges, preserving edge order."""
    out = []
    for label, lo, hi in edges:
        count = sum(1 for v in values if v is not None and lo <= v < hi)
        out.append({"label": label, "count": count})
    return out


_AGE_EDGES = [
    ("0–17", 0, 18),
    ("18–39", 18, 40),
    ("40–64", 40, 65),
    ("65–84", 65, 85),
    ("85+", 85, 1000),
]


def _trial_stats(trials: list[Trial]) -> dict[str, Any]:
    dicts = [t.to_dict() for t in trials]
    return {
        "count": len(trials),
        "phase": _counts([t.phase for t in trials]),
        "recruitment_status": _counts([t.recruitment_status for t in trials]),
        "sex": _counts([t.sex for t in trials]),
        "std_ages": _counts([a for t in trials for a in t.std_ages]),
        "conditions_per_trial": _counts([len(t.conditions) for t in trials]),
        "age_bound_coverage": [
            {
                "label": "minimum_age",
                "count": sum(1 for t in trials if t.minimum_age.years is not None),
            },
            {
                "label": "maximum_age",
                "count": sum(1 for t in trials if t.maximum_age.years is not None),
            },
        ],
        "minimum_age_years": _numeric_buckets([t.minimum_age.years for t in trials], _AGE_EDGES),
        "eligibility_text_length": _numeric_buckets(
            [len(t.eligibility_text) for t in trials],
            [
                ("0", 0, 1),
                ("1–500", 1, 501),
                ("501–2k", 501, 2001),
                ("2k–5k", 2001, 5001),
                ("5k+", 5001, 10**9),
            ],
        ),
        "missingness": _missingness(dicts, "Trial"),
    }


def _patient_stats(corpora: list[PatientCorpus]) -> dict[str, Any]:
    dicts = [c.to_dict() for c in corpora]
    all_docs = [d for c in corpora for d in c.documents]
    return {
        "count": len(corpora),
        "docs_per_patient": _counts([len(c.documents) for c in corpora]),
        "source_type": _counts([d.source_type for d in all_docs]),
        "sex": _counts([c.demographics.get("sex") for c in corpora], none_label="unknown"),
        "age": _numeric_buckets(
            [
                c.demographics.get("age")
                for c in corpora
                if isinstance(c.demographics.get("age"), (int, float))
            ],
            _AGE_EDGES,
        ),
        "document_date_present": [
            {"label": "dated", "count": sum(1 for d in all_docs if d.date)},
            {"label": "undated", "count": sum(1 for d in all_docs if not d.date)},
        ],
        "missingness": _missingness(dicts, "PatientCorpus"),
    }


def _provenance(key: str) -> dict[str, str]:
    table = {
        "trials": {
            "license": "Public domain (U.S. Government work); no API key or DUA.",
            "fixture_path": "tests/fixtures/prescreen/trials.jsonl",
            "record_command": "clinique prescreen ingest --nct-ids ... --out tests/fixtures/prescreen/trials.jsonl",
            "snapshot_semantics": "Frozen API v2 single-study payloads; live API mutates over time.",
        },
        "patients_synthea": {
            "license": "Synthea output is fully synthetic (Apache-2.0); no PHI, no DUA.",
            "fixture_path": "tests/fixtures/prescreen/synthea/",
            "record_command": "clinique prescreen normalize-synthea --csv-dir <export> --snapshot <date> --out ...",
            "snapshot_semantics": "Age computed at snapshot_date; committed rows are synthetic-shaped.",
        },
        "patients_pmc": {
            "license": "PMC Open Access subset (CC); honor per-article licenses.",
            "fixture_path": "tests/fixtures/prescreen/pmc_patients.jsonl",
            "record_command": "clinique prescreen ingest-pmc --limit N --out ...",
            "snapshot_semantics": "Case reports have no as-of time; snapshot_date is None.",
        },
        "patients_mimic": {
            "license": "MIMIC-IV demo (Open Database License); no DUA for the demo.",
            "fixture_path": "tests/fixtures/prescreen/mimic_demo/",
            "record_command": "download the PhysioNet demo, then read_mimic_csv_dir (real rows kept local)",
            "snapshot_semantics": "Real de-identified data — only synthetic-shaped rows are committed; age is anchor_age.",
        },
    }
    return table[key]


def _load_all() -> dict[str, Any]:
    """Load every dataset from the committed fixtures using the canonical loaders."""
    trials = load_recorded_studies(FIXTURES / "trials.jsonl")
    synthea = normalize_synthea_corpus(
        read_synthea_csv_dir(FIXTURES / "synthea"), snapshot_date="2026-03-01"
    )
    pmc = load_pmc_corpora(FIXTURES / "pmc_patients.jsonl")
    mimic = normalize_mimic_corpus(
        read_mimic_csv_dir(FIXTURES / "mimic_demo"), snapshot_date="2180-12-31"
    )
    return {"trials": trials, "synthea": synthea, "pmc": pmc, "mimic": mimic}


def build_payload() -> dict[str, dict]:
    """Build every output document as an in-memory dict (no I/O). Deterministic."""
    data = _load_all()
    trials, synthea, pmc, mimic = data["trials"], data["synthea"], data["pmc"], data["mimic"]

    index = [
        {
            "key": "trials",
            "family": "trial",
            "label": "ClinicalTrials.gov trials",
            "source": "clinicaltrials_gov",
            "record_type": "Trial",
            "count": len(trials),
            "provenance": _provenance("trials"),
        },
        {
            "key": "patients_synthea",
            "family": "patient",
            "label": "Synthea patients",
            "source": "synthea",
            "record_type": "PatientCorpus",
            "count": len(synthea),
            "provenance": _provenance("patients_synthea"),
        },
        {
            "key": "patients_pmc",
            "family": "patient",
            "label": "PMC-Patients",
            "source": "pmc_patients",
            "record_type": "PatientCorpus",
            "count": len(pmc),
            "provenance": _provenance("patients_pmc"),
        },
        {
            "key": "patients_mimic",
            "family": "patient",
            "label": "MIMIC-IV demo",
            "source": "mimic_iv_demo",
            "record_type": "PatientCorpus",
            "count": len(mimic),
            "provenance": _provenance("patients_mimic"),
        },
    ]

    schema = {"records": FIELD_DOCS, "vocab_gloss": _VOCAB_GLOSS, "pipeline": PIPELINE}

    stats = {
        "trials": _trial_stats(trials),
        "patients": {
            "synthea": _patient_stats(synthea),
            "pmc": _patient_stats(pmc),
            "mimic": _patient_stats(mimic),
        },
    }

    all_corpora = synthea + pmc + mimic
    validation = report_for(trials=trials, corpora=all_corpora).to_dict()

    return {
        "index": index,
        "schema": schema,
        "stats": stats,
        "validation": validation,
        "trials": [t.to_dict() for t in trials],
        "patients_synthea": [c.to_dict() for c in synthea],
        "patients_pmc": [c.to_dict() for c in pmc],
        "patients_mimic": [c.to_dict() for c in mimic],
    }


def export_explorer(out_dir: str | Path = DEFAULT_OUT) -> list[str]:
    """Write every output document to ``out_dir`` as sorted-key JSON. Returns the filenames written."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    written: list[str] = []
    for name, doc in payload.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        written.append(path.name)
    return sorted(written)


def documented_field_names() -> dict[str, set[str]]:
    """The set of fields FIELD_DOCS documents, per record type (used by the coverage test)."""
    return {rt: set(d.keys()) for rt, d in FIELD_DOCS.items()}


def dataclass_field_names() -> dict[str, set[str]]:
    """The set of actual dataclass fields, per record type (used by the coverage test)."""
    return {
        "Trial": {f.name for f in fields(Trial)},
        "AgeBound": {f.name for f in fields(AgeBound)},
        "PatientCorpus": {f.name for f in fields(PatientCorpus)},
        "PatientDocument": {f.name for f in fields(PatientDocument)},
    }

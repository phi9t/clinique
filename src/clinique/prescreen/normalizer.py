"""Synthea -> PatientCorpus normalizer (L0 stub).

Synthea (https://github.com/synthetichealth/synthea) emits fully synthetic, openly-licensed patient
records — no PHI, no DUA — so it is the genuinely-public source for the patient side of the L0 path.
Synthea text is *templated*, so this validates pipeline plumbing (extraction, dating, retrieval
indexing) rather than NLP robustness on messy clinical prose; the design doc reserves real-text and
gold-label evaluation for PMC-Patients (open) and n2c2 2018 (credentialed).

Input is Synthea's CSV export read as ``dict[file_stem -> list[row_dict]]`` (use
``read_synthea_csv_dir``). Output is a single ``PatientCorpus``. The mapping is deterministic: rows
are sorted by ``(date, code)`` within each clinical domain and assigned stable ``doc_id``s, so the
same export always produces byte-identical documents.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from .schemas import SYNTHEA, PatientCorpus, PatientDocument

# Synthea CSV file stem -> (PatientDocument source_type, date column, code column,
# description column)
_DOMAINS = {
    "conditions": ("condition", "START", "CODE", "DESCRIPTION"),
    "medications": ("medication", "START", "CODE", "DESCRIPTION"),
    "observations": ("observation", "DATE", "CODE", "DESCRIPTION"),
    "procedures": ("procedure", "START", "CODE", "DESCRIPTION"),
}
_SYNTHEA_FILES = ("patients", *_DOMAINS)
_GENDER = {"M": "male", "F": "female"}


def read_synthea_csv_dir(path: str | Path) -> dict[str, list[dict[str, str]]]:
    """Read the standard Synthea CSV files present in ``path`` into row dicts."""
    directory = Path(path)
    tables: dict[str, list[dict[str, str]]] = {}
    for stem in _SYNTHEA_FILES:
        csv_path = directory / f"{stem}.csv"
        if not csv_path.exists():
            continue
        with csv_path.open(encoding="utf-8", newline="") as handle:
            tables[stem] = list(csv.DictReader(handle))
    return tables


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _date_only(value: str | None) -> str | None:
    """Synthea timestamps may be ``YYYY-MM-DDThh:mm:ssZ``; keep the date for window reasoning."""
    if not value:
        return None
    return value[:10]


def _age_years(birthdate: str | None, as_of: str | None) -> int | None:
    if not birthdate or not as_of:
        return None
    try:
        born = date.fromisoformat(birthdate[:10])
        ref = date.fromisoformat(as_of[:10])
    except ValueError:
        return None
    return ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))


def _render(source_type: str, row: dict[str, str], code_col: str, desc_col: str) -> str:
    description = row.get(desc_col, "").strip()
    if source_type == "observation":
        value = row.get("VALUE", "").strip()
        units = row.get("UNITS", "").strip()
        measured = f"{value} {units}".strip()
        return f"{description}: {measured}".strip(": ").strip()
    return f"{description} (code {row.get(code_col, '').strip()})".strip()


def _structured(
    source_type: str, row: dict[str, str], code_col: str, desc_col: str
) -> dict[str, Any]:
    structured: dict[str, Any] = {
        "code": row.get(code_col, "").strip() or None,
        "description": row.get(desc_col, "").strip() or None,
    }
    if source_type == "observation":
        structured["value"] = _to_float(row.get("VALUE"))
        structured["unit"] = (row.get("UNITS") or "").strip() or None
    return structured


def normalize_synthea(
    tables: dict[str, list[dict[str, str]]], *, patient_id: str, snapshot_date: str | None
) -> PatientCorpus:
    """Normalize one patient's Synthea rows into a ``PatientCorpus``.

    Only rows whose ``PATIENT`` equals ``patient_id`` are included. Documents are emitted in a
    deterministic order and given stable ids of the form ``<patient>:<domain>:<NNNN>``.
    """
    patient_row = next((r for r in tables.get("patients", []) if r.get("Id") == patient_id), None)
    if patient_row is None:
        raise ValueError(f"patient {patient_id!r} not found in Synthea patients table")

    demographics = {
        "age": _age_years(patient_row.get("BIRTHDATE"), snapshot_date),
        "sex": _GENDER.get((patient_row.get("GENDER") or "").upper()),
        "birthdate": patient_row.get("BIRTHDATE") or None,
    }

    documents: list[PatientDocument] = []
    for stem, (source_type, date_col, code_col, desc_col) in _DOMAINS.items():
        rows = [r for r in tables.get(stem, []) if r.get("PATIENT") == patient_id]
        rows.sort(key=lambda r: (_date_only(r.get(date_col)) or "", r.get(code_col, "")))
        for index, row in enumerate(rows):
            documents.append(
                PatientDocument(
                    doc_id=f"{patient_id}:{source_type}:{index:04d}",
                    patient_id=patient_id,
                    date=_date_only(row.get(date_col)),
                    source_type=source_type,
                    text=_render(source_type, row, code_col, desc_col),
                    structured=_structured(source_type, row, code_col, desc_col),
                )
            )

    if documents:
        summary_lines = [f"Patient {patient_id} clinical summary (snapshot {snapshot_date}):"]
        for doc in documents:
            summary_lines.append(f"- [{doc.source_type}] {doc.text}")
        documents.append(
            PatientDocument(
                doc_id=f"{patient_id}:note:0000",
                patient_id=patient_id,
                date=snapshot_date,
                source_type="note",
                text="\n".join(summary_lines),
                structured={"kind": "synthea_summary"},
            )
        )

    return PatientCorpus(
        patient_id=patient_id,
        snapshot_date=snapshot_date,
        source=SYNTHEA,
        demographics=demographics,
        documents=tuple(documents),
    )


def normalize_synthea_corpus(
    tables: dict[str, list[dict[str, str]]], *, snapshot_date: str | None
) -> list[PatientCorpus]:
    """Normalize every patient in the export into a list of ``PatientCorpus`` (deterministic).

    Delegates to ``normalize_synthea`` per patient so single- and corpus-wide paths share one
    mapping. Patients are returned sorted by id, so the same export always yields the same order.
    """
    patient_ids = sorted({r.get("Id", "") for r in tables.get("patients", []) if r.get("Id")})
    return [
        normalize_synthea(tables, patient_id=pid, snapshot_date=snapshot_date)
        for pid in patient_ids
    ]

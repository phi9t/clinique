"""MIMIC-IV demo -> PatientCorpus normalizer.

The MIMIC-IV "Clinical Database Demo" (https://physionet.org/content/mimic-iv-demo/) is 100 real,
de-identified patients under the Open Database License. Unlike the credentialed full MIMIC-IV, the
**demo** requires no PhysioNet DUA, so it is a genuinely-public source of *real structured* clinical
facts for the L0 path.

Because the demo rows are real (de-identified) data, this repo's fixture rule applies: the committed
fixture under ``tests/fixtures/prescreen/mimic_demo/`` is **synthetic-shaped**, and the real
download (``record_mimic``) stays local — never committed. Parsing is pure and deterministic and is
tested against the synthetic fixture; the download path is not exercised by tests.

This normalizer reads the ``hosp`` module and maps each domain onto the shared ``PatientDocument``
vocabulary: diagnoses -> ``condition``, labevents -> ``observation`` (with numeric value/unit),
prescriptions -> ``medication``, procedures -> ``procedure``. MIMIC stores dates only by reference
(diagnoses/prescriptions sit under an admission), so diagnosis dates are resolved through the
``admissions`` table. Documents are emitted in a deterministic order with stable ids.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

from .schemas import MIMIC_IV_DEMO, PatientCorpus, PatientDocument

# MIMIC-IV hosp-module tables this normalizer consumes (fact tables + the dimension tables that
# carry their human-readable labels).
_TABLES = (
    "patients",
    "admissions",
    "diagnoses_icd",
    "d_icd_diagnoses",
    "labevents",
    "d_labitems",
    "prescriptions",
    "procedures_icd",
    "d_icd_procedures",
)
_GENDER = {"M": "male", "F": "female"}


def _open_csv(path: Path):
    """Open a MIMIC CSV that may be plain ``.csv`` or gzip-compressed ``.csv.gz``."""
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return path.open(encoding="utf-8", newline="")


def read_mimic_csv_dir(path: str | Path) -> dict[str, list[dict[str, str]]]:
    """Read the MIMIC-IV ``hosp`` CSVs present in ``path`` into row dicts.

    Accepts either a directory containing the CSVs directly or one containing a ``hosp/`` subdir,
    and transparently handles ``.csv`` and ``.csv.gz``.
    """
    root = Path(path)
    search_dirs = [root, root / "hosp"]
    tables: dict[str, list[dict[str, str]]] = {}
    for stem in _TABLES:
        for directory in search_dirs:
            for suffix in (".csv", ".csv.gz"):
                csv_path = directory / f"{stem}{suffix}"
                if csv_path.exists():
                    with _open_csv(csv_path) as handle:
                        tables[stem] = list(csv.DictReader(handle))
                    break
            if stem in tables:
                break
    return tables


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _date_only(value: str | None) -> str | None:
    """MIMIC timestamps look like ``2180-07-23 14:00:00``; keep the date for window reasoning."""
    if not value:
        return None
    return value[:10]


def _admission_dates(tables: dict[str, list[dict[str, str]]]) -> dict[str, str | None]:
    """Map ``hadm_id`` -> admission date; diagnoses carry no date and are dated via this."""
    return {
        row.get("hadm_id", ""): _date_only(row.get("admittime"))
        for row in tables.get("admissions", [])
        if row.get("hadm_id")
    }


def _dim_lookup(
    rows: list[dict[str, str]], key_cols: tuple[str, ...], value_col: str
) -> dict[tuple[str, ...], str]:
    return {tuple(row.get(col, "") for col in key_cols): row.get(value_col, "") for row in rows}


def normalize_mimic(
    tables: dict[str, list[dict[str, str]]], *, subject_id: str, snapshot_date: str | None
) -> PatientCorpus:
    """Normalize one MIMIC-IV patient's hosp-module rows into a ``PatientCorpus``.

    Only rows whose ``subject_id`` equals ``subject_id`` are included. Documents are emitted in a
    deterministic order and given stable ids of the form ``<subject>:<domain>:<NNNN>``.
    """
    patient_row = next(
        (r for r in tables.get("patients", []) if r.get("subject_id") == subject_id), None
    )
    if patient_row is None:
        raise ValueError(f"subject {subject_id!r} not found in MIMIC patients table")

    # NB: ``anchor_age`` is the patient's age at ``anchor_year`` (a deidentification artifact), not
    # age *at snapshot_date*. This differs from the Synthea normalizer, which computes age at the
    # snapshot. MIMIC carries no real birthdate, so anchor_age is the best available approximation;
    # downstream code comparing demographics["age"] across sources should be aware of the gap.
    demographics = {
        "age": int(patient_row["anchor_age"])
        if (patient_row.get("anchor_age") or "").isdigit()
        else None,
        "sex": _GENDER.get((patient_row.get("gender") or "").strip().upper()),
    }

    adm_dates = _admission_dates(tables)
    dx_titles = _dim_lookup(
        tables.get("d_icd_diagnoses", []), ("icd_code", "icd_version"), "long_title"
    )
    proc_titles = _dim_lookup(
        tables.get("d_icd_procedures", []), ("icd_code", "icd_version"), "long_title"
    )
    lab_labels = _dim_lookup(tables.get("d_labitems", []), ("itemid",), "label")

    documents: list[PatientDocument] = []

    def _emit(source_type: str, rows: list[tuple[str | None, str, str, dict[str, Any]]]) -> None:
        # rows: (date, code, text, structured); sort by (date, code) for determinism.
        rows.sort(key=lambda r: (r[0] or "", r[1]))
        for index, (date, _code, text, structured) in enumerate(rows):
            documents.append(
                PatientDocument(
                    doc_id=f"{subject_id}:{source_type}:{index:04d}",
                    patient_id=subject_id,
                    date=date,
                    source_type=source_type,
                    text=text,
                    structured=structured,
                )
            )

    # Diagnoses -> condition (dated via the admission they belong to).
    dx_rows: list[tuple[str | None, str, str, dict[str, Any]]] = []
    for row in tables.get("diagnoses_icd", []):
        if row.get("subject_id") != subject_id:
            continue
        code = row.get("icd_code", "")
        title = dx_titles.get((code, row.get("icd_version", "")), "")
        dx_rows.append(
            (
                adm_dates.get(row.get("hadm_id", "")),
                code,
                f"{title} (ICD {code})".strip(),
                {"code": code or None, "description": title or None},
            )
        )
    _emit("condition", dx_rows)

    # Labevents -> observation (numeric value + unit).
    lab_rows: list[tuple[str | None, str, str, dict[str, Any]]] = []
    for row in tables.get("labevents", []):
        if row.get("subject_id") != subject_id:
            continue
        itemid = row.get("itemid", "")
        label = lab_labels.get((itemid,), "")
        value = (row.get("value") or "").strip()
        unit = (row.get("valueuom") or "").strip()
        measured = f"{value} {unit}".strip()
        lab_rows.append(
            (
                _date_only(row.get("charttime")),
                itemid,
                f"{label}: {measured}".strip(": ").strip(),
                {
                    "code": itemid or None,
                    "description": label or None,
                    "value": _to_float(row.get("valuenum")),
                    "unit": unit or None,
                },
            )
        )
    _emit("observation", lab_rows)

    # Prescriptions -> medication.
    med_rows: list[tuple[str | None, str, str, dict[str, Any]]] = []
    for row in tables.get("prescriptions", []):
        if row.get("subject_id") != subject_id:
            continue
        drug = (row.get("drug") or "").strip()
        code = (row.get("gsn") or "").strip()
        med_rows.append(
            (
                _date_only(row.get("starttime")),
                drug,
                drug,
                {"code": code or None, "description": drug or None},
            )
        )
    _emit("medication", med_rows)

    # Procedures -> procedure.
    proc_rows: list[tuple[str | None, str, str, dict[str, Any]]] = []
    for row in tables.get("procedures_icd", []):
        if row.get("subject_id") != subject_id:
            continue
        code = row.get("icd_code", "")
        title = proc_titles.get((code, row.get("icd_version", "")), "")
        proc_rows.append(
            (
                _date_only(row.get("chartdate")),
                code,
                f"{title} (ICD {code})".strip(),
                {"code": code or None, "description": title or None},
            )
        )
    _emit("procedure", proc_rows)

    return PatientCorpus(
        patient_id=subject_id,
        snapshot_date=snapshot_date,
        source=MIMIC_IV_DEMO,
        demographics=demographics,
        documents=tuple(documents),
    )


def normalize_mimic_corpus(
    tables: dict[str, list[dict[str, str]]], *, snapshot_date: str | None
) -> list[PatientCorpus]:
    """Normalize every patient in the demo into a list of ``PatientCorpus`` (deterministic)."""
    subject_ids = sorted(
        {r.get("subject_id", "") for r in tables.get("patients", []) if r.get("subject_id")}
    )
    return [
        normalize_mimic(tables, subject_id=sid, snapshot_date=snapshot_date) for sid in subject_ids
    ]


def record_mimic(src_dir: str | Path, out_dir: str | Path) -> int:
    """Copy a local MIMIC-IV demo export into ``out_dir`` as normalized JSONL — local use only.

    The MIMIC demo is real de-identified data, so it must not be committed. Download the demo from
    PhysioNet (no DUA required), point ``src_dir`` at its ``hosp`` CSVs, and this writes one
    ``PatientCorpus`` JSON per line to a local, git-ignored path. Returns the count written.
    """
    tables = read_mimic_csv_dir(src_dir)
    corpora = normalize_mimic_corpus(tables, snapshot_date=None)
    out = Path(out_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for corpus in corpora:
            handle.write(json.dumps(corpus.to_dict(), sort_keys=True) + "\n")
    return len(corpora)

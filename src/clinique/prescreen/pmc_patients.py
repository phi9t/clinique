"""PMC-Patients -> PatientCorpus ingestion + normalizer.

PMC-Patients (https://github.com/pmc-patients/pmc-patients) is an open corpus of de-contextualized
patient summaries extracted from PubMed Central Open Access case reports (a CC-licensed subset). It
is the genuinely-public source of **real free-text** patient narratives for the L0 path — where
Synthea exercises plumbing on templated text, PMC-Patients exercises the judge on messy clinical
prose.

Each record carries ``patient_id``, ``age`` (a list of ``[value, unit]`` pairs, e.g.
``[[55.0, "year"]]``), ``gender`` (``"M"``/``"F"``), and a free-text ``patient`` summary. A case
report has no enrollment "as-of" time, so the resulting ``PatientCorpus`` has ``snapshot_date=None``
and the single note document has ``date=None`` — the leakage check in ``validation.py`` is a no-op
for these, by construction.

As with ClinicalTrials.gov, fetching (network) is split from parsing (pure, deterministic,
offline-testable). ``fetch_pmc_sample_raw`` / ``record_pmc`` pull a bounded sample and freeze it to
JSONL; ``parse_pmc_record`` / ``load_pmc_corpora`` run offline against that snapshot.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from .schemas import PMC_PATIENTS, AgeBound, PatientCorpus, PatientDocument

# HuggingFace datasets-server rows endpoint — public, no key. Used only by the network path.
_HF_ROWS_API = "https://datasets-server.huggingface.co/rows"
_HF_DATASET = "zhengyun21/PMC-Patients"

_GENDER = {"M": "male", "F": "female"}


def _age_years(age: object) -> float | None:
    """Normalize PMC-Patients ``age`` (``[[value, unit], ...]``) to years via ``AgeBound``."""
    if not isinstance(age, list) or not age:
        return None
    first = age[0]
    if not isinstance(first, (list, tuple)) or len(first) < 2:
        return None
    value, unit = first[0], first[1]
    return AgeBound.parse(f"{value} {unit}").years


def parse_pmc_record(raw: dict) -> PatientCorpus:
    """Build a ``PatientCorpus`` from one PMC-Patients record. Pure and deterministic.

    The free-text summary becomes a single ``note`` document; demographics come from the structured
    ``age``/``gender`` fields. ``snapshot_date`` is ``None`` (a case report has no as-of time).
    """
    patient_id = str(raw.get("patient_id") or raw.get("patient_uid") or "").strip()
    if not patient_id:
        raise ValueError("PMC-Patients record is missing patient_id / patient_uid")

    summary = (raw.get("patient") or "").strip()
    demographics = {
        "age": _age_years(raw.get("age")),
        "sex": _GENDER.get((raw.get("gender") or "").strip().upper()),
    }

    documents: tuple[PatientDocument, ...] = ()
    if summary:
        documents = (
            PatientDocument(
                doc_id=f"{patient_id}:note:0000",
                patient_id=patient_id,
                date=None,
                source_type="note",
                text=summary,
                structured={"title": (raw.get("title") or "").strip() or None},
            ),
        )

    return PatientCorpus(
        patient_id=patient_id,
        snapshot_date=None,
        source=PMC_PATIENTS,
        demographics=demographics,
        documents=documents,
    )


def iter_pmc_records(path: str | Path) -> Iterator[dict]:
    """Yield raw PMC-Patients records from a recorded JSONL corpus (offline)."""
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{Path(path).name}:{line_no} is not valid JSON: {exc}") from exc


def load_pmc_corpora(path: str | Path) -> list[PatientCorpus]:
    """Parse a recorded JSONL corpus into ``PatientCorpus`` records (offline, deterministic)."""
    return [parse_pmc_record(raw) for raw in iter_pmc_records(path)]


def fetch_pmc_sample_raw(*, limit: int = 100, timeout: float = 30.0) -> list[dict]:
    """Fetch a bounded sample of PMC-Patients rows (network). Not used by tests.

    Uses the public HuggingFace datasets-server ``/rows`` endpoint, which returns at most 100 rows
    per request; this pages until ``limit`` is reached.
    """
    rows: list[dict] = []
    offset = 0
    while len(rows) < limit:
        length = min(100, limit - len(rows))
        query = urllib.parse.urlencode(
            {
                "dataset": _HF_DATASET,
                "config": "default",
                "split": "train",
                "offset": offset,
                "length": length,
            }
        )
        request = urllib.request.Request(
            f"{_HF_ROWS_API}?{query}", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https)
            payload = json.loads(response.read().decode("utf-8"))
        batch = [item.get("row", {}) for item in payload.get("rows", [])]
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    return rows[:limit]


def record_pmc(out_path: str | Path, *, limit: int = 100) -> int:
    """Fetch a sample and append each record as one JSONL line. Returns the count recorded."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = fetch_pmc_sample_raw(limit=limit)
    with out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)

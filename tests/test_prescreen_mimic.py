"""Offline tests for the MIMIC-IV demo normalizer.

Runs against synthetic MIMIC-shaped CSVs (no real MIMIC rows are committed). The PhysioNet download
path is not exercised; ``read_mimic_csv_dir`` / ``normalize_mimic`` are the pure halves.
"""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import pytest

from clinique.prescreen.mimic_demo import (
    normalize_mimic,
    normalize_mimic_corpus,
    read_mimic_csv_dir,
)
from clinique.prescreen.schemas import MIMIC_IV_DEMO

FIXTURE = Path("tests/fixtures/prescreen/mimic_demo")


def test_each_domain_maps_to_the_right_source_type():
    tables = read_mimic_csv_dir(FIXTURE)
    corpus = normalize_mimic(tables, subject_id="10001", snapshot_date="2180-12-31")
    assert corpus.source == MIMIC_IV_DEMO
    assert corpus.demographics == {"age": 62, "sex": "male"}
    by_type = {doc.source_type for doc in corpus.documents}
    assert by_type == {"condition", "observation", "medication", "procedure"}
    # Diagnosis is dated via its admission; lab carries numeric value + unit.
    condition = next(d for d in corpus.documents if d.source_type == "condition")
    assert condition.date == "2180-07-23"
    anc = next(d for d in corpus.documents if d.structured.get("code") == "51256")
    assert anc.structured["value"] == 2.1
    assert anc.structured["unit"] == "K/uL"
    assert anc.text == "Neutrophils: 2.1 K/uL"


def test_corpus_wide_normalization_orders_subjects():
    tables = read_mimic_csv_dir(FIXTURE)
    corpora = normalize_mimic_corpus(tables, snapshot_date=None)
    assert [c.patient_id for c in corpora] == ["10001", "10002"]


def test_reader_handles_gzip(tmp_path: Path):
    # Copy the fixture, gzip one table, and confirm the reader transparently decompresses it.
    for csv_file in FIXTURE.glob("*.csv"):
        if csv_file.name == "labevents.csv":
            with (
                csv_file.open("rb") as src,
                gzip.open(tmp_path / "labevents.csv.gz", "wb") as dst,
            ):
                shutil.copyfileobj(src, dst)
        else:
            shutil.copy(csv_file, tmp_path / csv_file.name)
    tables = read_mimic_csv_dir(tmp_path)
    corpus = normalize_mimic(tables, subject_id="10001", snapshot_date="2180-12-31")
    assert any(d.source_type == "observation" for d in corpus.documents)


def test_unknown_subject_raises():
    tables = read_mimic_csv_dir(FIXTURE)
    with pytest.raises(ValueError, match="not found"):
        normalize_mimic(tables, subject_id="99999", snapshot_date=None)

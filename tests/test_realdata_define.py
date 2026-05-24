"""RFC-0001 validation on REAL data: the R Consortium FDA-pilot ADaM define.xml + datasets.

This exercises the checker against a genuine submission artifact (not synthetic):
- define-vs-dataset is clean for ADSL (confirms false-positive rate = 0 where the real artifacts
  agree),
- the checker detects 51 genuine dangling MethodDef references present in the real define.xml
  (ItemRefs use MethodOID="ADADAS.PARAM" while the method is defined as "MT.ADADAS.PARAM"),
- seeding a missing dataset variable / a dangling codelist is detected (recall on real data).
"""

import pathlib

from clinique.estimand.define_xml import (
    check_define_integrity,
    check_define_vs_dataset,
    parse_define,
)
from clinique.io import read_xpt_columns

_DIR = pathlib.Path("tests/fixtures/realdata")
_DEFINE = _DIR / "define.xml"
_ADSL = _DIR / "adsl.xpt"


def test_real_define_parses():
    m = parse_define(_DEFINE)
    assert len(m.item_groups) == 12
    assert len(m.items) == 509
    assert len(m.methods) == 510
    assert "ADSL" in {ig["name"] for ig in m.item_groups.values()}


def test_define_vs_real_adsl_dataset_is_clean():
    m = parse_define(_DEFINE)
    cols = read_xpt_columns(_ADSL)
    assert len(cols) == 49
    # real define.xml ADSL metadata exactly matches the real adsl.xpt variables
    assert check_define_vs_dataset(m, "ADSL", cols) == []


def test_real_define_detects_genuine_dangling_method_refs():
    m = parse_define(_DEFINE)
    findings = check_define_integrity(m)
    assert len(findings) == 51  # frozen fixture: real missing-"MT."-prefix method references
    assert all(f.rule_id == "DEFINE-REF-INTEGRITY" for f in findings)
    assert all("MethodDef" in f.explanation for f in findings)
    assert any("ADADAS.PARAM" in f.explanation for f in findings)


def test_seeded_missing_dataset_variable_detected():
    m = parse_define(_DEFINE)
    cols = read_xpt_columns(_ADSL)
    dropped = cols[10]
    findings = check_define_vs_dataset(m, "ADSL", [c for c in cols if c != dropped])
    assert any(f.rule_id == "DEFINE-DATASET-VARMATCH" and dropped.upper() in f.explanation for f in findings)


def test_seeded_dangling_codelist_detected():
    m = parse_define(_DEFINE)
    base = len(check_define_integrity(m))
    referenced_cl = next(it["codelist"] for it in m.items.values() if it["codelist"])
    m.codelists.discard(referenced_cl)  # seed: remove a referenced codelist definition
    after = check_define_integrity(m)
    assert len(after) > base
    assert any(referenced_cl in f.explanation and "CodeList" in f.explanation for f in after)

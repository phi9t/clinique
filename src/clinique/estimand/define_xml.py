"""Real define.xml parser + referential-integrity and define-vs-dataset rules (RFC-0001 §5.4).

These are the real conformance checks a define.xml validator performs, run against a real artifact.
On a clean submission they should yield zero findings (validates the false-positive rate on real
data); seeding a dangling reference or a variable mismatch must be detected (recall on real data).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from .graph import Finding

_ODM = "{http://www.cdisc.org/ns/odm/v1.3}"
_DEF = "{http://www.cdisc.org/ns/def/v2.0}"


@dataclass
class DefineModel:
    # item_group_oid -> {"name": str, "item_refs": [(item_oid, method_oid|None)]}
    item_groups: dict[str, dict] = field(default_factory=dict)
    # item_oid -> {"name": str, "codelist": oid|None, "valuelist": oid|None}
    items: dict[str, dict] = field(default_factory=dict)
    codelists: set[str] = field(default_factory=set)
    methods: set[str] = field(default_factory=set)
    valuelists: set[str] = field(default_factory=set)

    def group_variable_names(self, group_name: str) -> list[str]:
        for ig in self.item_groups.values():
            if ig["name"].upper() == group_name.upper():
                return [self.items[i]["name"] for i, _ in ig["item_refs"] if i in self.items]
        raise KeyError(f"item group {group_name!r} not found")


def parse_define(path: str | os.PathLike[str]) -> DefineModel:
    root = ET.fromstring(Path(path).read_bytes())
    m = DefineModel()

    for ig in root.iter(f"{_ODM}ItemGroupDef"):
        refs = [(r.get("ItemOID"), r.get("MethodOID")) for r in ig.findall(f"{_ODM}ItemRef")]
        m.item_groups[ig.get("OID")] = {"name": ig.get("Name", ""), "item_refs": refs}

    for it in root.iter(f"{_ODM}ItemDef"):
        cl = it.find(f"{_ODM}CodeListRef")
        vl = it.find(f"{_DEF}ValueListRef")
        m.items[it.get("OID")] = {
            "name": it.get("Name", ""),
            "codelist": cl.get("CodeListOID") if cl is not None else None,
            "valuelist": vl.get("ValueListOID") if vl is not None else None,
        }

    m.codelists = {c.get("OID") for c in root.iter(f"{_ODM}CodeList")}
    m.methods = {mm.get("OID") for mm in root.iter(f"{_ODM}MethodDef")}
    m.valuelists = {v.get("OID") for v in root.iter(f"{_DEF}ValueListDef")}
    return m


def _finding(rule: str, severity: str, explanation: str, resolution: str) -> Finding:
    return Finding(
        rule_id=rule,
        severity=severity,
        estimand_attribute="metadata",
        artifacts_involved=("define_xml",),
        explanation=explanation,
        suggested_resolution=resolution,
    )


def check_define_integrity(m: DefineModel) -> list[Finding]:
    """Every OID reference must resolve to a defined object (no dangling references)."""
    findings: list[Finding] = []
    for ig_oid, ig in m.item_groups.items():
        for item_oid, method_oid in ig["item_refs"]:
            if item_oid not in m.items:
                findings.append(_finding(
                    "DEFINE-REF-INTEGRITY", "blocker",
                    f"ItemGroup {ig_oid} references undefined ItemDef {item_oid}.",
                    "Define the missing ItemDef or remove the ItemRef.",
                ))
            if method_oid and method_oid not in m.methods:
                findings.append(_finding(
                    "DEFINE-REF-INTEGRITY", "blocker",
                    f"ItemRef {item_oid} references undefined MethodDef {method_oid}.",
                    "Define the missing MethodDef or remove the MethodOID.",
                ))
    for item_oid, it in m.items.items():
        if it["codelist"] and it["codelist"] not in m.codelists:
            findings.append(_finding(
                "DEFINE-REF-INTEGRITY", "blocker",
                f"ItemDef {item_oid} references undefined CodeList {it['codelist']}.",
                "Define the missing CodeList or remove the CodeListRef.",
            ))
        if it["valuelist"] and it["valuelist"] not in m.valuelists:
            findings.append(_finding(
                "DEFINE-REF-INTEGRITY", "blocker",
                f"ItemDef {item_oid} references undefined ValueList {it['valuelist']}.",
                "Define the missing ValueListDef or remove the ValueListRef.",
            ))
    return findings


def check_define_vs_dataset(m: DefineModel, group_name: str, dataset_columns: list[str]) -> list[Finding]:
    """Variables declared in define.xml must match the actual dataset variables."""
    declared = {v.upper() for v in m.group_variable_names(group_name)}
    actual = {c.upper() for c in dataset_columns}
    findings: list[Finding] = []
    for missing in sorted(declared - actual):
        findings.append(_finding(
            "DEFINE-DATASET-VARMATCH", "major",
            f"Variable '{missing}' is defined in define.xml ({group_name}) but absent from the dataset.",
            "Add the variable to the dataset or remove it from define.xml.",
        ))
    for extra in sorted(actual - declared):
        findings.append(_finding(
            "DEFINE-DATASET-VARMATCH", "major",
            f"Variable '{extra}' is in the dataset ({group_name}) but not described in define.xml.",
            "Document the variable in define.xml or drop it from the dataset.",
        ))
    return findings

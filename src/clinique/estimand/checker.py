"""Consistency checker entry point (RFC-0001 §5.1).

Read-only: runs the deterministic rules over a graph and returns findings. There is intentionally
no API here to modify source artifacts.
"""

from __future__ import annotations

from .graph import ArtifactGraph, Finding
from .rules import ALL_RULES


def check_consistency(graph: ArtifactGraph) -> list[Finding]:
    findings: list[Finding] = []
    for rule in ALL_RULES:
        findings.extend(rule(graph))
    return findings

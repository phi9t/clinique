"""Validator-report ingestion (RFC-0004 §5.2).

Parses a CDISC CORE / Pinnacle 21 style report (list of issue objects) into structured issues.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ConformanceIssue:
    issue_id: str
    message: str
    severity: str  # Error | Warning | Notice
    domain: str = ""
    variable: str = ""
    count: int = 0


def parse_report(data: str | list[dict]) -> list[ConformanceIssue]:
    rows = json.loads(data) if isinstance(data, str) else data
    issues: list[ConformanceIssue] = []
    for r in rows:
        issues.append(
            ConformanceIssue(
                issue_id=str(r.get("core_id") or r.get("issue_id") or r.get("id", "")),
                message=str(r.get("message", "")),
                severity=str(r.get("severity", "")).strip().title(),
                domain=str(r.get("domain", "")),
                variable=str(r.get("variable", "")),
                count=int(r.get("count", 0) or 0),
            )
        )
    return issues

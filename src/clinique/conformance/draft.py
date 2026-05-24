"""Draft conformance summary (RFC-0004 §5.1), no-fabrication.

The draft is assembled ONLY from fields present in the parsed issues + their triage. It never
introduces metadata (domains, variables, counts) that is not in the source.
"""

from __future__ import annotations

from .report import ConformanceIssue
from .triage import Triage


def draft_summary(issues: list[ConformanceIssue], triages: list[Triage]) -> str:
    by_id = {t.issue_id: t for t in triages}
    lines = [f"Conformance review: {len(issues)} issue(s)."]
    for issue in issues:
        t = by_id.get(issue.issue_id)
        cls = t.classification if t else "unclassified"
        loc = "/".join(p for p in (issue.domain, issue.variable) if p)
        where = f" in {loc}" if loc else ""
        lines.append(f"- [{cls}] {issue.issue_id}{where}: {issue.message} ({issue.count} occurrence(s)).")
    return "\n".join(lines)

"""Render a :class:`ScoreReport` to JSON and a standalone HTML scorecard."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .score import ScoreReport

# Metrics where lower is better (rendered red when non-zero).
_LOWER_IS_BETTER = {
    "unsafe_clearance_rate",
    "unsafe_clearance_count",
    "unsupported_decision_count",
    "fabricated_quote_count",
}
_HEADLINE = (
    "score",
    "criterion_macro_f1",
    "evidence_support_accuracy",
    "blocking_criterion_recall",
    "overall_recommendation_accuracy",
    "unsafe_clearance_rate",
    "unsupported_decision_count",
    "fabricated_quote_count",
    "schema_valid_rate",
)


def to_json(report: ScoreReport, *, agent: str | None = None) -> dict[str, Any]:
    payload = report.to_dict()
    if agent is not None:
        payload = {"agent": agent, **payload}
    return payload


def write_json(report: ScoreReport, path: str | Path, *, agent: str | None = None) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_json(report, agent=agent), indent=2, sort_keys=True) + "\n")


def _row(label: str, value: Any, *, bad: bool) -> str:
    cls = "bad" if bad else "ok"
    shown = f"{value:.3f}" if isinstance(value, float) else html.escape(str(value))
    return f'<tr><td>{html.escape(label)}</td><td class="{cls}">{shown}</td></tr>'


def to_html(report: ScoreReport, *, agent: str | None = None) -> str:
    data = report.to_dict()
    title = f"PrescreenBench — {report.benchmark_id} — {report.split}"
    if agent:
        title += f" — {agent}"
    gate_class = "ok" if report.passed_hard_gates else "bad"
    gate_text = (
        "PASS" if report.passed_hard_gates else f"FAIL ({', '.join(report.hard_gate_breaches)})"
    )

    headline_rows = []
    for key in _HEADLINE:
        value = data.get(key)
        if value is None:
            bad = False
        elif key in _LOWER_IS_BETTER:
            bad = bool(value)
        elif key == "schema_valid_rate":
            bad = value < 1.0
        else:
            bad = False
        headline_rows.append(_row(key, value, bad=bool(bad)))

    class_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{c['f1']:.3f}</td>"
        f"<td>{c['precision']:.3f}</td><td>{c['recall']:.3f}</td>"
        f"<td>{int(c['support'])}</td></tr>"
        for label, c in report.per_class_f1.items()
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
 body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; color: #1a1a1a; }}
 h1 {{ font-size: 1.25rem; }}
 table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
 td, th {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
 th {{ background: #f5f5f5; }}
 .ok {{ color: #11772b; font-variant-numeric: tabular-nums; }}
 .bad {{ color: #b00020; font-weight: 600; font-variant-numeric: tabular-nums; }}
 .gate {{ font-size: 1.1rem; padding: .5rem 0; }}
 .score {{ font-size: 2rem; font-weight: 700; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="score">{report.score:.3f}</p>
<p class="gate {gate_class}">Hard safety gates: {html.escape(gate_text)}</p>
<p>{report.cases} cases · {report.criterion_total} criterion labels</p>
<h2>Headline metrics</h2>
<table><tr><th>metric</th><th>value</th></tr>{"".join(headline_rows)}</table>
<h2>Per-class F1</h2>
<table><tr><th>label</th><th>F1</th><th>precision</th><th>recall</th><th>support</th></tr>
{class_rows}</table>
<p style="color:#888;font-size:.85rem">unknown_actionability is proxied by unknown_recall
({report.unknown_recall:.3f}) until human ratings exist.</p>
</body></html>
"""


def write_html(report: ScoreReport, path: str | Path, *, agent: str | None = None) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_html(report, agent=agent), encoding="utf-8")

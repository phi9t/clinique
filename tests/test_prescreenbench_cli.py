"""End-to-end CLI tests for `clinique benchmark prescreen run|score|export-explorer`."""

import json

from clinique.cli import main


def test_run_then_score_clinique_rule_exit_zero(tmp_path):
    pred = tmp_path / "pred.jsonl"
    report = tmp_path / "report.json"
    html = tmp_path / "report.html"

    assert (
        main(
            [
                "benchmark",
                "prescreen",
                "run",
                "--split",
                "synthetic",
                "--agent",
                "clinique-rule",
                "--out",
                str(pred),
            ]
        )
        == 0
    )
    assert pred.is_file()
    lines = [json.loads(line) for line in pred.read_text().splitlines() if line.strip()]
    assert lines and "overall_recommendation" in lines[0]

    rc = main(
        [
            "benchmark",
            "prescreen",
            "score",
            "--split",
            "synthetic",
            "--pred",
            str(pred),
            "--out",
            str(report),
            "--html",
            str(html),
            "--agent",
            "clinique_rule",
        ]
    )
    assert rc == 0
    payload = json.loads(report.read_text())
    assert payload["agent"] == "clinique_rule"
    assert payload["passed_hard_gates"] is True
    assert html.is_file() and "PrescreenBench" in html.read_text()


def test_score_returns_nine_on_hard_gate_failure(tmp_path):
    pred = tmp_path / "kw.jsonl"
    assert (
        main(
            [
                "benchmark",
                "prescreen",
                "run",
                "--split",
                "synthetic",
                "--agent",
                "keyword_rule",
                "--out",
                str(pred),
            ]
        )
        == 0
    )
    rc = main(
        [
            "benchmark",
            "prescreen",
            "score",
            "--split",
            "synthetic",
            "--pred",
            str(pred),
            "--out",
            str(tmp_path / "kw.json"),
        ]
    )
    assert rc == 9


def test_run_unknown_agent_errors(tmp_path):
    rc = main(
        [
            "benchmark",
            "prescreen",
            "run",
            "--split",
            "synthetic",
            "--agent",
            "does_not_exist",
            "--out",
            str(tmp_path / "x.jsonl"),
        ]
    )
    assert rc == 2


def test_export_explorer_writes_static_bundle(tmp_path):
    out = tmp_path / "prescreenbench"
    rc = main(
        [
            "benchmark",
            "prescreen",
            "export-explorer",
            "--split",
            "synthetic",
            "--agents",
            "always_unknown,keyword_rule,clinique_rule",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert (out / "index.json").is_file()
    assert (out / "definitions.json").is_file()
    assert (out / "synthetic.json").is_file()


def test_export_explorer_accepts_custom_prediction(tmp_path):
    pred = tmp_path / "pred.jsonl"
    out = tmp_path / "bundle"
    assert (
        main(
            [
                "benchmark",
                "prescreen",
                "run",
                "--split",
                "synthetic",
                "--agent",
                "clinique_rule",
                "--out",
                str(pred),
            ]
        )
        == 0
    )
    rc = main(
        [
            "benchmark",
            "prescreen",
            "export-explorer",
            "--split",
            "synthetic",
            "--agents",
            "",
            "--prediction",
            f"custom={pred}",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    payload = json.loads((out / "synthetic.json").read_text())
    assert [agent["agent"] for agent in payload["agents"]] == ["custom"]


def test_export_explorer_bad_mapping_errors(tmp_path, capsys):
    rc = main(
        [
            "benchmark",
            "prescreen",
            "export-explorer",
            "--split",
            "synthetic",
            "--prediction",
            "badsyntax",
            "--out",
            str(tmp_path / "bundle"),
        ]
    )
    assert rc == 2
    assert "expected agent=path" in capsys.readouterr().err


def test_export_explorer_report_without_prediction_errors(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text('{"agent": "orphan"}\n')
    rc = main(
        [
            "benchmark",
            "prescreen",
            "export-explorer",
            "--split",
            "synthetic",
            "--agents",
            "",
            "--report",
            f"orphan={report}",
            "--out",
            str(tmp_path / "bundle"),
        ]
    )
    assert rc == 2
    assert "custom report without predictions" in capsys.readouterr().err

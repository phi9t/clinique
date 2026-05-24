from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.replay import evidence_at


FIXTURES = Path("tests/fixtures/edc_query")


def test_evidence_at_excludes_future_snapshots_and_rules():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 2, tzinfo=timezone.utc))

    assert evidence.snapshot.snapshot_id == "snap-2026-03-01"
    assert {rule.rule_id for rule in evidence.active_rules} == {
        "RULE-MISSING-AE",
        "RULE-CONMED-AE-DATE",
    }
    assert "snap-2026-03-08" not in [source.source_id for source in evidence.sources]


def test_evidence_at_refuses_dates_before_first_snapshot():
    bundle = load_fixture_bundle(FIXTURES)

    try:
        evidence_at(bundle, datetime(2026, 2, 1, tzinfo=timezone.utc))
    except ValueError as exc:
        assert "No snapshot" in str(exc)
    else:
        raise AssertionError("expected missing snapshot failure")


def test_replay_evidence_exposes_no_write_methods():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))

    forbidden = {"write", "update", "delete", "close_query", "issue_query"}

    assert forbidden.isdisjoint(set(dir(evidence)))

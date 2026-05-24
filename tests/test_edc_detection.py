from datetime import datetime, timezone
from pathlib import Path

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.replay import evidence_at


FIXTURES = Path("tests/fixtures/edc_query")


def test_detect_candidate_queries_generates_expected_categories():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
    by_key = {(c.subject_id, c.form, c.field): c for c in candidates}

    assert by_key[("SUBJ-001", "AE", "term")].query_category == "missing"
    assert by_key[("SUBJ-001", "ConMeds", "start_date")].query_category == "inconsistent"
    assert by_key[("SUBJ-002", "Vitals", "visit_date")].query_category == "impossible"
    assert by_key[("SUBJ-003", "Labs", "hemoglobin")].is_duplicate is True


def test_detect_candidate_queries_excludes_future_query_logs_from_duplicate_detection():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 1, tzinfo=timezone.utc))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    assert not any(candidate.is_duplicate for candidate in candidates)


def test_duplicate_candidate_queries_include_query_log_evidence():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
    duplicate = next(candidate for candidate in candidates if candidate.is_duplicate)

    assert ("query_log", "Q-001") in {
        (source.source_type, source.source_id) for source in duplicate.evidence
    }


def test_candidate_queries_are_draft_only_and_evidence_backed():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=timezone.utc))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    assert all(candidate.draft_only for candidate in candidates)
    assert all(candidate.evidence for candidate in candidates)

from datetime import UTC, datetime
from pathlib import Path

from clinique.edc.detection import detect_candidate_queries
from clinique.edc.fixtures import load_fixture_bundle
from clinique.edc.records import QueryLog
from clinique.edc.replay import evidence_at

FIXTURES = Path("tests/fixtures/edc_query")


def test_detect_candidate_queries_generates_expected_categories():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=UTC))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
    by_key = {(c.subject_id, c.form, c.field): c for c in candidates}

    assert by_key[("SUBJ-001", "AE", "term")].query_category == "missing"
    assert by_key[("SUBJ-001", "ConMeds", "start_date")].query_category == "inconsistent"
    assert by_key[("SUBJ-002", "Vitals", "visit_date")].query_category == "impossible"
    assert by_key[("SUBJ-003", "Labs", "hemoglobin")].is_duplicate is True


def test_detect_candidate_queries_excludes_future_query_logs_from_duplicate_detection():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 1, tzinfo=UTC))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    assert not any(candidate.is_duplicate for candidate in candidates)


def test_duplicate_candidate_queries_include_query_log_evidence():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=UTC))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)
    duplicate = next(candidate for candidate in candidates if candidate.is_duplicate)

    assert ("query_log", "Q-001") in {
        (source.source_type, source.source_id) for source in duplicate.evidence
    }


def test_detect_candidate_queries_does_not_match_query_logs_across_sites():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=UTC))
    wrong_site_query = QueryLog(
        query_id="Q-WRONG-SITE",
        snapshot_id="snap-2026-03-01",
        study_id="STUDY-EDC-001",
        site_id="SITE-99",
        subject_id="SUBJ-003",
        form="Labs",
        field="hemoglobin",
        query_text="Please confirm hemoglobin value.",
        query_category="duplicate",
        opened_at=datetime(2026, 3, 2, tzinfo=UTC),
        closed_at=None,
        status="open",
        resolution="pending",
    )

    candidates = detect_candidate_queries(evidence, existing_queries=(wrong_site_query,))

    assert not any(candidate.is_duplicate for candidate in candidates)


def test_candidate_queries_are_draft_only_and_evidence_backed():
    bundle = load_fixture_bundle(FIXTURES)
    evidence = evidence_at(bundle, datetime(2026, 3, 8, tzinfo=UTC))

    candidates = detect_candidate_queries(evidence, existing_queries=bundle.query_logs)

    assert all(candidate.draft_only for candidate in candidates)
    assert all(candidate.evidence for candidate in candidates)
    assert {candidate.snapshot_id for candidate in candidates} == {evidence.snapshot.snapshot_id}

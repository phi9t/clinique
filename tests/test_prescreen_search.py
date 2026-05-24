"""Offline tests for ClinicalTrials.gov search-page parsing.

The network search path (``search_studies_raw``) is not exercised; ``parse_search_page`` is the
pure half and runs against a recorded (synthetic) search-response page frozen in version control.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinique.prescreen.ingestion import (
    parse_search_page,
    parse_study,
    search_studies_raw,
)
from clinique.prescreen.schemas import CLINICALTRIALS_GOV

FIXTURE = Path("tests/fixtures/prescreen/search_nsclc_page.json")


def _page() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_search_page_extracts_studies():
    studies = parse_search_page(_page())
    nct_ids = [s["protocolSection"]["identificationModule"]["nctId"] for s in studies]
    assert nct_ids == ["NCT00000001", "NCT00000002"]


def test_search_studies_round_trip_through_parse_study():
    # A search result is just another way to populate the Trial corpus.
    trials = [parse_study(s) for s in parse_search_page(_page())]
    assert {t.trial_id for t in trials} == {"NCT00000001", "NCT00000002"}
    assert all(t.source == CLINICALTRIALS_GOV for t in trials)
    phase3 = next(t for t in trials if t.trial_id == "NCT00000002")
    assert phase3.phase == "PHASE3"
    assert phase3.maximum_age.years == 75.0


def test_parse_search_page_rejects_non_search_payload():
    with pytest.raises(ValueError, match="studies"):
        parse_search_page({"protocolSection": {}})


def test_unbounded_search_is_refused_before_any_network_call():
    # No query and no max_studies -> must raise (the generator validates eagerly), so this never
    # touches the network even though search_studies_raw is otherwise a network path.
    with pytest.raises(ValueError, match="unbounded"):
        next(search_studies_raw())

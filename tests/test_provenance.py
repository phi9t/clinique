"""RFC-0000 §5 provenance ledger tests."""

from clinique.substrate.provenance import HumanReview, LedgerRecord, ProvenanceLedger


def _ledger(tmp_path):
    return ProvenanceLedger(tmp_path / "run.ledger.jsonl")


def test_append_assigns_id_and_timestamp(tmp_path):
    led = _ledger(tmp_path)
    rid = led.append(LedgerRecord(capability="rfc-0003"))
    assert rid
    rows = led.all()
    assert len(rows) == 1
    assert rows[0]["record_id"] == rid
    assert rows[0]["produced_at"]  # UTC ISO-8601 set


def test_reload_roundtrip_and_ordering(tmp_path):
    led = _ledger(tmp_path)
    ids = [led.append(LedgerRecord(capability=f"cap-{i}")) for i in range(3)]
    rows = led.all()
    assert [r["record_id"] for r in rows] == ids  # append order preserved
    # a fresh handle reads the same persisted records
    assert ProvenanceLedger(led.path).all() == rows


def test_human_review_defaults(tmp_path):
    led = _ledger(tmp_path)
    led.append(LedgerRecord(capability="rfc-0003"))
    hr = led.all()[0]["human_review"]
    assert hr == {
        "required": True,
        "role": "biostatistician",
        "status": "pending",
        "reviewer": None,
        "at": None,
    }


def test_append_only_no_mutation_api(tmp_path):
    led = _ledger(tmp_path)
    # the ledger is append-only by design: no update/delete surface
    assert not hasattr(led, "update")
    assert not hasattr(led, "delete")
    assert not hasattr(led, "remove")


def test_custom_human_review_persists(tmp_path):
    led = _ledger(tmp_path)
    led.append(LedgerRecord(capability="rfc-0003", human_review=HumanReview(role="lead-biostat")))
    assert led.all()[0]["human_review"]["role"] == "lead-biostat"
